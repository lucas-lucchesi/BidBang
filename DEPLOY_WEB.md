# Déployer BidBang sur le Web (Vercel + Railway)

```text
Navigateur (PC, Android, iPhone)
        |
        v
Vercel : client Godot Web (fichiers statiques de web_build/)
        |  HTTPS + WSS
        v
Railway : serveur FastAPI (bid-bang/server), salons et parties en mémoire
```

Le même projet Godot (`bid-bang/`) sert aux trois cibles : navigateur, Android, iOS. Seul le Web a un profil d'export dédié (`bid-bang/export_presets.cfg`).

## 0. Pourquoi vous voyiez `{"detail":"Not Found"}`

Cette réponse est celle de FastAPI (le serveur Python) quand on demande `/` : il n'a pas de page d'accueil. Votre déploiement Vercel exécutait donc le serveur Python, pas le jeu. Causes probables, à vérifier dans Vercel (Settings > General) : *Framework Preset* sur « FastAPI » ou « Python », ou *Root Directory* sur `bid-bang/server`. Le dépôt ne contenait de toute façon ni `vercel.json`, ni dossier `web_build` : même avec les bons réglages, Vercel n'aurait eu aucun client à servir. Un build « réussi » ne prouve pas que le jeu est déployé : cela prouve seulement que la commande de build n'a pas échoué.

Correction : `web_build/` et `vercel.json` existent maintenant à la racine du dépôt, et le projet Vercel doit utiliser les réglages de la section 5.

Le serveur répond désormais `{"service":"BidBang API","status":"ok"}` sur `/` : si vous l'ouvrez dans un navigateur, c'est l'API, pas le jeu.

## 1. Installer les modèles d'export Godot

Godot exporte vers le Web à partir de « modèles d'export » de la même version que l'éditeur (ici 4.7.2).

**Option légère (recommandée, environ 22 Mo)** : seuls les modèles Web sans threads.

```bash
python3 bid-bang/tools/install_web_templates.py
```

Ils sont installés dans `~/.local/share/godot/export_templates/4.7.2.stable/`. Cette option est déjà faite sur votre machine.

**Option complète (1,3 Go, nécessaire pour Android et iOS)** : dans l'éditeur Godot, *Éditeur > Gérer les modèles d'exportation > Télécharger et installer*. Ou téléchargez `Godot_v4.7.2-stable_export_templates.tpz` depuis <https://godotengine.org/download/archive/4.7.2-stable/> puis *Installer depuis un fichier*.

## 2. Générer l'export Web

```bash
bid-bang/tools/export_web.sh
```

Le script trouve Godot (variable `GODOT=/chemin/vers/Godot` pour le forcer ; il cherche aussi `~/Desktop/Godot_v4.7.2-stable_linux.x86_64.exe`), importe les ressources, exporte dans `web_build/` avec le profil « Web », puis lance `bid-bang/tools/check_web_build.py`. Ce contrôle vérifie la présence de `index.html`, `index.js`, `index.wasm`, `index.pck`, affiche les tailles, signale les fichiers qui dépasseraient les limites de GitHub (100 Mo, avertissement dès 50 Mo), et refuse l'export s'il y trouve le dossier serveur, des tests, un `.env` ou un motif de clé API.

Profil d'export (`bid-bang/export_presets.cfg`) :

- renderer Compatibility (`gl_compatibility`, déjà celui du projet), sans threads : pas besoin d'en-têtes spéciaux, fonctionne sur Safari iOS ;
- exclus de l'export : `server/`, `tools/`, `sprite/`, `assets/legacy_pixel/`, les polices inutilisées (Cinzel, Lato), `*.py`, `*.sh`, `*.md`, `.env` ; le dossier `bid-bang/server/` contient aussi un fichier `.gdignore`, donc Godot ne l'importe ni ne l'exporte jamais ;
- clavier virtuel expérimental activé (champs de saisie sur téléphone).

Taille actuelle : `index.wasm` 39,5 Mo (environ 10 Mo compressé par Vercel), `index.pck` 2,5 Mo.

## 3. Tester en local (jamais avec `file://`)

Un export Web ne fonctionne pas ouvert directement depuis le disque : il faut un serveur HTTP.

```bash
# terminal 1 : serveur de jeu (le fournisseur IA simulé permet de tester la partie IA sans clé)
cd bid-bang/server && source .venv/bin/activate
BIDBANG_MOCK_AI=1 python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# terminal 2 : client Web
python3 -m http.server 8080 --bind 127.0.0.1 --directory web_build
```

