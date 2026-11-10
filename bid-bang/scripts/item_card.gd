extends RefCounted
## Carte d'objet (texte seul) et petits helpers d'affichage. Fonctions statiques.
## Usage : const ItemCard = preload("res://scripts/item_card.gd")

const STAT_NAMES := {
	"confort": "Confort", "style": "Style", "utilite": "Utilité",
	"securite": "Sécurité", "sante": "Santé",
}
const RARITY_NAMES := ["Commun", "Rare", "Épique", "Légendaire"]
const RARITY_COLORS := [
	Color(0.7, 0.72, 0.8, 1), Color(0.4, 0.7, 1, 1),
	Color(0.75, 0.5, 1, 1), Color(1, 0.75, 0.25, 1),
]


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
	l.text = content
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
			parts.append("%s %d" % [STAT_NAMES[key], v])
	return " - ".join(parts)


static func make_card(item: Dictionary, show_price: bool = true) -> PanelContainer:
	var card := PanelContainer.new()
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 6)
	card.add_child(box)
	var rarity: int = clampi(int(item.get("rarity", 0)), 0, 3)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.13, 0.15, 0.23, 1)
	sb.set_corner_radius_all(18)
	sb.border_width_left = 10
	sb.border_color = RARITY_COLORS[rarity]
	sb.content_margin_left = 22.0
	sb.content_margin_right = 18.0
	sb.content_margin_top = 16.0
	sb.content_margin_bottom = 16.0
	card.add_theme_stylebox_override("panel", sb)
	var title: Label = make_label(box, str(item.get("name", "?")), "HeadingLabel")
	title.add_theme_color_override("font_color", RARITY_COLORS[rarity])
	var sub: String = str(RARITY_NAMES[rarity])
	if show_price:
		sub += " - " + format_money(int(item.get("price", 0)))
	make_label(box, sub, "MutedLabel")
	make_label(box, stats_text(item))
	var tags: Array = item.get("tags", [])
	if tags.size() > 0:
		make_label(box, "Tags : " + ", ".join(PackedStringArray(tags)), "MutedLabel")
	return card
