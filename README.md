# Assistant vocal : agent LangGraph + outils MCP

Un assistant vocal qui tourne sur ton ordinateur. Tu parles, Whisper transcrit, un agent décide quoi faire,
agit à travers des outils MCP, et la réponse est lue à voix haute.

La version 1 reconnaissait des commandes avec des regex. La version 2 garde ce mode comme secours et ajoute
un vrai agent par-dessus.

| Ce qui manquait | Ce qui le fournit maintenant |
|---|---|
| Une seule action par phrase | Boucle `agent → review → tools` du graphe : le modèle enchaîne autant d'outils que nécessaire |
| Aucune mémoire de conversation | Checkpointer LangGraph, une conversation par navigateur (`thread_id`) |
| Aucune confirmation | `interrupt()` avant toute action sensible, reprise sur le « oui » ou le « non » de l'utilisateur |
| Recherche web qui ouvre juste un onglet | Outils `web_search` et `read_page` : l'agent lit les résultats et les résume |
| LLM appelé seulement en dernier recours, sans outil | Le LLM choisit les outils ; les regex ne servent plus que hors-ligne |
| Fonctions câblées dans le code | Serveurs MCP décrits dans `mcp.json` : ajouter un outil = ajouter un serveur |

## Architecture

```
 navigateur (React)                       backend (FastAPI)
┌───────────────────┐  audio / texte   ┌──────────────────────────────────────────────────────────┐
│ micro, historique │ ───────────────► │ server.py   WebSocket /ws                                │
│ synthèse vocale   │ ◄─────────────── │   │  stt.py (Whisper)                                    │
└───────────────────┘  step / confirm  │   ▼                                                      │
                       result          │ agent/runtime.py ── pas de LLM ? ──► router.py + skills.py│
                                       │   │                                   (regex, hors-ligne)│
                                       │   ▼                                                      │
                                       │ agent/graph.py  (LangGraph)                              │
                                       │   START ─► agent ─► review ─► tools ─┐                   │
                                       │              ▲   │      │            │                   │
                                       │              └───┼──────┼────────────┘                   │
                                       │                  ▼      ▼                                │
                                       │                 END   interrupt() : « Tu confirmes ? »   │
                                       │   │                                                      │
                                       │   ▼ agent/toolbox.py                                     │
                                       │   ├─ outils locaux : minuteurs, mémoire durable          │
                                       │   └─ agent/mcp_client.py ──stdio──► mcp_servers/         │
                                       │                                      ├ desktop_server.py │
                                       │                                      ├ web_server.py     │
                                       │                                      └ notes_server.py   │
                                       └──────────────────────────────────────────────────────────┘
```

Les trois nœuds du graphe :

- **agent** : le modèle lit la conversation et choisit de répondre ou d'appeler un ou plusieurs outils.
- **review** : le garde-fou (`agent/policy.py`) décide si ces appels exigent un oui. Si oui, le graphe se met en pause.
- **tools** : exécute les appels acceptés. Les lectures partent en parallèle, les actions une par une dans l'ordre demandé.

## Les outils

13 outils viennent de trois serveurs MCP, 5 sont locaux.

| Serveur MCP | Outils | Confirmation |
|---|---|---|
| `bureau` | `open_app`, `set_volume`, `take_screenshot`, `battery_status` | non |
| `bureau` | `lock_screen` | toujours |
| `web` | `get_weather`, `web_search`, `read_page`, `play_youtube`, `open_in_browser` | non |
| `notes` | `add_note`, `list_notes` | non |
| `notes` | `clear_notes` | toujours |
| (local) | `start_timer`, `list_timers`, `cancel_timers`, `remember` | non |
| (local) | `forget_memory` | toujours |

Les minuteurs et la mémoire restent locaux parce qu'ils ont besoin du processus du serveur web : c'est lui qui
tient la connexion au navigateur pour annoncer la fin d'un minuteur.

Chaque serveur décrit lui-même ses outils avec les annotations standard de MCP (`read_only_hint`,
`destructive_hint`, `open_world_hint`). L'agent ne connaît aucun outil à l'avance : il les découvre au démarrage.

### Brancher un autre serveur MCP

`backend/mcp.json` a le même format que celui de Claude Desktop ou de Cursor. Pour ajouter un serveur existant
(fichiers, agenda, GitHub…), ajoute une entrée, sans toucher au code :

```json
{
  "mcpServers": {
    "bureau": { "command": "python", "args": ["mcp_servers/desktop_server.py"] },
    "fichiers": { "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:/Users/moi/Documents"] }
  }
}
```

