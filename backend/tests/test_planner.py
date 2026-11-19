"""Lot 3 : liste de tâches et rappels à heure fixe."""
import json
import time
from datetime import datetime

import notifier
import planner

MAINTENANT = datetime(2026, 11, 19, 14, 0)


# ---------- tâches ----------
def test_taches_ajout_liste_et_doublon(tmp_path):
    f = str(tmp_path / "t.json")
    assert planner.list_tasks(path=f) == "Ta liste de tâches est vide."
    assert planner.add_task("Réviser le RAG.", path=f) == "Tâche ajoutée : Réviser le RAG."
    assert planner.add_task("Appeler la banque", path=f) == "Tâche ajoutée : Appeler la banque."
    assert "déjà dans ta liste" in planner.add_task("reviser le rag", path=f)       # accents et majuscules ignorés
    assert planner.list_tasks(path=f) == "2 tâches à faire : 1. Réviser le RAG ; 2. Appeler la banque."
    assert planner.add_task("  ", path=f) == "La tâche est vide, je n'ai rien ajouté."


def test_taches_terminees_par_mots_ou_numero(tmp_path):
    f = str(tmp_path / "t.json")
    for t in ("Réviser le RAG", "Réviser LangGraph", "Appeler la banque"):
        planner.add_task(t, path=f)
    assert planner.complete_task("la banque", path=f) == "Tâche terminée : Appeler la banque."
    assert planner.complete_task("réviser", path=f).startswith("Plusieurs tâches correspondent")
    assert planner.complete_task("2", path=f) == "Tâche terminée : Réviser LangGraph."
    assert "Je ne trouve pas" in planner.complete_task("piscine", path=f)
    vue = planner.tasks_snapshot(path=f)
    assert [(t["text"], t["done"]) for t in vue] == [("Réviser le RAG", False), ("Réviser LangGraph", True),
                                                     ("Appeler la banque", True)]
    assert planner.clear_done_tasks(path=f) == "2 tâches terminées retirées."
    assert [t["text"] for t in planner.tasks_snapshot(path=f)] == ["Réviser le RAG"]


def test_cocher_depuis_le_panneau(tmp_path):
    f = str(tmp_path / "t.json")
    planner.add_task("Réviser le RAG", path=f)
    assert planner.toggle_task(1, path=f) and planner.tasks_snapshot(path=f)[0]["done"] is True
    assert planner.toggle_task(1, path=f) and planner.tasks_snapshot(path=f)[0]["done"] is False
    assert planner.toggle_task(99, path=f) is False


# ---------- rappels ----------
def test_heure_comprise():
    assert planner.parse_when("18:30", MAINTENANT) == datetime(2026, 11, 19, 18, 30)
    assert planner.parse_when("18h", MAINTENANT) == datetime(2026, 11, 19, 18, 0)
    assert planner.parse_when("9h15", MAINTENANT) == datetime(2026, 11, 20, 9, 15)        # passée : demain
    assert planner.parse_when("2026-11-21T08:00", MAINTENANT) == datetime(2026, 11, 21, 8, 0)
    assert planner.parse_when("25:00", MAINTENANT) is None
    assert planner.parse_when("ce soir", MAINTENANT) is None


def test_rappel_programme_puis_annule(tmp_path):
    f = str(tmp_path / "r.json")
    texte = planner.set_reminder("18:30", "appeler maman", path=f, now=datetime.now().replace(hour=8, minute=0))
    assert texte.startswith("C'est noté, je te rappellerai") and texte.endswith(": appeler maman.")
    assert [r["text"] for r in planner.reminders_snapshot(path=f)] == ["appeler maman"]
    assert "Je n'ai pas compris" in planner.set_reminder("plus tard", "x", path=f)
    assert "plus d'un mois" in planner.set_reminder("2099-01-01 10:00", "x", path=f)
    assert planner.cancel_reminders(path=f) == "1 rappel annulé." and planner.reminders_snapshot(path=f) == []


def test_le_rappel_sonne_et_disparait(tmp_path, monkeypatch):
    f = str(tmp_path / "r.json")
    recus = []
    monkeypatch.setattr(notifier, "push", recus.append)
    bientot = datetime.fromtimestamp(time.time() + 1.2)
    planner.set_reminder(bientot.strftime("%Y-%m-%d %H:%M:%S"), "boire de l'eau", path=f,
                         now=datetime.fromtimestamp(time.time()))
    for _ in range(40):
        if recus:
            break
        time.sleep(0.1)
    assert recus == ["Rappel : boire de l'eau"] and planner.reminders_snapshot(path=f) == []


def test_rappels_reprogrammes_au_demarrage(tmp_path, monkeypatch):
    f = tmp_path / "r.json"
    f.write_text(json.dumps([{"id": 7, "text": "réunion", "at": round((time.time() + 3600) * 1000)}]))
    assert planner.restore_reminders(path=str(f)) == 1
    assert 7 in planner._timers
    planner.cancel_reminders(path=str(f))
