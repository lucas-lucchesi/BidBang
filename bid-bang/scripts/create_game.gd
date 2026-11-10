extends Control
## Création d'un salon : réglages de la partie.

const UI = preload("res://scripts/ui.gd")

var _box: VBoxContainer
var _error: Label
var _mode: OptionButton
var _theme: OptionButton
var _budget: OptionButton
var _items: OptionButton
var _timer: OptionButton
var _create: Button


func _ready() -> void:
	_box = UI.page(self, "", 0.5)
	var back: Button = UI.button(_box, "< Retour", "BackButton")
	back.alignment = HORIZONTAL_ALIGNMENT_LEFT
	back.pressed.connect(func() -> void: UI.goto(self, "res://menu.tscn"))
	UI.label(_box, "Nouvelle partie", "HeadingLabel")
	_error = UI.label(_box, "Chargement des lieux...", "MutedLabel")
	Session.net.http_done.connect(_on_http_done)
	Session.net.request("locations", Session.server_url, HTTPClient.METHOD_GET, "/locations")


func _on_http_done(tag: String, ok: bool, data: Dictionary) -> void:
	if tag == "locations":
		if not ok:
			_error.text = str(data.get("detail", "Erreur."))
			_error.theme_type_variation = "ErrorLabel"
			return
		_error.text = ""
		_build_form(data.get("locations", []))
	elif tag == "create":
		_create.disabled = false
		if ok:
			Session.enter_room(data)
			if not UI.goto(self, "res://scenes/lobby.tscn"):
				_error.text = "Impossible d'ouvrir le salon."
		else:
			_error.text = str(data.get("detail", "Erreur."))


func _build_form(locations: Array) -> void:
	var names: Array = []
	var ids: Array = []
	for loc in locations:
		var d: Dictionary = loc
		names.append(str(d["name"]))
		ids.append(str(d["id"]))
	_mode = UI.option(_box, "Mode", ["Construction", "Survie"], ["construction", "survie"], "construction")
	_theme = UI.option(_box, "Lieu", names, ids, ids[0] if ids.size() > 0 else "")
	_budget = UI.option(_box, "Budget", ["1 200 €", "2 200 €", "3 500 €"], [1200, 2200, 3500], 2200)
	_items = UI.option(_box, "Nombre d'objets", ["6", "8", "10"], [6, 8, 10], 8)
	_timer = UI.option(_box, "Chrono d'enchère", ["10 s", "15 s", "20 s", "30 s"], [10, 15, 20, 30], 15)
	_create = UI.button(_box, "Créer le salon", "PrimaryButton")
	_create.pressed.connect(_on_create)


func _selected(o: OptionButton) -> Variant:
	return o.get_item_metadata(o.selected)


func _on_create() -> void:
	_create.disabled = true
	_error.text = ""
	var settings := {
		"mode": _selected(_mode),
		"theme_id": _selected(_theme),
		"budget": _selected(_budget),
		"item_count": _selected(_items),
		"bid_timer": _selected(_timer),
	}
	Session.net.request("create", Session.server_url, HTTPClient.METHOD_POST, "/rooms",
		{"pseudo": Session.pseudo, "settings": settings})