Un outil sans annotations est traité comme la spécification MCP le prévoit : supposé destructif, donc soumis à confirmation.

## Le garde-fou

Trois règles, appliquées à chaque appel d'outil demandé par le modèle (`agent/policy.py`) :

1. Un outil en lecture seule passe toujours.
2. Un outil marqué « à confirmer » par son serveur demande toujours un oui.
3. Tout autre outil qui agit sur la machine demande un oui **si du contenu web est entré dans la demande en cours**.

La règle 3 est la défense contre l'injection de prompt. Une page piégée peut convaincre le modèle d'appeler
`open_in_browser`, mais elle ne peut pas répondre « oui » à la place de l'utilisateur. En complément :

- le contenu web est encadré par `<contenu_externe>` et le prompt système dit de n'y voir que des données ;
- il est retiré du contexte à la demande suivante, donc il ne peut pas agir à retardement ;
- `read_page` refuse les adresses locales (`127.0.0.1`, réseau privé), `open_app` refuse ce qui ressemble à une commande.

La question de confirmation reprend les arguments compris (« Je vais ouvrir chrome. Tu confirmes ? »), ce qui
permet aussi de rattraper une erreur de transcription. Si l'utilisateur répond autre chose que oui ou non
(« non, mets plutôt un minuteur »), l'action est abandonnée et sa phrase est transmise au modèle.

## Installation

Python 3.11 ou plus récent, Node 18 ou plus récent.

```powershell
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate            # Linux / macOS : source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env            # puis mets ta clé dans .env
python server.py

# Frontend (autre terminal)
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

Au démarrage, le serveur affiche `Mode agent : 18 outils disponibles.` ou `Mode hors-ligne (regex) : …` avec la raison.
`GET /api/status` donne le mode, le modèle, la liste des outils et leur règle de confirmation.

Sous Windows, lance bien `python server.py` et non `uvicorn --reload` : le rechargement automatique change la
boucle asyncio et peut empêcher le lancement des serveurs MCP.

### Changer de modèle

Le graphe ne dépend que de l'interface commune de LangChain. Une variable suffit :

```
VA_LLM=anthropic:claude-haiku-4-5-20251001    # défaut
VA_LLM=ollama:qwen3:8b                         # modèle local, aucune clé (pip install langchain-ollama)
```

## Tests

```powershell
cd backend
pytest                    # aucun appel réseau, aucune clé d'API nécessaire

cd ../frontend
npm test
```

| Fichier | Ce qu'il vérifie |
|---|---|
| `test_agent.py` | le graphe, avec un faux modèle : multi-actions, confirmation, refus, injection, mémoire, limites |
| `test_mcp.py` | les trois serveurs MCP lancés pour de vrai et interrogés par le client |
| `test_assistant.py` | l'assemblage complet : faux modèle → graphe → serveurs MCP réels → WebSocket |
| `test_policy.py`, `test_actions.py` | le garde-fou et les fonctions, en Python pur |
| les autres | le mode hors-ligne d'origine, inchangé |

## Mesures

Deux sources de chiffres.

**Latence réelle.** Chaque demande ajoute une ligne à `backend/metrics.jsonl` (durées et noms d'outils, jamais le
texte prononcé). `GET /api/metrics` en donne la médiane et le 90ᵉ centile, par mode, avec la part de la
transcription, du modèle et des outils.

**Qualité des décisions.** `python eval/run_eval.py` joue 23 scénarios parlés contre le vrai modèle, avec des
outils simulés : rien n'est exécuté sur la machine. Il donne le taux de réussite par catégorie (une action,
plusieurs actions, mémoire, confirmation, injection), la latence par tour et le nombre d'injections bloquées.
`--model` permet de comparer deux modèles sur les mêmes scénarios.

## Limites connues

- La mémoire de conversation est en RAM (`InMemorySaver`) : elle disparaît au redémarrage du serveur. Pour la
  garder, passe un checkpointer SQLite à `VoiceAgent` (`langgraph-checkpoint-sqlite`).
- Après une question de confirmation, il faut rappuyer sur le micro pour répondre : l'écoute ne redémarre pas seule.
- On ne peut pas interrompre l'agent pendant qu'il réfléchit.
- La synthèse vocale est celle du navigateur ; l'arabe dialectal dépend des voix installées.
- `read_page` vérifie l'adresse avant de la lire, mais ne protège pas contre un DNS qui change de réponse entre les deux.
- Un serveur MCP qui plante en cours de route n'est pas relancé automatiquement.
