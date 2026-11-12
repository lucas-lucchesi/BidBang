#!/usr/bin/env python3
"""Contrôle d'un export Web avant publication : fichiers attendus, tailles, rien de secret ni de serveur.

Usage : python3 tools/check_web_build.py ../web_build
Code de sortie 1 si un problème bloquant est trouvé.
"""
import json
import re
import sys
from pathlib import Path

REQUIRED = ["index.html", "index.js", "index.wasm", "index.pck"]
GITHUB_LIMIT = 100 * 1024 * 1024       # refus de GitHub au-delà
GITHUB_WARN = 50 * 1024 * 1024         # avertissement de GitHub
FORBIDDEN_IN_PCK = [b"res://server/", b"server/app/", b"requirements.txt", b".venv", b"/tests/test_",
                    b"res://sprite/", b"res://tools/", b"legacy_pixel", b".env", b"export_presets",
                    b"railway.json", b"catalog.json"]
SECRET_PATTERNS = [rb"AIza[0-9A-Za-z_\-]{30,}", rb"sk-ant-[A-Za-z0-9_\-]{20,}", rb"sk-[A-Za-z0-9]{30,}",
                   rb"(?i)api[_-]?key\s*[:=]\s*[\"'][A-Za-z0-9_\-]{16,}[\"']"]
LOCAL_URL = re.compile(rb"https?://(127\.0\.0\.1|localhost|10\.0\.2\.2)[:/0-9]*")


def main(path: str) -> int:
    out = Path(path)
    problems: list[str] = []
    warnings: list[str] = []
    for name in REQUIRED:
        if not (out / name).is_file():
            problems.append(f"fichier manquant : {name}")
    if problems:
        print("\n".join("ERREUR " + p for p in problems))
        return 1
    print("Fichiers de l'export :")
    for f in sorted(out.rglob("*")):
        if f.is_file():
            size = f.stat().st_size
            print(f"  {f.relative_to(out)!s:34} {size / 1e6:8.2f} Mo")
            if size > GITHUB_LIMIT:
                problems.append(f"{f.name} dépasse la limite de GitHub (100 Mo)")
            elif size > GITHUB_WARN:
                warnings.append(f"{f.name} dépasse 50 Mo : GitHub avertit au push")
    total = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"  total {total / 1e6:.1f} Mo")
    pck = (out / "index.pck").read_bytes()
    for needle in FORBIDDEN_IN_PCK:
        if needle in pck:
            problems.append(f"le .pck contient « {needle.decode()} » (ne doit pas être distribué)")
    for rx in SECRET_PATTERNS:
        for f in out.rglob("*"):
            if f.is_file() and f.suffix in (".pck", ".js", ".html", ".json"):
                if re.search(rx, f.read_bytes()):
                    problems.append(f"motif de clé API trouvé dans {f.name}")
    if LOCAL_URL.search(pck):
        # l'adresse locale par défaut de session.gd est normale (développement natif) ; la version
        # Web publique ne l'utilise jamais (voir Session._init_web_server)
        warnings.append("adresse locale (127.0.0.1) présente dans le .pck : normal (valeur par défaut native), "
                        "ignorée par la version Web publique")
    cfg = out / "config.json"
    if cfg.is_file():
        url = str(json.loads(cfg.read_text(encoding="utf-8")).get("server_url", ""))
        if not url:
            warnings.append("config.json sans server_url : la version publique affichera « serveur non configuré »")
        elif not url.startswith("https://") or "127.0.0.1" in url or "localhost" in url:
            problems.append(f"config.json : server_url invalide pour la production ({url})")
        else:
            print(f"  serveur de production : {url}")
    for w in warnings:
        print("AVERTISSEMENT", w)
    for p in problems:
        print("ERREUR", p)
    print("OK : export sain" if not problems else "ÉCHEC du contrôle")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "../web_build"))
