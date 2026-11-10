extends Control
## Rejoindre un salon avec un code à 6 caractères.

const UI = preload("res://scripts/ui.gd")
const T = preload("res://scripts/texts.gd")

var _code: LineEdit
var _error: Label
var _join: Button


func _ready() -> void:
	var box: VBoxContainer = UI.page(self, "", 0.5)
	var back: Button = UI.button(box, T.t("< Retour"), "BackButton")
	back.alignment = HORIZONTAL_ALIGNMENT_LEFT
	back.pressed.connect(func() -> void: UI.goto(self, "res://menu.tscn"))
	UI.label(box, T.t("Rejoindre une partie"), "HeadingLabel")
	_code = UI.field(box, T.t("Code du salon"), "", 6)
	_code.placeholder_text = "ABC123"
	_code.text_changed.connect(func(t: String) -> void:
		var up: String = t.to_upper()
		if up != t:
			var pos: int = _code.caret_column
			_code.text = up
			_code.caret_column = pos)
	_code.text_submitted.connect(func(_t: String) -> void: _on_join())
	_error = UI.label(box, "", "ErrorLabel")
	_join = UI.button(box, T.t("Rejoindre"), "PrimaryButton")
	_join.pressed.connect(_on_join)
	Session.net.http_done.connect(_on_http_done)


func _on_join() -> void:
	var c: String = _code.text.strip_edges().to_upper()
	if c.length() != 6:
		_error.text = T.t("Le code contient 6 caractères.")
		return
	_join.disabled = true
	_error.text = ""
	Session.net.request("join", Session.server_url, HTTPClient.METHOD_POST,
		"/rooms/%s/join" % c, {"pseudo": Session.pseudo})


func _on_http_done(tag: String, ok: bool, data: Dictionary) -> void:
	if tag != "join":
		return
	_join.disabled = false
	if ok:
		Session.enter_room(data)
		if not UI.goto(self, "res://scenes/lobby.tscn"):
			_error.text = T.t("Impossible d'ouvrir le salon.")
	else:
		_error.text = T.t(str(data.get("detail", "Erreur.")))
