import time

from fastapi.testclient import TestClient

import notifier
import server
import skills
from router import dispatch


class FauxTimer:
    demarres = []

    def __init__(self, secondes, fonction):
        self.secondes, self.fonction, self.daemon = secondes, fonction, False

    def start(self):
        FauxTimer.demarres.append(self)


def _minuteur(monkeypatch, phrase):
    FauxTimer.demarres = []
    monkeypatch.setattr(skills.threading, "Timer", FauxTimer)
    return dispatch(phrase)


def test_minuteur_en_minutes_avec_nombre_en_lettres(monkeypatch):
    pushed = []
    monkeypatch.setattr(notifier, "push", pushed.append)
    assert _minuteur(monkeypatch, "minuteur de cinq minutes") == "Minuteur de 5 minutes lancé."
    assert FauxTimer.demarres[0].secondes == 300
    FauxTimer.demarres[0].fonction()
    assert pushed == ["Ton minuteur est terminé !"]


def test_minuteur_en_secondes_et_heures(monkeypatch):
    assert _minuteur(monkeypatch, "minuteur de 1 seconde") == "Minuteur de 1 seconde lancé."
    assert FauxTimer.demarres[0].secondes == 1
    assert _minuteur(monkeypatch, "timer 2 heures") == "Minuteur de 2 heures lancé."
    assert FauxTimer.demarres[0].secondes == 7200


def test_minuteur_duree_incomprise(monkeypatch):
    assert _minuteur(monkeypatch, "minuteur de bientôt minutes") == "Je n'ai pas compris la durée."
    assert FauxTimer.demarres == []


def _attendre(condition, delai=2.0):
    fin = time.time() + delai
    while time.time() < fin:
        if condition():
            return True
        time.sleep(0.02)
    return False


def test_notification_poussee_au_client_websocket():
    client = TestClient(server.app)
    with client.websocket_connect("/ws") as ws:
        assert _attendre(lambda: len(notifier._subscribers) == 1)
        notifier.push("bip")
        assert ws.receive_json() == {"type": "notification", "text": "bip"}
    assert _attendre(lambda: len(notifier._subscribers) == 0)  # désinscription à la fermeture