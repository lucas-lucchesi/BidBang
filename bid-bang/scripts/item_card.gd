extends RefCounted
## Carte d'objet (papier crème, contour encre, pastille de rareté) et petits helpers d'affichage. Fonctions statiques.
## Usage : const ItemCard = preload("res://scripts/item_card.gd")

const ItemArt = preload("res://scripts/item_art.gd")
const T = preload("res://scripts/texts.gd")
const STAT_NAMES := {
	"confort": "Confort", "style": "Style", "utilite": "Utilité",
	"securite": "Sécurité", "sante": "Santé",
}
const RARITY_NAMES := ["Commun", "Rare", "Épique", "Légendaire"]
## Couleurs de rareté (lisibles sur fond bleu pétrole comme sur papier crème)
const RARITY_COLORS := [
	Color("#A9BDC0"), Color("#5FA8D3"), Color("#A98BD8"), Color("#F2C14E"),
]
const PAPER := Color("#F3E4C9")
const INK := Color("#10262F")
const INK_SOFT := Color("#4A5F66")


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


static func stats_text(item: Dictionary) -> String:
	var parts: PackedStringArray = []
	var stats: Dictionary = item.get("stats", {})
	for key in STAT_NAMES:
		var v: int = int(stats.get(key, 0))
		if v > 0:
			parts.append("%s %d" % [T.t(STAT_NAMES[key]), v])
	return " - ".join(parts)


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
## paid : le prix affiché est celui payé (inventaire) plutôt que le prix indicatif.
static func make_card(item: Dictionary, show_price: bool = true, with_art: bool = true, compact: bool = false, art_height: float = 190.0, paid: bool = false) -> PanelContainer:
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
	var title: Label = _ink_label(box, str(item.get("name", "?")), "HeadingLabel", INK)
	title.add_theme_font_size_override("font_size", 32 if compact else 38)
	if not compact:
		title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var tags_row: Container = HFlowContainer.new()
	tags_row.add_theme_constant_override("h_separation", 8)
	tags_row.add_theme_constant_override("v_separation", 6)
	if not compact:
		(tags_row as HFlowContainer).alignment = FlowContainer.ALIGNMENT_CENTER
	box.add_child(tags_row)
	pill(tags_row, T.t(str(RARITY_NAMES[rarity])), RARITY_COLORS[rarity], INK)
	if show_price:
		var price_text: String = format_money(int(item.get("price", 0)))
		if paid:
			price_text = T.t("payé ") + price_text
		pill(tags_row, price_text, Color("#2C5362"), Color("#F3E4C9"))
	var stats: Dictionary = item.get("stats", {})
	for key in STAT_NAMES:
		var v: int = int(stats.get(key, 0))
		if v > 0:
			pill(tags_row, "%s %d" % [T.t(STAT_NAMES[key]), v], Color("#E4D0A8"), INK, 20)
	var tags: Array = item.get("tags", [])
	if tags.size() > 0 and not compact:
		var tl: Label = _ink_label(box, T.t("Tags : ") + ", ".join(PackedStringArray(tags)), "MutedLabel", INK_SOFT)
		tl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		tl.add_theme_font_size_override("font_size", 20)
	return card
