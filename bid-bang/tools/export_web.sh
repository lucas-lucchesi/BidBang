#!/usr/bin/env bash
# Exporte BidBang pour le Web dans ../web_build (à la racine du dépôt), puis contrôle le résultat.
#
#   bid-bang/tools/export_web.sh                  # export (garde web_build/config.json existant)
#   BIDBANG_SERVER_URL=https://xxx.up.railway.app bid-bang/tools/export_web.sh   # écrit aussi config.json
#
# Variables : GODOT = chemin de l'exécutable Godot 4.7.2 (sinon recherche automatique).
# Prérequis : modèles d'export Web sans threads installés (voir DEPLOY_WEB.md).
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(cd "$PROJECT_DIR/.." && pwd)"
OUT_DIR="$REPO_DIR/web_build"
VERSION="4.7.2.stable"

find_godot() {
  if [[ -n "${GODOT:-}" ]]; then echo "$GODOT"; return; fi
  for c in godot godot4 "$HOME/Desktop/Godot_v4.7.2-stable_linux.x86_64.exe" \
           "$HOME/Desktop/Godot_v4.7.2-stable_linux.x86_64" "$HOME/Downloads/Godot_v4.7.2-stable_linux.x86_64"; do
    if command -v "$c" >/dev/null 2>&1; then command -v "$c"; return; fi
    if [[ -x "$c" ]]; then echo "$c"; return; fi
  done
  return 1
}

GODOT_BIN="$(find_godot)" || { echo "Godot introuvable : définissez GODOT=/chemin/vers/Godot_v4.7.2-stable_linux.x86_64" >&2; exit 1; }
echo "Godot : $GODOT_BIN ($("$GODOT_BIN" --version | tail -1))"

# Certains terminaux (VS Code installé avec snap) redéfinissent XDG_DATA_HOME : Godot chercherait alors
# ses modèles d'export au mauvais endroit. On force les dossiers standards (GODOT_KEEP_XDG=1 pour désactiver).
if [[ -z "${GODOT_KEEP_XDG:-}" ]]; then
  export XDG_DATA_HOME="$HOME/.local/share"
  export XDG_CONFIG_HOME="$HOME/.config"
  export XDG_CACHE_HOME="$HOME/.cache"
fi
TEMPLATES="${XDG_DATA_HOME:-$HOME/.local/share}/godot/export_templates/$VERSION"
if [[ ! -f "$TEMPLATES/web_nothreads_release.zip" ]]; then
  echo "Modèle d'export Web introuvable : $TEMPLATES/web_nothreads_release.zip" >&2
  echo "Voir DEPLOY_WEB.md, section « Installer les modèles d'export »." >&2
  exit 1
fi

mkdir -p "$OUT_DIR"
# 1re passe : importer les ressources (nécessaire sur un clone neuf, sans dossier .godot)
"$GODOT_BIN" --headless --path "$PROJECT_DIR" --import >/dev/null 2>&1 || true
echo "Export Web (renderer Compatibility, sans threads) -> $OUT_DIR"
"$GODOT_BIN" --headless --path "$PROJECT_DIR" --export-release "Web" "$OUT_DIR/index.html"

# config.json : adresse du serveur lue au démarrage par le jeu (jamais intégrée au .pck)
if [[ -n "${BIDBANG_SERVER_URL:-}" ]]; then
  python3 - "$OUT_DIR/config.json" "$BIDBANG_SERVER_URL" <<'PY'
import json, sys
path, url = sys.argv[1], sys.argv[2].strip().rstrip("/")
if not url.startswith("https://"):
    sys.exit("BIDBANG_SERVER_URL doit commencer par https:// (la version Web publique n'accepte que HTTPS)")
json.dump({"server_url": url}, open(path, "w"), indent=2)
open(path, "a").write("\n")
print("config.json écrit :", url)
PY
elif [[ ! -f "$OUT_DIR/config.json" ]]; then
  printf '{\n  "server_url": ""\n}\n' > "$OUT_DIR/config.json"
  echo "config.json créé SANS adresse de serveur : renseignez-la (voir DEPLOY_WEB.md)."
fi

python3 "$PROJECT_DIR/tools/check_web_build.py" "$OUT_DIR"
