"""Speech-to-Text hors-ligne avec faster-whisper."""
from faster_whisper import WhisperModel
from config import LANGUAGE, WHISPER_MODEL

_model = None


def load():
    global _model
    if _model is None:
        _model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    return _model


def transcribe(audio) -> str:
    segments, _ = load().transcribe(
        audio, language=LANGUAGE, beam_size=1,
        vad_filter=True, condition_on_previous_text=False,
    )
    return " ".join(s.text.strip() for s in segments).strip().lower()