Ouvrez <http://localhost:8080> dans deux fenêtres (ou deux navigateurs) avec deux pseudos. Servie depuis `localhost`, la page utilise automatiquement `http://127.0.0.1:8000` ; vous pouvez en viser un autre avec `http://localhost:8080/?server=http://127.0.0.1:9000`. Ce paramètre n'est accepté que sur une page servie depuis `localhost`.

Le développement natif ne change pas : lancez FastAPI en local, puis le jeu dans l'éditeur Godot (F5) comme avant.

## 4. Envoyer sur GitHub

```bash
git status                       # vérifiez : pas de .env, pas de clé
git add -A
git commit -m "Mise à jour du client Web"
git push -u origin <votre-branche>   # puis ouvrez une pull request vers main
```

`web_build/` est versionné pour que Vercel le serve sans avoir besoin de Godot. Le fichier `index.wasm` (39,5 Mo) est sous l'avertissement de GitHub (50 Mo) et sous sa limite (100 Mo) ; il ne change qu'avec la version de Godot, donc il ne gonfle pas le dépôt à chaque export. `index.pck` (2,5 Mo) change à chaque export. Si le dépôt grossit trop plus tard, passez à Git LFS ou à un export fait par GitHub Actions.

## 4 bis. Variante sans Railway : le serveur sur votre ordinateur, le client sur Vercel

Votre ordinateur fait tourner le serveur Python ; un tunnel HTTPS gratuit le rend joignable par vos amis ; le client reste sur Vercel. **Votre ordinateur doit rester allumé** pendant les parties, avec le script lancé ; l'arrêter supprime les parties en cours.

1. **Installer `cloudflared`** (une fois ; Linux x86-64, sans compte) :
   ```bash
   mkdir -p ~/.local/bin && curl -L -o ~/.local/bin/cloudflared \
     https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
     && chmod +x ~/.local/bin/cloudflared && cloudflared --version
   ```
2. **Lancer** (remplacez par le domaine de votre projet Vercel, sans `/` final) :
   ```bash
   python3 bid-bang/tools/serve_public.py --origin https://VOTRE-PROJET.vercel.app --push
   ```
   Le script démarre le serveur en mode production (CORS et WebSocket limités à votre site Vercel), ouvre le tunnel, vérifie que `https://xxxx.trycloudflare.com/health` répond, écrit l'adresse dans `web_build/config.json`, puis (avec `--push`) commite **seulement ce fichier** et le pousse : Vercel redéploie le client en environ une minute. Sans `--push`, le script affiche les trois commandes git à lancer vous-même. Vous pouvez aussi définir `BIDBANG_WEB_ORIGIN` au lieu de `--origin`.
