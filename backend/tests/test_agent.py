"""Le graphe LangGraph, piloté par un faux modèle (tests/fakes.py) : aucun appel réseau, aucune clé d'API.

On vérifie ce que le graphe fait des décisions du modèle : quels outils partent, dans quel ordre,
lesquels attendent un oui, et ce que le modèle voit de la conversation."""
import asyncio

import pytest

pytest.importorskip("langgraph")

from langchain_core.messages import HumanMessage  # noqa: E402

from agent.graph import INTERRUPTED, LLM_DOWN, REDACTED, TOO_MANY_STEPS, window  # noqa: E402
from fakes import ai, creer  # noqa: E402


def jouer(agent, *phrases, conversation="c1", emit=None):
    async def tout():
        return [await agent.run_turn(conversation, p, emit) for p in phrases]
    return asyncio.run(tout())


def contenus(messages, type_):
    return [m.content for m in messages if m.type == type_]


# ---------- réponse simple, outils, multi-actions ----------
def test_reponse_sans_outil():
    agent, modele, journal = creer([ai("Bonjour !")])
    (r,) = jouer(agent, "salut")
    assert (r.kind, r.reply, r.tools, journal) == ("result", "Bonjour !", [], [])
    assert modele.vus[0][0].type == "system" and modele.vus[0][-1].content == "salut"
    assert {o["function"]["name"] for o in modele.outils} >= {"get_weather", "lock_screen"}


def test_deux_actions_dans_la_meme_phrase():
    agent, modele, journal = creer([
        ai("", ("get_weather", {"city": "Sousse"}), ("start_timer", {"seconds": 600})),
        ai("Il fait 27 degrés à Sousse, et ton minuteur de dix minutes est lancé."),
    ])
    (r,) = jouer(agent, "donne-moi la météo à Sousse et mets un minuteur de dix minutes")
    assert journal == [("get_weather", {"city": "Sousse"}), ("start_timer", {"seconds": 600})]
    assert r.kind == "result" and r.tools == ["get_weather", "start_timer"]
    assert contenus(modele.vus[1], "tool") == ["À Sousse, il fait 27 degrés.", "Minuteur lancé."]
    assert r.timings["llm_calls"] == 2


def test_actions_enchainees_sur_plusieurs_tours_de_boucle():
    agent, modele, journal = creer([
        ai("", ("get_weather", {})), ai("", ("start_timer", {"seconds": 60})), ai("C'est fait."),
    ])
    (r,) = jouer(agent, "météo puis minuteur")
    assert [nom for nom, _ in journal] == ["get_weather", "start_timer"] and len(modele.vus) == 3


def test_les_etapes_sont_diffusees_pendant_l_execution():
    recus = []

    async def emit(evenement):
        recus.append(evenement)

    agent, _, _ = creer([ai("", ("get_weather", {})), ai("Voilà.")])
    jouer(agent, "météo", emit=emit)
    assert [e for e in recus if e["type"] == "step"] == [{"type": "step", "tool": "get_weather", "label": "get_weather"}]
    # le schéma animé suit le parcours du graphe : réflexion, validation, outils, réflexion
    assert [e["node"] for e in recus if e["type"] == "node"] == ["agent", "review", "tools", "agent"]


# ---------- confirmation orale (interrupt / reprise) ----------
def test_action_sensible_attend_un_oui():
    agent, modele, journal = creer([ai("", ("lock_screen", {})), ai("L'écran est verrouillé.")])
    question, reponse = jouer(agent, "verrouille l'écran", "oui vas-y")
    assert question.kind == "confirm" and question.reply == "Je vais verrouiller l'écran. Tu confirmes ?"
    assert reponse.kind == "result" and reponse.reply == "L'écran est verrouillé."
    assert journal == [("lock_screen", {})] and reponse.tools == ["lock_screen"]
    assert len(modele.vus) == 2          # la question ne coûte aucun appel au modèle


def test_rien_n_est_execute_avant_la_reponse():
    agent, _, journal = creer([ai("", ("lock_screen", {}))])
    (question,) = jouer(agent, "verrouille l'écran")
    assert question.kind == "confirm" and journal == []


def test_un_non_annule_l_action():
    agent, modele, journal = creer([ai("", ("lock_screen", {})), ai("D'accord, j'annule.")])
    _, reponse = jouer(agent, "verrouille l'écran", "non")
    assert journal == [] and reponse.tools == [] and reponse.reply == "D'accord, j'annule."
    assert "refusé" in contenus(modele.vus[1], "tool")[0]


