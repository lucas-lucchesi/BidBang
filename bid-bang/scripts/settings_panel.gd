extends Node
## Fenêtre Paramètres (superposée à l'écran courant) : son, langue, préférences, serveur.
## Ouverture : SettingsPanel.open(self) depuis n'importe quel écran.

const UI = preload("res://scripts/ui.gd")
const T = preload("res://scripts/texts.gd")

const FPS_VALUES := [30, 60, 90, 120, 0]

var _initial_language: String = ""
var _initial_theme: String = ""
var _vol_bar: ProgressBar
var _vol_label: Label
var _server: LineEdit
var _error: Label


static func open(host: Node) -> void:
	var script: GDScript = load("res://scripts/settings_panel.gd")
	var panel: Node = script.new()
	host.get_tree().current_scene.add_child(panel)


func _ready() -> void:
	_initial_language = Session.language
	_initial_theme = Session.theme_mode
	var content: VBoxContainer = UI.modal(self, "Paramètres", "Fermer", _can_close)
	get_meta_root(content).tree_exited.connect(queue_free)
	# son
	var sound: VBoxContainer = UI.section(content, T.t("Son"), "RowPanel")
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	sound.add_child(row)
	UI.icon_button(row, UI.ICON_MINUS).pressed.connect(_on_volume.bind(-10))
	_vol_bar = ProgressBar.new()
	_vol_bar.show_percentage = false
	_vol_bar.min_value = 0.0
	_vol_bar.max_value = 100.0
	_vol_bar.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_vol_bar.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_vol_bar.custom_minimum_size = Vector2(0, 28)
	row.add_child(_vol_bar)
	UI.icon_button(row, UI.ICON_PLUS).pressed.connect(_on_volume.bind(10))
	_vol_label = UI.label(sound, "", "MutedLabel")
	_vol_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_show_volume()
	# apparence
	var look: VBoxContainer = UI.section(content, T.t("Apparence"), "RowPanel")
	UI.choice_row(look, "", ["Mode sombre", "Mode clair"], ["dark", "light"], Session.theme_mode, _on_theme)
	# langue
	var lang: VBoxContainer = UI.section(content, T.t("Langue"), "RowPanel")
	UI.choice_row(lang, "", ["Français", "English"], ["fr", "en"], Session.language, _on_language)
	# préférences
	var labels: Array = []
	for v in FPS_VALUES:
		labels.append("Illimité" if v == 0 else str(v))
	var prefs: VBoxContainer = UI.section(content, T.t("Images par seconde (FPS)"), "RowPanel")
	UI.choice_row(prefs, "", labels, FPS_VALUES, Session.max_fps, _on_fps)
	# serveur
	var srv: VBoxContainer = UI.section(content, T.t("Adresse du serveur"), "RowPanel")
	_server = UI.field(srv, "", Session.server_url)
	_server.text_changed.connect(_on_server_text)
	UI.label(srv, "Émulateur Android : http://10.0.2.2:8000", "MutedLabel")
	_error = UI.label(content, "", "ErrorLabel")


func get_meta_root(content: Control) -> Node:
	return content.get_meta("modal_root")


## Appelé par le bouton « Fermer » : refuse la fermeture si l'adresse du serveur est invalide.
func _can_close() -> bool:
	if not Session.server_url_valid():
		_error.text = T.t("L'adresse du serveur doit commencer par http:// ou https://.")
		return false
	Session.save_settings()
	if Session.language != _initial_language or Session.theme_mode != _initial_theme:
		get_tree().call_deferred("reload_current_scene")
	return true


func _show_volume() -> void:
	var pct: int = int(round(Session.volume * 100.0))
	_vol_bar.value = pct
	_vol_label.text = "%d %%" % pct


func _on_theme(value: Variant) -> void:
	Session.theme_mode = str(value)
	Session.apply_settings()
	Session.save_settings()


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
