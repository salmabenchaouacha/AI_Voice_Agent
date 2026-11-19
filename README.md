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
| Une réponse en texte seul | Cartes visuelles, graphe animé, trace des étapes, panneau de suivi (voir ci-dessous) |

## Ce qu'on voit à l'écran

- **Le graphe de l'agent, animé** : les cases Réflexion → Validation → Outils s'allument en direct pendant la
  demande. La case Validation passe en orange quand l'agent attend un oui.
- **La réponse en direct** : le texte s'écrit au fur et à mesure que le modèle le génère (`astream`). Pendant la
  lecture à voix haute, les mots se surlignent (karaoké).
- **Les mots incertains** : chaque mot transcrit arrive avec sa probabilité Whisper. Sous 60 %, il est souligné,
  ce qui montre d'où vient une erreur de transcription (« source » au lieu de « Sousse »).
- **La trace des étapes** sous chaque réponse : « 4 étapes · 1,6 s », puis le détail de chaque appel du modèle
  et de chaque outil, avec sa durée.
- **Des cartes visuelles** sous la réponse :
  - la météo avec les prévisions sur 4 jours ;
  - les sources cliquables d'une recherche web ;
  - une carte OpenStreetMap d'un lieu ;
  - la miniature d'une capture d'écran ;
  - les événements Google Agenda d'un jour.
- **Le panneau de droite**, mis à jour après chaque réponse :
  - les minuteurs qui décomptent ;
  - les rappels à venir ;
  - la liste de tâches, qu'on peut cocher à la souris ;
  - les dernières notes ;
  - le journal des actions sensibles (confirmée / refusée).

Une carte voyage avec le texte de l'outil, derrière un marqueur (`backend/cards.py`), et passe donc telle quelle
par MCP. La boîte à outils la détache avant que le modèle ne lise le résultat. Le modèle ne voit jamais le JSON
de la carte, et ne lit donc ni coordonnées ni liens à voix haute.

## Architecture

```
 navigateur (React)                       backend (FastAPI)
┌───────────────────┐  audio / texte   ┌──────────────────────────────────────────────────────────┐
│ micro, historique │ ───────────────► │ server.py   WebSocket /ws                                │
│ synthèse vocale   │ ◄─────────────── │   │  stt.py (Whisper)                                    │
└───────────────────┘  node / delta /  │   ▼                                                      │
                       step / result   │ agent/runtime.py ── pas de LLM ? ──► router.py + skills.py│
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
                                       │   ├─ outils locaux : minuteurs, rappels, mémoire         │
                                       │   └─ agent/mcp_client.py ──stdio──► mcp_servers/         │
                                       │                                      ├ desktop_server.py │
                                       │                                      ├ web_server.py     │
                                       │                                      ├ notes_server.py   │
                                       │                                      └ calendar_server.py│
                                       └──────────────────────────────────────────────────────────┘
```

Les trois nœuds du graphe :

- **agent** : le modèle lit la conversation et choisit de répondre ou d'appeler un ou plusieurs outils.
- **review** : le garde-fou (`agent/policy.py`) décide si ces appels exigent un oui. Si oui, le graphe se met en pause.
- **tools** : exécute les appels acceptés. Les lectures partent en parallèle, les actions une par une dans l'ordre demandé.

## Les outils

18 outils viennent de trois serveurs MCP, 8 sont locaux. Le serveur `agenda` en ajoute 2 une fois Google connecté.

| Serveur MCP | Outils | Confirmation |
|---|---|---|
| `bureau` | `open_app`, `set_volume`, `take_screenshot`, `battery_status` | non |
| `bureau` | `lock_screen` | toujours |
| `web` | `get_weather`, `show_map`, `web_search`, `read_page`, `play_youtube`, `open_in_browser` | non |
| `notes` | `add_note`, `list_notes`, `add_task`, `list_tasks`, `complete_task`, `clear_done_tasks` | non |
| `notes` | `clear_notes` | toujours |
| `agenda` (désactivé par défaut) | `list_events`, `create_event` | non |
| (local) | `start_timer`, `list_timers`, `cancel_timers`, `set_reminder`, `list_reminders`, `cancel_reminders`, `remember` | non |
| (local) | `forget_memory` | toujours |

