extends Control
## Salon d'attente temps réel.

const UI = preload("res://scripts/ui.gd")
const T = preload("res://scripts/texts.gd")
const Fx = preload("res://scripts/fx.gd")

var _box: VBoxContainer
var _players_box: VBoxContainer
var _info: Label
var _kind: Label
var _situation: Label
var _heading: Label
var _seen: Dictionary = {}
var _error: Label
var _start: Button
var _opening_game: bool = false
var _copy_hint: Label
var _copy_tween: Tween


func _ready() -> void:
	if not Session.in_room():
		UI.goto(self, "res://menu.tscn")
		return
	_box = UI.page(self, str(Session.room.get("settings", {}).get("theme_id", "")), 0.5)
	# billet d'invitation : le code en grand, touchez pour copier
	var ticket: VBoxContainer = UI.section(_box, "", "HeroPanel")
	UI.label(ticket, T.t("Code d'invitation"), "SectionLabel").horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var code_button: Button = UI.button(ticket, Session.code, "BackButton")
	code_button.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	code_button.add_theme_font_size_override("font_size", 76)
	var code_col := Color("#193A49") if Session.is_light() else Color("#F3E4C9")
	var code_hi := Color("#BD6B1A") if Session.is_light() else Color("#E8A044")
	code_button.add_theme_color_override("font_color", code_col)
	code_button.add_theme_color_override("font_hover_color", code_hi)
	code_button.add_theme_color_override("font_pressed_color", code_hi)
	code_button.pressed.connect(_on_copy_code)
	_copy_hint = UI.label(ticket, T.t("Touchez le code pour le copier."), "MutedLabel")
	_copy_hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	# type de partie et situation (parties personnalisées / IA)
	_kind = UI.label(_box, "", "HeadingLabel")
	_kind.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_kind.visible = false
	_situation = UI.label(_box, "", "InfoLabel")
	_situation.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_situation.visible = false
	_info = UI.label(_box, "", "MutedLabel")
	_info.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_heading = UI.label(_box, T.t("Joueurs"), "HeadingLabel")
	_players_box = VBoxContainer.new()
	_players_box.add_theme_constant_override("separation", 12)
	_box.add_child(_players_box)
	_error = UI.label(_box, "", "ErrorLabel")
	_start = UI.button(_box, T.t("Lancer la partie"), "PrimaryButton")
	_start.pressed.connect(_on_start)
	var leave: Button = UI.button(_box, T.t("Quitter le salon"), "DangerButton")
	leave.pressed.connect(_on_leave)
	var st: Button = UI.settings_button(_box, self, "BackButton")
	st.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	Session.room_updated.connect(_refresh)
	Session.game_updated.connect(_on_game)
	Session.error_received.connect(_on_error)
	Session.connection_lost.connect(_on_connection_lost)
	Session.kicked.connect(func() -> void: UI.goto(self, "res://menu.tscn"))
	_refresh(Session.room)
	Fx.stagger_in(_box, 0.06)
	if not Session.game.is_empty():
		_on_game(Session.game)


func _refresh(room: Dictionary) -> void:
	for c in _players_box.get_children():
		c.queue_free()
	var host_id: String = str(room.get("host_id", ""))
	var players: Array = room.get("players", [])
	_heading.text = "%s (%d/%d)" % [T.t("Joueurs"), players.size(), int(room.get("max_players", 4))]
	for p in players:
		var d: Dictionary = p
		var pid: String = str(d["id"])
		var online: bool = bool(d.get("connected", false))
		var row: HBoxContainer = UI.row(_players_box)
		var av: Control = UI.avatar(row, str(d["pseudo"]), 68.0, pid == host_id)
		if not online:
			av.modulate.a = 0.5
		var names := VBoxContainer.new()
		names.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		names.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		names.add_theme_constant_override("separation", 0)
		row.add_child(names)
		var nl: Label = UI.label(names, str(d["pseudo"]), "HeadingLabel")
		nl.add_theme_font_size_override("font_size", 32)
		nl.clip_text = true
		var sub: String = T.t("Hôte") if pid == host_id else T.t("Joueur")
		if pid == Session.player_id:
			sub += T.t(" - vous")
		if not online:
			sub = T.t("Hors ligne")
		UI.label(names, sub, "MutedLabel")
		var dot := Label.new()
		dot.text = T.t("En ligne") if online else ""
		dot.theme_type_variation = "InfoLabel"
		row.add_child(dot)
		if Session.is_host() and pid != Session.player_id:
			var kick: Button = UI.button(row, T.t("Exclure"), "SmallButton")
			kick.pressed.connect(_on_kick.bind(pid))
		if not _seen.has(pid):
			_seen[pid] = true
			Fx.pop(row.get_parent() as Control, 1.06)
	var s: Dictionary = room.get("settings", {})
	var mode_names := {"construction": "Construction", "aveugle": "Enchère à l'aveugle", "survie": "Survie"}
	var mode_text: String = T.t(str(mode_names.get(str(s.get("mode", "")), "Construction")))
	_info.text = T.t("%s - %d objets - budget %d € - chrono %d s - %d/%d joueurs") % [
		mode_text, int(s.get("item_count", 0)), int(s.get("budget", 0)),
		int(s.get("bid_timer", 0)), players.size(), int(room.get("max_players", 4))]
	var creation: String = str(s.get("creation_type", "classic"))
	var custom: bool = creation != "classic"
	var kinds := {"classic": "Partie classique", "custom": "Partie personnalisée", "ai": "Partie avec IA"}
	_kind.visible = true
	_kind.text = "%s - %s" % [T.t(str(kinds.get(creation, "Partie classique"))), mode_text]
	_situation.visible = custom
	var ready_to_start: bool = true
	if custom:
		var scenario: Dictionary = s.get("scenario", {})
		_situation.text = str(scenario.get("description", ""))
		var chosen: Array = s.get("item_ids", [])
		_info.text += "\n" + T.t("%d objets sélectionnés, %d mis aux enchères") % [chosen.size(), int(s.get("item_count", 0))]
		ready_to_start = bool(s.get("ready", true))
	_start.visible = Session.is_host()
	_start.disabled = players.size() < 2 or not ready_to_start
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


func _on_kick(target_id: String) -> void:
	_error.text = ""
	Session.send({"type": "kick", "target": target_id})


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
