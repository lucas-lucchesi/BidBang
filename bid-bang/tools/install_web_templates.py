#!/usr/bin/env python3
"""Installe seulement les modèles d'export Web (sans threads) de Godot, sans télécharger les 1,3 Go du
fichier .tpz complet : l'archive officielle est un zip, dont on lit l'index et les trois fichiers utiles
par requêtes HTTP partielles (environ 22 Mo au total).

Usage : python3 bid-bang/tools/install_web_templates.py [version]    (défaut : 4.7.2)

Installe dans ~/.local/share/godot/export_templates/<version>.stable/ . Les modèles Android et iOS ne
sont PAS installés : pour eux, utilisez Éditeur > Gérer les modèles d'exportation dans Godot.
"""
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

VERSION = sys.argv[1] if len(sys.argv) > 1 else "4.7.2"
URL = (f"https://github.com/godotengine/godot/releases/download/{VERSION}-stable/"
       f"Godot_v{VERSION}-stable_export_templates.tpz")
WANT = ("templates/version.txt", "templates/web_nothreads_release.zip", "templates/web_nothreads_debug.zip")
DEST = Path.home() / ".local/share/godot/export_templates" / f"{VERSION}.stable"


class RangeFile(io.RawIOBase):
    """Fichier distant en lecture seule, lu par blocs avec l'en-tête HTTP Range."""

    def __init__(self, url: str):
        head = urllib.request.urlopen(urllib.request.Request(url, method="HEAD"))
        self.url, self.size, self.pos, self.fetched = head.geturl(), int(head.headers["Content-Length"]), 0, 0

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = {0: offset, 1: self.pos + offset, 2: self.size + offset}[whence]
        return self.pos

    def readinto(self, buf):
        n = min(len(buf), self.size - self.pos)
        if n <= 0:
            return 0
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{self.pos + n - 1}"})
        data = urllib.request.urlopen(req).read()
        buf[:len(data)] = data
        self.pos += len(data)
        self.fetched += len(data)
        return len(data)


def main() -> None:
    remote = RangeFile(URL)
    with zipfile.ZipFile(io.BufferedReader(remote, buffer_size=1 << 20)) as archive:
        names = set(archive.namelist())
        missing = [n for n in WANT if n not in names]
        if missing:
            sys.exit(f"Archive inattendue, fichiers absents : {missing}")
        DEST.mkdir(parents=True, exist_ok=True)
        for name in WANT:
            (DEST / Path(name).name).write_bytes(archive.read(name))
            print("installé :", DEST / Path(name).name)
    print(f"Téléchargé : {remote.fetched / 1e6:.0f} Mo (archive complète : {remote.size / 1e6:.0f} Mo)")


if __name__ == "__main__":
    main()