3. **Jouer** : ouvrez `https://VOTRE-PROJET.vercel.app` et envoyez ce lien à vos amis. Arrêtez avec Ctrl+C (serveur et tunnel s'arrêtent ensemble).

Limites : l'adresse d'un tunnel rapide **change à chaque lancement**, donc relancez le script (et laissez-le pousser `config.json`) à chaque session ; attendez la fin du redéploiement Vercel avant d'inviter. Les tunnels rapides sont prévus pour des essais : pas de garantie de disponibilité. Pour une adresse fixe (tunnel nommé Cloudflare, ngrok avec un domaine fixe...), lancez votre tunnel vous-même puis `serve_public.py --origin ... --public-url https://votre-adresse-fixe --push` : le script ne lance alors pas de tunnel. Les parties du serveur local restent en mémoire, comme sur Railway.

## 5. Railway : le serveur de jeu

1. Sur <https://railway.com>, *New Project > Deploy from GitHub repo* > `BidBang`. Railway est un service payant à l'usage, avec un essai limité : vérifiez leur tarification actuelle avant de créer le projet. Rien n'a été créé ni déployé sur votre compte.
2. Dans le service : **Settings > Source > Root Directory : `bid-bang/server`**.
3. Le fichier `bid-bang/server/railway.json` fournit la commande de démarrage et le contrôle de santé (rien à saisir à la main) :
   - Start Command : `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1 --proxy-headers --forwarded-allow-ips='*'`
   - Healthcheck Path : `/health`
   - Replicas : 1 (obligatoire : les salons sont en mémoire d'un seul processus)
   - `--proxy-headers` : Railway est un proxy ; sans cela le serveur verrait toutes les connexions comme venant de la même adresse (les limites anti-abus s'appliqueraient à tout le monde à la fois) et croirait recevoir du HTTP en clair (la clé API de l'hôte serait refusée).
4. **Variables** (onglet *Variables*) :

   | Variable | Valeur | Rôle |
   |---|---|---|
   | `BIDBANG_ENV` | `production` | désactive la doc d'API, le fournisseur simulé, la clé lue dans l'environnement ; origines locales refusées |
   | `ALLOWED_ORIGINS` | `https://VOTRE-PROJET.vercel.app` | origine du client Web autorisée (CORS et WebSocket) ; plusieurs valeurs séparées par des virgules ; jamais de `*` |
   | `MAX_ROOMS` | `100` (facultatif, défaut 200) | plafond de salons en mémoire |
   | `ALLOWED_ORIGIN_REGEX` | facultatif | pour des domaines variables, ex. aperçus Vercel : `https://bidbang-[a-z0-9-]+-VOTRE-COMPTE\.vercel\.app` |

   `PORT` est fourni par Railway. Ne mettez **aucune clé IA** ici : chaque hôte saisit la sienne dans le jeu (elle transite en HTTPS et n'est jamais conservée). Les variables facultatives `BIDBANG_GEMINI_MODEL` et `BIDBANG_OPENAI_MODEL` changent seulement les modèles.
5. **Settings > Networking > Generate Domain** : Railway donne une adresse `https://xxxx.up.railway.app`. Notez-la.
6. Vérifiez : `https://xxxx.up.railway.app/health` doit répondre `{"status":"ok"}`.

Les salons et parties sont **en mémoire** : un redémarrage ou un redéploiement du serveur supprime toutes les parties en cours (les joueurs sont renvoyés au menu). C'est acceptable pour une bêta ; PostgreSQL ou Redis ne sont pas ajoutés.

## 6. Donner l'adresse du serveur au client

Le client Web lit l'adresse dans `web_build/config.json` (servi à côté de `index.html`, **jamais** intégré au jeu) :

```bash
BIDBANG_SERVER_URL=https://xxxx.up.railway.app bid-bang/tools/export_web.sh
```

Ou, sans réexporter, éditez `web_build/config.json` :

```json
{ "server_url": "https://xxxx.up.railway.app" }
```

Seul HTTPS est accepté (le WebSocket utilise alors WSS automatiquement ; la validation TLS n'est jamais désactivée). Puis `git add web_build && git commit && git push` : Vercel redéploie. Sur la version publique, le champ « adresse du serveur » des Paramètres est masqué, l'adresse ne peut pas être changée par l'URL de la page ni par une valeur enregistrée dans le navigateur, et `127.0.0.1` n'est jamais contacté.

## 7. Vercel : le client Web

Dans Vercel, importez le dépôt GitHub (ou corrigez le projet existant, sans le supprimer) et réglez **Settings > General** :

| Paramètre | Valeur |
|---|---|
| Framework Preset | **Other** |
| Root Directory | *(vide)* : la racine du dépôt, **pas** `bid-bang/server` |
| Build Command | *(vide)* |
| Output Directory | `web_build` |
| Install Command | *(vide)* |
| Environment Variables | aucune |

`vercel.json` à la racine impose déjà : pas de framework, pas de build, sortie `web_build`, fichiers `.wasm` servis en `application/wasm`, pas de cache périmé (`max-age=0, must-revalidate`), `config.json` jamais mis en cache. Aucune fonction Python n'est configurée. Ne cochez pas « Include source files outside of the Root Directory ». Après avoir corrigé les réglages : *Deployments > ⋯ > Redeploy* (décochez « Use existing Build Cache »).

Ensuite, reportez le domaine Vercel obtenu (`https://VOTRE-PROJET.vercel.app`) dans la variable `ALLOWED_ORIGINS` de Railway, et redéployez Railway si besoin.

## 8. Redéployer après une modification du jeu

1. Modifiez le jeu dans Godot (ou les scripts).
2. `bid-bang/tools/export_web.sh` (ajoutez `BIDBANG_SERVER_URL=...` si `config.json` n'a pas encore l'adresse).
3. Testez en local (section 3).
4. `git add -A && git commit && git push` : Vercel redéploie le client automatiquement à chaque push sur la branche de production ; Railway redéploie le serveur si `bid-bang/server/` a changé.

Modifier uniquement le serveur ne demande aucun nouvel export. Redéployer le serveur supprime les parties en cours.

## 9. Diagnostiquer

**404 / `{"detail":"Not Found"}` sur l'URL Vercel** : Vercel exécute le serveur Python. Revoyez la section 5 (preset *Other*, Root Directory vide, Output Directory `web_build`). Vérifiez que `https://VOTRE-PROJET.vercel.app/index.wasm` se télécharge (et non du JSON), et que `web_build/` est bien dans le dépôt GitHub.

**Écran noir ou page blanche** : ouvrez les outils du navigateur (F12) > Console. Cherchez une erreur sur `index.wasm` ou `index.pck` (404 : `web_build` incomplet ; type MIME : vérifiez `vercel.json`). Sur un vieux téléphone, WebGL 2 est nécessaire.

**« Le serveur de jeu n'est pas configuré (config.json) »** : `web_build/config.json` n'a pas de `server_url` HTTPS, ou n'est pas déployé. Ouvrez `https://VOTRE-PROJET.vercel.app/config.json`.

**« Impossible de contacter le serveur » / erreur CORS dans la console** (« blocked by CORS policy ») : `ALLOWED_ORIGINS` de Railway ne contient pas exactement l'origine de la page (schéma `https://`, pas de `/` final, domaine exact ; le `www` et le domaine personnalisé sont des origines différentes). Testez : `curl -i -X OPTIONS https://xxxx.up.railway.app/rooms -H "Origin: https://VOTRE-PROJET.vercel.app" -H "Access-Control-Request-Method: POST"` doit répondre `204` avec `access-control-allow-origin`. Après avoir changé une variable Railway, attendez le redéploiement.

**Le salon se crée mais la partie ne démarre pas / « Connexion perdue »** (WebSocket) : dans F12 > Réseau > WS, regardez la connexion `wss://…/ws/CODE`. Un échec immédiat signifie en général une origine refusée (même cause que CORS) ; `ws://` au lieu de `wss://` signifie que `config.json` n'est pas en `https://`. Le jeton est vérifié à l'ouverture : un salon supprimé par un redémarrage du serveur fait aussi échouer la reconnexion.

**429 « Trop de tentatives / de salons créés »** : limites par adresse (10 salons créés par minute, 10 échecs par minute). Derrière Railway, vérifiez la présence de `--proxy-headers` dans la commande de démarrage.

**503 « Le serveur est plein »** : `MAX_ROOMS` atteint ; attendez (les salons inutilisés sont supprimés après 5 minutes) ou augmentez la valeur.

**La génération IA échoue** : 429 du fournisseur = quota dépassé (message explicite, aucune bascule vers un autre fournisseur) ; 503 = fournisseur surchargé, réessayez ; « HTTPS » = le serveur n'a pas reçu la requête en HTTPS (voir `--proxy-headers`).

## 10. Sécurité de la bêta publique

En place : CORS limité aux origines configurées (pas de cookies, jetons dans l'en-tête `Authorization`) ; origine vérifiée à l'ouverture des WebSockets (les navigateurs d'autres sites sont refusés ; les applications natives, sans en-tête `Origin`, restent acceptées, toujours avec jeton) ; plafond de salons, de créations par minute et d'essais de codes ; salons jamais ouverts supprimés après 5 minutes ; messages WebSocket limités à 8 Ko ; documentation de l'API désactivée ; fournisseur simulé et clé d'environnement désactivés en production ; clés API des hôtes uniquement en HTTPS, jamais stockées, jamais journalisées ; aucune clé dans le client Web (contrôlé à chaque export).

À savoir : il n'y a pas de comptes ; quiconque connaît un code de salon peut le rejoindre tant qu'il reste de la place ; les limites sont en mémoire, par processus ; un redémarrage efface tout. Pour une diffusion large, prévoyez une base de données, une authentification et une surveillance. L'export contient le code du jeu (GDScript compilé), pas de secrets, mais n'importe qui peut le lire : aucun secret ne doit jamais y être intégré.

## 11. Ce qui a été vérifié, et ce qui ne l'a pas été

Vérifié sur cette machine : export Web avec Godot 4.7.2 et le renderer Compatibility ; page servie en HTTP local (jamais `file://`) ; jeu chargé dans Google Chrome 149 (headless, rendu WebGL logiciel), sans erreur de console ; création de salon, deux joueurs dans deux contextes de navigateur, partie classique complète jusqu'au classement ; inventaire ; parcours IA avec le fournisseur simulé jusqu'au lancement de la partie ; requêtes CORS préliminaires (POST, PUT avec jeton) ; mode « Web public » (adresse issue de `config.json`, aucune requête vers 127.0.0.1) ; démarrage du serveur avec la commande de `railway.json` ; 299 tests du serveur.

**Non vérifié** : Safari, Firefox, Android, iPhone et le comportement tactile / clavier virtuel ; saisie d'accents avec un vrai clavier ; enchère à l'aveugle, partie personnalisée et revanche dans le navigateur (couvertes par les tests du serveur, pas par un test d'interface) ; déploiements réels sur Railway et Vercel (non effectués : aucun compte n'a été utilisé) ; fournisseurs IA réels.
