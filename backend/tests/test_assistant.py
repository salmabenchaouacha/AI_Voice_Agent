"""L'assistant assemblé de bout en bout : faux modèle → graphe LangGraph → serveurs MCP réels → API WebSocket."""
import asyncio

import pytest

pytest.importorskip("langgraph")
pytest.importorskip("mcp")

from fastapi.testclient import TestClient  # noqa: E402

import config  # noqa: E402
import llm  # noqa: E402
import server  # noqa: E402
from agent.runtime import Assistant  # noqa: E402
from fakes import FauxModele, ai, creer  # noqa: E402

ORIGINE = {"Origin": "http://localhost:5173"}


def test_assemblage_complet_avec_les_vrais_serveurs_mcp(tmp_path, monkeypatch):
    modele = FauxModele([ai("", ("add_note", {"text": "appeler PROXYM"})), ai("C'est noté."),
                         ai("", ("clear_notes", {})), ai("Tes notes sont effacées.")])
    monkeypatch.setenv("VA_NOTES", str(tmp_path / "notes.txt"))
    monkeypatch.setattr(config, "AGENT_MODE", "auto")
    monkeypatch.setattr(config, "MEMORY_FILE", str(tmp_path / "memoire.json"))
    monkeypatch.setattr(llm, "missing_key", lambda spec=None: None)
    monkeypatch.setattr(llm, "get_chat_model", lambda spec=None: modele)

    async def scenario():
        assistant = Assistant()
        await assistant.start()
        try:
            etat = assistant.status()
            note = await assistant.handle("note d'appeler PROXYM", "s1")
            contenu = (tmp_path / "notes.txt").read_text(encoding="utf-8")
            question = await assistant.handle("efface mes notes", "s1")
            encore_la = (tmp_path / "notes.txt").exists()
            fin = await assistant.handle("oui", "s1")
            return etat, note, contenu, question, encore_la, fin
        finally:
            await assistant.stop()

    etat, note, contenu, question, encore_la, fin = asyncio.run(scenario())
    assert etat["mode"] == "agent" and etat["mcp_errors"] == {}
    assert len(etat["tools"]) == 18                                   # 13 outils MCP + 5 outils locaux
    assert note == {"type": "result", "reply": "C'est noté.", "tools": ["note"], "mode": "agent",
                    "timings": note["timings"], "trace": note["trace"]}
    assert [e["kind"] for e in note["trace"]] == ["llm", "tool", "llm"]
    assert "appeler PROXYM" in contenu
    assert question["type"] == "confirm" and question["reply"] == "Je vais effacer toutes tes notes. Tu confirmes ?"
    assert encore_la                                                  # rien n'est effacé avant le oui
    assert fin["reply"] == "Tes notes sont effacées." and not (tmp_path / "notes.txt").exists()


def test_sans_cle_d_api_le_mode_hors_ligne_prend_le_relais(monkeypatch):
    monkeypatch.setattr(config, "AGENT_MODE", "auto")
    monkeypatch.setattr(llm, "missing_key", lambda spec=None: "ANTHROPIC_API_KEY")

    async def scenario():
        assistant = Assistant()
        await assistant.start()
        return assistant.status(), await assistant.handle("quelle heure est-il", "s")

    etat, reponse = asyncio.run(scenario())
    assert etat["mode"] == "offline" and "ANTHROPIC_API_KEY" in etat["reason"]
    assert reponse["mode"] == "offline" and reponse["reply"].startswith("Il est ")


def test_modele_en_panne_la_phrase_repasse_par_les_regex(monkeypatch):
    agent, _, _ = creer([RuntimeError("réseau coupé")])
    assistant = Assistant()
    assistant.agent, assistant.mode = agent, "agent"
    reponse = asyncio.run(assistant.handle("quelle heure est-il", "s"))
    assert reponse["mode"] == "offline" and reponse["reply"].startswith("Il est ") and "réseau coupé" in reponse["error"]


