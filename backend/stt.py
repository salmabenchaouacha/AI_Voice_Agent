"""Reconnaissance vocale avec faster-whisper.

transcribe_detailed() rend aussi chaque mot avec sa probabilité : l'interface souligne les mots dont Whisper
n'est pas sûr (« source » au lieu de « Sousse »), pour que l'utilisateur voie d'où vient une erreur.
"""
from faster_whisper import WhisperModel

from config import LANGUAGE, WHISPER_MODEL, WHISPER_PROMPT, WORD_CONFIDENCE

_model = None


def load():
    global _model
    if _model is None:
        _model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    return _model


def transcribe_detailed(audio) -> tuple[str, list[dict]]:
    """(texte en minuscules, [{"w": mot, "p": probabilité entre 0 et 1}, …])."""
    segments, _ = load().transcribe(
        audio, language=LANGUAGE, beam_size=1,
        vad_filter=True, condition_on_previous_text=False,
        initial_prompt=WHISPER_PROMPT or None,
        word_timestamps=WORD_CONFIDENCE,
    )
    segments = list(segments)
    text = " ".join(s.text.strip() for s in segments).strip().lower()
    words = [{"w": w.word.strip().lower(), "p": round(float(w.probability), 2)}
             for s in segments for w in (getattr(s, "words", None) or []) if w.word.strip()]
    return text, words


def transcribe(audio) -> str:
    return transcribe_detailed(audio)[0]
