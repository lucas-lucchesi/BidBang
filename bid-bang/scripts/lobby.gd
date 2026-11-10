extends Control
## Salon d'attente temps réel.

const UI = preload("res://scripts/ui.gd")
const Fx = preload("res://scripts/fx.gd")

var _box: VBoxContainer
var _players_box: VBoxContainer
var _info: Label
var _error: Label
var _start: Button
var _opening_game: bool = false


func _ready() -> void:
	if not Session.in_room():
		UI.goto(self, "res://menu.tscn")
		return
	_box = UI.page(self, str(Session.room.get("settings", {}).get("theme_id", "")))
	UI.label(_box, "Salon", "MutedLabel")
	var code_label: Label = UI.label(_box, Session.code, "TitleLabel")
	code_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	UI.label(_box, "Partagez ce code avec vos amis.", "MutedLabel").horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_info = UI.label(_box, "", "MutedLabel")
	UI.label(_box, "Joueurs", "HeadingLabel")
	_players_box = VBoxContainer.new()
	_players_box.add_theme_constant_override("separation", 8)
	_box.add_child(_players_box)
	_error = UI.label(_box, "", "ErrorLabel")
	_start = UI.button(_box, "Lancer la partie", "PrimaryButton")
	_start.pressed.connect(_on_start)
	var leave: Button = UI.button(_box, "Quitter le salon")
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
			line += " (hôte)"
		if str(d["id"]) == Session.player_id:
			line += " - vous"
		var row := PanelContainer.new()
		var l := Label.new()
		l.text = line
		if not bool(d.get("connected", false)):
			l.theme_type_variation = "MutedLabel"
			l.text += " (hors ligne)"
		row.add_child(l)
		_players_box.add_child(row)
	var s: Dictionary = room.get("settings", {})
	var mode_text: String = "Construction" if str(s.get("mode", "")) == "construction" else "Survie"
	_info.text = "%s - %d objets - budget %d € - chrono %d s - %d/%d joueurs" % [
		mode_text, int(s.get("item_count", 0)), int(s.get("budget", 0)),
		int(s.get("bid_timer", 0)), players.size(), int(room.get("max_players", 4))]
	_start.visible = Session.is_host()
	_start.disabled = players.size() < 2
	_start.text = "Lancer la partie" if players.size() >= 2 else "En attente d'un autre joueur..."


func _on_error(message: String) -> void:
	_error.text = message


func _on_connection_lost() -> void:
	_error.text = "Connexion perdue avec le serveur."


func _on_start() -> void:
	_error.text = ""
	Session.send({"type": "start_game"})


func _on_game(_game: Dictionary) -> void:
	if _opening_game:
		return
	_opening_game = true
	if not UI.goto(self, "res://scenes/game.tscn"):
		_opening_game = false
		_error.text = "Impossible d'ouvrir l'écran de partie."


func _on_leave() -> void:
	Session.leave_room()
	UI.goto(self, "res://menu.tscn")
