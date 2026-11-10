extends Control
## Salon d'attente temps réel.

const UI = preload("res://scripts/ui.gd")
const T = preload("res://scripts/texts.gd")
const Fx = preload("res://scripts/fx.gd")

var _box: VBoxContainer
var _players_box: VBoxContainer
var _info: Label
var _error: Label
var _start: Button
var _opening_game: bool = false
var _copy_hint: Label
var _copy_tween: Tween


func _ready() -> void:
	if not Session.in_room():
		UI.goto(self, "res://menu.tscn")
		return
	_box = UI.page(self, "", 0.5)
	UI.label(_box, T.t("Salon"), "MutedLabel")
	var code_button: Button = UI.button(_box, Session.code, "BackButton")
	code_button.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	code_button.add_theme_font_size_override("font_size", 32)
	code_button.add_theme_color_override("font_color", Color(1, 0.78, 0.3, 1))
	code_button.add_theme_color_override("font_hover_color", Color(1, 0.9, 0.6, 1))
	code_button.pressed.connect(_on_copy_code)
	_copy_hint = UI.label(_box, T.t("Touchez le code pour le copier."), "MutedLabel")
	_copy_hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_info = UI.label(_box, "", "MutedLabel")
	UI.label(_box, T.t("Joueurs"), "HeadingLabel")
	_players_box = VBoxContainer.new()
	_players_box.add_theme_constant_override("separation", 4)
	_box.add_child(_players_box)
	_error = UI.label(_box, "", "ErrorLabel")
	_start = UI.button(_box, T.t("Lancer la partie"), "PrimaryButton")
	_start.pressed.connect(_on_start)
	UI.settings_button(_box, self)
	var leave: Button = UI.button(_box, T.t("Quitter le salon"))
	leave.pressed.connect(_on_leave)
	Session.room_updated.connect(_refresh)
	Session.game_updated.connect(_on_game)
	Session.error_received.connect(_on_error)
	Session.connection_lost.connect(_on_connection_lost)
	_refresh(Session.room)
	Fx.stagger_in(_box, 0.06)
	if not Session.game.is_empty():
		_on_game(Session.game)


func _refresh(room: Dictionary) -> void:
	for c in _players_box.get_children():
		c.queue_free()
	var host_id: String = str(room.get("host_id", ""))
	var players: Array = room.get("players", [])
	for p in players:
		var d: Dictionary = p
		var line: String = str(d["pseudo"])
		if str(d["id"]) == host_id:
			line += T.t(" (hôte)")
		if str(d["id"]) == Session.player_id:
			line += T.t(" - vous")
		var row := PanelContainer.new()
		var l := Label.new()
		l.text = line
		if not bool(d.get("connected", false)):
			l.theme_type_variation = "MutedLabel"
			l.text += T.t(" (hors ligne)")
		row.add_child(l)
		_players_box.add_child(row)
	var s: Dictionary = room.get("settings", {})
	var mode_text: String = T.t("Construction") if str(s.get("mode", "")) == "construction" else T.t("Survie")
	_info.text = T.t("%s - %d objets - budget %d € - chrono %d s - %d/%d joueurs") % [
		mode_text, int(s.get("item_count", 0)), int(s.get("budget", 0)),
		int(s.get("bid_timer", 0)), players.size(), int(room.get("max_players", 4))]
	_start.visible = Session.is_host()
	_start.disabled = players.size() < 2
	_start.text = T.t("Lancer la partie") if players.size() >= 2 else T.t("En attente d'un autre joueur...")


func _on_error(message: String) -> void:
	_error.text = T.t(message)


func _on_connection_lost() -> void:
	_error.text = T.t("Connexion perdue avec le serveur.")


func _on_copy_code() -> void:
	DisplayServer.clipboard_set(Session.code)
	_copy_hint.text = T.t("Code copié !")
	_copy_hint.theme_type_variation = "InfoLabel"
	if _copy_tween != null:
		_copy_tween.kill()
	_copy_tween = create_tween()
	_copy_tween.tween_interval(2.0)
	_copy_tween.tween_callback(_reset_copy_hint)


func _reset_copy_hint() -> void:
	_copy_hint.text = T.t("Touchez le code pour le copier.")
	_copy_hint.theme_type_variation = "MutedLabel"


func _on_start() -> void:
	_error.text = ""
	Session.send({"type": "start_game"})


func _on_game(_game: Dictionary) -> void:
	if _opening_game:
		return
	_opening_game = true
	if not UI.goto(self, "res://scenes/game.tscn"):
		_opening_game = false
		_error.text = T.t("Impossible d'ouvrir l'écran de partie.")


func _on_leave() -> void:
	Session.leave_room()
	UI.goto(self, "res://menu.tscn")
