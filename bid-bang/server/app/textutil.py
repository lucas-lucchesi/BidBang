"""Petits utilitaires de texte partagés (identifiants ASCII, nettoyage)."""
import re
import unicodedata


def slugify(text: str) -> str:
    """Identifiant ASCII minuscule : « Générateur d'oxygène » -> generateur_d_oxygene."""
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "_", norm.lower()).strip("_")
    return slug[:40]


def clean(text: str) -> str:
    """Normalise les espaces et retire les caractères de contrôle."""
    text = "".join(ch for ch in text if ch == " " or not unicodedata.category(ch).startswith("C"))
    return " ".join(text.split())
