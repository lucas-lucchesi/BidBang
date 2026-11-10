extends Control
## Menu : pseudo, adresse du serveur, créer / rejoindre un salon.

const UI = preload("res://scripts/ui.gd")
const Logo = preload("res://scripts/logo.gd")
const Fx = preload("res://scripts/fx.gd")

var _pseudo: LineEdit
var _server: LineEdit
var _error: Label


func _ready() -> void:
	var box: VBoxContainer = UI.page(self)
	box.add_child(Logo.new())
	UI.label(box, "BidBang", "TitleLabel").horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	UI.label(box, "Enchérissez. Construisez. Survivez.", "MutedLabel").horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var gap := Control.new()
	gap.custom_minimum_size = Vector2(0, 30)
	box.add_child(gap)
	_pseudo = UI.field(box, "Pseudo", Session.pseudo, 16)
	_pseudo.placeholder_text = "Votre pseudo"
	_server = UI.field(box, "Adresse du serveur", Session.server_url)
	_error = UI.label(box, "", "ErrorLabel")
	var create: Button = UI.button(box, "Créer une partie", "PrimaryButton")
	create.pressed.connect(_on_create)
	var join: Button = UI.button(box, "Rejoindre avec un code")
	join.pressed.connect(_on_join)
	Fx.stagger_in(box, 0.07)


func _validate() -> bool:
	var name_text: String = _pseudo.text.strip_edges()
	if name_text == "":
		_error.text = "Choisissez un pseudo."
		return false
	var url: String = _server.text.strip_edges()
	if not (url.begins_with("http://") or url.begins_with("https://")):
		_error.text = "L'adresse doit commencer par http:// ou https://."
		return false
	Session.pseudo = name_text
	Session.server_url = url
	Session.save_settings()
	return true


func _on_create() -> void:
	if _validate() and not UI.goto(self, "res://scenes/create_game.tscn"):
		_error.text = "Impossible d'ouvrir l'écran de création."


func _on_join() -> void:
	if _validate() and not UI.goto(self, "res://scenes/join_game.tscn"):
		_error.text = "Impossible d'ouvrir l'écran pour rejoindre."