« Non » veut dire : pas de confirmation, sauf après du contenu web (voir le garde-fou).

Minuteurs, rappels et mémoire restent locaux, parce qu'ils ont besoin du processus du serveur web : c'est lui qui
tient la connexion au navigateur pour annoncer la fin d'un minuteur ou un rappel. Les rappels sont aussi écrits
sur disque et reprogrammés au redémarrage. Les tâches vivent dans un fichier JSON partagé entre le serveur MCP
`notes` (l'agent) et le serveur web (la case à cocher du panneau).

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

Au démarrage, le serveur affiche `Mode agent : 26 outils disponibles.` ou `Mode hors-ligne (regex) : …` avec la raison.
`GET /api/status` donne le mode, le modèle, la liste des outils et leur règle de confirmation.

Sous Windows, lance bien `python server.py` et non `uvicorn --reload` : le rechargement automatique change la
boucle asyncio et peut empêcher le lancement des serveurs MCP.

### Google Agenda (facultatif)

Le serveur MCP `agenda` lit et crée des événements dans le Google Agenda de l'utilisateur. Il est désactivé dans
`mcp.json` tant que le compte n'est pas connecté. La mise en place se fait une seule fois :

1. Sur [console.cloud.google.com](https://console.cloud.google.com), crée un projet et active **Google Calendar API**.
2. Dans *API et services → Écran de consentement OAuth*, choisis « Externe » et ajoute ton adresse comme
   utilisateur de test.
3. Dans *Identifiants*, crée un **ID client OAuth** de type « Application de bureau », télécharge le JSON et
   enregistre-le sous `backend/google_credentials.json`. Ce fichier est dans `.gitignore`.
4. Installe les bibliothèques et autorise l'accès :
   ```powershell
   pip install google-api-python-client google-auth-oauthlib
   python mcp_servers/calendar_server.py --login
   ```
   Le jeton est gardé dans `~/.assistant_google_token.json`, hors du projet.
5. Dans `backend/mcp.json`, passe `"enabled"` du serveur `agenda` à `true`, puis relance le serveur
   (28 outils au démarrage).

Exemples : « Qu'est-ce que j'ai demain ? », « Ajoute une réunion PFE jeudi à 10 h ».

### Changer de modèle

Le graphe ne dépend que de l'interface commune de LangChain. Une variable suffit :

```
VA_LLM=google_genai:gemini-3.5-flash-lite      # celui utilisé pour l'évaluation (pip install langchain-google-genai)
VA_LLM=anthropic:claude-haiku-4-5-20251001    # défaut du code
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
| `test_cards.py` | cartes visuelles : marqueur, météo et prévisions, carte d'un lieu, sources, second essai de la recherche |
| `test_planner.py` | tâches (ajout, doublons, recherche à l'oral, case à cocher) et rappels (heure comprise, rappel qui sonne, reprise au démarrage) |
| `test_agenda.py` | Google Agenda avec un faux service Google, et le serveur MCP `agenda` lancé pour de vrai |
| `test_stt.py` | probabilité de chaque mot transcrit, avec un faux modèle Whisper |
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

Résultat avec `gemini-3.5-flash-lite` : **91 % de réussite (21 scénarios sur 23)**, latence médiane de l'agent
**1,2 s** par tour.

## Limites connues

- La mémoire de conversation est en RAM (`InMemorySaver`) : elle disparaît au redémarrage du serveur. Pour la
  garder, passe un checkpointer SQLite à `VoiceAgent` (`langgraph-checkpoint-sqlite`).
- Après une question de confirmation, il faut rappuyer sur le micro pour répondre : l'écoute ne redémarre pas seule.
- Le surlignage des mots est exact avec les voix locales de Windows. D'autres voix ne signalent pas les mots :
  la position est alors estimée au temps.
- La réponse en direct n'est pas lue avant d'être complète : la synthèse vocale démarre à la fin.
- On ne peut pas interrompre l'agent pendant qu'il réfléchit.
- La synthèse vocale est celle du navigateur ; l'arabe dialectal dépend des voix installées.
- `read_page` vérifie l'adresse avant de la lire, mais ne protège pas contre un DNS qui change de réponse entre les deux.
- Un serveur MCP qui plante en cours de route n'est pas relancé automatiquement.
