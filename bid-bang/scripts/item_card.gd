extends RefCounted
## Carte d'objet (papier crème, contour encre, pastille de rareté) et petits helpers d'affichage. Fonctions statiques.
## Usage : const ItemCard = preload("res://scripts/item_card.gd")

const ItemArt = preload("res://scripts/item_art.gd")
const T = preload("res://scripts/texts.gd")
## Libellés des critères (identifiants du serveur : data/criteria.json). Remplacés par la liste
## reçue du serveur via register_criteria() : un nouveau critère s'affiche sans changer ce fichier.
static var criteria_labels: Dictionary = {
	"soins": "Soins", "nourriture": "Nourriture", "eau": "Eau", "protection": "Protection",
	"transport": "Transport", "energie": "Énergie", "abri": "Abri", "chaleur": "Chaleur",
	"communication": "Communication", "outils": "Outils", "confort": "Confort",
	"decoration": "Décoration", "luxe": "Luxe", "divertissement": "Divertissement",
	"nature": "Nature", "technologie": "Technologie",
}
const USEFULNESS_TEXT := {
	"high": "Très utile", "medium": "Utile", "low": "Peu utile", "none": "Presque inutile",
}
const SUCCESS := Color("#72A48A")
const DANGER := Color("#C4685A")
const ACCENT := Color("#E8A044")
const RARITY_NAMES := ["Commun", "Rare", "Épique", "Légendaire"]
## Couleurs de rareté (lisibles sur fond bleu pétrole comme sur papier crème)
const RARITY_COLORS := [
	Color("#A9BDC0"), Color("#5FA8D3"), Color("#A98BD8"), Color("#F2C14E"),
]
const PAPER := Color("#F3E4C9")
const INK := Color("#10262F")
const INK_SOFT := Color("#4A5F66")


static func register_criteria(criteria: Array) -> void:
	for c in criteria:
		var d: Dictionary = c
		if d.has("id") and d.has("label"):
			criteria_labels[str(d["id"])] = str(d["label"])


static func criterion_label(criterion_id: String) -> String:
	if criteria_labels.has(criterion_id):
		return T.t(str(criteria_labels[criterion_id]))
	# texte libre (catégorie d'une carte IA : « Gardien », « Métier »...) : affiché tel quel
	return criterion_id.substr(0, 1).to_upper() + criterion_id.substr(1)


## Libellés des critères utiles d'un objet, séparés par des virgules.
static func useful_text(item: Dictionary) -> String:
	var names: PackedStringArray = []
	for cid in item.get("useful_criteria", []):
		names.append(criterion_label(str(cid)))
	return ", ".join(names)


## « Très utile pour cette situation : Soins, Protection. » (vide si l'objet n'a pas de points de partie).
static func usefulness_line(item: Dictionary) -> String:
	if not item.has("usefulness"):
		return ""
	var level: String = str(item["usefulness"])
	var head: String = T.t(str(USEFULNESS_TEXT.get(level, "Utile")))
	var crit: String = useful_text(item)
	if crit == "" or level == "none":
		return head + T.t(" pour cette situation.")
	return head + T.t(" pour cette situation : ") + crit + "."


## Économie (positive) ou surcoût (négatif) : texte explicite, jamais seulement une couleur.
static func savings_text(savings: int) -> String:
	if savings > 0:
		return T.t("Économie %s") % format_money(savings)
	if savings < 0:
		return T.t("Surcoût %s") % format_money(-savings)
	return T.t("Prix juste")


static func savings_color(savings: int) -> Color:
	if savings > 0:
		return SUCCESS
	if savings < 0:
		return DANGER
	return Color("#B0C2C2")


static func format_money(amount: int) -> String:
	var digits: String = str(absi(amount))
	var out: String = ""
	for i in digits.length():
		if i > 0 and (digits.length() - i) % 3 == 0:
			out += " "
		out += digits[i]
	return ("-" if amount < 0 else "") + out + " €"


static func make_label(parent: Node, content: String, variation: String = "") -> Label:
	var l := Label.new()
	l.text = T.t(content)
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	if variation != "":
		l.theme_type_variation = variation
	parent.add_child(l)
	return l


## Petite pastille arrondie (rareté, prix, stat). Retourne le Label interne.
static func pill(parent: Node, content: String, bg: Color, fg: Color, font_size: int = 22) -> Label:
	var p := PanelContainer.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg
	sb.set_corner_radius_all(16)
	sb.set_border_width_all(2)
	sb.border_color = INK
	sb.content_margin_left = 14.0
	sb.content_margin_right = 14.0
	sb.content_margin_top = 3.0
	sb.content_margin_bottom = 5.0
	p.add_theme_stylebox_override("panel", sb)
	parent.add_child(p)
	var l := Label.new()
	l.text = content
	l.add_theme_font_size_override("font_size", font_size)
	l.add_theme_color_override("font_color", fg)
	l.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0))
	p.add_child(l)
	return l