def test_websocket_etapes_confirmation_puis_resultat(monkeypatch):
    agent, _, journal = creer([
        ai("", ("get_weather", {"city": "Sousse"})), ai("Il fait 27 degrés à Sousse."),
        ai("", ("lock_screen", {})), ai("L'écran est verrouillé."),
    ])
    monkeypatch.setattr(server.assistant, "agent", agent)
    monkeypatch.setattr(server.assistant, "mode", "agent")

    with TestClient(server.app).websocket_connect("/ws?session=test-session-1", headers=ORIGINE) as ws:
        def recevoir():                       # ignore le panneau et le schéma animé (testés à part)
            while (message := ws.receive_json())["type"] in ("state", "node"):
                pass
            return message

        ws.send_text('{"type": "text", "text": "météo à Sousse"}')
        etape, resultat = recevoir(), recevoir()
        ws.send_text('{"type": "text", "text": "verrouille l\'écran"}')
        question = recevoir()
        ws.send_text('{"type": "text", "text": "oui"}')
        etape_2, fin = recevoir(), recevoir()

    assert etape == {"type": "step", "tool": "get_weather", "label": "get_weather"}
    assert [e["kind"] for e in resultat["trace"]] == ["llm", "tool", "llm"]
    assert resultat["type"] == "result" and resultat["reply"] == "Il fait 27 degrés à Sousse."
    assert resultat["tools"] == ["get_weather"] and resultat["mode"] == "agent" and "llm_ms" in resultat["timings"]
    assert question["type"] == "confirm" and question["reply"] == "Je vais verrouiller l'écran. Tu confirmes ?"
    assert etape_2["tool"] == "lock_screen" and fin["reply"] == "L'écran est verrouillé."
    assert journal == [("get_weather", {"city": "Sousse"}), ("lock_screen", {})]


def test_le_panneau_suit_les_minuteurs_et_les_notes(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "NOTES_FILE", str(tmp_path / "notes.txt"))
    agent, _, _ = creer([ai("C'est fait.")])
    monkeypatch.setattr(server.assistant, "agent", agent)
    monkeypatch.setattr(server.assistant, "mode", "agent")
    monkeypatch.setattr(server.actions, "timers_snapshot",
                        lambda: [{"id": 1, "label": "pâtes", "end": 1_000_000, "seconds": 600}])
    server.actions.add_note("réviser LangGraph")

    with TestClient(server.app).websocket_connect("/ws", headers=ORIGINE) as ws:
        ws.send_text('{"type": "text", "text": "lance un minuteur"}')
        messages = [ws.receive_json() for _ in range(3)]          # nœud actif, réponse, état du panneau
        resultat, etat = messages[-2], messages[-1]
        assert messages[0] == {"type": "node", "node": "agent"}

    assert resultat["type"] == "result" and etat["type"] == "state"
    assert etat["timers"][0]["label"] == "pâtes" and etat["notes"][0]["text"] == "réviser LangGraph"
    assert TestClient(server.app).get("/api/state").json()["notes"][0]["text"] == "réviser LangGraph"


def test_etat_de_l_assistant_expose_par_l_api():
    client = TestClient(server.app)
    assert client.get("/api/status").json()["mode"] == "offline"
    assert client.get("/api/metrics").json() == {"demandes": 0}
    assert client.get("/api/status", headers={"Origin": "https://evil.example"}).status_code == 403


def test_le_journal_des_actions_sensibles_est_dans_l_etat(tmp_path, monkeypatch):
    import audit
    monkeypatch.setattr(audit, "PATH", str(tmp_path / "audit.jsonl"))
    audit.record([{"tool": "lock_screen", "label": "verrouillage", "action": "verrouiller l'écran",
                   "reason": "action sensible", "outcome": "refusée"}])
    etat = TestClient(server.app).get("/api/state").json()
    assert etat["audit"][0]["outcome"] == "refusée" and etat["audit"][0]["t"] > 0
