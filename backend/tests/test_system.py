from types import SimpleNamespace

import psutil
import pytest

import skills
import system
from router import dispatch


@pytest.fixture
def linux(monkeypatch):
    monkeypatch.setattr(system, "OS", "Linux")


def test_ouvre_un_site(monkeypatch):
    ouverts = []
    monkeypatch.setattr(system.webbrowser, "open", ouverts.append)
    assert dispatch("ouvre youtube") == "J'ouvre youtube."
    assert ouverts == ["https://www.youtube.com"]


def test_ouvre_une_application_linux(linux, monkeypatch):
    lances = []
    monkeypatch.setattr(system.subprocess, "Popen", lambda cmd, **kw: lances.append(cmd))
    assert dispatch("ouvre la calculatrice") == "J'ouvre calculatrice."
    assert lances == [["gnome-calculator"]]


def test_application_inconnue_sous_windows(monkeypatch):
    monkeypatch.setattr(system, "OS", "Windows")
    monkeypatch.setattr(system.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1))
    assert dispatch("ouvre logiciel") == "Je n'arrive pas à ouvrir logiciel."


def test_refuse_les_noms_dangereux(monkeypatch):
    def interdit(*a, **k):
        raise AssertionError("aucune commande ne doit être lancée")
    monkeypatch.setattr(system.subprocess, "run", interdit)
    monkeypatch.setattr(system.subprocess, "Popen", interdit)
    assert system._launch("calc & del *", "x") == "Je n'arrive pas à ouvrir x."


def test_volume_linux(linux, monkeypatch):
    commandes = []
    monkeypatch.setattr(system.subprocess, "run", lambda cmd, **kw: commandes.append(cmd))
    assert dispatch("monte le volume") == "Volume augmenté."
    assert dispatch("baisse le volume") == "Volume baissé."
    assert dispatch("coupe le son") == "C'est fait."
    assert commandes == [
        ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+10%"],
        ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-10%"],
        ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"],
    ]


def test_capture_et_verrouillage(monkeypatch):
    verrouille = []
    monkeypatch.setattr(system, "screenshot", lambda: "/tmp/capture.png")
    monkeypatch.setattr(system, "lock_screen", lambda: verrouille.append(True))
    assert dispatch("fais une capture d'écran") == "Capture enregistrée : /tmp/capture.png"
    assert dispatch("verrouille l'écran") == "Écran verrouillé."
    assert verrouille == [True]


def test_batterie(monkeypatch):
    monkeypatch.setattr(psutil, "sensors_battery", lambda: SimpleNamespace(percent=63.4, power_plugged=True))
    assert dispatch("quel est l'état de la batterie") == "La batterie est à 63 pourcent, en charge."
    monkeypatch.setattr(psutil, "sensors_battery", lambda: None)
    assert dispatch("batterie") == "Je ne détecte pas de batterie."


def test_aide_liste_les_capacites():
    aide = dispatch("aide")
    for mot in ("minuteur", "météo", "volume", "capture d'écran"):
        assert mot in aide