# Serveur BidBang

FastAPI, salons et parties en mémoire. Le serveur fait autorité : le client envoie des intentions, jamais de résultats.

## Lancer

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload   # en dev : relance seul quand le code change
```

## HTTP

| Route | Corps | Réponse |
|---|---|---|
| `GET /health` | | `{status}` |
| `GET /locations` | | `{locations: [{id, name, description}]}` |
| `POST /rooms` | `{pseudo, settings?}` | `{code, player_id, token, room}` |
| `POST /rooms/{code}/join` | `{pseudo}` | `{code, player_id, token, room}` |
| `GET /items` | | `{items, categories, stats, trial_packs}` : objets du catalogue au format commun |
| `GET /ai/providers` | | `{providers: [{id, label}]}` |
| `PUT /rooms/{code}/selection` | `{item_ids}` + `Authorization: Bearer <token>` | `{room}` (hôte, partie `ai`) |
| `POST /rooms/{code}/ai/generate` | `{provider, api_key}` + `Authorization: Bearer <token>` | `{items, trials, trials_source, generations_left}` (hôte, partie `ai`) |

Erreurs : HTTP `{detail}` avec un message en français (400 par défaut ; 401 session invalide, 403 pas l'hôte, 409 partie déjà lancée, 429 limites, 502/504 fournisseur IA). Les erreurs de validation de corps (422) sont volontairement réduites à `{detail: "Requête invalide."}` : le format FastAPI par défaut renvoie la valeur reçue, qui pourrait être une clé API.

## Types de création et réglages

Deux notions indépendantes : le **type de création** (`creation_type`) et le **mode de jeu** (`mode`).

| `creation_type` | Contenu |
|---|---|
| `classic` (défaut, aussi quand le champ est absent) | un lieu du catalogue (`theme_id`) ; comportement historique |
| `custom` | `scenario` + `item_ids` (objets du catalogue, tous lieux confondus) |
| `ai` | `scenario`, puis objets générés par une IA externe, puis validation de la sélection |

Réglages communs : `max_players` (2 / 3 / 4, défaut 4 : taille maximale du salon), `mode` (`construction` / `survie` / `aveugle`), `budget` (1200 / 2200 / 3500), `item_count` (6 / 8 / 10), `bid_timer` (10 / 15 / 20 / 30 s).
`classic` : `theme_id`. `custom` / `ai` : `scenario` `{description (5 à 300 caractères, 600 pour `ai`), title? (60 max, déduit sinon)}` (une simple chaîne est acceptée), `item_ids` (identifiants uniques et connus, au moins `item_count`, 80 max), `trial_pack` (`generique` / `catastrophe` / `expedition` / `reception`, utilisé en Survie). Le serveur ajoute `ready` (sélection valide) ; `theme_id` vaut alors le type de création.

Exemple `custom` :

```json
{"creation_type": "custom", "mode": "construction", "budget": 2200, "item_count": 6, "bid_timer": 15,
 "scenario": {"description": "Organisez le mariage le plus extravagant possible."},
 "item_ids": ["cabane_01", "plage_01", "bureau_01", "plage_02", "cabane_02", "station_01"]}
