extends Control
## Création d'un salon : réglages de la partie.

const UI = preload("res://scripts/ui.gd")

## Mode « Enchère à l'aveugle » : mettre à false pour le masquer de la création de salon.
const ENABLE_BLIND_MODE := true
const T = preload("res://scripts/texts.gd")
const Fx = preload("res://scripts/fx.gd")

var _box: VBoxContainer
var _error: Label
var _mode: ButtonGroup
var _mode_hint: Label
var _theme: ButtonGroup
var _budget: ButtonGroup
var _items: ButtonGroup
var _timer: ButtonGroup
var _create: Button


func _ready() -> void:
	_box = UI.page(self, "", 0.5)
	var back: Button = UI.button(_box, T.t("< Retour"), "BackButton")
	back.alignment = HORIZONTAL_ALIGNMENT_LEFT
	back.pressed.connect(func() -> void: UI.goto(self, "res://menu.tscn"))
	UI.label(_box, T.t("Nouvelle partie"), "HeadingLabel")
	_error = UI.label(_box, T.t("Chargement des lieux..."), "MutedLabel")
	Session.net.http_done.connect(_on_http_done)
	Session.net.request("locations", Session.server_url, HTTPClient.METHOD_GET, "/locations")


func _on_http_done(tag: String, ok: bool, data: Dictionary) -> void:
	if tag == "locations":
		if not ok:
			_error.text = T.t(str(data.get("detail", "Erreur.")))
			_error.theme_type_variation = "ErrorLabel"
			return
		_error.text = ""
		_build_form(data.get("locations", []))
	elif tag == "create":
		_create.disabled = false
		if ok:
			Session.enter_room(data)
			if not UI.goto(self, "res://scenes/lobby.tscn"):
				_error.text = T.t("Impossible d'ouvrir le salon.")
		else:
			_error.text = T.t(str(data.get("detail", "Erreur.")))


func _build_form(locations: Array) -> void:
	var names: Array = []
	var ids: Array = []
	for loc in locations:
		var d: Dictionary = loc
		names.append(str(d["name"]))
		ids.append(str(d["id"]))
	var mode_labels: Array = ["Construction", "Survie"]
	var mode_values: Array = ["construction", "survie"]
	if ENABLE_BLIND_MODE:
		mode_labels.insert(1, "Enchère à l'aveugle")
		mode_values.insert(1, "aveugle")
	var mode_card: VBoxContainer = UI.section(_box, T.t("Mode"))
	_mode = UI.choice_row(mode_card, "", mode_labels, mode_values, "construction", _on_mode_selected)
	_mode_hint = UI.label(mode_card, "", "MutedLabel")
	_on_mode_selected("construction")
	var place_card: VBoxContainer = UI.section(_box, T.t("Lieu"))
	_theme = UI.choice_row(place_card, "", names, ids, ids[0] if ids.size() > 0 else "")
	var rules_card: VBoxContainer = UI.section(_box, T.t("Réglages"))
	_budget = UI.choice_row(rules_card, "Budget", ["1 200 €", "2 200 €", "3 500 €"], [1200, 2200, 3500], 2200)
	_items = UI.choice_row(rules_card, "Nombre d'objets", ["6", "8", "10"], [6, 8, 10], 8)
	_timer = UI.choice_row(rules_card, "Chrono d'enchère", ["10 s", "15 s", "20 s", "30 s"], [10, 15, 20, 30], 15)
	_create = UI.button(_box, T.t("Créer le salon"), "PrimaryButton")
	_create.pressed.connect(_on_create)
	Fx.stagger_in(_box, 0.05)


func _on_mode_selected(mode: Variant) -> void:
	var hints := {
		"construction": "Enchères publiques : surenchérissez en temps réel, puis votez pour la meilleure collection.",
		"aveugle": "Enchère à l'aveugle : chacun mise en secret une seule fois, la plus haute mise gagne.",
		"survie": "Survie : achetez le matériel pour réussir 3 épreuves.",
	}
	_mode_hint.text = T.t(str(hints[str(mode)]))


func _on_create() -> void:
	_create.disabled = true
	_error.text = ""
	var settings := {
		"mode": UI.choice_value(_mode),
		"theme_id": UI.choice_value(_theme),
		"budget": UI.choice_value(_budget),
		"item_count": UI.choice_value(_items),
		"bid_timer": UI.choice_value(_timer),
	}
	Session.net.request("create", Session.server_url, HTTPClient.METHOD_POST, "/rooms",
		{"pseudo": Session.pseudo, "settings": settings})
