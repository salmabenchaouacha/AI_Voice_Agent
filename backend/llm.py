"""Accès au modèle de langage.

  - get_chat_model() : le modèle de chat de l'agent, choisi par VA_LLM au format « fournisseur:modèle ».
    Changer de fournisseur (Claude, GPT, Gemini, Mistral, ou un modèle local servi par Ollama) ne demande
    qu'une variable d'environnement : le graphe ne dépend que de l'interface commune de LangChain.
  - ask_llm() : l'ancien repli du mode hors-ligne, une question → une réponse, sans outil.
"""
import os

import config

# Variable d'environnement attendue par chaque fournisseur (aucune pour un modèle local)
PROVIDER_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google_genai": "GOOGLE_API_KEY",
    "mistralai": "MISTRAL_API_KEY",
    "groq": "GROQ_API_KEY",
    "ollama": None,
}


def missing_key(spec: str | None = None) -> str | None:
    """Nom de la clé d'API manquante pour ce modèle, ou None si tout est en place."""
    provider = (spec or config.LLM).split(":", 1)[0]
    key = PROVIDER_KEYS.get(provider)
    return key if key and not os.getenv(key) else None


def get_chat_model(spec: str | None = None):
    from langchain.chat_models import init_chat_model
    spec = spec or config.LLM
    options = {"temperature": 0}              # mêmes décisions d'outils d'un essai à l'autre
    if not spec.startswith("ollama:"):
        options["max_tokens"] = 500           # des réponses faites pour l'oral (Ollama n'a pas ce paramètre)
    return init_chat_model(spec, **options)


_client = None


def ask_llm(question: str):
    global _client
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        if _client is None:
            import anthropic
            _client = anthropic.Anthropic()
        r = _client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system="Tu es un assistant vocal. Réponds en une ou deux phrases courtes, sans markdown ni liste.",
            messages=[{"role": "user", "content": question}],
        )
        return r.content[0].text.strip()
    except Exception:
        return None
