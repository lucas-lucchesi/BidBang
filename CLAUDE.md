# BidBang : contexte du projet pour Claude Code

Réponds en **français** (code, noms de variables et commits en anglais ou français, comme le code existant : textes affichés en français).

## Le projet

Jeu mobile multijoueur d'enchères (Android d'abord, iOS ensuite). 2 à 4 joueurs (6 plus tard), parties de 10 à 15 minutes. Les joueurs rejoignent un salon privé avec un code de 6 caractères, définissent une **situation** (critères de besoins), enchérissent sur des objets dont l'utilité dépend de cette situation, puis un gagnant est désigné.

**Victoire : score = somme des points des objets remportés.** Les points de chaque objet sont calculés par le serveur AVANT les enchères pour la situation de la partie (`scoring.py`), puis figés. Ni rareté, ni synergies, ni votes, ni épreuves.

| Mode d'enchères (`mode`) | Principe |
|---|---|
| `normal` | Enchères publiques en temps réel |
| `aveugle` | Chaque joueur mise en secret une seule fois par objet |

Construction, survie, mariage, villa… ne sont plus des modes : ce sont des **situations** (critères + objets). Anciens modes `construction` et `survie` : acceptés et migrés en `normal` (`game.normalize_mode`).

Principe non négociable : **le serveur fait autorité**. Le téléphone n'affiche que l'état reçu et envoie des intentions (miser, se coucher). Il ne décide jamais qui gagne ni combien d'argent a un joueur.

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
scripts/game.gd            écran de partie (enchères, résultats), UI construite en code
scripts/item_card.gd       carte d'objet (papier crème : points, prix estimé, prix payé, économie, critères utiles), fonctions statiques
scripts/results_view.gd    écran de résultats (podium, détail par joueur, bonnes affaires, distinctions)
scripts/item_picker.gd     sélecteur d'objets réutilisable (recherche, filtres, ajouter / retirer)
theme/main_theme.tres      thème commun (variations : PrimaryButton, TitleLabel, MutedLabel, ErrorLabel, InfoLabel, FieldLabel, HeadingLabel, BackButton)
server/app/                main.py (routes, WebSocket), rooms.py (salons), game.py (moteur, résultats), catalog.py, models.py, errors.py,
                           criteria.py (registre et validation des critères), scoring.py (formule des points, module pur),
                           creation.py (situation / sélection), items.py (format commun des objets),
                           ai/ (profile.py profil de génération, debug.py logs `BIDBANG_AI_DEBUG=1`, base.py interface fournisseur, anthropic/openai, gemini (SDK google-genai, sorties structurées, modèle `gemini-3.5-flash-lite`), mock_provider.py (BIDBANG_MOCK_AI=1), generator.py, limits.py)
server/data/catalog.json   7 lieux (critères de situation inclus), 84 objets au format commun (généré par tools/gen_catalog.py)
server/data/criteria.json  registre des critères (id, libellé) et modèles de critères (zombie, mariage, villa...)
server/tests/              283 tests pytest
server/tools/gen_catalog.py  génère data/catalog.json (attributs et points de base écrits à la main par objet)
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
- Composants réutilisables : `scripts/ui.gd` (page avec marges de sécurité, `section`, `row`, `avatar`, `modal`, `choice_row`, `collapsible`), `avatar.gd` (pastille de joueur), `ring_timer.gd` (chrono circulaire), `logo.gd` (logo dessiné en code), `item_card.gd` (carte papier crème, pastilles de points, rareté, prix estimé, prix payé, économie), `podium.gd`, `fx.gd` (animations Tween), `confetti.gd`.
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
   Enchères normales / Aveugle (la situation et ses critères changent, pas les règles)