def test_une_autre_phrase_remplace_la_confirmation():
    agent, modele, journal = creer([
        ai("", ("lock_screen", {})), ai("", ("start_timer", {"seconds": 300})), ai("Minuteur de cinq minutes lancé."),
    ])
    _, reponse = jouer(agent, "verrouille l'écran", "mets plutôt un minuteur de cinq minutes")
    assert journal == [("start_timer", {"seconds": 300})]
    assert "mets plutôt un minuteur de cinq minutes" in contenus(modele.vus[1], "tool")[0]
    assert reponse.kind == "result"


def test_action_ordinaire_sans_confirmation():
    agent, _, journal = creer([ai("", ("open_app", {"name": "chrome"})), ai("J'ouvre Chrome.")])
    (r,) = jouer(agent, "ouvre chrome")
    assert r.kind == "result" and journal == [("open_app", {"name": "chrome"})]


# ---------- injection de prompt par du contenu web ----------
def test_apres_du_contenu_web_toute_action_demande_un_oui():
    agent, modele, journal = creer([
        ai("", ("web_search", {"query": "actualités"})),
        ai("", ("open_app", {"name": "evil.example"})),     # le modèle s'est laissé convaincre par la page piégée
        ai("Je n'ai rien ouvert."),
    ])
    question, reponse = jouer(agent, "cherche les actualités", "non")
    assert question.kind == "confirm" and "ouvrir evil.example" in question.reply
    assert journal == [("web_search", {"query": "actualités"})]            # l'action injectée n'est jamais partie
    assert contenus(modele.vus[1], "tool")[0].startswith("<contenu_externe>")
    assert reponse.kind == "result"


def test_le_contenu_web_quitte_le_contexte_a_la_demande_suivante():
    agent, modele, journal = creer([
        ai("", ("web_search", {"query": "x"})), ai("Voici un résumé."),
        ai("", ("open_app", {"name": "chrome"})), ai("J'ouvre Chrome."),
    ])
    _, suite = jouer(agent, "cherche x", "ouvre chrome")
    assert suite.kind == "result" and journal[-1] == ("open_app", {"name": "chrome"})   # plus de confirmation
    assert contenus(modele.vus[2], "tool") == [REDACTED]
    assert not any("IGNORE" in str(m.content) for m in modele.vus[2])


# ---------- mémoire de conversation ----------
def test_la_conversation_est_memorisee_par_identifiant():
    agent, modele, _ = creer([ai("Enchanté Salma."), ai("Tu t'appelles Salma."), ai("Je ne sais pas.")])
    jouer(agent, "je m'appelle Salma", "comment je m'appelle ?", conversation="a")
    jouer(agent, "comment je m'appelle ?", conversation="b")
    assert contenus(modele.vus[1], "human") == ["je m'appelle Salma", "comment je m'appelle ?"]
    assert contenus(modele.vus[1], "ai") == ["Enchanté Salma."]
    assert contenus(modele.vus[2], "human") == ["comment je m'appelle ?"]


def test_seules_les_dernieres_demandes_sont_envoyees_au_modele():
    agent, modele, _ = creer([ai("un"), ai("deux"), ai("trois")], history_turns=2)
    jouer(agent, "première", "deuxième", "troisième")
    assert contenus(modele.vus[2], "human") == ["deuxième", "troisième"]


def test_les_faits_retenus_sont_dans_le_prompt_systeme():
    agent, modele, _ = creer([ai("Oui.")], facts=lambda: ["Elle s'appelle Salma"], city="Sousse")
    jouer(agent, "tu me connais ?")
    assert "Elle s'appelle Salma" in modele.vus[0][0].content and "Sousse" in modele.vus[0][0].content


# ---------- robustesse ----------
def test_boucle_d_outils_arretee():
    agent, _, journal = creer([ai("", ("get_weather", {})) for _ in range(5)], max_steps=2)
    (r,) = jouer(agent, "météo en boucle")
    assert r.reply == TOO_MANY_STEPS and len(journal) == 2


def test_modele_injoignable():
    agent, _, _ = creer([RuntimeError("401 clé invalide")])
    (r,) = jouer(agent, "bonjour")
    assert r.kind == "result" and r.reply == LLM_DOWN and "401" in r.error


