"""Les serveurs MCP sont lancés pour de vrai (sous-processus, protocole stdio) et interrogés par le client de l'agent."""
import asyncio

import pytest

pytest.importorskip("mcp")

import config  # noqa: E402
from agent.mcp_client import MCPManager, load_config  # noqa: E402
from agent.policy import needs_confirmation  # noqa: E402
from agent.toolbox import Toolbox  # noqa: E402


def avec_serveurs(scenario, serveurs=None):
    async def tout():
        async with MCPManager(serveurs or load_config(config.MCP_CONFIG), base_dir=config.BASE_DIR) as mcp:
            boite = Toolbox()
            mcp.register_into(boite)
            return await scenario(mcp, boite)
    return asyncio.run(tout())


def test_les_trois_serveurs_exposent_leurs_outils():
    async def scenario(mcp, boite):
        return mcp.errors, {s.name: s for s in boite.specs()}

    erreurs, outils = avec_serveurs(scenario)
    assert erreurs == {}
    assert {"open_app", "set_volume", "take_screenshot", "lock_screen", "battery_status", "get_weather", "web_search",
            "read_page", "play_youtube", "open_in_browser", "add_note", "list_notes", "clear_notes"} == set(outils)
    assert outils["lock_screen"].source == "bureau" and outils["web_search"].source == "web"
    assert outils["get_weather"].label == "météo" and outils["open_app"].action == "ouvrir {name}"


def test_les_annotations_mcp_pilotent_le_garde_fou():
    async def scenario(mcp, boite):
        return {s.name: s for s in boite.specs()}

    outils = avec_serveurs(scenario)
    toujours = {n for n, s in outils.items() if needs_confirmation(s, tainted=False)}
    jamais = {n for n, s in outils.items() if not needs_confirmation(s, tainted=True)}
    assert toujours == {"lock_screen", "clear_notes"}
    assert jamais == {"battery_status", "get_weather", "web_search", "read_page", "list_notes"}
    assert {n for n, s in outils.items() if s.open_world} == {"web_search", "read_page"}     # contenu non fiable


def test_appels_reels_au_serveur_de_notes(tmp_path, monkeypatch):
    monkeypatch.setenv("VA_NOTES", str(tmp_path / "notes.txt"))        # hérité par le sous-processus du serveur

    async def scenario(mcp, boite):
        ecrit = await boite.call("add_note", {"text": "réviser LangGraph"})
        lu = await boite.call("list_notes", {})
        efface = await boite.call("clear_notes", {})
        return ecrit, lu, efface

    ecrit, lu, efface = avec_serveurs(scenario)
    assert (ecrit.text, ecrit.is_error) == ("Note enregistrée.", False)
    assert "réviser LangGraph" in lu.text and efface.text == "Toutes les notes sont effacées."
    assert not (tmp_path / "notes.txt").exists()


def test_arguments_invalides_et_garde_fous_des_serveurs():
    async def scenario(mcp, boite):
        return (await boite.call("set_volume", {"action": "très fort"}),
                await boite.call("open_app", {"name": "rm -rf dossier"}),
                await boite.call("read_page", {"url": "http://127.0.0.1:8000/api/config"}),
                await boite.call("open_in_browser", {"url": "file:///etc/passwd"}))

    volume, appli, page, lien = avec_serveurs(scenario)
    assert volume.is_error                                         # le schéma de l'outil refuse la valeur
    assert appli.text == "Je ne connais pas l'application rm -rf dossier."
    assert page.text == "Je ne peux lire que des pages web publiques."
    assert "http" in lien.text


def test_un_serveur_en_panne_n_empeche_pas_les_autres():
    serveurs = {**load_config(config.MCP_CONFIG), "fantôme": {"command": "python", "args": ["mcp_servers/absent.py"]}}

    async def scenario(mcp, boite):
        return mcp.errors, len(boite.specs())

    erreurs, nombre = avec_serveurs(scenario, serveurs)
    assert list(erreurs) == ["fantôme"] and nombre == 13


def test_noms_en_double_prefixes_par_le_serveur():
    cfg = load_config(config.MCP_CONFIG)

    async def scenario(mcp, boite):
        return [s.name for s in boite.specs()]

    noms = avec_serveurs(scenario, {"notes": cfg["notes"], "copie": cfg["notes"]})
    assert "add_note" in noms and "copie__add_note" in noms
