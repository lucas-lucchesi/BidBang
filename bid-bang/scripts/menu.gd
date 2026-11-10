extends Control
## Menu : pseudo, adresse du serveur, créer / rejoindre un salon.

const UI = preload("res://scripts/ui.gd")
const T = preload("res://scripts/texts.gd")
const Fx = preload("res://scripts/fx.gd")

var _pseudo: LineEdit
var _server: LineEdit
var _error: Label
var _server_toggle: Button
var _server_panel: VBoxContainer


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
	_build_server_option(box)
	UI.settings_button(box, self)
	Fx.stagger_in(box, 0.07)
	if _pseudo.text == "":
		_pseudo.grab_focus()


## Réglage du serveur : masqué par défaut, ouvert par un petit bouton.
func _build_server_option(box: VBoxContainer) -> void:
	_server_toggle = UI.button(box, T.t("Options du serveur  ") + "v", "BackButton")
	_server_panel = VBoxContainer.new()
	_server_panel.visible = false
	box.add_child(_server_panel)
	_server = UI.field(_server_panel, T.t("Adresse du serveur"), Session.server_url)
	UI.label(_server_panel, T.t("Émulateur Android : http://10.0.2.2:8000"), "MutedLabel")
	_server_toggle.pressed.connect(_toggle_server)


func _toggle_server() -> void:
	_server_panel.visible = not _server_panel.visible
	_server_toggle.text = T.t("Options du serveur  ") + ("^" if _server_panel.visible else "v")
	if _server_panel.visible:
		_server.grab_focus()


func _validate() -> bool:
	var name_text: String = _pseudo.text.strip_edges()
	if name_text == "":
		_error.text = T.t("Choisissez un pseudo.")
		return false
	var url: String = _server.text.strip_edges()
	if not (url.begins_with("http://") or url.begins_with("https://")):
		_error.text = T.t("L'adresse du serveur doit commencer par http:// ou https://.")
		if not _server_panel.visible:
			_toggle_server()
		return false
	Session.pseudo = name_text
	Session.server_url = url
	Session.save_settings()
	return true


func _on_create() -> void:
	if _validate() and not UI.goto(self, "res://scenes/create_game.tscn"):
		_error.text = T.t("Impossible d'ouvrir l'écran de création.")


func _on_join() -> void:
	if _validate() and not UI.goto(self, "res://scenes/join_game.tscn"):
		_error.text = T.t("Impossible d'ouvrir l'écran pour rejoindre.")
