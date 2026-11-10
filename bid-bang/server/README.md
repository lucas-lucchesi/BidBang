# Serveur BidBang

FastAPI, salons et parties en mémoire. Le serveur fait autorité : le client envoie des intentions, jamais de résultats.

## Lancer

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## HTTP

| Route | Corps | Réponse |
|---|---|---|
| `GET /health` | | `{status}` |
| `GET /locations` | | `{locations: [{id, name, description}]}` |
| `POST /rooms` | `{pseudo, settings?}` | `{code, player_id, token, room}` |
| `POST /rooms/{code}/join` | `{pseudo}` | `{code, player_id, token, room}` |

Erreurs : HTTP 400 `{detail}` avec un message en français.

Réglages : `mode` (`construction` / `survie`), `theme_id`, `budget` (1200 / 2200 / 3500), `item_count` (6 / 8 / 10), `bid_timer` (10 / 15 / 20 / 30 s).

## WebSocket `WS /ws/{code}?token=...`

Fermeture 4401 (jeton invalide) ou 4404 (salon inconnu).

Serveur vers client : `room_state` {room}, `game_state` {game} (état complet à chaque changement et à la reconnexion), `error` {message}, `pong`.

Client vers serveur : `start_game` (hôte), `bid` {amount}, `fold`, `vote` {target}, `leave`, `ping`.

`game_state.game` : `phase` (`auction` / `voting` / `finished`), `mode`, `settings`, `location`, `scenario`, `item_index`, `item_total`, `auction` {item, start_price, step, current_bid, leader_id, required_bid, folded, seconds_left}, `vote` {seconds_left, voted_ids, your_vote}, `players` [{id, pseudo, budget, items, folded}], `last_result`, `results`, `you`.

## Règles

Voir `app/game.py` (constantes en tête de fichier). Seuils de survie donnés pour 6 objets, mis à l'échelle selon `item_count`. Le catalogue est généré par `python tools/gen_catalog.py`.
