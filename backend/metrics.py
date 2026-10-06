"""Mesures de latence : une ligne JSON par demande, sans le texte de ce qui a été dit.

C'est ce fichier qui fournit les chiffres du projet : délai de réponse médian, part du modèle,
part des outils, nombre d'appels. `summary()` est servi par GET /api/metrics."""
import json
import statistics
import threading
import time

import config

_lock = threading.Lock()


def record(entry: dict) -> None:
    if not config.METRICS_FILE:
        return
    try:
        with _lock, open(config.METRICS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": round(time.time()), **entry}, ensure_ascii=False) + "\n")
    except OSError:
        pass                                    # les mesures ne doivent jamais gêner l'assistant


def _load() -> list[dict]:
    try:
        with open(config.METRICS_FILE, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    except (OSError, ValueError):
        return []


def _stats(values: list[float]) -> dict:
    if not values:
        return {}
    values = sorted(values)
    return {"mediane_ms": round(statistics.median(values)),
            "p90_ms": round(values[min(len(values) - 1, int(0.9 * len(values)))]),
            "max_ms": round(values[-1])}


def summary() -> dict:
    rows = _load()
    out = {"demandes": len(rows)}
    for mode in ("agent", "offline"):
        sel = [r for r in rows if r.get("mode") == mode]
        if not sel:
            continue
        out[mode] = {
            "demandes": len(sel),
            "total": _stats([r["total_ms"] for r in sel if "total_ms" in r]),
            "transcription": _stats([r["stt_ms"] for r in sel if r.get("stt_ms")]),
            "modele": _stats([r["llm_ms"] for r in sel if r.get("llm_ms")]),
            "outils": _stats([r["tool_ms"] for r in sel if r.get("tool_ms")]),
            "avec_outils": sum(1 for r in sel if r.get("tools")),
            "confirmations": sum(1 for r in sel if r.get("type") == "confirm"),
        }
    return out
