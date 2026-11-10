extends Control
## Fenêtre Paramètres (superposée à l'écran courant) : langue, volume, FPS.
## Ouverture : SettingsPanel.open(self) depuis n'importe quel écran.

const UI = preload("res://scripts/ui.gd")
const T = preload("res://scripts/texts.gd")

const FPS_VALUES := [30, 60, 90, 120, 0]

var _initial_language: String = ""
var _vol_bar: ProgressBar
var _vol_label: Label
var _server: LineEdit
var _error: Label


static func open(host: Node) -> void:
	var script: GDScript = load("res://scripts/settings_panel.gd")
	var panel: Control = script.new()
	host.get_tree().current_scene.add_child(panel)


func _ready() -> void:
	_initial_language = Session.language
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.7)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(dim)
	var center := CenterContainer.new()
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	var panel := PanelContainer.new()
	panel.custom_minimum_size = Vector2(600, 0)
	panel.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	panel.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	center.add_child(panel)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 14)
	panel.add_child(box)
	UI.label(box, "Paramètres", "HeadingLabel").horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	# langue
	UI.choice_row(box, "Langue", ["Français", "English"], ["fr", "en"], Session.language, _on_language)
	# volume
	UI.label(box, "Volume", "FieldLabel")
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	box.add_child(row)
	UI.icon_button(row, UI.ICON_MINUS).pressed.connect(_on_volume.bind(-10))
	_vol_bar = ProgressBar.new()
	_vol_bar.show_percentage = false
	_vol_bar.min_value = 0.0
	_vol_bar.max_value = 100.0
	_vol_bar.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_vol_bar.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_vol_bar.custom_minimum_size = Vector2(0, 24)
	row.add_child(_vol_bar)
	UI.icon_button(row, UI.ICON_PLUS).pressed.connect(_on_volume.bind(10))
	_vol_label = UI.label(box, "", "MutedLabel")
	_show_volume()
	# FPS
	var labels: Array = []
	for v in FPS_VALUES:
		labels.append("Illimité" if v == 0 else str(v))
	UI.choice_row(box, "Images par seconde (FPS)", labels, FPS_VALUES, Session.max_fps, _on_fps)
	# serveur
	_server = UI.field(box, "Adresse du serveur", Session.server_url)
	_server.text_changed.connect(_on_server_text)
	UI.label(box, "Émulateur Android : http://10.0.2.2:8000", "MutedLabel")
	_error = UI.label(box, "", "ErrorLabel")
	var close: Button = UI.button(box, "Fermer", "PrimaryButton")
	close.pressed.connect(_on_close)


func _show_volume() -> void:
	var pct: int = int(round(Session.volume * 100.0))
	_vol_bar.value = pct
	_vol_label.text = "%d %%" % pct


func _on_language(value: Variant) -> void:
	Session.language = str(value)
	Session.apply_settings()
	Session.save_settings()


func _on_volume(delta: int) -> void:
	Session.volume = clampf(Session.volume + delta / 100.0, 0.0, 1.0)
	Session.apply_settings()
	Session.save_settings()
	_show_volume()


func _on_fps(value: Variant) -> void:
	Session.max_fps = int(value)
	Session.apply_settings()
	Session.save_settings()


func _on_server_text(text: String) -> void:
	Session.server_url = text.strip_edges()
	_error.text = ""


func _on_close() -> void:
	if not Session.server_url_valid():
		_error.text = T.t("L'adresse du serveur doit commencer par http:// ou https://.")
		return
	Session.save_settings()
	var changed: bool = Session.language != _initial_language
	queue_free()
	if changed:
		get_tree().reload_current_scene()
