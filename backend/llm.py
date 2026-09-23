"""Bonus : repli sur un LLM quand aucune commande ne correspond (nécessite ANTHROPIC_API_KEY)."""
import os

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