```

`creation_type` : `classic` (lieu du catalogue avec ses critères prédéfinis, défaut si absent), `custom` (situation écrite + critères choisis + sélection libre d'objets de tous les lieux, aperçu des points via `POST /scoring/preview`), `ai` (une phrase -> cartes libres générées par une IA externe avec la clé de l'hôte : objets, joueurs, métiers, personnalités, personnages... ; l'IA déduit d'abord un **profil** de la situation (objectif, types de cartes admis, personnes réelles ou non, rôles à couvrir ; `server/app/ai/profile.py`), que le serveur valide et applique à chaque carte, puis attribue elle-même les points, sans critères ; jamais de carte du catalogue ni de remplissage : au plus une correction, sinon erreur claire ; l'hôte choisit les cartes à garder). Classique et personnalisée utilisent la même formule de points (critères) ; en partie IA, les points viennent de l'IA (validés 1-100, figés au lancement). Écran `create_game.gd` : assistant en étapes (type, réglages / situation, critères (personnalisée), sélection, aperçu des points, clé API pour `ai`), les choix sont gardés dans `_state`. Pour `ai`, le salon est créé avant la génération ; la clé passe par `POST /rooms/{code}/ai/generate` (HTTPS, jamais stockée ni journalisée) et la sélection est validée par `PUT /rooms/{code}/selection`. Règles de sécurité, limites et validation des réponses IA : `server/README.md`. Le texte de la situation n'est jamais une règle. L'IA ne désigne jamais le gagnant : le serveur calcule le classement.

## Protocole (détail dans server/README.md)

- `GET /items` (catalogue, critères, modèles), `POST /scoring/preview`, `PUT /rooms/{code}/selection`, `POST /rooms/{code}/ai/generate` : voir server/README.md.
- `POST /rooms` {pseudo, settings} et `POST /rooms/{code}/join` {pseudo} répondent `{code, player_id, token, room}`.
- `WS /ws/{code}?token=...` : le serveur envoie `room_state` (salon) et `game_state` (partie, état complet à chaque changement, y compris à la reconnexion), `error`, `pong`.
- Le client envoie `start_game`, `bid` {amount}, `fold`, `kick` {target} (hôte, salon d'attente), `rematch` {settings?} (hôte, partie terminée : même salon, mêmes joueurs, mode / budget / chrono / nombre de cartes modifiables ; le serveur répond par `room_state` puis `rematch`), `leave`, `ping`. (`vote` n'existe plus.) Le serveur compare son horloge à l'échéance avant de traiter une mise ou un abandon.
- Réglages d'une partie : `mode` (`normal` / `aveugle`), `theme_id`, `budget` (1200/2200/3500), `item_count` (6 à 20, 12 au plus en classique), `bid_timer` (10/15/20/30 s).

## Règles de jeu implémentées (source : server/app/game.py)

- Enchères **en temps réel**. Mise d'ouverture **libre** (minimum 10 €, le prix de l'objet n'est qu'indicatif) ; ensuite pas minimal = 8 % du prix arrondi à la dizaine (10 € minimum). Le chrono repart à chaque mise ; à zéro, le meneur remporte l'objet, sinon il reste invendu.
- **Se coucher** est définitif pour l'objet ; le meneur ne peut pas se coucher. La manche s'arrête tout de suite si personne d'autre ne peut ou ne veut surenchérir. Qui ne peut pas payer la mise minimale (10 €) est couché d'office.
- **Points d'un objet** (`scoring.py`, figés au lancement) : pour chaque critère nécessaire de la situation que l'objet possède, `(valeur/5) * (importance/5)` ; on garde les 3 meilleures (poids 1 / 0,35 / 0,12), normalisées en pertinence ; `points = 1 + 89 * pertinence^1,15 + 10 * base_points/50`, borné à 1-100. Le prix et la rareté n'y entrent pas ; la pertinence prime sur le nombre de caractéristiques. Détail et exemples : `server/README.md`.
- Un objet a deux prix distincts : `price` (estimé, jamais remplacé) et, dans l'achat `{item, purchase_price}`, le prix payé. Économie = `price - purchase_price` (négatif : surcoût).
- Score final = somme des `points` des objets remportés. Résultats par joueur : score, valeur estimée, argent dépensé, économie, budget restant. `bargains` (classement par économie) et `awards` (distinctions) sont informatifs et ne changent jamais le gagnant ; sans achat, aucune distinction.
- Enchère à l'aveugle : une mise secrète (ou « passe ») par joueur et par objet, le chrono ne repart pas ; dès que tous ont joué (ou à zéro) la plus haute mise gagne et paie sa propre mise (égalité : le premier à avoir joué). Les mises sont révélées après coup dans `last_result.bids`.
- Égalité de score : le plus gros budget restant passe devant ; sinon co-vainqueurs.

## Conventions et pièges déjà rencontrés

- **GDScript** : annoter explicitement les types quand la valeur vient d'un `Dictionary` ou d'un `Array` (`var x: int = d["a"]`, pas `:=`). Éviter les paramètres nommés `size`, `name`, `text` dans les scripts de `Control`. Pas de `class_name` pour les helpers : utiliser `const X = preload(...)`.
- Les scènes `.tscn` sont écrites à la main : chaque nœud a un `unique_id` unique ; les nœuds référencés avec `%Nom` ont `unique_name_in_owner = true`.
- **Autoload** : `Session` est déclaré dans `project.godot`. Quand Godot est ouvert pendant qu'un fichier est modifié depuis l'extérieur, il peut réécrire d'anciennes versions (déjà arrivé pour `project.godot` et des scènes). Fermer ou recharger le projet avant de modifier hors de l'éditeur.
- Pas d'emoji dans les textes d'interface (rendu non garanti sur Android). Les icônes d'objets du catalogue sont des emoji de données, non affichés pour l'instant (cartes en texte seul).
- Serveur : toute règle vit dans `game.py` (formule des points dans `scoring.py`) et se teste dans `tests/` (`test_game.py`, `test_scoring.py`, `test_results.py`...). Chronomètres : un compteur de version écarte les chronomètres périmés.
- Les messages d'erreur renvoyés au joueur sont en français.

## État actuel

Fait : menu, créer / rejoindre un salon privé, salon d'attente temps réel, catalogue (7 lieux, 84 objets avec caractéristiques), situations à critères, calcul des points figés au lancement, enchères temps réel et à l'aveugle, classement par points, écran de résultats (podium, détail, économies, bonnes affaires), 3 types de création (classique, personnalisée, IA) côté serveur (228 tests) et Godot (non exécuté dans le moteur).

Refonte « victoire simplifiée » : serveur testé (`python -m pytest`). Côté Godot, écrit sans accès au moteur, **à tester à la main** : cartes d'objets (points, estimé, payé, économie), écran de résultats (`results_view.gd`, podium avec budget et 4e joueur), création personnalisée (étape critères : pastilles Non / 1 à 5, modèles, ajout et retrait), aperçu des points, parcours IA (nombre de cartes 6-20 avec - et +, objectif compris, cartes générées avec points de l'IA, sélection, aperçu), étape critères de la partie personnalisée avec le même sélecteur du nombre de cartes, salon, inventaire, revanche (boutons « Rejouer » et « Changer de mode ou de réglages » sur l'écran de résultats pour l'hôte ; retour automatique des autres joueurs au salon d'attente).

Non vérifié : **la partie Godot n'a jamais été exécutée dans le moteur** (écrite sans accès à Godot). Dernier problème signalé avant la refonte : l'écran de partie « charge en boucle » après « Lancer la partie », avec une erreur autour d'une fonction d'aide de `scripts/item_card.gd` (`make_label`, `format_money` renommées ; cause à confirmer avec le message d'erreur de la sortie Godot). **Première tâche : lancer le jeu, lire les erreurs, corriger.**

## Points ouverts et idées

- Équilibrage : dépenser tout son budget est presque gratuit (seuls les points et le budget restant en cas d'égalité comptent) ; les constantes de la formule (`ScoringConfig`) sont à régler après des parties réelles ; les illustrations d'objets (`image`) sont encore à venir.
- Illustrations des cartes (aujourd'hui texte seul) ; police emoji si on veut les afficher sur Android.
- Reconnexion complète après redémarrage de l'application (aujourd'hui la session est perdue).
- Hébergement du serveur en ligne (HTTPS/WSS requis pour un export Android sans trafic en clair), puis PostgreSQL.
- Export Android (puis iOS : nécessite un Mac).
- Génération de thèmes et d'objets par IA avec la clé de l'hôte (facultatif, jamais stockée).
- Éventuellement : placement visuel des objets dans le lieu (non prévu pour le MVP).

## Façon de travailler

- Avant de changer une règle de jeu, la modifier d'abord dans `server/app/game.py` (ou `scoring.py` pour les points) avec un test, puis adapter l'écran.
- Garder `server/README.md` à jour quand le protocole ou les règles changent.
- Lancer `python -m pytest` dans `server/` avant de conclure une modification du serveur.
- Pour tout changement Godot, indiquer ce qu'il faut tester à la main (le moteur n'est pas lancé automatiquement).
