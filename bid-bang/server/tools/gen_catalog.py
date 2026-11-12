"""Génère data/catalog.json (7 lieux, 84 objets au format commun).

Usage : python tools/gen_catalog.py

Format d'un objet : id, location_id, name, description, category, icon, price (estimé),
rarity (0-3), base_points (0-50), attributes {critère: 1..5}, image (null).
Les critères sont ceux de data/criteria.json ; une caractéristique absente n'est pas stockée.
La rareté et le prix n'entrent pas dans le calcul des points (voir app/scoring.py).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CRITERIA = {c["id"] for c in json.loads((ROOT / "data" / "criteria.json").read_text(encoding="utf-8"))["criteria"]}


def need(*crit):
    """Critères de lieu : ("soins", 5) = nécessaire d'importance 5 ; ("luxe", 0) = non nécessaire."""
    return [{"id": c, "necessary": imp > 0, "importance": imp} for c, imp in crit]


# (nom, icone, prix estimé, rareté 0-3, points de base, {critère: 1..5}, description)
LOCATIONS = [
    {
        "id": "cabane", "name": "Cabane en forêt",
        "description": "Une cabane isolée au milieu des bois, loin de tout.",
        "situation": {"title": "Une semaine sans réseau",
                      "description": "La neige bloque la route. Il faut tenir jusqu'à l'arrivée des secours."},
        "criteria": need(("abri", 5), ("chaleur", 5), ("nourriture", 4), ("outils", 4), ("soins", 3),
                         ("luxe", 0), ("divertissement", 0)),
        "items": [
            ("Poêle à bois", "fire", 220, 1, 22, {"chaleur": 5, "abri": 2, "confort": 2}, "Un poêle en fonte qui chauffe toute la cabane."),
            ("Hache de bûcheron", "axe", 90, 0, 18, {"outils": 5, "protection": 2}, "Fendre le bois et se défendre au besoin."),
            ("Fauteuil en cuir", "chair", 180, 1, 10, {"confort": 4, "luxe": 2, "decoration": 1}, "Profond, moelleux, un peu trop chic pour les bois."),
            ("Tapis en peau d'ours", "rug", 260, 2, 8, {"chaleur": 3, "decoration": 4, "luxe": 3}, "Imposant devant la cheminée."),
            ("Lampe tempête", "lamp", 60, 0, 15, {"energie": 2, "outils": 2, "protection": 1}, "Une lumière fiable quand le courant lâche."),
            ("Réserve de conserves", "can", 120, 0, 25, {"nourriture": 5}, "De quoi tenir plusieurs semaines."),
            ("Couverture de laine", "blanket", 70, 0, 18, {"chaleur": 4, "confort": 3}, "Épaisse, rêche, efficace."),
            ("Fusil de chasse", "gun", 340, 2, 20, {"protection": 4, "nourriture": 3, "outils": 2}, "Pour se défendre et ramener du gibier."),
            ("Trousse de secours", "kit", 100, 0, 25, {"soins": 5}, "Pansements, antiseptique et bandages."),
            ("Cheminée en pierre", "stone", 420, 3, 15, {"chaleur": 5, "decoration": 3, "luxe": 3, "confort": 3}, "Un foyer monumental en pierre taillée."),
            ("Serrure renforcée", "lock", 130, 1, 12, {"protection": 4}, "Une porte qui résiste à tout."),
            ("Lit en rondins", "bed", 200, 1, 12, {"confort": 4, "abri": 2, "nature": 2}, "Rustique, solide, étonnamment confortable."),
        ],
    },
    {
        "id": "appartement", "name": "Appartement en ville",
        "description": "Un trois-pièces lumineux au cinquième étage, en plein centre.",
        "situation": {"title": "Coupure générale",
                      "description": "Plus d'électricité ni d'eau courante dans toute la ville pendant plusieurs jours."},
        "criteria": need(("confort", 5), ("decoration", 4), ("technologie", 4), ("eau", 3), ("energie", 3),
                         ("transport", 0)),
        "items": [
            ("Canapé d'angle", "sofa", 300, 1, 12, {"confort": 5, "decoration": 3, "divertissement": 2}, "Un grand canapé moelleux pour six personnes."),
            ("Télévision 4K", "tv", 280, 1, 10, {"divertissement": 5, "technologie": 4, "communication": 2}, "Image parfaite, tant qu'il y a du courant."),
            ("Cafetière italienne", "coffee", 40, 0, 10, {"nourriture": 2, "confort": 2, "outils": 1}, "Marche sur le gaz, sans électricité."),
            ("Plantes d'intérieur", "plant", 50, 0, 8, {"decoration": 4, "nature": 4}, "Un petit coin de jungle au salon."),
            ("Lampe de designer", "lamp", 150, 1, 6, {"decoration": 5, "luxe": 3}, "Une sculpture qui éclaire."),
            ("Porte blindée", "door", 380, 2, 15, {"protection": 5}, "Rien ne passe."),
            ("Ventilateur silencieux", "fan", 70, 0, 10, {"confort": 4, "technologie": 1}, "Un souffle d'air frais dans l'été."),
            ("Réchaud de camping", "stove", 60, 0, 18, {"nourriture": 3, "outils": 3, "chaleur": 2}, "Cuire sans cuisinière ni électricité."),
            ("Tableau de maître", "art", 450, 3, 6, {"decoration": 5, "luxe": 5}, "Une toile célèbre au-dessus du canapé."),
            ("Bureau en chêne", "desk", 210, 1, 10, {"outils": 3, "confort": 2, "decoration": 2, "technologie": 1}, "Massif et élégant."),
            ("Réserve d'eau", "water", 80, 0, 25, {"eau": 5, "soins": 1}, "Des bidons d'eau potable."),
            ("Système d'alarme", "alarm", 190, 1, 12, {"protection": 4, "technologie": 3, "communication": 1}, "Capteurs, sirène et application."),
        ],
    },
    {
        "id": "plage", "name": "Plage tropicale",
        "description": "Sable blanc, cocotiers et une île à peine habitée.",
        "situation": {"title": "Naufragés",
                      "description": "Le bateau est parti sans vous. Les secours passeront dans quelques jours."},
        "criteria": need(("eau", 5), ("abri", 4), ("nourriture", 4), ("communication", 4), ("confort", 3),
                         ("divertissement", 2), ("luxe", 0)),
        "items": [
            ("Parasol géant", "umbrella", 80, 0, 12, {"abri": 3, "confort": 3, "soins": 1}, "Une ombre bienvenue sous le soleil."),
            ("Hamac brodé", "hammock", 110, 0, 8, {"confort": 5, "decoration": 2, "nature": 1}, "Dormir entre deux palmiers."),
            ("Planche de surf", "surf", 260, 1, 8, {"divertissement": 5, "transport": 2, "nature": 2}, "Pour glisser sur les vagues."),
            ("Filtre à eau", "filter", 130, 1, 25, {"eau": 5, "soins": 2}, "Rend l'eau de mer ou de pluie buvable."),
            ("Noix de coco", "coconut", 20, 0, 12, {"nourriture": 3, "eau": 2, "nature": 3}, "À boire et à manger."),
            ("Canot de sauvetage", "boat", 400, 2, 22, {"transport": 5, "protection": 3}, "Pour quitter l'île."),
            ("Crème solaire", "sun", 30, 0, 14, {"soins": 4}, "Indice 50, indispensable."),
            ("Bar à cocktails", "bar", 320, 2, 6, {"divertissement": 4, "luxe": 4, "nourriture": 2}, "Parasols en papier inclus."),
            ("Fusée de détresse", "flare", 140, 1, 20, {"communication": 5, "protection": 2}, "Un signal visible à des kilomètres."),
            ("Tente de toile", "tent", 150, 0, 18, {"abri": 5, "confort": 2, "protection": 2}, "Légère et rapide à monter."),
            ("Couteau suisse", "knife", 60, 0, 15, {"outils": 5, "nourriture": 1}, "Vingt-sept outils en un."),
            ("Villa sur pilotis", "villa", 480, 3, 15, {"abri": 5, "luxe": 5, "confort": 5, "decoration": 3, "protection": 3}, "Le grand luxe au-dessus du lagon."),
        ],
    },
    {
        "id": "montagne", "name": "Refuge de montagne",
        "description": "Un refuge à 2 500 mètres d'altitude, face aux glaciers.",
        "situation": {"title": "Avalanche",
                      "description": "Le col est fermé. Il faut tenir en altitude jusqu'à la fin de la tempête."},
        "criteria": need(("chaleur", 5), ("abri", 4), ("protection", 4), ("communication", 4), ("nourriture", 3),
                         ("soins", 3), ("luxe", 0)),
        "items": [
            ("Sac de couchage polaire", "bag", 150, 1, 20, {"chaleur": 5, "confort": 3, "abri": 2}, "Confort garanti jusqu'à -30 °C."),
            ("Piolet", "pick", 90, 0, 12, {"outils": 4, "protection": 3, "transport": 3}, "Pour grimper et se rattraper."),
            ("Corde d'escalade", "rope", 70, 0, 14, {"protection": 4, "transport": 3, "outils": 2}, "Quarante mètres de sécurité."),
            ("Réchaud à gaz", "stove", 80, 0, 16, {"chaleur": 3, "nourriture": 3, "outils": 2, "energie": 2}, "De l'eau chaude en deux minutes."),
            ("Balise de détresse", "beacon", 240, 1, 20, {"communication": 5, "technologie": 3, "protection": 2}, "Alerte les secours par satellite."),
            ("Doudoune en duvet", "coat", 170, 1, 14, {"chaleur": 5, "confort": 3}, "Légère comme une plume, chaude comme un four."),
            ("Bouteille d'oxygène", "o2", 300, 2, 20, {"soins": 5, "protection": 2, "technologie": 2}, "Contre le mal des montagnes."),
            ("Skis de randonnée", "ski", 280, 1, 10, {"transport": 5, "divertissement": 3}, "Descendre la vallée en glissant."),
            ("Radio longue portée", "radio", 200, 1, 16, {"communication": 5, "technologie": 3, "energie": 1}, "Joindre la vallée malgré la tempête."),
            ("Fondue en kit", "cheese", 60, 0, 12, {"nourriture": 4, "chaleur": 2, "divertissement": 2}, "Réconfortant et convivial."),
            ("Lunettes de glacier", "glasses", 50, 0, 10, {"protection": 3, "soins": 2}, "Évitent la cécité des neiges."),
            ("Chalet panoramique", "chalet", 500, 3, 15, {"abri": 5, "confort": 5, "luxe": 4, "chaleur": 4, "decoration": 3}, "Baies vitrées, sauna et cheminée."),
        ],
    },
    {
        "id": "bureau", "name": "Bureau de start-up",
        "description": "Un open space branché avec baby-foot et machine à café.",
        "situation": {"title": "Nuit de livraison",
                      "description": "Le produit doit sortir demain matin. L'équipe ne dormira pas."},
        "criteria": need(("technologie", 5), ("outils", 4), ("confort", 4), ("nourriture", 3), ("energie", 3),
                         ("communication", 3), ("luxe", 0)),
        "items": [
            ("Chaise ergonomique", "chair", 250, 1, 12, {"confort": 5, "soins": 2}, "Le dos remercie."),
            ("Double écran", "screens", 320, 1, 15, {"technologie": 5, "outils": 4}, "Deux fois plus de code visible."),
            ("Machine à café pro", "coffee", 180, 1, 12, {"nourriture": 3, "confort": 2, "energie": 2}, "Le carburant de la nuit."),
            ("Baby-foot", "foot", 200, 1, 6, {"divertissement": 5, "decoration": 2}, "Pour décompresser entre deux bugs."),
            ("Casque anti-bruit", "headset", 130, 0, 10, {"technologie": 3, "confort": 3, "communication": 2}, "Le silence en pleine open space."),
            ("Tableau blanc", "board", 60, 0, 10, {"outils": 4, "communication": 3}, "Schémas, flèches et post-its."),
            ("Canapé de sieste", "sofa", 280, 1, 8, {"confort": 5, "soins": 2, "decoration": 1}, "Vingt minutes qui sauvent la journée."),
            ("Serveur de secours", "server", 400, 2, 20, {"technologie": 5, "energie": 3, "protection": 3, "communication": 2}, "Quand la prod tombe, il prend le relais."),
            ("Distributeur de snacks", "snack", 90, 0, 10, {"nourriture": 4, "divertissement": 1}, "Barres, chips et bonbons."),
            ("Plante anti-stress", "plant", 40, 0, 6, {"nature": 4, "decoration": 3, "soins": 2}, "Verte, calme, silencieuse."),
            ("Bureau assis-debout", "desk", 300, 1, 10, {"outils": 3, "confort": 4, "soins": 2, "technologie": 1}, "Se lève au bouton."),
            ("Terrasse sur le toit", "roof", 450, 3, 12, {"luxe": 4, "decoration": 4, "confort": 4, "nature": 3, "divertissement": 3}, "Barbecue avec vue sur la ville."),
        ],
    },
    {
        "id": "station", "name": "Station spatiale",
        "description": "Un module orbital avec vue sur la Terre, loin de tout secours.",
        "situation": {"title": "Dépressurisation",
                      "description": "Un module est touché par des débris. L'équipage attend la navette de relève."},
        "criteria": need(("protection", 5), ("energie", 5), ("nourriture", 5), ("soins", 4), ("technologie", 3),
                         ("luxe", 0), ("divertissement", 0)),
        "items": [
            ("Recycleur d'air", "air", 380, 2, 25, {"soins": 4, "eau": 3, "protection": 3, "technologie": 3}, "Chaque souffle est recyclé."),
            ("Panneaux solaires", "solar", 300, 1, 20, {"energie": 5, "technologie": 3}, "L'électricité vient du Soleil."),
            ("Combinaison pressurisée", "suit", 340, 1, 18, {"protection": 5, "transport": 2, "soins": 1}, "Survivre à l'extérieur du module."),
            ("Bouclier anti-radiations", "shield", 420, 2, 20, {"protection": 5, "soins": 2}, "Contre les tempêtes solaires."),
            ("Kit de réparation", "wrench", 110, 0, 18, {"outils": 5, "technologie": 2}, "Colmater une fuite en urgence."),
            ("Rations lyophilisées", "food", 70, 0, 25, {"nourriture": 5}, "Pas bon, mais énergétique."),
            ("Hublot panoramique", "window", 260, 1, 6, {"decoration": 4, "luxe": 3, "divertissement": 3}, "La Terre en grand."),
            ("Batterie de secours", "battery", 150, 0, 18, {"energie": 5, "technologie": 1}, "Quand tout le reste lâche."),
            ("Capsule d'évacuation", "pod", 480, 3, 25, {"transport": 5, "protection": 5, "communication": 2}, "Retour express sur Terre."),
            ("Couchette magnétique", "bunk", 120, 0, 12, {"confort": 4, "abri": 2}, "Dormir sans flotter."),
            ("Robot assistant", "robot", 360, 2, 12, {"technologie": 5, "outils": 3, "divertissement": 2}, "Répare, porte et raconte des blagues."),
            ("Jardin hydroponique", "garden", 220, 1, 18, {"nourriture": 4, "nature": 4, "eau": 2, "decoration": 2, "soins": 1}, "Des légumes frais en orbite."),
        ],
    },
    {
        "id": "villa", "name": "Villa luxueuse",
        "description": "Une villa de rêve avec piscine, garage et vue sur la mer.",
        "situation": {"title": "Vacances de rêve",
                      "description": "Aménagez la villa la plus agréable possible pour recevoir vos invités."},
        "criteria": need(("confort", 5), ("luxe", 5), ("divertissement", 4), ("decoration", 3),
                         ("protection", 0), ("outils", 0)),
        "items": [
            ("Jacuzzi", "tub", 500, 2, 30, {"confort": 5, "luxe": 4, "divertissement": 3}, "Un bain à remous haut de gamme."),
            ("Canapé de salon", "sofa", 300, 1, 12, {"confort": 5, "decoration": 3, "divertissement": 1}, "Le roi du salon."),
            ("Limousine", "limo", 480, 3, 20, {"luxe": 5, "transport": 4, "confort": 3, "decoration": 1}, "Chauffeur en option."),
            ("Fontaine de chocolat", "fountain", 260, 2, 10, {"divertissement": 4, "luxe": 3, "decoration": 3, "nourriture": 2}, "Une cascade gourmande."),
            ("Piscine à débordement", "pool", 450, 3, 15, {"luxe": 4, "divertissement": 4, "decoration": 3, "eau": 2}, "L'horizon se jette dans la mer."),
            ("Home cinéma", "cinema", 380, 2, 12, {"divertissement": 5, "technologie": 4, "confort": 3}, "Écran géant et fauteuils inclinables."),
            ("Cave à vin", "wine", 240, 1, 10, {"luxe": 3, "nourriture": 2, "decoration": 2}, "Quelques grands crus."),
            ("Générateur électrique", "generator", 320, 1, 25, {"energie": 5}, "Quand le courant disparaît."),
            ("Véhicule blindé", "armored", 420, 2, 22, {"protection": 5, "transport": 5}, "Rien ne l'arrête."),
            ("Trousse médicale", "medkit", 150, 0, 25, {"soins": 5, "protection": 1}, "Un kit contenant du matériel de premiers secours."),
            ("Réserve alimentaire", "pantry", 130, 0, 25, {"nourriture": 5}, "Des mois de provisions."),
            ("Œuvre d'art", "art", 400, 3, 6, {"decoration": 5, "luxe": 5}, "Une pièce de collection."),
        ],
    },
]


