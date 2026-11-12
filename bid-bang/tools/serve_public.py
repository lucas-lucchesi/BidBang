#!/usr/bin/env python3
"""Serveur BidBang sur VOTRE ordinateur, joignable par vos amis grâce à un tunnel HTTPS, avec le client
Web hébergé sur Vercel.

    python3 bid-bang/tools/serve_public.py --origin https://VOTRE-PROJET.vercel.app [--push]

Ce que fait le script :
  1. démarre le serveur FastAPI en local (127.0.0.1:8000) en mode production : CORS et WebSocket limités
     à l'origine de votre site Vercel, pas de fournisseur simulé, pas de clé lue dans l'environnement ;
  2. démarre un tunnel Cloudflare gratuit (`cloudflared`, sans compte) qui donne une adresse
     https://xxxx.trycloudflare.com ;
  3. vérifie que le serveur répond par cette adresse ;
  4. écrit l'adresse dans web_build/config.json (lue par le client Web au démarrage) ;
  5. avec --push : commite ce seul fichier et le pousse (Vercel redéploie en ~1 minute). Sans --push, le
     script affiche les commandes à lancer.

L'adresse d'un tunnel rapide change à chaque lancement : il faut donc relancer le script (et pousser
config.json) chaque fois. Avec votre propre adresse fixe (tunnel nommé, ngrok...), utilisez --public-url :
le script ne lance alors pas de tunnel. Votre ordinateur doit rester allumé pendant les parties ; arrêter le
script (Ctrl+C) arrête le serveur et le tunnel, et supprime les parties en cours.
"""
import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = PROJECT_DIR.parent
SERVER_DIR = PROJECT_DIR / "server"
CONFIG_PATH = REPO_DIR / "web_build" / "config.json"
TUNNEL_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
ORIGIN_RE = re.compile(r"^https://[A-Za-z0-9.-]+(:\d{1,5})?$")


def extract_tunnel_url(line: str) -> str | None:
    m = TUNNEL_URL_RE.search(line)
    return m.group(0) if m else None


def check_https_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if not re.match(r"^https://[A-Za-z0-9.-]+(:\d{1,5})?$", url):
        raise SystemExit(f"Adresse invalide (https:// attendu, sans chemin) : {url}")
    return url


def write_config(path: Path, server_url: str) -> bool:
    """Écrit {"server_url": ...} ; renvoie True si le fichier a changé."""
    new = json.dumps({"server_url": check_https_url(server_url)}, indent=2) + "\n"
    old = path.read_text(encoding="utf-8") if path.is_file() else ""
    if old == new:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new, encoding="utf-8")
    return True


def server_python() -> str:
    venv = SERVER_DIR / ".venv" / "bin" / "python"
    return str(venv) if venv.is_file() else sys.executable


def start_server(port: int, origin: str, extra_env: dict | None = None) -> subprocess.Popen:
    env = {**os.environ, "BIDBANG_ENV": "production", "ALLOWED_ORIGINS": origin, **(extra_env or {})}
    for risky in ("BIDBANG_MOCK_AI", "BIDBANG_ALLOW_ENV_KEY", "BIDBANG_ALLOW_INSECURE_AI"):
        env.pop(risky, None)  # jamais exposés publiquement
    cmd = [server_python(), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port),
           "--workers", "1", "--proxy-headers", "--forwarded-allow-ips=127.0.0.1"]
    return subprocess.Popen(cmd, cwd=SERVER_DIR, env=env, start_new_session=True)


def wait_http(url: str, seconds: float, expect: bytes = b"ok") -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            if expect in urllib.request.urlopen(url, timeout=5).read():
                return True
        except OSError:
            pass
        time.sleep(0.5)
    return False


