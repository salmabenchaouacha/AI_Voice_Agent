import pytest

import skills
from router import QuitAssistant, dispatch, normalize


def test_normalize_retire_ponctuation_et_apostrophes_typographiques():
    assert normalize("Quelle heure est-il ?") == "quelle heure est-il"
    assert normalize("L’heure") == "l'heure"


def test_heure():
    assert dispatch("Quelle heure est-il ?").startswith("Il est ")


def test_date():
    assert dispatch("quel jour sommes-nous").startswith("Nous sommes le ")


def test_blague():
    assert dispatch("raconte-moi une blague") in skills.BLAGUES


def test_quitter():
    with pytest.raises(QuitAssistant):
        dispatch("au revoir")


def test_note(tmp_path, monkeypatch):
    fichier = tmp_path / "notes.txt"
    monkeypatch.setattr(skills, "NOTES_FILE", str(fichier))
    assert dispatch("prends une note acheter du pain") == "Note enregistrée."
    assert "acheter du pain" in fichier.read_text(encoding="utf-8")


def test_phrase_inconnue():
    assert "pas compris" in dispatch("zzz qqq")