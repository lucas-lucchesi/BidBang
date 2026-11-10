"""Génère data/catalog.json (6 lieux, 72 cartes, épreuves de survie).

Usage : python tools/gen_catalog.py
Stats : confort, style, utilite, securite, sante (0 à 5).
Seuils de survie donnés pour 6 objets ; le moteur les ramène à item_count.
"""
import json
from pathlib import Path

STATS = ["confort", "style", "utilite", "securite", "sante"]

# (nom, icone, prix, rarete 0-3, [confort, style, utilite, securite, sante], [tags])
LOCATIONS = [
    {
        "id": "cabane",
        "name": "Cabane en forêt",
        "description": "Une cabane isolée au milieu des bois, loin de tout.",
        "scenario": {
            "title": "Une semaine sans réseau",
            "text": "La neige bloque la route. Il faut tenir jusqu'à l'arrivée des secours.",
            "trials": [
                {"id": "froid", "name": "Nuit glaciale", "stat": "confort", "threshold": 9},
                {"id": "tempete", "name": "Tempête de neige", "stat": "securite", "threshold": 8},
                {"id": "faim", "name": "Pénurie de vivres", "stat": "utilite", "threshold": 9},
            ],
        },
        "items": [
            ("Poêle à bois", "fire", 220, 1, [4, 1, 4, 2, 0], ["chaleur", "bois"]),
            ("Hache de bûcheron", "axe", 90, 0, [0, 1, 4, 2, 0], ["bois", "outil"]),
            ("Fauteuil en cuir", "chair", 180, 1, [5, 3, 0, 0, 0], ["confort", "cuir"]),
            ("Tapis en peau d'ours", "rug", 260, 2, [4, 4, 0, 0, 0], ["chaleur", "cuir"]),
            ("Lampe tempête", "lamp", 60, 0, [1, 1, 3, 3, 0], ["lumiere", "outil"]),
            ("Réserve de conserves", "can", 120, 0, [0, 0, 4, 0, 4], ["vivres"]),
            ("Couverture de laine", "blanket", 70, 0, [4, 1, 1, 0, 1], ["chaleur", "confort"]),
            ("Fusil de chasse", "gun", 340, 2, [0, 2, 3, 5, 0], ["outil", "securite"]),
            ("Trousse de secours", "kit", 100, 0, [0, 0, 2, 2, 5], ["soin"]),
            ("Cheminée en pierre", "stone", 420, 3, [5, 5, 3, 1, 0], ["chaleur", "bois"]),
            ("Serrure renforcée", "lock", 130, 1, [0, 0, 1, 5, 0], ["securite"]),
            ("Lit en rondins", "bed", 200, 1, [5, 2, 1, 0, 2], ["confort", "bois"]),
        ],
    },
    {
        "id": "appartement",
        "name": "Appartement en ville",
        "description": "Un trois-pièces lumineux au cinquième étage, en plein centre.",
        "scenario": {
            "title": "Coupure générale",
            "text": "Plus d'électricité ni d'eau courante dans toute la ville pendant plusieurs jours.",
            "trials": [
                {"id": "noir", "name": "Plongée dans le noir", "stat": "utilite", "threshold": 9},
                {"id": "chaleur", "name": "Canicule", "stat": "confort", "threshold": 8},
                {"id": "pillage", "name": "Quartier agité", "stat": "securite", "threshold": 8},
            ],
        },
        "items": [
            ("Canapé d'angle", "sofa", 300, 1, [5, 3, 0, 0, 0], ["confort", "salon"]),
            ("Télévision 4K", "tv", 280, 1, [2, 3, 2, 0, 0], ["ecran", "salon"]),
            ("Cafetière italienne", "coffee", 40, 0, [1, 1, 3, 0, 1], ["cuisine"]),
            ("Plantes d'intérieur", "plant", 50, 0, [2, 3, 0, 0, 3], ["deco", "nature"]),
            ("Lampe de designer", "lamp", 150, 1, [1, 5, 2, 0, 0], ["deco", "lumiere"]),
            ("Porte blindée", "door", 380, 2, [0, 1, 1, 5, 0], ["securite"]),
            ("Ventilateur silencieux", "fan", 70, 0, [4, 0, 3, 0, 1], ["confort"]),
            ("Réchaud de camping", "stove", 60, 0, [0, 0, 4, 1, 1], ["cuisine", "outil"]),
            ("Tableau de maître", "art", 450, 3, [0, 5, 0, 0, 0], ["deco", "luxe"]),
            ("Bureau en chêne", "desk", 210, 1, [2, 4, 3, 0, 0], ["bureau", "luxe"]),
            ("Réserve d'eau", "water", 80, 0, [0, 0, 3, 1, 5], ["vivres"]),
            ("Système d'alarme", "alarm", 190, 1, [0, 0, 2, 5, 0], ["securite", "ecran"]),
        ],
    },
    {
        "id": "plage",
        "name": "Plage tropicale",
        "description": "Sable blanc, cocotiers et une île à peine habitée.",
        "scenario": {
            "title": "Naufragés",
            "text": "Le bateau est parti sans vous. Les secours passeront dans quelques jours.",
            "trials": [
                {"id": "soleil", "name": "Soleil de plomb", "stat": "sante", "threshold": 8},
                {"id": "soif", "name": "Soif", "stat": "utilite", "threshold": 9},
                {"id": "orage", "name": "Orage tropical", "stat": "securite", "threshold": 8},
            ],
        },
        "items": [
            ("Parasol géant", "umbrella", 80, 0, [3, 2, 1, 0, 4], ["ombre", "plage"]),
            ("Hamac brodé", "hammock", 110, 0, [5, 3, 0, 0, 1], ["confort", "plage"]),
            ("Planche de surf", "surf", 260, 1, [0, 5, 2, 0, 1], ["sport", "plage"]),
            ("Filtre à eau", "filter", 130, 1, [0, 0, 5, 1, 4], ["eau", "outil"]),
            ("Noix de coco", "coconut", 20, 0, [1, 1, 2, 0, 3], ["vivres", "nature"]),
            ("Canot de sauvetage", "boat", 400, 2, [1, 1, 3, 5, 0], ["eau", "securite"]),
            ("Crème solaire", "sun", 30, 0, [0, 0, 1, 0, 5], ["soin"]),
            ("Bar à cocktails", "bar", 320, 2, [3, 5, 1, 0, 0], ["luxe", "plage"]),
            ("Fusée de détresse", "flare", 140, 1, [0, 0, 3, 5, 0], ["securite", "outil"]),
            ("Tente de toile", "tent", 150, 0, [4, 1, 2, 3, 1], ["ombre", "abri"]),
            ("Couteau suisse", "knife", 60, 0, [0, 0, 5, 2, 0], ["outil"]),
            ("Villa sur pilotis", "villa", 480, 3, [5, 5, 2, 3, 0], ["luxe", "abri"]),
        ],
    },
    {
        "id": "montagne",
        "name": "Refuge de montagne",
        "description": "Un refuge à 2 500 mètres d'altitude, face aux glaciers.",
        "scenario": {
            "title": "Avalanche",
            "text": "Le col est fermé. Il faut tenir en altitude jusqu'à la fin de la tempête.",
            "trials": [
                {"id": "gel", "name": "Gel extrême", "stat": "confort", "threshold": 9},
                {"id": "alt", "name": "Mal des montagnes", "stat": "sante", "threshold": 8},
                {"id": "sauv", "name": "Évacuation", "stat": "securite", "threshold": 9},
            ],
        },
        "items": [
            ("Sac de couchage polaire", "bag", 150, 1, [5, 0, 2, 1, 2], ["chaleur", "camp"]),
            ("Piolet", "pick", 90, 0, [0, 1, 3, 3, 0], ["escalade", "outil"]),
            ("Corde d'escalade", "rope", 70, 0, [0, 0, 3, 4, 0], ["escalade", "securite"]),
            ("Réchaud à gaz", "stove", 80, 0, [2, 0, 4, 1, 1], ["chaleur", "camp"]),
            ("Balise de détresse", "beacon", 240, 1, [0, 0, 2, 5, 0], ["securite", "tech"]),
            ("Doudoune en duvet", "coat", 170, 1, [5, 3, 1, 0, 2], ["chaleur", "style"]),
            ("Bouteille d'oxygène", "o2", 300, 2, [0, 0, 2, 2, 5], ["soin", "tech"]),
            ("Skis de randonnée", "ski", 280, 1, [0, 4, 3, 1, 0], ["sport", "escalade"]),
            ("Radio longue portée", "radio", 200, 1, [0, 0, 3, 4, 0], ["tech", "securite"]),
            ("Fondue en kit", "cheese", 60, 0, [3, 2, 1, 0, 2], ["vivres", "chaleur"]),
            ("Lunettes de glacier", "glasses", 50, 0, [0, 3, 1, 0, 3], ["style", "soin"]),
            ("Chalet panoramique", "chalet", 500, 3, [5, 5, 2, 3, 1], ["luxe", "chaleur"]),
        ],
    },
    {
        "id": "bureau",
        "name": "Bureau de start-up",
        "description": "Un open space branché avec baby-foot et machine à café.",
        "scenario": {
            "title": "Nuit de livraison",
            "text": "Le produit doit sortir demain matin. L'équipe ne dormira pas.",
            "trials": [
                {"id": "fatigue", "name": "Fatigue extrême", "stat": "confort", "threshold": 8},
                {"id": "bug", "name": "Bug critique", "stat": "utilite", "threshold": 9},
                {"id": "stress", "name": "Pression du client", "stat": "sante", "threshold": 7},
            ],
        },
        "items": [
            ("Chaise ergonomique", "chair", 250, 1, [5, 2, 2, 0, 3], ["confort", "bureau"]),
            ("Double écran", "screens", 320, 1, [1, 3, 5, 0, 0], ["tech", "bureau"]),
            ("Machine à café pro", "coffee", 180, 1, [2, 1, 4, 0, 1], ["vivres", "cafe"]),
            ("Baby-foot", "foot", 200, 1, [2, 4, 0, 0, 2], ["jeu", "deco"]),
            ("Casque anti-bruit", "headset", 130, 0, [3, 1, 3, 0, 2], ["tech", "confort"]),
            ("Tableau blanc", "board", 60, 0, [0, 1, 4, 0, 0], ["bureau", "outil"]),
            ("Canapé de sieste", "sofa", 280, 1, [5, 2, 0, 0, 3], ["confort", "deco"]),
            ("Serveur de secours", "server", 400, 2, [0, 0, 5, 4, 0], ["tech", "securite"]),
            ("Distributeur de snacks", "snack", 90, 0, [1, 1, 2, 0, 2], ["vivres", "cafe"]),
            ("Plante anti-stress", "plant", 40, 0, [1, 2, 0, 0, 4], ["deco", "soin"]),
            ("Bureau assis-debout", "desk", 300, 1, [3, 3, 3, 0, 3], ["bureau", "confort"]),
            ("Terrasse sur le toit", "roof", 450, 3, [4, 5, 1, 1, 4], ["deco", "luxe"]),
        ],
    },
    {
        "id": "station",
        "name": "Station spatiale",
        "description": "Un module orbital avec vue sur la Terre, loin de tout secours.",
        "scenario": {
            "title": "Dépressurisation",
            "text": "Un module est touché par des débris. L'équipage attend la navette de relève.",
            "trials": [
                {"id": "air", "name": "Manque d'oxygène", "stat": "sante", "threshold": 9},
                {"id": "panne", "name": "Panne électrique", "stat": "utilite", "threshold": 10},
                {"id": "radiation", "name": "Tempête solaire", "stat": "securite", "threshold": 9},
            ],
        },
        "items": [
            ("Recycleur d'air", "air", 380, 2, [1, 0, 3, 2, 5], ["vie", "tech"]),
            ("Panneaux solaires", "solar", 300, 1, [0, 1, 5, 1, 0], ["energie", "tech"]),
            ("Combinaison pressurisée", "suit", 340, 1, [2, 2, 2, 4, 2], ["securite", "vie"]),
            ("Bouclier anti-radiations", "shield", 420, 2, [0, 0, 2, 5, 3], ["securite", "tech"]),
            ("Kit de réparation", "wrench", 110, 0, [0, 0, 5, 2, 0], ["outil", "energie"]),
            ("Rations lyophilisées", "food", 70, 0, [1, 0, 3, 0, 4], ["vie", "vivres"]),
            ("Hublot panoramique", "window", 260, 1, [3, 5, 0, 0, 1], ["deco", "luxe"]),
            ("Batterie de secours", "battery", 150, 0, [0, 0, 4, 2, 0], ["energie", "outil"]),
            ("Capsule d'évacuation", "pod", 480, 3, [2, 2, 3, 5, 2], ["securite", "luxe"]),
            ("Couchette magnétique", "bunk", 120, 0, [5, 1, 0, 0, 3], ["confort"]),
            ("Robot assistant", "robot", 360, 2, [2, 4, 5, 1, 0], ["tech", "energie"]),
            ("Jardin hydroponique", "garden", 220, 1, [2, 3, 1, 0, 5], ["vie", "deco"]),
        ],
    },
]


def build() -> dict:
    locations, items = [], []
    for loc in LOCATIONS:
        locations.append({
            "id": loc["id"],
            "name": loc["name"],
            "description": loc["description"],
            "survival": loc["scenario"],
        })
        for n, (name, icon, price, rarity, stats, tags) in enumerate(loc["items"], start=1):
            items.append({
                "id": f"{loc['id']}_{n:02d}",
                "location_id": loc["id"],
                "name": name,
                "icon": icon,
                "price": price,
                "rarity": rarity,
                "stats": dict(zip(STATS, stats)),
                "tags": tags,
            })
    return {"stats": STATS, "locations": locations, "items": items}


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "data" / "catalog.json"
    out.write_text(json.dumps(build(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(LOCATIONS)} lieux, {sum(len(l['items']) for l in LOCATIONS)} cartes -> {out}")
