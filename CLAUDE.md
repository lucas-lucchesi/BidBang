# BidBang : contexte du projet pour Claude Code

Réponds en **français** (code, noms de variables et commits en anglais ou français, comme le code existant : textes affichés en français).

## Le projet

Jeu mobile multijoueur d'enchères (Android d'abord, iOS ensuite). 2 à 4 joueurs (6 plus tard), parties de 10 à 15 minutes. Les joueurs rejoignent un salon privé avec un code de 6 caractères, enchérissent sur des cartes d'objets liées à un lieu, puis un gagnant est désigné.

| Mode | Objectif | Fin de partie |
|---|---|---|
| Construction | Acheter les meilleurs objets pour un lieu | Score + synergies + votes des joueurs |
| Enchère à l'aveugle (`aveugle`) | Comme Construction, mais chaque joueur mise en secret une seule fois par objet | Score + synergies + votes (mêmes règles que Construction) |
| Survie | Acheter le matériel adapté à un scénario | 3 épreuves à seuils, classement |

Principe non négociable : **le serveur fait autorité**. Le téléphone n'affiche que l'état reçu et envoie des intentions (miser, se coucher, voter). Il ne décide jamais qui gagne ni combien d'argent a un joueur.

## Architecture

```
Godot 4.7 (GDScript)  --HTTP + WebSocket-->  FastAPI (Python)
                                              ├─ salons et parties en mémoire
                                              └─ catalogue : server/data/catalog.json
```

Prévu plus tard (pas encore fait) : PostgreSQL, Cloudflare R2 (illustrations), génération IA facultative avec la clé de l'hôte, hébergement en ligne.

## Structure du dépôt

```
project.godot              scène principale : menu.tscn ; autoload : Session
menu.tscn                  menu (pseudo, adresse du serveur, créer / rejoindre)
scenes/                    create_game, join_game, lobby, game
scripts/session.gd         autoload : pseudo, salon courant, dernier game_state, client réseau
scripts/net_client.gd      HTTP (créer/rejoindre) + WebSocketPeer + signaux
scripts/lobby.gd           salon d'attente
scripts/game.gd            écran de partie (enchères, vote, résultats), UI construite en code
scripts/item_card.gd       carte d'objet (papier crème), fonctions statiques
scripts/item_picker.gd     sélecteur d'objets réutilisable (recherche, filtres, ajouter / retirer)
theme/main_theme.tres      thème commun (variations : PrimaryButton, TitleLabel, MutedLabel, ErrorLabel, InfoLabel, FieldLabel, HeadingLabel, BackButton)
server/app/                main.py (routes, WebSocket), rooms.py (salons), game.py (moteur), catalog.py, models.py, errors.py,
                           creation.py (scénario / sélection), items.py (format commun des objets), trials.py (épreuves),
                           ai/ (base.py interface fournisseur, anthropic_provider.py, generator.py, limits.py)
server/data/catalog.json   6 lieux, 72 cartes, épreuves de survie (généré par tools/gen_catalog.py)
server/tests/              192 tests pytest
server/tools/gen_catalog.py  génère data/catalog.json (le prototype web de référence n'est pas dans le dépôt)
```

## Direction artistique (jeu de société moderne, chaleureux)

Style « soirée jeux entre amis » : formes très arrondies, boutons épais en relief (jetons), cartes papier crème posées sur des panneaux bleu pétrole, ombres douces, petits jetons colorés qui flottent en fond. Pas de pixel art, pas de casino, pas de texture photo-réaliste sur l'interface. Police : Fredoka (variable, graisses 400/600/700). Écran 720x1280 (stretch `canvas_items`), fenêtre de bureau 450x800.

| Rôle | Couleur |
|---|---|
| Fond | `#193A49` (dégradé `#21495a` -> `#142f3b`) |
| Panneaux | `#2C5362` (lignes de liste `#37677A`) |
| Bouton principal / accents | `#E8A044` (texte dessus `#3A210B`) |
| Texte clair | `#F3E4C9` (secondaire `#B0C2C2`) |
| Validation | `#72A48A` |
| Danger | `#C4685A` |
| Contour commun | `#10262F` |
| Raretés | `#A9BDC0` `#5FA8D3` `#A98BD8` `#F2C14E` |