def test_outil_invente_par_le_modele():
    agent, modele, journal = creer([ai("", ("teleporter", {})), ai("Je ne sais pas faire ça.")])
    (r,) = jouer(agent, "téléporte-moi")
    assert journal == [] and "n'existe pas" in contenus(modele.vus[1], "tool")[0] and r.tools == []


def test_la_reponse_est_nettoyee_pour_la_voix():
    agent, _, _ = creer([ai([{"type": "text", "text": "**Voici** : voir [le site](https://exemple.tn/page)."}])])
    (r,) = jouer(agent, "dis-moi")
    assert r.reply == "Voici : voir le site."


def test_un_appel_reste_sans_resultat_est_repare():
    agent, _, _ = creer([])
    orphelin = ai("", ("lock_screen", {}))
    fenetre = window([HumanMessage(content="un"), orphelin, HumanMessage(content="deux")], agent.toolbox, 8)
    assert [m.type for m in fenetre] == ["human", "ai", "tool", "human"]
    assert fenetre[2].content == INTERRUPTED and fenetre[2].tool_call_id == orphelin.tool_calls[0]["id"]


# ---------- trace des étapes et journal des actions sensibles ----------
def test_la_trace_detaille_chaque_etape():
    agent, _, _ = creer([ai("", ("get_weather", {}), ("start_timer", {"seconds": 60})), ai("C'est fait.")])
    (r,) = jouer(agent, "météo et minuteur")
    assert [e["kind"] for e in r.trace] == ["llm", "tool", "tool", "llm"]
    assert r.trace[0]["calls"] == ["get_weather", "start_timer"]
    assert [e["status"] for e in r.trace if e["kind"] == "tool"] == ["ok", "ok"]
    assert all(isinstance(e["ms"], int) for e in r.trace)


def test_la_pause_de_confirmation_est_visible_et_journalisee():
    journal, recus = [], []

    async def emit(e):
        recus.append(e)

    agent, _, _ = creer([ai("", ("lock_screen", {})), ai("Écran verrouillé.")], on_decision=journal.extend)
    question, fin = jouer(agent, "verrouille l'écran", "oui", emit=emit)
    assert "waiting" in [e["node"] for e in recus if e["type"] == "node"]
    assert journal == [{"tool": "lock_screen", "label": "lock_screen", "action": "verrouiller l'écran",
                        "reason": "action sensible", "outcome": "confirmée"}]
    assert {"kind": "review", "items": [{"label": "lock_screen", "outcome": "confirmée"}]} in fin.trace


def test_refus_et_changement_d_avis_sont_journalises():
    journal = []
    agent, _, _ = creer([ai("", ("lock_screen", {})), ai("Annulé."),
                         ai("", ("lock_screen", {})), ai("", ("start_timer", {"seconds": 60})), ai("Minuteur lancé.")],
                        on_decision=journal.extend)
    jouer(agent, "verrouille", "non", "verrouille", "non, mets plutôt un minuteur d'une minute")
    assert [e["outcome"] for e in journal] == ["refusée", "remplacée"]


def test_action_bloquee_apres_contenu_web_journalisee_avec_sa_raison():
    journal = []
    agent, _, _ = creer([ai("", ("web_search", {"query": "x"})), ai("", ("open_app", {"name": "evil"})), ai("Rien ouvert.")],
                        on_decision=journal.extend)
    jouer(agent, "cherche x", "non")
    assert journal[0]["reason"] == "après contenu web" and journal[0]["action"] == "ouvrir evil"
    assert journal[0]["outcome"] == "refusée"


# ---------- cartes visuelles (lot 2) ----------
def test_les_cartes_des_outils_arrivent_avec_la_reponse():
    import cards
    from agent.toolbox import ToolSpec
    agent, modele, _ = creer([ai("", ("show_map", {"place": "Sousse"})), ai("Sousse est en Tunisie.")])
    agent.toolbox.register(ToolSpec(name="show_map", description="", schema={}, read_only=True, open_world=False,
                                    label="carte"),
                           lambda a: cards.attach("Lieu trouvé : Sousse.", {"kind": "map", "name": "Sousse"}))
    (r,) = jouer(agent, "où est Sousse ?")
    assert r.cards == [{"kind": "map", "name": "Sousse"}]
    vu_par_le_modele = contenus(modele.vus[-1], "tool")
    assert vu_par_le_modele == ["Lieu trouvé : Sousse."]           # le JSON de la carte ne va jamais au modèle
