extends RefCounted
## Podium de fin de partie : les 3 premiers sur des marches qui montent une à une ; un 4e joueur
## éventuel apparaît dans une ligne sous le podium. Classement : points, puis budget restant.
## Usage : Podium.build(parent, results)  (results = game["results"], déjà triés)

const ItemCard = preload("res://scripts/item_card.gd")
const T = preload("res://scripts/texts.gd")
const Avatar = preload("res://scripts/avatar.gd")

const COLUMN_WIDTH := 200.0
const HEIGHTS := {1: 170.0, 2: 120.0, 3: 84.0}
const COLORS := {
	1: Color("#F2C14E"), 2: Color("#BFD0D4"), 3: Color("#D79B6A"),
}
const INK := Color("#10262F")


static func build(parent: Node, results: Array) -> void:
	var top: Array = results.slice(0, mini(3, results.size()))
	var order: Array = []
	if top.size() >= 3:
		order = [top[1], top[0], top[2]]
	elif top.size() == 2:
		order = [top[1], top[0]]
	else:
		order = top
	var row := HBoxContainer.new()
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	row.add_theme_constant_override("separation", 10)
	row.custom_minimum_size = Vector2(0, 500)
	parent.add_child(row)
	for r in order:
		var d: Dictionary = r
		_column(row, d, order.size())
	for r in results.slice(3):
		var d: Dictionary = r
		_extra_line(parent, d)


static func _extra_line(parent: Node, d: Dictionary) -> void:
	var panel := PanelContainer.new()
	panel.theme_type_variation = "RowPanel"
	parent.add_child(panel)
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 14)
	panel.add_child(h)
	h.add_child(Avatar.make(str(d["pseudo"]), 56.0, false))
	var col := VBoxContainer.new()
	col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	col.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	col.add_theme_constant_override("separation", -2)
	h.add_child(col)
	var nm: Label = ItemCard.make_label(col, "%d. %s" % [int(d["rank"]), str(d["pseudo"])], "")
	nm.autowrap_mode = TextServer.AUTOWRAP_OFF
	nm.clip_text = true
	ItemCard.make_label(col, "%s - %s" % [T.t("%d pts") % int(d["score"]),
		T.t("reste %s") % ItemCard.format_money(int(d["budget"]))], "MutedLabel")


static func _column(row: HBoxContainer, d: Dictionary, count: int) -> void:
	var rank: int = clampi(int(d["rank"]), 1, 3)
	var col := VBoxContainer.new()
	col.size_flags_vertical = Control.SIZE_SHRINK_END
	col.add_theme_constant_override("separation", 4)
	row.add_child(col)
	var av: Control = Avatar.make(str(d["pseudo"]), 96.0 if rank == 1 else 80.0, rank == 1)
	col.add_child(av)
	var name_label: Label = ItemCard.make_label(col, str(d["pseudo"]), "")
	name_label.custom_minimum_size = Vector2(COLUMN_WIDTH, 0)
	name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	name_label.autowrap_mode = TextServer.AUTOWRAP_OFF
	name_label.clip_text = true
	if str(d["player_id"]) == Session.player_id:
		name_label.add_theme_color_override("font_color", Color("#E8A044"))
	var score: Label = ItemCard.make_label(col, T.t("%d pts") % int(d["score"]), "MutedLabel")
	score.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var money: Label = ItemCard.make_label(col, T.t("reste %s") % ItemCard.format_money(int(d["budget"])), "MutedLabel")
	money.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	money.add_theme_font_size_override("font_size", 20)
	var block := PanelContainer.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = COLORS[rank]
	sb.border_width_left = 4
	sb.border_width_right = 4
	sb.border_width_top = 4
	sb.border_color = INK
	sb.corner_radius_top_left = 20
	sb.corner_radius_top_right = 20
	sb.shadow_color = Color(0.04, 0.1, 0.13, 0.5)
	sb.shadow_size = 8
	sb.content_margin_top = 10.0
	block.add_theme_stylebox_override("panel", sb)
	block.custom_minimum_size = Vector2(COLUMN_WIDTH, 0)
	col.add_child(block)
	var num: Label = ItemCard.make_label(block, str(int(d["rank"])), "HeadingLabel")
	num.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	num.add_theme_font_size_override("font_size", 56)
	num.add_theme_color_override("font_color", INK)
	num.add_theme_color_override("font_shadow_color", Color(1, 1, 1, 0.35))
	# la marche monte : 3e d'abord, puis 2e, puis 1re
	var target: float = HEIGHTS[rank]
	var delay: float = 0.3 + (3 - rank) * 0.45
	# le joueur apparaît quand sa marche est montée
	col.modulate.a = 0.0
	var appear: Tween = col.create_tween()
	appear.tween_property(col, "modulate:a", 1.0, 0.25).set_delay(delay)
	var tw: Tween = block.create_tween()
	tw.tween_property(block, "custom_minimum_size", Vector2(COLUMN_WIDTH, target), 0.5).set_delay(delay).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
