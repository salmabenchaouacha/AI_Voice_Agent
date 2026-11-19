"""Lot 5 : Google Agenda, avec un faux service Google (aucun réseau, aucun compte)."""
import asyncio
from datetime import date, datetime

import agenda
import config
from agent.mcp_client import MCPManager, load_config
from agent.policy import needs_confirmation
from agent.toolbox import Toolbox

JEUDI = date(2026, 11, 19)


class FauxGoogle:
    def __init__(self, items=None):
        self.items, self.ajouts, self.requetes = items or [], [], []

    def events(self):
        return self

    def list(self, **params):
        self.requetes.append(params)
        return self

    def insert(self, calendarId, body):
        self.ajouts.append(body)
        return self

    def execute(self):
        return {"items": self.items}


def test_jours_dits_a_l_oral():
    assert agenda.parse_day("aujourd'hui", JEUDI) == JEUDI
    assert agenda.parse_day("demain", JEUDI) == date(2026, 11, 20)
    assert agenda.parse_day("vendredi", JEUDI) == date(2026, 11, 20)
    assert agenda.parse_day("jeudi", JEUDI) == date(2026, 11, 26)                # jeudi prochain, pas aujourd'hui
    assert agenda.parse_day("2026-12-01", JEUDI) == date(2026, 12, 1)
    assert agenda.parse_day("02/01", JEUDI) == date(2027, 1, 2)
    assert agenda.parse_day("un jour", JEUDI) is None


def test_evenements_d_un_jour():
    faux = FauxGoogle([
        {"summary": "Férié", "start": {"date": "2026-11-20"}, "end": {"date": "2026-11-21"}},
        {"summary": "Réunion PFE", "start": {"dateTime": "2026-11-20T10:00:00+01:00"},
         "end": {"dateTime": "2026-11-20T11:30:00+01:00"}},
    ])
    texte, carte = agenda.list_events("demain", svc=faux, today=JEUDI)
    assert texte.startswith("Demain, 2 événements : toute la journée, Férié ; à ")
    assert carte["kind"] == "agenda" and carte["title"] == "Demain" and len(carte["events"]) == 2
    assert faux.requetes[0]["singleEvents"] is True
    vide, _ = agenda.list_events("aujourd'hui", svc=FauxGoogle(), today=JEUDI)
    assert vide == "Aujourd'hui, rien dans ton agenda."


def test_ajout_d_un_evenement():
    faux = FauxGoogle()
    texte, carte = agenda.create_event("Réunion PFE", "2026-11-26 10:00", 90, svc=faux, now=datetime(2026, 11, 19, 12))
    assert texte.startswith("C'est ajouté à ton agenda : Réunion PFE")
    corps = faux.ajouts[0]
    assert corps["summary"] == "Réunion PFE" and corps["start"]["dateTime"].startswith("2026-11-26T10:00")
    assert corps["end"]["dateTime"].startswith("2026-11-26T11:30")
    assert carte["added"] is True and carte["events"][0]["time"] == "10:00"
    assert "déjà passée" in agenda.create_event("x", "2020-01-01 10:00", svc=faux)[0]
    assert "pas compris" in agenda.create_event("x", "jeudi", svc=faux)[0]


def test_agenda_pas_encore_connecte(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "GOOGLE_TOKEN", str(tmp_path / "absent.json"))
    texte, carte = agenda.list_events("demain")
    assert "pas encore connecté" in texte or "bibliothèques Google" in texte
    assert carte is None


def test_le_serveur_mcp_agenda_demarre_et_se_decrit():
    import json
    with open(config.MCP_CONFIG, encoding="utf-8") as f:
        brut = json.load(f)["mcpServers"]
    assert brut["agenda"]["enabled"] is False                             # désactivé tant que Google n'est pas connecté
    assert "agenda" not in load_config(config.MCP_CONFIG)

    async def scenario():
        async with MCPManager({"agenda": {**brut["agenda"], "enabled": True}}, base_dir=config.BASE_DIR) as mcp:
            boite = Toolbox()
            mcp.register_into(boite)
            return mcp.errors, {s.name: s for s in boite.specs()}

    erreurs, outils = asyncio.run(scenario())
    assert erreurs == {} and set(outils) == {"list_events", "create_event"}
    assert not needs_confirmation(outils["list_events"], tainted=True)
    assert outils["create_event"].action.startswith("ajouter")
