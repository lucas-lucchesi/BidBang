extends RefCounted
## Podium de fin de partie : les 3 premiers sur des marches qui montent une à une.
## Usage : Podium.build(parent, results)  (results = game["results"], déjà triés)

const ItemCard = preload("res://scripts/item_card.gd")
const T = preload("res://scripts/texts.gd")
const Crown = preload("res://scripts/crown.gd")

const COLUMN_WIDTH := 100.0
const HEIGHTS := {1: 70.0, 2: 48.0, 3: 30.0}
const COLORS := {
	1: Color(1, 0.78, 0.25), 2: Color(0.78, 0.8, 0.88), 3: Color(0.8, 0.52, 0.3),
}


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
	row.add_theme_constant_override("separation", 4)
	row.custom_minimum_size = Vector2(0, 170)
	parent.add_child(row)
	for r in order:
		var d: Dictionary = r
		_column(row, d, order.size())


static func _column(row: HBoxContainer, d: Dictionary, count: int) -> void:
	var rank: int = clampi(int(d["rank"]), 1, 3)
	var col := VBoxContainer.new()
	col.size_flags_vertical = Control.SIZE_SHRINK_END
	col.add_theme_constant_override("separation", 2)
	row.add_child(col)
	if rank == 1:
		col.add_child(Crown.new())
	var name_label: Label = ItemCard.make_label(col, str(d["pseudo"]), "")
	name_label.custom_minimum_size = Vector2(COLUMN_WIDTH, 0)
	name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	if str(d["player_id"]) == Session.player_id:
		name_label.add_theme_color_override("font_color", Color(1, 0.85, 0.4))
	var score: Label = ItemCard.make_label(col, T.t("%d pts") % int(d["score"]), "MutedLabel")
	score.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var block := PanelContainer.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = COLORS[rank]
	sb.border_width_left = 2
	sb.border_width_right = 2
	sb.border_width_top = 2
	sb.border_color = Color(0.2, 0.1, 0.05)
	sb.content_margin_top = 4.0
	block.add_theme_stylebox_override("panel", sb)
	block.custom_minimum_size = Vector2(COLUMN_WIDTH, 0)
	col.add_child(block)
	var num: Label = ItemCard.make_label(block, str(int(d["rank"])), "HeadingLabel")
	num.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	num.add_theme_color_override("font_color", Color(0.25, 0.12, 0.05))
	num.add_theme_color_override("font_shadow_color", Color(1, 1, 1, 0.35))
	# la marche monte : 3e d'abord, puis 2e, puis 1re
	var target: float = HEIGHTS[rank]
	var delay: float = 0.3 + (3 - rank) * 0.45
	var tw: Tween = block.create_tween()
	tw.tween_property(block, "custom_minimum_size", Vector2(COLUMN_WIDTH, target), 0.5).set_delay(delay).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
