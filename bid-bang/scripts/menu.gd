extends Control
## Menu : pseudo, créer / rejoindre un salon. L'adresse du serveur se règle dans les Paramètres.

const UI = preload("res://scripts/ui.gd")
const T = preload("res://scripts/texts.gd")
const Fx = preload("res://scripts/fx.gd")
const Logo = preload("res://scripts/logo.gd")

var _pseudo: LineEdit
var _error: Label
var _avatar: Control


func _ready() -> void:
	var box: VBoxContainer = UI.page(self)
	box.add_theme_constant_override("separation", 18)
	var logo: Control = Logo.new()
	box.add_child(logo)
	var tag: Label = UI.label(box, T.t("Enchérissez. Construisez. Survivez."), "MutedLabel")
	tag.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var gap := Control.new()
	gap.custom_minimum_size = Vector2(0, 24)
	box.add_child(gap)
	# carte « joueur » : pastille colorée + pseudo
	var card: VBoxContainer = UI.section(box, T.t("Pseudo"))
	var line := HBoxContainer.new()
	line.add_theme_constant_override("separation", 16)
	card.add_child(line)
	_avatar = UI.avatar(line, Session.pseudo if Session.pseudo != "" else "?", 84.0)
	_pseudo = LineEdit.new()
	_pseudo.text = Session.pseudo
	_pseudo.max_length = 16
	_pseudo.placeholder_text = T.t("Votre pseudo")
	_pseudo.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_pseudo.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_pseudo.text_changed.connect(_on_pseudo_changed)
	line.add_child(_pseudo)
	_error = UI.label(box, "", "ErrorLabel")
	_error.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	if Session.notice != "":
		_error.text = T.t(Session.notice)
		Session.notice = ""
	var create: Button = UI.button(box, T.t("Créer une partie"), "PrimaryButton")
	create.pressed.connect(_on_create)
	var join: Button = UI.button(box, T.t("Rejoindre avec un code"))
	join.pressed.connect(_on_join)
	var settings: Button = UI.settings_button(box, self, "BackButton")
	settings.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	Fx.stagger_in(box, 0.07)
	if _pseudo.text == "":
		_pseudo.grab_focus()


func _on_pseudo_changed(t: String) -> void:
	_avatar.set("pseudo", t if t.strip_edges() != "" else "?")
	_avatar.queue_redraw()


func _validate() -> bool:
	var name_text: String = _pseudo.text.strip_edges()
	if name_text == "":
		_error.text = T.t("Choisissez un pseudo.")
		return false
	if not Session.server_url_valid():
		_error.text = T.t("L'adresse du serveur doit commencer par http:// ou https://.")
		UI.open_settings(self)
		return false
	Session.pseudo = name_text
	Session.save_settings()
	return true


func _on_create() -> void:
	if _validate() and not UI.goto(self, "res://scenes/create_game.tscn"):
		_error.text = T.t("Impossible d'ouvrir l'écran de création.")


func _on_join() -> void:
	if _validate() and not UI.goto(self, "res://scenes/join_game.tscn"):
		_error.text = T.t("Impossible d'ouvrir l'écran pour rejoindre.")
