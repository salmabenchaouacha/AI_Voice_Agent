import sys
import types

import llm
import router


def _faux_anthropic(monkeypatch, texte=None, erreur=None):
    appels = []

    class Messages:
        def create(self, **kwargs):
            appels.append(kwargs)
            if erreur:
                raise erreur
            return types.SimpleNamespace(content=[types.SimpleNamespace(text=texte)])

    module = types.ModuleType("anthropic")
    module.Anthropic = lambda: types.SimpleNamespace(messages=Messages())
    monkeypatch.setitem(sys.modules, "anthropic", module)
    monkeypatch.setattr(llm, "_client", None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "cle-de-test")
    return appels


def test_sans_cle_api_aucun_appel(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert llm.ask_llm("bonjour") is None


def test_avec_cle_api(monkeypatch):
    appels = _faux_anthropic(monkeypatch, texte="  Paris.  ")
    assert llm.ask_llm("capitale de la France ?") == "Paris."
    assert appels[0]["max_tokens"] == 200
    assert appels[0]["messages"][0]["content"] == "capitale de la France ?"


def test_erreur_api_retourne_none(monkeypatch):
    _faux_anthropic(monkeypatch, erreur=RuntimeError("panne"))
    assert llm.ask_llm("bonjour") is None


def test_le_routeur_appelle_le_llm_en_dernier_recours(monkeypatch):
    monkeypatch.setattr(router, "ask_llm", lambda question: "Réponse du LLM")
    assert dispatch_inconnu() == "Réponse du LLM"


def test_les_commandes_passent_avant_le_llm(monkeypatch):
    monkeypatch.setattr(router, "ask_llm", lambda question: "NON")
    assert router.dispatch("quelle heure est-il").startswith("Il est ")


def dispatch_inconnu():
    return router.dispatch("zzz qqq")