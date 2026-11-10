extends RefCounted
## Petits utilitaires d'interface (UI construite en code). Usage : const UI = preload("res://scripts/ui.gd")

const Background = preload("res://scripts/background.gd")
const Fx = preload("res://scripts/fx.gd")
const T = preload("res://scripts/texts.gd")
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
		margin.add_theme_constant_override("margin_" + side, 28)
	root.add_child(margin)
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	margin.add_child(scroll)
	var box := VBoxContainer.new()
	box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	box.add_theme_constant_override("separation", 16)
	scroll.add_child(box)
	return box


static func label(parent: Node, content: String, variation: String = "") -> Label:
	var l := Label.new()
	l.text = T.t(content)
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	if variation != "":
		l.theme_type_variation = variation
	parent.add_child(l)
	return l


static func button(parent: Node, content: String, variation: String = "") -> Button:
	var b := Button.new()
	b.text = T.t(content)
	if variation != "":
		b.theme_type_variation = variation
	# boutons compacts : à la largeur de leur texte (jamais pleine largeur)
	var compact: bool = variation == "BackButton" or variation == "SmallButton"
	b.custom_minimum_size = Vector2(0 if compact else 300, 0)
	if variation == "BackButton":
		b.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	elif variation != "SmallButton":
		b.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	Fx.squish(b)
	parent.add_child(b)
	return b


## Choix par pastilles (au lieu d'un menu déroulant) : une rangée qui passe à la ligne si besoin.
## Retourne le ButtonGroup ; lire la valeur avec choice_value(group). on_change(value) est facultatif.
static func choice_row(parent: Node, caption: String, labels: Array, values: Array, selected: Variant, on_change: Callable = Callable()) -> ButtonGroup:
	label(parent, caption, "FieldLabel")
	var flow := HFlowContainer.new()
	flow.add_theme_constant_override("h_separation", 10)
	flow.add_theme_constant_override("v_separation", 10)
	parent.add_child(flow)
	var group := ButtonGroup.new()
	for i in labels.size():
		var b := Button.new()
		b.text = T.t(str(labels[i]))
		b.toggle_mode = true
		b.button_group = group
		b.theme_type_variation = "ChoiceButton"
		b.set_meta("value", values[i])
		flow.add_child(b)
		b.button_pressed = values[i] == selected
	if on_change.is_valid():
		group.pressed.connect(func(btn: BaseButton) -> void: on_change.call(btn.get_meta("value")))
	return group


static func choice_value(group: ButtonGroup) -> Variant:
	var b: BaseButton = group.get_pressed_button()
	return b.get_meta("value") if b != null else null


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
		o.add_item(T.t(str(labels[i])), i)
		o.set_item_metadata(i, values[i])
		if values[i] == selected:
			o.select(i)
	parent.add_child(o)
	return o


## Bouton "Paramètres" qui ouvre la fenêtre de réglages par-dessus l'écran courant.
static func settings_button(parent: Node, host: Node) -> Button:
	var b: Button = button(parent, "Paramètres")
	b.pressed.connect(func() -> void: open_settings(host))
	return b


static func open_settings(host: Node) -> void:
	var panel_script: GDScript = load("res://scripts/settings_panel.gd")
	panel_script.call("open", host)


## Section dépliable : un bouton-titre qui montre / cache le contenu. Retourne le conteneur du contenu.
## on_toggle(expanded: bool) permet de mémoriser l'état d'un écran reconstruit à chaque mise à jour.
static func collapsible(parent: Node, title: String, expanded: bool = false, on_toggle: Callable = Callable()) -> VBoxContainer:
	var wrap := VBoxContainer.new()
	wrap.add_theme_constant_override("separation", 6)
	parent.add_child(wrap)
	var head := Button.new()
	head.alignment = HORIZONTAL_ALIGNMENT_LEFT
	head.clip_text = true
	head.custom_minimum_size = Vector2(0, 64)
	head.text = ("^ " if expanded else "v ") + title
	Fx.squish(head)
	wrap.add_child(head)
	var content := VBoxContainer.new()
	content.add_theme_constant_override("separation", 6)
	content.visible = expanded
	wrap.add_child(content)
	head.pressed.connect(func() -> void:
		content.visible = not content.visible
		head.text = ("^ " if content.visible else "v ") + title
		if on_toggle.is_valid():
			on_toggle.call(content.visible))
	return content


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
	b.custom_minimum_size = Vector2(0, 18)
	parent.add_child(b)
	return b


static func set_bar_fraction(bar: ProgressBar, fraction: float) -> void:
	bar.value = clampf(fraction, 0.0, 1.0)
	var fill := StyleBoxFlat.new()
	fill.set_corner_radius_all(6)
	if fraction > 0.5:
		fill.bg_color = Color(0.95, 0.78, 0.35, 1)
	elif fraction > 0.25:
		fill.bg_color = Color(0.95, 0.55, 0.2, 1)
	else:
		fill.bg_color = Color(0.85, 0.2, 0.2, 1)
	bar.add_theme_stylebox_override("fill", fill)


## Icônes rondes (textures générées : assets/ui_real/icon_<nom>[_hover|_pressed].png)
const ICON_PLUS := "plus"
const ICON_MINUS := "minus"
const ICON_DOLLAR := "dollar"


## Bouton-icône rond. `icon` : une des constantes ICON_*.
static func icon_button(parent: Node, icon: String) -> TextureButton:
	var b := TextureButton.new()
	b.texture_normal = load("res://assets/ui_real/icon_%s.png" % icon)
	b.texture_hover = load("res://assets/ui_real/icon_%s_hover.png" % icon)
	b.texture_pressed = load("res://assets/ui_real/icon_%s_pressed.png" % icon)
	b.ignore_texture_size = true
	b.stretch_mode = TextureButton.STRETCH_KEEP_ASPECT_CENTERED
	b.custom_minimum_size = Vector2(88, 88)
	Fx.squish(b)
	parent.add_child(b)
	return b