static func _ink_label(parent: Node, content: String, variation: String, color: Color) -> Label:
	var l: Label = make_label(parent, content, variation)
	l.add_theme_color_override("font_color", color)
	l.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0))
	return l


## Carte d'objet. compact : disposition horizontale (listes, inventaire). art_height : taille de l'illustration.
## paid_price >= 0 : prix réellement payé (inventaire, résultats) ; le prix estimé reste affiché à côté
## et l'économie ou le surcoût est indiqué. Les points apparaissent si l'objet en a (partie en cours).
static func make_card(item: Dictionary, show_price: bool = true, with_art: bool = true, compact: bool = false, art_height: float = 190.0, paid_price: int = -1) -> PanelContainer:
	var card := PanelContainer.new()
	var rarity: int = clampi(int(item.get("rarity", 0)), 0, 3)
	var sb := StyleBoxFlat.new()
	sb.bg_color = PAPER
	sb.set_corner_radius_all(24)
	sb.set_border_width_all(4)
	sb.border_width_bottom = 9
	sb.border_color = INK
	sb.shadow_color = Color(0.04, 0.1, 0.13, 0.45)
	sb.shadow_size = 10
	sb.shadow_offset = Vector2(0, 6)
	sb.content_margin_left = 16.0
	sb.content_margin_right = 16.0
	sb.content_margin_top = 14.0
	sb.content_margin_bottom = 12.0
	card.add_theme_stylebox_override("panel", sb)
	var root: BoxContainer = HBoxContainer.new() if compact else VBoxContainer.new()
	root.add_theme_constant_override("separation", 14 if compact else 8)
	card.add_child(root)
	if with_art:
		var art: Control = ItemArt.new()
		art.call("setup", item)
		if compact:
			art.custom_minimum_size = Vector2(art_height, art_height)
			art.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		else:
			art.custom_minimum_size = Vector2(0, art_height)
		root.add_child(art)
	var box: BoxContainer
	if compact:
		box = VBoxContainer.new()
		box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		box.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		box.add_theme_constant_override("separation", 6)
		root.add_child(box)
	else:
		box = root
	var title_text: String = str(item.get("name", "?"))
	var title: Label = _ink_label(box, title_text, "HeadingLabel", INK)
	title.add_theme_font_size_override("font_size", 32 if compact else 38)
	if not compact:
		title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var tags_row: Container = HFlowContainer.new()
	tags_row.add_theme_constant_override("h_separation", 8)
	tags_row.add_theme_constant_override("v_separation", 6)
	if not compact:
		(tags_row as HFlowContainer).alignment = FlowContainer.ALIGNMENT_CENTER
	box.add_child(tags_row)
	if item.has("points"):
		pill(tags_row, T.t("%d points") % int(item["points"]), ACCENT, Color("#3A210B"), 24)
	pill(tags_row, T.t(str(RARITY_NAMES[rarity])), RARITY_COLORS[rarity], INK)
	if show_price:
		pill(tags_row, T.t("estimé ") + format_money(int(item.get("price", 0))), Color("#2C5362"), Color("#F3E4C9"))
	if paid_price >= 0:
		pill(tags_row, T.t("payé ") + format_money(paid_price), Color("#2C5362"), Color("#F3E4C9"))
		var savings: int = int(item.get("price", 0)) - paid_price
		var fg: Color = INK if savings >= 0 else Color("#F3E4C9")
		pill(tags_row, savings_text(savings), savings_color(savings), fg, 20)
	# carte créée par l'IA (joueur, métier, personnalité, objet...) : son poste ou son type
	var ai_card: bool = str(item.get("source", "")) == "ai"
	if ai_card and str(item.get("category", "")) != "":
		pill(tags_row, criterion_label(str(item["category"])), Color("#E4D0A8"), INK, 20)
	# caractéristiques : seulement celles utiles à la situation si elle est connue, sinon toutes
	var shown: Array = item.get("useful_criteria", [])
	if shown.is_empty() and not item.has("usefulness"):
		shown = (item.get("attributes", {}) as Dictionary).keys()
	var attrs: Dictionary = item.get("attributes", {})
	for key in shown:
		if attrs.has(key):
			pill(tags_row, "%s %d" % [criterion_label(str(key)), int(attrs[key])], Color("#E4D0A8"), INK, 20)
	if ai_card and not compact and str(item.get("description", "")) != "":
		var dl: Label = _ink_label(box, str(item["description"]), "MutedLabel", INK_SOFT)
		dl.add_theme_font_size_override("font_size", 20)
		dl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var line: String = usefulness_line(item)
	if line != "":
		var ul: Label = _ink_label(box, line, "MutedLabel", INK_SOFT)
		ul.add_theme_font_size_override("font_size", 20)
		if not compact:
			ul.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	return card
