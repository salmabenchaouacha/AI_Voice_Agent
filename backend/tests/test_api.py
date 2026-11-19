import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import server

ORIGINE_OK = {"Origin": "http://localhost:5173"}
ORIGINE_ETRANGERE = {"Origin": "https://evil.example"}


@pytest.fixture
def client():
    return TestClient(server.app)


def test_config(client):
    assert client.get("/api/config").json() == {"language": "fr"}


def test_commande_rest(client):
    r = client.post("/api/command", json={"text": "quelle heure est-il ?"})
    assert r.status_code == 200
    assert r.json()["reply"].startswith("Il est ")


def test_commande_vide(client):
    assert client.post("/api/command", json={"text": "   "}).status_code == 400


def test_origine_etrangere_refusee_en_http(client):
    assert client.get("/api/config", headers=ORIGINE_ETRANGERE).status_code == 403
    assert client.post("/api/command", json={"text": "bonjour"}, headers=ORIGINE_ETRANGERE).status_code == 403


def test_ws_commande_texte(client):
    with client.websocket_connect("/ws", headers=ORIGINE_OK) as ws:
        ws.send_text('{"type": "text", "text": "quelle heure est-il"}')
        data = ws.receive_json()
    assert data["type"] == "result" and data["source"] == "text"
    assert data["heard"] == "quelle heure est-il"
    assert data["reply"].startswith("Il est ")


def test_ws_json_invalide(client):
    with client.websocket_connect("/ws", headers=ORIGINE_OK) as ws:
        ws.send_text("pas du json")
        assert ws.receive_json()["reply"] == "Je n'ai rien compris. Réessaie."


def test_ws_audio_transcrit_puis_execute(client, monkeypatch):
    monkeypatch.setattr(server, "transcribe_bytes", lambda data: "quelle heure est-il")
    with client.websocket_connect("/ws", headers=ORIGINE_OK) as ws:
        ws.send_bytes(b"\x00\x01\x02")
        data = ws.receive_json()
    assert data["source"] == "voice" and data["heard"] == "quelle heure est-il"
    assert data["reply"].startswith("Il est ")


def test_ws_audio_inintelligible(client, monkeypatch):
    monkeypatch.setattr(server, "transcribe_bytes", lambda data: "")
    with client.websocket_connect("/ws", headers=ORIGINE_OK) as ws:
        ws.send_bytes(b"\x00")
        data = ws.receive_json()
    assert data["heard"] == "" and "rien compris" in data["reply"]


def test_ws_origine_etrangere_refusee(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws", headers=ORIGINE_ETRANGERE) as ws:
            ws.receive_json()

def test_miniature_de_capture_seulement_pour_ses_propres_fichiers(client, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))                 # Windows
    (tmp_path / "capture_20261119_120000.png").write_bytes(b"\x89PNG\r\n")
    (tmp_path / "secret.txt").write_text("non")
    assert client.get("/api/captures/capture_20261119_120000.png").status_code == 200
    assert client.get("/api/captures/secret.txt").status_code == 404
    assert client.get("/api/captures/capture_20990101_000000.png").status_code == 404


def test_cocher_une_tache_depuis_le_panneau(client):
    import planner
    planner.add_task("Réviser le RAG")
    etat = client.post("/api/tasks/1/toggle").json()
    assert etat["type"] == "state" and etat["tasks"][0] == {"id": 1, "text": "Réviser le RAG", "done": True}
    assert client.post("/api/tasks/999/toggle").status_code == 404
    assert "reminders" in client.get("/api/state").json()
