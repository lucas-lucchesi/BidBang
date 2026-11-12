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
| `GET /locations` | | `{locations: [{id, name, description, criteria}]}` (critères avec libellés) |
| `POST /rooms` | `{pseudo, settings?}` | `{code, player_id, token, room}` |
| `POST /rooms/{code}/join` | `{pseudo}` | `{code, player_id, token, room}` |
| `GET /items` | | `{items, locations, criteria, templates}` : objets du catalogue (sans points : ils dépendent de la situation), registre des critères, modèles de critères |
| `POST /scoring/preview` | `{criteria, item_ids}` | `{criteria, items}` : objets du catalogue avec leurs `points` pour ces critères (aperçu, rien n'est créé ni figé) |
| `GET /ai/providers` | | `{providers: [{id, label}]}` |
| `PUT /rooms/{code}/selection` | `{item_ids}` + `Authorization: Bearer <token>` (`criteria` : refusé en partie `ai`) | `{room, situation, items}` : cartes choisies avec leurs points (hôte, partie `ai`) |
| `POST /rooms/{code}/ai/generate` | `{provider, api_key}` ou `{provider: "gemini", use_env_key: true}` + `Authorization: Bearer <token>` | `{situation, profile, corrected, items, generations_left}` (hôte, partie `ai`) : `items` = cartes avec les `points` attribués par l'IA, `profile` = objectif validé par le serveur |

Erreurs : HTTP `{detail}` avec un message en français (400 par défaut ; 401 session invalide, 403 pas l'hôte, 409 partie déjà lancée, 429 limites, 502/504 fournisseur IA). Les erreurs de validation de corps (422) sont volontairement réduites à `{detail: "Requête invalide."}` : le format FastAPI par défaut renvoie la valeur reçue, qui pourrait être une clé API.

## Victoire, situation et points des objets

**Score final = somme des points des objets remportés.** Rien d'autre : ni bonus de rareté, ni synergie, ni vote, ni épreuve, ni appel IA. Classement : score décroissant, puis budget restant décroissant ; égalité parfaite = même rang (co-vainqueurs).

Chaque partie a une **situation** `{title, description, criteria}`. Un critère est `{id, necessary, importance}` : `id` du registre `data/criteria.json` (ASCII minuscule : `decoration`, affiché « Décoration » ; ajouter un critère = ajouter `{id, label}` à ce fichier, sans toucher au moteur), `necessary` booléen, `importance` de 1 à 5 si nécessaire (0 sinon). Les objets utilisent les mêmes identifiants dans `attributes`.

**Formule** (`app/scoring.py`, pure, déterministe, réglable via `ScoringConfig`) : pour chaque critère nécessaire que l'objet possède, `contribution = (valeur/5) * (importance/5)`. On garde les 3 plus fortes, pondérées 1 / 0,35 / 0,12, normalisées en une *pertinence* entre 0 et 1. `points = 1 + 89 * pertinence^1,15 + 10 * base_points/50`, borné à 1-100. Le prix et la rareté n'entrent pas dans le calcul ; la pertinence prime sur le nombre de caractéristiques (seules les 3 meilleures comptent, avec un poids décroissant) ; les caractéristiques hors situation ne rapportent rien ; `base_points` (0-50) n'apporte que 10 points au maximum ; tout objet garde au moins 1 point.

Exemples avec les modèles livrés : Trousse médicale 68 / 6 / 6 (apocalypse zombie / mariage / villa), Jacuzzi 7 / 69 / 87, Véhicule blindé 77 / 5 / 5.

**Points figés** : calculés une seule fois à la création de la partie (`Game.__init__`, au `start_game`), dans des copies indépendantes des objets (`points`, `useful_criteria`, `usefulness`). Ils sont identiques pour tous, ne dépendent jamais des achats des autres et ne changent plus : modifier le catalogue ou les critères d'un salon pendant la partie n'a aucun effet.

**Prix** : `item.price` est le prix *estimé* (jamais remplacé). Chaque achat est `{item, purchase_price}` (prix réellement payé) ; `savings = item.price - purchase_price` (négatif : surcoût).

## Types de création et réglages

Deux notions indépendantes : le **type de création** (`creation_type`) et le **mode d'enchères** (`mode`).

| `creation_type` | Contenu |
|---|---|
| `classic` (défaut, aussi quand le champ est absent) | un lieu du catalogue (`theme_id`) : ses critères et sa situation sont prédéfinis dans `catalog.json` |
| `custom` | `scenario` (situation + `criteria`) + `item_ids` (objets du catalogue, tous lieux confondus) |
| `ai` | `scenario` (une phrase), puis cartes générées par une IA externe : objets, joueurs, métiers, personnalités, personnages... **avec leurs points attribués par l'IA** ; pas de critères ; l'hôte choisit les cartes à garder |

Réglages communs : `max_players` (2 / 3 / 4, défaut 4), `mode` (`normal` / `aveugle`), `budget` (1200 / 2200 / 3500), `item_count` (nombre de cartes mises aux enchères : entier de 6 à 20, au choix de l'hôte ; 12 au plus pour une partie classique, qui n'a que 12 objets par lieu), `bid_timer` (10 / 15 / 20 / 30 s).
**Migration** : les anciens modes `construction` et `survie` sont acceptés et deviennent `normal` (`game.normalize_mode`) ; l'ancien réglage `trial_pack` est ignoré ; un scénario `custom` sans `criteria` (ancien format) reçoit les critères du modèle `polyvalent`.
`classic` : `theme_id`. `custom` / `ai` : `scenario` `{description (5 à 300 caractères, 600 pour `ai`), title? (60 max, déduit sinon), criteria}` (une simple chaîne est acceptée), `item_ids` (identifiants uniques et connus, au moins `item_count`, 80 max). `criteria` : identifiants connus, sans doublon, au moins un critère nécessaire, importance entière 1-5 (partie `ai` : peut être vide avant la génération). Le serveur ajoute `ready` (sélection valide) ; `theme_id` vaut alors le type de création.

Exemple `custom` :

```json
{"creation_type": "custom", "mode": "normal", "budget": 2200, "item_count": 6, "bid_timer": 15,
 "scenario": {"description": "Organisez le mariage le plus extravagant possible.",
              "criteria": [{"id": "luxe", "necessary": true, "importance": 5},
                           {"id": "decoration", "necessary": true, "importance": 5},
                           {"id": "soins", "necessary": false}]},
 "item_ids": ["villa_01", "villa_04", "villa_12", "plage_08", "cabane_10", "station_07"]}
```

Le serveur tire `item_count` objets au hasard parmi la sélection (ordre aléatoire) et n'utilise que celle-ci. Le texte de la situation est une donnée affichée : il n'influence jamais les règles ; seuls les critères structurés comptent.

### Format commun des objets (`app/items.py`)

`{id, name, description, category, icon, price (estimé), rarity (0-3), base_points (0-50), attributes{critère: 1-5}, image (null ou chemin), source ("catalog" | "ai")}` (+ `location_id` pour le catalogue). Une caractéristique absente n'est pas stockée (pas de `soins: 0`). Les objets générés vivent dans le salon (`room.ai_items`) le temps de la partie. Pendant la partie, chaque objet porte en plus `points`, `useful_criteria` (critères nécessaires qu'il couvre, du plus utile au moins utile) et `usefulness` (`high` / `medium` / `low` / `none`). `python tools/gen_catalog.py` régénère `data/catalog.json` (7 lieux, 84 objets) ; l'ancien format (`stats`, `tags`) n'est plus produit.

## Partie avec IA : flux et sécurité

1. `POST /rooms` avec `creation_type: "ai"` (une phrase, sans `item_ids`) : salon en attente, `ready: false`.
2. `POST /rooms/{code}/ai/generate` (hôte) : le serveur appelle le fournisseur, valide la réponse (titre, description, cartes) et renvoie la situation et les cartes proposées, avec les points attribués par l'IA.
3. `PUT /rooms/{code}/selection` (hôte) : sélection finale parmi les cartes générées (le catalogue n'est pas utilisé en partie IA ; au moins `item_count` cartes). `start_game` est refusé tant que la sélection n'est pas validée. Une nouvelle génération invalide la sélection.
4. Une fois la partie lancée, plus aucune génération (409) et l'IA n'intervient jamais pendant les enchères. Elle ne décide ni des points, ni du gagnant, ni des scores.

**Clé API** (fournie par l'hôte, jamais par le jeu) : envoyée dans le corps JSON (jamais dans l'URL), uniquement en HTTPS (ou en local : 127.0.0.1, localhost, 10.0.2.2 ; derrière un proxy, lancer uvicorn avec `--proxy-headers` ; `BIDBANG_ALLOW_INSECURE_AI=1` lève la contrainte, à ne jamais utiliser en production). Elle n'est ni stockée (ni salon, ni catalogue, ni base), ni journalisée, ni renvoyée (HTTP ou WebSocket), ni mise en tâche de fond : elle vit dans les variables locales d'une requête puis les références sont supprimées (l'effacement physique de la mémoire n'est pas garanti). Les erreurs du fournisseur sont converties en messages génériques (jamais le texte brut). La vérification des certificats TLS n'est jamais désactivée.

**Risques à connaître** : l'hôte confie sa clé au serveur de jeu le temps d'un appel ; un serveur compromis ou malveillant pourrait la lire. Recommandation : clé dédiée au jeu, avec plafond de dépenses chez le fournisseur, à révoquer après usage. Le fournisseur peut facturer chaque génération. Il appartient à l'hôte de vérifier que son contrat avec le fournisseur autorise cet usage (non vérifié par ce projet).

**Limites** (`app/ai/limits.py`) : 5 générations par salon (échecs compris), 5 s minimum entre deux, une seule à la fois par salon, 3 simultanées sur le serveur, 10 requêtes refusées (jeton, salon inconnu) par minute et par adresse, sortie plafonnée à 8000 jetons, délai de 60 s, réponse de plus de 40 000 caractères rejetée, 30 objets lus au maximum.

**Profil de génération** (`app/ai/profile.py`) : une même requête structurée contient le **profil** de la situation et les cartes. Le prompt demande d'abord à l'IA de déterminer l'objectif exact de la partie (pas seulement le thème), puis de générer des cartes qui le respectent :

```json
{"goal": "Composer un onze historique", "allowed_entity_types": ["football_player"],
 "real_entities_only": true, "organization": "Olympique de Marseille",
 "required_roles": ["Gardien", "Défenseur", "Milieu", "Attaquant"], "allow_unrelated_items": false}
```

Le profil n'est pas propre au football (types de cartes, rôles et organisation sont libres : `marvel_character`, `job`, `equipment`, `venue`...). Le serveur le valide (`AIProfile` : objectif 3-140 caractères, 1 à 6 types, au plus 12 rôles, booléens stricts) ; un profil absent ou invalide fait échouer la génération (502 « objectif valide ») au lieu d'être deviné. Il est ensuite **appliqué à chaque carte** : la carte doit avoir un `entity_type` admis, une catégorie qui correspond à un rôle requis (« Défenseur central » couvre « Défenseur »), et `is_real: true` si `real_entities_only`. Une carte qui ne respecte pas le profil est écartée (un meuble dans un onze de football, un personnage fictif parmi des joueurs réels, un « Gandalf » dans les buts). `allow_unrelated_items: true` désactive ce filtre (à réserver aux situations sans contrainte). Chaque rôle requis doit avoir au moins une carte valide. Le profil validé est renvoyé à l'hôte et affiché (« Objectif compris »).

**Génération insuffisante** : le serveur ne complète jamais avec des cartes du catalogue ni des cartes inventées. S'il manque des cartes valides ou des rôles, il fait **une seule** requête de correction, qui ne demande que les cartes manquantes (même profil, noms déjà acceptés exclus, texte de l'hôte toujours encadré comme donnée). Si cela ne suffit pas : erreur 502 claire (« L'IA n'a proposé que N carte(s) valide(s)… Aucune carte n'a été ajoutée à la place : relancez la génération »), rien n'est enregistré dans le salon, et l'hôte peut relancer (dans la limite des 5 générations du salon). Une régénération remplace entièrement les propositions précédentes et efface la sélection.

**Nombre de cartes** : l'hôte choisit de 6 à 20 cartes mises aux enchères. Le prompt demande à l'IA `item_count + 2 × nombre de joueurs` cartes (40 au plus : `generator.pool_size`, constantes `POOL_PER_PLAYER` et `MAX_POOL`) pour que l'hôte puisse choisir ; il faut ensuite au moins `item_count` cartes sélectionnées.

**Limite à connaître** : le serveur contrôle la cohérence du format et du profil, pas la véracité. Que Basile Boli ait joué à l'OM repose sur l'IA ; `is_real` est une attestation de l'IA, pas une preuve. Le prompt lui demande de ne pas inventer de personne, de citer un fait vérifiable dans la description et de ne pas mettre une personne dont elle n'est pas sûre, et l'écran invite l'hôte à vérifier. Une validation factuelle stricte demanderait une source de données (base de joueurs par club, par exemple) ou une liste de références fiables, non branchée ici.

**Journal de développement** : `BIDBANG_AI_DEBUG=1` journalise (niveau warning, `bidbang.ai.debug`) les identifiants et noms des cartes à chaque étape : profil, cartes acceptées et écartées avec la raison, correction, propositions enregistrées dans le salon, sélection validée. Jamais de clé API ni de réponse brute. Désactivé par défaut.

**Cartes libres** : une partie IA n'est pas limitée aux objets. Le prompt (`generator.build_system_prompt`) demande à l'IA de choisir le type de carte qui convient à la situation : objets, joueurs d'un sport, métiers, personnalités publiques (réelles ou fictives), personnages, invités, etc. (ex. « un 11 de légende au football » = des joueurs de tous les postes ; « monter une startup » = des métiers). La carte a `name`, `description`, `category` (texte libre : « Gardien », « Métier »...), `rarity`, `price` (estimation) et `points`.

**Points** : l'IA attribue les points de chaque carte (entier de 1 à 100) selon la situation, une seule fois, avant la partie. Il n'y a ni critères ni formule serveur en partie IA. Le serveur valide les bornes, copie les cartes au lancement (points figés, identiques pour tous) et calcule seul le classement ; l'IA ne désigne jamais le gagnant et n'intervient plus pendant les enchères. Le prompt demande des points variés et reflétant la valeur dans la situation, pas la célébrité. Limite connue : le jeu ne vérifie pas qu'une équipe est équilibrée (ex. un seul gardien) : le score est seulement la somme des points.

**Validation** (`app/items.py`, `app/ai/profile.py`, `app/ai/generator.py`) : la réponse est du JSON non fiable. Chaque carte est validée avec Pydantic et écartée si elle est incorrecte (`points` absents, non entiers ou hors 1-100, rareté hors 0-3, champs manquants ou trop longs) ou si elle ne respecte pas le profil ; les champs inconnus (dont `catalog_id`, `critères`, `winner`, `scores`) sont ignorés. La génération est refusée s'il reste moins de `max(item_count, 6)` cartes valides après la correction. Les identifiants (`ai_<nom>`, uniques) sont calculés par le serveur ; le prix estimé proposé n'est retenu que s'il est entre 20 et 600 (sinon calcul serveur) ; noms en double écartés ; l'icône est imposée ; rien n'est exécuté.

**Écran IA (Godot)** : le prompt (une ou deux phrases, 600 caractères ; éventuellement des cartes à inclure avec leur prix), le nombre de joueurs, le nombre de cartes (boutons - et +, de 6 à 20) et la clé API ; mode `normal`, budget 2200 et chrono 15 s sont imposés. L'hôte retire les cartes qu'il ne veut pas, voit l'aperçu des points puis passe au salon. La présence des cartes demandées n'est pas vérifiée par le serveur.

**Fournisseur simulé** : avec `BIDBANG_MOCK_AI=1`, le fournisseur `mock` apparaît dans `GET /ai/providers` ; il renvoie une réponse déterministe (cartes de football si le scénario parle de foot ou de 11, sinon des métiers), sans appel réseau, et n'importe quelle clé de 10 caractères ou plus convient. Pour les essais locaux uniquement. Les tests utilisent leur propre faux fournisseur : aucune vraie clé n'est nécessaire.

**Fournisseurs** : interface `AIProvider` (`app/ai/base.py`), choisis par `provider` dans la requête de génération :

| `provider` | Accès | Modèle par défaut (variable d'environnement) |
|---|---|---|
| `anthropic` | SDK officiel | `claude-opus-5-5` (`BIDBANG_AI_MODEL`) |
| `openai` | HTTPS `api.openai.com`, clé en `Authorization: Bearer` | `gpt-4o-mini` (`BIDBANG_OPENAI_MODEL`) |
| `gemini` | SDK officiel `google-genai` (asynchrone), sorties structurées | `gemini-3.5-flash-lite` (`BIDBANG_GEMINI_MODEL`) |

OpenAI passe par `app/ai/http_provider.py` : URL fixée dans le code, TLS vérifié, aucune redirection suivie, réponse bornée, erreurs génériques. Pour ajouter un fournisseur : écrire la classe et l'enregistrer dans `_registry()` de `base.py`. Un fournisseur qui a l'attribut `structured = True` reçoit en plus `json_schema` (`generator.response_schema()`).

### Gemini (gratuit, pour tester)

Gemini sert à tester la génération de parties (cartes et points) sans dépenser de crédits OpenAI.

- **Sorties structurées** : le schéma `generator.response_schema()` (titre, description, cartes avec `points` de 1 à 100) est transmis à Gemini. La réponse est quand même revalidée par les mêmes validateurs que les autres fournisseurs.
- **Aucun outil** : ni recherche Internet, ni génération d'images. **Aucun nouvel essai automatique** et aucune bascule vers un autre fournisseur ou une offre payante.
- **Quota gratuit dépassé** (HTTP 429 du fournisseur) : l'API renvoie 429 avec « Quota gratuit Gemini dépassé… ». Attendez ou utilisez une autre clé. Les erreurs 400/401/403 (clé refusée), 404 (modèle introuvable), 5xx, délai dépassé et contenu bloqué ont chacune un message générique en français (jamais le texte du SDK, qui pourrait citer la clé).
- **Modèle** : `BIDBANG_GEMINI_MODEL` (côté serveur seulement, jamais fourni par le client ; caractères alphanumériques, `-`, `.`, `_`).

**Créer une clé gratuite** : ouvrir <https://aistudio.google.com/apikey> avec un compte Google, « Create API key », la copier. Le niveau gratuit a des limites de requêtes par minute et par jour, et selon les conditions du fournisseur, les données envoyées peuvent y être utilisées pour améliorer ses produits : n'envoyez rien de sensible. Ne commitez jamais la clé.

**Tester en local** :

```bash
cd server
pip install -r requirements-dev.txt              # installe google-genai
export GEMINI_API_KEY="<votre clé>"              # dans votre terminal, jamais dans un fichier du dépôt
export BIDBANG_ALLOW_ENV_KEY=1                   # autorise le serveur à lire GEMINI_API_KEY (local seulement)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Dans le jeu : Partie avec IA, fournisseur « Google Gemini (gratuit) », laisser le champ clé vide. Sans variable d'environnement, collez la clé dans le champ (HTTPS ou serveur local). La clé d'environnement n'est utilisée que si `BIDBANG_ALLOW_ENV_KEY=1`, que le fournisseur est `gemini`, que la requête vient de la machine locale (127.0.0.1, localhost, 10.0.2.2) et que le client envoie `use_env_key: true` ; sinon le serveur répond 400. Un serveur public ne dépense donc jamais la clé de son propriétaire. Avec `use_env_key`, le corps de la requête est `{"provider": "gemini", "use_env_key": true}`.

Sans Internet ni clé : `BIDBANG_MOCK_AI=1` active le fournisseur `mock` ; `python -m pytest` n'appelle jamais Gemini (les tests de `tests/test_gemini.py` simulent les réponses HTTP du SDK).

## WebSocket `WS /ws/{code}?token=...`

Fermeture 4401 (jeton invalide) ou 4404 (salon inconnu).

Serveur vers client : `room_state` {room}, `game_state` {game} (état complet à chaque changement et à la reconnexion), `error` {message}, `rematch` (l'hôte relance une partie : les écrans de résultats reviennent au salon d'attente), `kicked` (le joueur vient d'être exclu ; la connexion se ferme avec le code 4403), `pong`.

Client vers serveur : `start_game` (hôte), `rematch` {settings?} (hôte, partie terminée : voir ci-dessous), `bid` {amount}, `fold`, `kick` {target} (hôte, avant le début de la partie : retire le joueur, invalide son jeton et l'empêche de rejoindre ce salon sous le même pseudo), `leave`, `ping`.

`game_state.game` : `creation_type`, `situation` `{title, description, criteria[{id, label, necessary, importance}]}` (toujours présente, aussi en classique), `phase` (`auction` / `finished`), `mode`, `settings`, `location`, `item_index`, `item_total`, `auction` {item (avec `points`), start_price (estimé, indicatif), opening_min, step, current_bid, leader_id, required_bid, folded, seconds_left}, `players` [{id, pseudo, budget, items, purchases[{item, purchase_price, savings}], folded}], `last_result` {item, winner_id, winner, purchase_price, bids?}, `results`, `bargains`, `awards`, `you`.

`results` (trié) : `[{player_id, pseudo, rank, winner, score, budget, items_count, estimated_value, total_spent, savings, purchases[{item, purchase_price, savings}]}]`. `bargains` : classement par économie décroissante `[{rank, player_id, pseudo, savings, items_count}]` (sans achat : en fin de liste). `awards` : `best_bidder` (plus grande économie totale, > 0), `best_deal` (objet acheté avec la plus grande économie, > 0), `most_valuable` (valeur estimée), `most_useful` (points) ; chacun `{player_id, pseudo, value}` ou `null`. Un joueur sans achat n'en reçoit aucune. `bargains` et `awards` sont informatifs et ne modifient jamais `results`.

## Revanche (rejouer sans recréer de salon)

Quand la partie est terminée (`room.status == "finished"`), l'hôte envoie `rematch` avec, facultativement, `settings: {mode, budget, bid_timer, item_count}`. Le serveur valide les changements comme à la création (rien d'autre ne peut changer : lieu, situation, cartes, nombre de joueurs), oublie la partie précédente (scores, résultats, chronomètre), remet le salon en attente (`status: "lobby"`), diffuse `room_state` puis `rematch` à tous. Les joueurs gardent leur identifiant, leur jeton et le code du salon ; l'hôte peut encore exclure quelqu'un, de nouveaux joueurs peuvent entrer s'il reste de la place, puis l'hôte envoie `start_game`. Un tirage neuf est fait pour une partie classique ; en partie personnalisée ou IA, la sélection validée est conservée sans nouvel appel à l'IA (`item_count` ne peut pas dépasser la sélection). Erreurs : pas l'hôte (403), partie non terminée (409), réglage invalide ou non modifiable (400) ; dans ces cas rien n'est réinitialisé. À la reconnexion après une revanche, un joueur reçoit l'état du salon d'attente, jamais l'ancienne partie.

## Règles

**Horloge serveur** : avant de traiter une mise ou un abandon, le moteur compare l'horloge du serveur à l'échéance (`Game._reject_if_late`). Une action reçue après l'échéance est refusée (« Temps écoulé... ») et l'étape est clôturée sur-le-champ, même si le chronomètre asyncio n'a pas encore tiré ; l'état est alors diffusé avant l'erreur.

Voir `app/game.py` (constantes en tête de fichier). Mode `aveugle` : `bid` et `fold` sont secrets (une seule fois par objet) ; `auction.blind`, `auction.submitted` (qui a joué) et `auction.your_bid` (0 = passé) remplacent `current_bid` / `leader_id` ; `last_result.bids` révèle toutes les mises après résolution.

Mise d'ouverture libre (`opening_min` = 10 € minimum), puis surenchère d'au moins `step` (8 % du prix estimé, arrondi à la dizaine, 10 € minimum). Mêmes règles d'enchères et même calcul de victoire (somme des points) pour tous les types de création ; seule l'origine des points change (critères du lieu, critères de l'hôte, ou points attribués par l'IA).
