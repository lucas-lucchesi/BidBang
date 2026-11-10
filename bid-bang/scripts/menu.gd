extends Control
## Menu : pseudo, créer / rejoindre un salon. L'adresse du serveur se règle dans les Paramètres.

const UI = preload("res://scripts/ui.gd")
const T = preload("res://scripts/texts.gd")
const Fx = preload("res://scripts/fx.gd")

var _pseudo: LineEdit
var _error: Label


func _ready() -> void:
	var box: VBoxContainer = UI.page(self)
	UI.label(box, "BidBang", "TitleLabel").horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	UI.label(box, T.t("Enchérissez. Construisez. Survivez."), "MutedLabel").horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var gap := Control.new()  # laisse voir l'enseigne du fond
	gap.custom_minimum_size = Vector2(0, 215)
	box.add_child(gap)
	_pseudo = UI.field(box, T.t("Pseudo"), Session.pseudo, 16)
	_pseudo.placeholder_text = T.t("Votre pseudo")
	_error = UI.label(box, "", "ErrorLabel")
	var create: Button = UI.button(box, T.t("Créer une partie"), "PrimaryButton")
	create.pressed.connect(_on_create)
	var join: Button = UI.button(box, T.t("Rejoindre avec un code"))
	join.pressed.connect(_on_join)
	UI.settings_button(box, self)
	Fx.stagger_in(box, 0.07)
	if _pseudo.text == "":
		_pseudo.grab_focus()


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