def start_tunnel(port: int, binary: str, seconds: float = 40.0) -> tuple[subprocess.Popen, str]:
    proc = subprocess.Popen([binary, "tunnel", "--url", f"http://127.0.0.1:{port}", "--no-autoupdate"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
                            start_new_session=True)
    found: list[str] = []

    def reader():
        for line in proc.stdout:  # cloudflared écrit l'adresse dans ses journaux
            url = extract_tunnel_url(line)
            if url and not found:
                found.append(url)

    threading.Thread(target=reader, daemon=True).start()
    deadline = time.time() + seconds
    while time.time() < deadline and not found and proc.poll() is None:
        time.sleep(0.2)
    if not found:
        stop(proc)
        raise SystemExit("Le tunnel n'a pas donné d'adresse. Vérifiez votre connexion et `cloudflared --version`.")
    return proc, found[0]


def stop(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=10)
    except Exception:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            pass


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def publish_config(repo: Path, config: Path, message: str = "Adresse du serveur (tunnel)") -> str:
    """Commite UNIQUEMENT config.json (rien d'autre) et le pousse sur la branche courante."""
    rel = str(config.resolve().relative_to(repo.resolve()))
    if git(repo, "add", "--", rel).returncode != 0:
        raise SystemExit("git add a échoué")
    if git(repo, "diff", "--cached", "--quiet", "--", rel).returncode == 0:
        return "config.json déjà à jour dans git : rien à pousser"
    c = git(repo, "commit", "-m", message, "--only", "--", rel)
    if c.returncode != 0:
        raise SystemExit("git commit a échoué : " + c.stderr.strip()[:300])
    p = git(repo, "push")
    if p.returncode != 0:
        raise SystemExit("git push a échoué : " + p.stderr.strip()[:300])
    return "config.json poussé : Vercel redéploie le client (environ 1 minute)"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Serveur BidBang local + tunnel HTTPS + client sur Vercel")
    ap.add_argument("--origin", default=os.environ.get("BIDBANG_WEB_ORIGIN"),
                    help="origine de votre site Vercel, ex. https://bidbang.vercel.app (ou variable BIDBANG_WEB_ORIGIN)")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--public-url", help="adresse https déjà disponible (tunnel nommé, ngrok...) : pas de tunnel lancé")
    ap.add_argument("--cloudflared", default=shutil.which("cloudflared") or "cloudflared")
    ap.add_argument("--push", action="store_true", help="commiter et pousser web_build/config.json")
    args = ap.parse_args(argv)

    if not args.origin or not ORIGIN_RE.match(args.origin.strip().rstrip("/")):
        ap.error("--origin https://votre-projet.vercel.app est obligatoire (sans / final)")
    origin = args.origin.strip().rstrip("/")
    if not args.public_url and not shutil.which(args.cloudflared):
        print("`cloudflared` est introuvable. Installation (Linux x86-64) :\n"
              "  mkdir -p ~/.local/bin && curl -L -o ~/.local/bin/cloudflared "
              "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 "
              "&& chmod +x ~/.local/bin/cloudflared\nPuis relancez ce script.", file=sys.stderr)
        return 1

    server = tunnel = None
    try:
        server = start_server(args.port, origin)
        if not wait_http(f"http://127.0.0.1:{args.port}/health", 30):
            print("Le serveur local n'a pas démarré (port déjà utilisé ? dépendances installées ?).", file=sys.stderr)
            return 1
        print(f"Serveur local prêt sur http://127.0.0.1:{args.port} (mode production, origine autorisée : {origin})")
        if args.public_url:
            public = check_https_url(args.public_url)
        else:
            tunnel, public = start_tunnel(args.port, args.cloudflared)
        print(f"Adresse publique : {public}")
        if not wait_http(public + "/health", 60):
            print("L'adresse publique ne répond pas encore. Attendez une minute puis ouvrez "
                  f"{public}/health ; sinon relancez le script.", file=sys.stderr)
        changed = write_config(CONFIG_PATH, public)
        print(f"{CONFIG_PATH} {'mis à jour' if changed else 'déjà à jour'} : {public}")
        if args.push:
            print(publish_config(REPO_DIR, CONFIG_PATH))
        else:
            print("Pour publier cette adresse sur Vercel :\n"
                  "  git add web_build/config.json && git commit -m 'Adresse du serveur' && git push")
        print("\nVos amis peuvent jouer sur votre site Vercel tant que ce script tourne. Ctrl+C pour arrêter.")
        while server.poll() is None and (tunnel is None or tunnel.poll() is None):
            time.sleep(1)
        print("Un des deux processus s'est arrêté.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nArrêt demandé.")
        return 0
    finally:
        stop(tunnel)
        stop(server)


if __name__ == "__main__":
    sys.exit(main())
