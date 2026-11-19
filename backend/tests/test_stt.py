"""Mots incertains : stt.transcribe_detailed avec un faux modèle Whisper (pas de téléchargement)."""
import sys
import types
from types import SimpleNamespace as NS

sys.modules.setdefault("faster_whisper", types.SimpleNamespace(WhisperModel=object))
import stt  # noqa: E402


class FauxWhisper:
    def transcribe(self, audio, **options):
        self.options = options
        mots = [NS(word=" Météo", probability=0.95), NS(word=" à", probability=0.9), NS(word=" source", probability=0.384)]
        return iter([NS(text=" Météo à source", words=mots)]), None


def test_texte_et_probabilite_de_chaque_mot(monkeypatch):
    faux = FauxWhisper()
    monkeypatch.setattr(stt, "load", lambda: faux)
    texte, mots = stt.transcribe_detailed(b"audio")
    assert texte == "météo à source"
    assert mots == [{"w": "météo", "p": 0.95}, {"w": "à", "p": 0.9}, {"w": "source", "p": 0.38}]
    assert faux.options["word_timestamps"] is True
    assert stt.transcribe(b"audio") == "météo à source"