```

Le serveur tire `item_count` objets au hasard parmi la sélection (ordre aléatoire) et n'utilise que celle-ci. Le texte du scénario est une donnée affichée : il n'influence jamais les règles. En Survie, les épreuves viennent d'une série prédéfinie (`app/trials.py`) ou de l'IA (validées, seuils 4 à 12), jamais du texte de l'hôte.

### Format commun des objets (`app/items.py`)

`{id, name, description, category, icon, price, rarity (0-3), stats{confort, style, utilite, securite, sante : 0-5}, tags[], source ("catalog" | "ai")}` (+ `location_id` pour le catalogue). Les objets générés vivent dans le salon (`room.ai_items`) le temps de la partie ; ce même format permettra plus tard une bibliothèque communautaire.

## Partie avec IA : flux et sécurité

1. `POST /rooms` avec `creation_type: "ai"` (sans `item_ids`) : salon en attente, `ready: false`.
2. `POST /rooms/{code}/ai/generate` (hôte) : le serveur appelle le fournisseur, valide la réponse et renvoie les objets proposés.
3. `PUT /rooms/{code}/selection` (hôte) : sélection finale (objets générés et/ou du catalogue). `start_game` est refusé tant qu'elle n'est pas validée. Une nouvelle génération invalide la sélection.
4. Une fois la partie lancée, plus aucune génération (409) et l'IA n'intervient jamais pendant les enchères.

**Clé API** (fournie par l'hôte, jamais par le jeu) : envoyée dans le corps JSON (jamais dans l'URL), uniquement en HTTPS (ou en local : 127.0.0.1, localhost, 10.0.2.2 ; derrière un proxy, lancer uvicorn avec `--proxy-headers` ; `BIDBANG_ALLOW_INSECURE_AI=1` lève la contrainte, à ne jamais utiliser en production). Elle n'est ni stockée (ni salon, ni catalogue, ni base), ni journalisée, ni renvoyée (HTTP ou WebSocket), ni mise en tâche de fond : elle vit dans les variables locales d'une requête puis les références sont supprimées (l'effacement physique de la mémoire n'est pas garanti). Les erreurs du fournisseur sont converties en messages génériques (jamais le texte brut). La vérification des certificats TLS n'est jamais désactivée.

**Risques à connaître** : l'hôte confie sa clé au serveur de jeu le temps d'un appel ; un serveur compromis ou malveillant pourrait la lire. Recommandation : clé dédiée au jeu, avec plafond de dépenses chez le fournisseur, à révoquer après usage. Le fournisseur peut facturer chaque génération. Il appartient à l'hôte de vérifier que son contrat avec le fournisseur autorise cet usage (non vérifié par ce projet).

**Limites** (`app/ai/limits.py`) : 5 générations par salon (échecs compris), 5 s minimum entre deux, une seule à la fois par salon, 3 simultanées sur le serveur, 10 requêtes refusées (jeton, salon inconnu) par minute et par adresse, sortie plafonnée à 8000 jetons, délai de 60 s, réponse de plus de 40 000 caractères rejetée, 30 objets lus au maximum.

**Validation** (`app/items.py`, `app/trials.py`, `app/ai/generator.py`) : la réponse est du JSON non fiable. Chaque objet est validé avec Pydantic ; un objet incorrect est écarté (stats hors 0-5 ou manquantes, rareté hors 0-3, somme de stats hors des plafonds par rareté, champs manquants ou trop longs, tags invalides) et la génération est refusée s'il reste moins de `max(item_count, 6)` objets. Les identifiants (`ai_<nom>`, uniques) et les prix sont calculés par le serveur ; noms en double écartés ; l'icône est imposée ; les URL et champs inconnus sont ignorés ; rien n'est exécuté. Épreuves de Survie : 3 épreuves sur des stats différentes, seuil 4-12, sinon la série prédéfinie est utilisée.

**Écran IA (Godot)** : seulement le prompt (situation + objets à intégrer obligatoirement avec leur prix, 600 caractères), le nombre de joueurs et la clé API ; mode `construction`, budget 2200, 8 objets, chrono 15 s sont imposés. L'IA peut proposer un `price` (20 à 600, arrondi à 10, sinon calcul serveur) ; la présence des objets imposés est demandée à l'IA mais pas vérifiée par le serveur.

**Fournisseurs** : interface `AIProvider` (`app/ai/base.py`), choisis par `provider` dans la requête de génération :

| `provider` | Accès | Modèle par défaut (variable d'environnement) |
|---|---|---|
| `anthropic` | SDK officiel | `claude-opus-5-5` (`BIDBANG_AI_MODEL`) |
| `openai` | HTTPS `api.openai.com`, clé en `Authorization: Bearer` | `gpt-4o-mini` (`BIDBANG_OPENAI_MODEL`) |
| `gemini` | HTTPS `generativelanguage.googleapis.com`, clé en `x-goog-api-key` (jamais dans l'URL) | `gemini-2.5-flash` (`BIDBANG_GEMINI_MODEL`) |

OpenAI et Gemini passent par `app/ai/http_provider.py` : URL fixée dans le code, TLS vérifié, aucune redirection suivie, réponse bornée, erreurs génériques. Pour en ajouter un : écrire la classe et l'enregistrer dans `_registry()` de `base.py`.

## WebSocket `WS /ws/{code}?token=...`

Fermeture 4401 (jeton invalide) ou 4404 (salon inconnu).

Serveur vers client : `room_state` {room}, `game_state` {game} (état complet à chaque changement et à la reconnexion), `error` {message}, `kicked` (le joueur vient d'être exclu ; la connexion se ferme avec le code 4403), `pong`.

Client vers serveur : `start_game` (hôte), `bid` {amount}, `fold`, `vote` {target}, `kick` {target} (hôte, avant le début de la partie : retire le joueur, invalide son jeton et l'empêche de rejoindre ce salon sous le même pseudo), `leave`, `ping`.

`game_state.game` : `creation_type`, `situation` (`{title, description}` ou null en classique), `phase` (`auction` / `voting` / `finished`), `mode`, `settings`, `location`, `scenario`, `item_index`, `item_total`, `auction` {item, start_price (indicatif), opening_min, step, current_bid, leader_id, required_bid, folded, seconds_left}, `vote` {seconds_left, voted_ids, your_vote}, `players` [{id, pseudo, budget, items, folded}], `last_result`, `results`, `you`.

## Règles

**Horloge serveur** : avant de traiter une mise, un abandon ou un vote, le moteur compare l'horloge du serveur à l'échéance (`Game._reject_if_late`). Une action reçue après l'échéance est refusée (« Temps écoulé... ») et l'étape est clôturée sur-le-champ, même si le chronomètre asyncio n'a pas encore tiré ; l'état est alors diffusé avant l'erreur.

Voir `app/game.py` (constantes en tête de fichier). Mode `aveugle` : `bid` et `fold` sont secrets (une seule fois par objet) ; `auction.blind`, `auction.submitted` (qui a joué) et `auction.your_bid` (0 = passé) remplacent `current_bid` / `leader_id` ; `last_result.bids` révèle toutes les mises après résolution.

Mise d'ouverture libre (`opening_min` = 10 € minimum), puis surenchère d'au moins `step`. `players[].purchases` et `results[].purchases` listent `{item, price}` ; `results[].spent` donne le total dépensé.

Seuils de survie donnés pour 6 objets, mis à l'échelle selon `item_count`. Le catalogue est généré par `python tools/gen_catalog.py`.