def category_of(attributes: dict[str, int]) -> str:
    """Catégorie fonctionnelle = caractéristique la plus forte (la première en cas d'égalité)."""
    return max(attributes, key=lambda k: attributes[k]) if attributes else "divers"


def build() -> dict:
    locations, items = [], []
    for loc in LOCATIONS:
        for c in loc["criteria"]:
            assert c["id"] in CRITERIA, c
        locations.append({k: loc[k] for k in ("id", "name", "description", "situation", "criteria")})
        for n, (name, icon, price, rarity, base, attrs, desc) in enumerate(loc["items"], start=1):
            assert set(attrs) <= CRITERIA and all(1 <= v <= 5 for v in attrs.values()), name
            assert 0 <= base <= 50 and 0 <= rarity <= 3 and price > 0, name
            items.append({
                "id": f"{loc['id']}_{n:02d}", "location_id": loc["id"], "name": name,
                "description": desc, "category": category_of(attrs), "icon": icon,
                "price": price, "rarity": rarity, "base_points": base,
                "attributes": attrs, "image": None,
            })
    return {"locations": locations, "items": items}


if __name__ == "__main__":
    out = ROOT / "data" / "catalog.json"
    out.write_text(json.dumps(build(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(LOCATIONS)} lieux, {sum(len(l['items']) for l in LOCATIONS)} objets -> {out}")
