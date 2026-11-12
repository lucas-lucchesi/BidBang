"""Fournisseur simulé pour les essais locaux : aucune clé réelle, aucun appel réseau.

Activé seulement si la variable d'environnement BIDBANG_MOCK_AI=1 (jamais en production).
Il renvoie une réponse JSON déterministe (cartes de football si le scénario parle de foot ou de 11, sinon des métiers) ; la clé
reçue est ignorée (n'importe quelle chaîne de 10 caractères ou plus convient).
"""
import json

name = "mock"


class MockProvider:
    name = "mock"
    label = "Simulé (test local)"

    async def complete(self, *, api_key: str, system: str, prompt: str,
                       max_tokens: int, timeout: float, json_schema: dict | None = None) -> str:
        text = prompt.lower()
        if "foot" in text or "11" in text or "om" in text.split():
            profile = {"goal": "Composer un onze de football", "allowed_entity_types": ["football_player"],
                       "real_entities_only": False, "organization": None,
                       "required_roles": ["Gardien", "Défenseur", "Milieu", "Attaquant"],
                       "allow_unrelated_items": False}
            title, desc = "Onze de légende", "Composez l'équipe de football de légende."
            kind, real = "football_player", False
            cards = [("Gardien d'or", "Gardien", 95), ("Défenseur mythique", "Défenseur", 88),
                     ("Libéro élégant", "Défenseur", 74), ("Milieu maestro", "Milieu", 97),
                     ("Régisseur discret", "Milieu", 70), ("Ailier fulgurant", "Attaquant", 92),
                     ("Buteur légendaire", "Attaquant", 99), ("Numéro 10 génial", "Milieu", 96),
                     ("Latéral infatigable", "Défenseur", 68), ("Gardien remplaçant", "Gardien", 35),
                     ("Milieu vieillissant", "Milieu", 22), ("Attaquant de réserve", "Attaquant", 25),
                     ("Défenseur central", "Défenseur", 85), ("Avant-centre", "Attaquant", 80)]
        else:
            profile = {"goal": "Recruter une équipe", "allowed_entity_types": ["job"],
                       "real_entities_only": False, "organization": None, "required_roles": [],
                       "allow_unrelated_items": False}
            title, desc = "Équipe de choc", "Recrutez les meilleurs profils pour la mission."
            kind, real = "job", False
            cards = [("Chef de projet", "Métier", 80), ("Développeuse senior", "Métier", 90),
                     ("Designer", "Métier", 65), ("Commercial", "Métier", 60),
                     ("Comptable", "Métier", 45), ("Stagiaire", "Métier", 20),
                     ("Expert sécurité", "Métier", 75), ("Community manager", "Métier", 50),
                     ("Juriste", "Métier", 40), ("Analyste", "Métier", 30),
                     ("Data scientist", "Métier", 85), ("Directeur financier", "Métier", 70)]
        items = [{"name": n, "description": f"{n} : une carte du jeu.", "category": c,
                  "entity_type": kind, "is_real": real,
                  "rarity": 3 if p >= 95 else 2 if p >= 85 else 1 if p >= 60 else 0,
                  "price": max(20, min(600, p * 5)), "points": p} for n, c, p in cards]
        return json.dumps({"title": title, "description": desc, "profile": profile, "items": items},
                          ensure_ascii=False)
