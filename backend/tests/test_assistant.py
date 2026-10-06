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
    assert note == {"type": "result", "reply": "C'est noté.", "tools": ["note"], "mode": "agent", "timings": note["timings"]}
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
        ws.send_text('{"type": "text", "text": "météo à Sousse"}')
        etape, resultat = ws.receive_json(), ws.receive_json()
        ws.send_text('{"type": "text", "text": "verrouille l\'écran"}')
        question = ws.receive_json()
        ws.send_text('{"type": "text", "text": "oui"}')
        etape_2, fin = ws.receive_json(), ws.receive_json()

    assert etape == {"type": "step", "tool": "get_weather", "label": "get_weather"}
    assert resultat["type"] == "result" and resultat["reply"] == "Il fait 27 degrés à Sousse."
    assert resultat["tools"] == ["get_weather"] and resultat["mode"] == "agent" and "llm_ms" in resultat["timings"]
    assert question["type"] == "confirm" and question["reply"] == "Je vais verrouiller l'écran. Tu confirmes ?"
    assert etape_2["tool"] == "lock_screen" and fin["reply"] == "L'écran est verrouillé."
    assert journal == [("get_weather", {"city": "Sousse"}), ("lock_screen", {})]


def test_etat_de_l_assistant_expose_par_l_api():
    client = TestClient(server.app)
    assert client.get("/api/status").json()["mode"] == "offline"
    assert client.get("/api/metrics").json() == {"demandes": 0}
    assert client.get("/api/status", headers={"Origin": "https://evil.example"}).status_code == 403