- Textures 9-patch (jetons) : `tools/gen_ui_textures.py` écrit `assets/ui_real/`, `tools/gen_theme.py` écrit `theme/main_theme.tres`. Modifier le style = modifier ces deux scripts puis les relancer avec `python3` (Pillow requis, hors du venv du serveur). Ordre : textures, puis thème.
- Deux thèmes : sombre (`theme/main_theme.tres`, textures `assets/ui_real/`, palette ci-dessus) et clair (`theme/light_theme.tres`, textures `assets/ui_light/`, fond sable, panneaux crème, texte `#193A49`). Les deux générateurs produisent les deux sans argument (ou `dark` / `light`). Réglage `Session.theme_mode` (sauvegardé, Paramètres > Apparence), appliqué par `Session.apply_settings()` sur la fenêtre ; l'écran est rechargé à la fermeture des paramètres. Le fond (`background.gd`) et quelques couleurs en code utilisent `Session.is_light()`.
- Variations de thème : PrimaryButton (orange), SuccessButton (vert), DangerButton, SmallButton, ChoiceButton (pastilles), BackButton (lien texte) ; panneaux HeroPanel (liseré orange), RowPanel (ligne de liste), ChipPanel, MoneyChip ; labels TitleLabel, HeadingLabel, SectionLabel, FieldLabel, MutedLabel, InfoLabel, ErrorLabel, MoneyLabel, BigMoneyLabel.
- Composants réutilisables : `scripts/ui.gd` (page avec marges de sécurité, `section`, `row`, `avatar`, `modal`, `choice_row`, `collapsible`), `avatar.gd` (pastille de joueur), `ring_timer.gd` (chrono circulaire), `logo.gd` (logo dessiné en code), `item_card.gd` (carte papier crème, pastilles de rareté/prix/stats), `podium.gd`, `fx.gd` (animations Tween), `confetti.gd`.
- Marges de sécurité : `UI.safe_insets()` lit `DisplayServer.get_display_safe_area()` (0 sur ordinateur). À vérifier sur un vrai téléphone ou un émulateur à encoche.
- Images réelles à venir (déposer simplement les fichiers, le code les détecte) : `assets/backgrounds/main.png` et `assets/backgrounds/<id du lieu>.png` (fond), `assets/items/<id de la carte>.png` (illustration). Sans image : fond et médaillons dessinés en code. Voir les `README.txt` de ces dossiers.
- `assets/legacy_pixel/` : ancienne version pixel art, conservée au cas où. Cinzel et Lato restent dans `assets/fonts/` mais ne sont plus utilisées.

## Lancer et tester

```bash
cd server
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest                                              # tests
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload   # serveur (--reload : relance seul quand le code change)
```

