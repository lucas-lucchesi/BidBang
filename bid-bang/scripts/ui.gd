extends RefCounted
## Petits utilitaires d'interface (UI construite en code). Usage : const UI = preload("res://scripts/ui.gd")

const BG_COLOR := Color(0.06, 0.07, 0.12, 1)


## Fond + marges + colonne de défilement. Retourne la VBoxContainer où ajouter le contenu.
static func page(root: Control) -> VBoxContainer:
	var bg := ColorRect.new()
	bg.color = BG_COLOR
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.add_child(bg)
	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 24)
	root.add_child(margin)
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	margin.add_child(scroll)
	var box := VBoxContainer.new()
	box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	box.add_theme_constant_override("separation", 14)
	scroll.add_child(box)
	return box


static func label(parent: Node, content: String, variation: String = "") -> Label:
	var l := Label.new()
	l.text = content
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	if variation != "":
		l.theme_type_variation = variation
	parent.add_child(l)
	return l


static func button(parent: Node, content: String, variation: String = "") -> Button:
	var b := Button.new()
	b.text = content
	if variation != "":
		b.theme_type_variation = variation
	parent.add_child(b)
	return b


static func field(parent: Node, caption: String, value: String = "", max_len: int = 0) -> LineEdit:
	label(parent, caption, "FieldLabel")
	var e := LineEdit.new()
	e.text = value
	if max_len > 0:
		e.max_length = max_len
	parent.add_child(e)
	return e


static func option(parent: Node, caption: String, labels: Array, values: Array, selected: Variant) -> OptionButton:
	label(parent, caption, "FieldLabel")
	var o := OptionButton.new()
	for i in labels.size():
		o.add_item(str(labels[i]), i)
		o.set_item_metadata(i, values[i])
		if values[i] == selected:
			o.select(i)
	parent.add_child(o)
	return o


static func goto(node: Node, path: String) -> bool:
	var err: int = node.get_tree().change_scene_to_file(path)
	return err == OK


## Pastille arrondie (variation : "ChipPanel" ou "MoneyChip"). Retourne le Label interne.
static func chip(parent: Node, content: String, variation: String = "ChipPanel", label_variation: String = "") -> Label:
	var p := PanelContainer.new()
	p.theme_type_variation = variation
	p.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	parent.add_child(p)
	var l := Label.new()
	l.text = content
	if label_variation != "":
		l.theme_type_variation = label_variation
	p.add_child(l)
	return l


## Barre de progression colorée (vert -> orange -> rouge selon la fraction restante).
static func timer_bar(parent: Node) -> ProgressBar:
	var b := ProgressBar.new()
	b.show_percentage = false
	b.min_value = 0.0
	b.max_value = 1.0
	b.value = 1.0
	b.custom_minimum_size = Vector2(0, 16)
	parent.add_child(b)
	return b


static func set_bar_fraction(bar: ProgressBar, fraction: float) -> void:
	bar.value = clampf(fraction, 0.0, 1.0)
	var fill := StyleBoxFlat.new()
	fill.set_corner_radius_all(8)
	if fraction > 0.5:
		fill.bg_color = Color(0.25, 0.8, 0.68, 1)
	elif fraction > 0.25:
		fill.bg_color = Color(0.96, 0.62, 0.12, 1)
	else:
		fill.bg_color = Color(1, 0.4, 0.4, 1)
	bar.add_theme_stylebox_override("fill", fill)
