extends Control
## Fenêtre Paramètres (superposée à l'écran courant) : langue, volume, FPS.
## Ouverture : SettingsPanel.open(self) depuis n'importe quel écran.

const UI = preload("res://scripts/ui.gd")
const T = preload("res://scripts/texts.gd")

const FPS_VALUES := [30, 60, 90, 120, 0]

var _initial_language: String = ""
var _vol_bar: ProgressBar
var _vol_label: Label


static func open(host: Node) -> void:
	var script: GDScript = load("res://scripts/settings_panel.gd")
	var panel: Control = script.new()
	host.get_tree().current_scene.add_child(panel)


func _ready() -> void:
	_initial_language = Session.language
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.7)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(dim)
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(300, 0)
	center.add_child(panel)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 6)
	panel.add_child(box)
	UI.label(box, "Paramètres", "HeadingLabel")
	# langue
	var lang: OptionButton = UI.option(box, "Langue", ["Français", "English"], ["fr", "en"], Session.language)
	lang.item_selected.connect(_on_language.bind(lang))
	# volume
	UI.label(box, "Volume", "FieldLabel")
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 4)
	box.add_child(row)
	UI.icon_button(row, UI.ICON_MINUS).pressed.connect(_on_volume.bind(-10))
	_vol_bar = ProgressBar.new()
	_vol_bar.show_percentage = false
	_vol_bar.min_value = 0.0
	_vol_bar.max_value = 100.0
	_vol_bar.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_vol_bar.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_vol_bar.custom_minimum_size = Vector2(0, 12)
	row.add_child(_vol_bar)
	UI.icon_button(row, UI.ICON_PLUS).pressed.connect(_on_volume.bind(10))
	_vol_label = UI.label(box, "", "MutedLabel")
	_show_volume()
	# FPS
	var labels: Array = []
	for v in FPS_VALUES:
		labels.append("Illimité" if v == 0 else str(v))
	var fps: OptionButton = UI.option(box, "Images par seconde (FPS)", labels, FPS_VALUES, Session.max_fps)
	fps.item_selected.connect(_on_fps.bind(fps))
	var close: Button = UI.button(box, "Fermer", "PrimaryButton")
	close.pressed.connect(_on_close)


func _show_volume() -> void:
	var pct: int = int(round(Session.volume * 100.0))
	_vol_bar.value = pct
	_vol_label.text = "%d %%" % pct


func _on_language(index: int, o: OptionButton) -> void:
	Session.language = str(o.get_item_metadata(index))
	Session.apply_settings()
	Session.save_settings()


func _on_volume(delta: int) -> void:
	Session.volume = clampf(Session.volume + delta / 100.0, 0.0, 1.0)
	Session.apply_settings()
	Session.save_settings()
	_show_volume()


func _on_fps(index: int, o: OptionButton) -> void:
	Session.max_fps = int(o.get_item_metadata(index))
	Session.apply_settings()
	Session.save_settings()


func _on_close() -> void:
	var changed: bool = Session.language != _initial_language
	queue_free()
	if changed:
		get_tree().reload_current_scene()