Utilise `python -m uvicorn` (et non `uvicorn` seul : il peut pointer vers l'installation du système).

Jeu : ouvrir le dossier dans Godot 4.7, F5. Pour jouer seul : Déboguer → Personnaliser les instances d'exécution, 2 à 3 instances avec des pseudos différents. Adresse du serveur par défaut : `http://127.0.0.1:8000` (émulateur Android : `http://10.0.2.2:8000`).

## Types de création de partie (indépendants du mode de jeu)

```
CRÉATION DE PARTIE
  ├── Classique       : catalogue prédéfini (un lieu)
  ├── Personnalisée   : objets sélectionnés par l'hôte
  └── IA              : objets générés puis validés
            │
            ▼
   MOTEUR D'ENCHÈRES (game.py, identique pour les 3)
            │
   Construction / Survie / Aveugle
```

`creation_type` : `classic` (lieu du catalogue, défaut si absent), `custom` (situation écrite + sélection libre d'objets de tous les lieux), `ai` (situation + objets générés par une IA externe avec la clé de l'hôte, puis validation). Écran `create_game.gd` : assistant en étapes (type, réglages / situation, sélection, clé API pour `ai`), les choix sont gardés dans `_state`. Pour `ai`, le salon est créé avant la génération ; la clé passe par `POST /rooms/{code}/ai/generate` (HTTPS, jamais stockée ni journalisée) et la sélection est validée par `PUT /rooms/{code}/selection`. Règles de sécurité, limites et validation des réponses IA : `server/README.md`. Le texte de la situation n'est jamais une règle ; en Survie les épreuves viennent de séries prédéfinies (`trials.py`) ou de l'IA validée.

## Protocole (détail dans server/README.md)

- `GET /items` (catalogue au format commun), `PUT /rooms/{code}/selection`, `POST /rooms/{code}/ai/generate` : voir server/README.md.
- `POST /rooms` {pseudo, settings} et `POST /rooms/{code}/join` {pseudo} répondent `{code, player_id, token, room}`.
- `WS /ws/{code}?token=...` : le serveur envoie `room_state` (salon) et `game_state` (partie, état complet à chaque changement, y compris à la reconnexion), `error`, `pong`.
- Le client envoie `start_game`, `bid` {amount}, `fold`, `vote` {target}, `kick` {target} (hôte, salon d'attente), `leave`, `ping`. Le serveur compare son horloge à l'échéance avant de traiter une mise, un abandon ou un vote.
- Réglages d'une partie : `mode`, `theme_id`, `budget` (1200/2200/3500), `item_count` (6/8/10), `bid_timer` (10/15/20/30 s).

## Règles de jeu implémentées (source : server/app/game.py)

- Enchères **en temps réel**. Mise d'ouverture **libre** (minimum 10 €, le prix de l'objet n'est qu'indicatif) ; ensuite pas minimal = 8 % du prix arrondi à la dizaine (10 € minimum). Le chrono repart à chaque mise ; à zéro, le meneur remporte l'objet, sinon il reste invendu.
- **Se coucher** est définitif pour l'objet ; le meneur ne peut pas se coucher. La manche s'arrête tout de suite si personne d'autre ne peut ou ne veut surenchérir. Qui ne peut pas payer la mise minimale (10 €) est couché d'office.
- Points d'une carte : somme des stats (+ bonus de rareté 0/2/4/7 en Construction). Synergies : 3 points par tag partagé au-delà du premier.
- Enchère à l'aveugle : une mise secrète (ou « passe ») par joueur et par objet, le chrono ne repart pas ; dès que tous ont joué (ou à zéro) la plus haute mise gagne et paie sa propre mise (égalité : le premier à avoir joué). Les mises sont révélées après coup dans `last_result.bids`.
- Construction : + 8 points par vote reçu (vote impossible pour soi, uniquement à 3 joueurs ou plus, 45 s max). Survie : 18 points par épreuve réussie, sinon 9 × stat / seuil (arrondi).
- Égalité : le plus gros budget restant passe devant ; sinon co-vainqueurs.

## Conventions et pièges déjà rencontrés

- **GDScript** : annoter explicitement les types quand la valeur vient d'un `Dictionary` ou d'un `Array` (`var x: int = d["a"]`, pas `:=`). Éviter les paramètres nommés `size`, `name`, `text` dans les scripts de `Control`. Pas de `class_name` pour les helpers : utiliser `const X = preload(...)`.
- Les scènes `.tscn` sont écrites à la main : chaque nœud a un `unique_id` unique ; les nœuds référencés avec `%Nom` ont `unique_name_in_owner = true`.
- **Autoload** : `Session` est déclaré dans `project.godot`. Quand Godot est ouvert pendant qu'un fichier est modifié depuis l'extérieur, il peut réécrire d'anciennes versions (déjà arrivé pour `project.godot` et des scènes). Fermer ou recharger le projet avant de modifier hors de l'éditeur.
- Pas d'emoji dans les textes d'interface (rendu non garanti sur Android). Les icônes d'objets du catalogue sont des emoji de données, non affichés pour l'instant (cartes en texte seul).
- Serveur : toute règle vit dans `game.py` et se teste dans `tests/test_game.py`. Chronomètres : un compteur de version écarte les chronomètres périmés.
- Les messages d'erreur renvoyés au joueur sont en français.

## État actuel

Fait : menu, créer / rejoindre un salon privé, salon d'attente temps réel, catalogue, enchères temps réel, votes, scores, classement, 3 types de création (classique, personnalisée, IA) côté serveur (192 tests) et Godot (non exécuté dans le moteur).

Non vérifié : **la partie Godot n'a jamais été exécutée dans le moteur** (écrite sans accès à Godot). Dernier problème signalé : l'écran de partie « charge en boucle » après « Lancer la partie », avec une erreur autour d'une fonction d'aide de `scripts/item_card.gd`. Les fonctions ont été renommées (`make_label`, `format_money`) et le salon affiche un message si la scène ne s'ouvre pas, mais la cause exacte reste à confirmer avec le message d'erreur de la sortie Godot. **Première tâche : lancer le jeu, lire les erreurs, corriger.**

## Points ouverts et idées

- Équilibrage : la stat Santé (Survie) n'est testée par aucune épreuve ; dépenser tout son budget est presque gratuit ; les 3 épreuves de survie sont toujours les mêmes par lieu.
- Illustrations des cartes (aujourd'hui texte seul) ; police emoji si on veut les afficher sur Android.
- Reconnexion complète après redémarrage de l'application (aujourd'hui la session est perdue).
- Hébergement du serveur en ligne (HTTPS/WSS requis pour un export Android sans trafic en clair), puis PostgreSQL.
- Export Android (puis iOS : nécessite un Mac).
- Génération de thèmes et d'objets par IA avec la clé de l'hôte (facultatif, jamais stockée).
- Éventuellement : placement visuel des objets dans le lieu (non prévu pour le MVP).

## Façon de travailler

- Avant de changer une règle de jeu, la modifier d'abord dans `server/app/game.py` avec un test, puis adapter l'écran.
- Garder `server/README.md` à jour quand le protocole ou les règles changent.
- Lancer `python -m pytest` dans `server/` avant de conclure une modification du serveur.
- Pour tout changement Godot, indiquer ce qu'il faut tester à la main (le moteur n'est pas lancé automatiquement).
