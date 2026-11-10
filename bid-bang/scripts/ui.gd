extends RefCounted
## Petits utilitaires d'interface (UI construite en code). Usage : const UI = preload("res://scripts/ui.gd")

const Background = preload("res://scripts/background.gd")
const Fx = preload("res://scripts/fx.gd")
const BG_COLOR := Color(0.06, 0.07, 0.12, 1)


## Fond + marges + colonne de défilement. Retourne la VBoxContainer où ajouter le contenu.
static func page(root: Control, scene_id: String = "", dim: float = 0.0) -> VBoxContainer:
	var bg: Control = Background.new()
	bg.set("scene_id", scene_id)
	bg.set("dim", dim)
	root.add_child(bg)
	root.set_meta("background", bg)
	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 12)
	root.add_child(margin)
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	margin.add_child(scroll)
	var box := VBoxContainer.new()
	box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	box.add_theme_constant_override("separation", 8)
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
	b.custom_minimum_size = Vector2(0, 24)
	Fx.squish(b)
	parent.add_child(b)
	return b


static func field(parent: Node, caption: String, value: String = "", max_len: int = 0) -> LineEdit:
	label(parent, caption, "FieldLabel")
	var e := LineEdit.new()
	e.text = value
	if max_len > 0:
		e.max_length = max_len
	e.caret_blink = true
	e.caret_blink_interval = 0.5
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
	b.custom_minimum_size = Vector2(0, 8)
	parent.add_child(b)
	return b


static func set_bar_fraction(bar: ProgressBar, fraction: float) -> void:
	bar.value = clampf(fraction, 0.0, 1.0)
	var fill := StyleBoxFlat.new()
	if fraction > 0.5:
		fill.bg_color = Color(0.45, 0.85, 0.55, 1)
	elif fraction > 0.25:
		fill.bg_color = Color(1, 0.75, 0.25, 1)
	else:
		fill.bg_color = Color(1, 0.4, 0.35, 1)
	bar.add_theme_stylebox_override("fill", fill)


const ICONS = preload("res://assets/ui/freebuttons2.png")
## Position des icônes dans freebuttons2.png : (ligne, paire). Jeu foncé = colonnes 0-3, clair = 4-7.
const ICON_PLUS := Vector2i(1, 0)
const ICON_CHECK := Vector2i(1, 1)
const ICON_CROSS := Vector2i(2, 0)
const ICON_MINUS := Vector2i(2, 1)
const ICON_DOLLAR := Vector2i(3, 1)


static func _icon_cell(row: int, col: int) -> AtlasTexture:
	var t := AtlasTexture.new()
	t.atlas = ICONS
	t.region = Rect2(col * 16, row * 16, 16, 16)
	return t


## Bouton-icône en pixel art (32x32 = échelle x2). `icon` : une des constantes ICON_*.
static func icon_button(parent: Node, icon: Vector2i) -> TextureButton:
	var b := TextureButton.new()
	b.texture_normal = _icon_cell(icon.x, icon.y * 2)
	b.texture_pressed = _icon_cell(icon.x, icon.y * 2 + 1)
	b.texture_hover = _icon_cell(icon.x, 4 + icon.y * 2)
	b.ignore_texture_size = true
	b.stretch_mode = TextureButton.STRETCH_SCALE
	b.custom_minimum_size = Vector2(32, 32)
	Fx.squish(b)
	parent.add_child(b)
	return b
