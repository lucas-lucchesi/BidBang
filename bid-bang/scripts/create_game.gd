extends Control
## Création d'un salon en plusieurs étapes. Trois types de création (indépendants du mode de jeu) :
##   classic : un lieu du catalogue (comportement historique)
##   custom  : situation écrite par l'hôte + sélection libre d'objets
##   ai      : situation + objets proposés par une IA externe (clé API de l'hôte), puis validation
## Les choix sont conservés dans _state quand on change d'étape ou qu'on revient en arrière.

const UI = preload("res://scripts/ui.gd")
const T = preload("res://scripts/texts.gd")
const Fx = preload("res://scripts/fx.gd")
const ItemPicker = preload("res://scripts/item_picker.gd")

## Mode « Enchère à l'aveugle » : mettre à false pour le masquer de la création de salon.
const ENABLE_BLIND_MODE := true
const MAX_SCENARIO := 300
const MAX_AI_PROMPT := 600
const MIN_SCENARIO := 5
const LOCAL_HOSTS := ["127.0.0.1", "localhost", "10.0.2.2", "[::1]"]
const GENERATE_TIMEOUT := 75.0

var _box: VBoxContainer
var _content: VBoxContainer
var _error: Label
var _step: String = "type"
var _pending: String = "type"
var _locations: Array = []
var _catalog: Dictionary = {}
var _ai_items: Array = []
var _ai_room: bool = false
var _handed_off: bool = false
var _busy: bool = false
var _state: Dictionary = {
	"creation_type": "", "mode": "construction", "theme_id": "", "budget": 2200,
	"item_count": 8, "bid_timer": 15, "description": "", "trial_pack": "generique",
	"selected": {}, "trials_source": "", "max_players": 4, "provider": "anthropic",
}
## Réglages imposés en partie IA (l'écran IA ne propose que le prompt et le nombre de joueurs).
const AI_DEFAULTS := {"mode": "construction", "budget": 2200, "item_count": 8, "bid_timer": 15, "trial_pack": "generique"}
# contrôles de l'étape courante (remis à null quand l'étape change)
var _mode: ButtonGroup = null
var _mode_hint: Label = null
var _theme: ButtonGroup = null
var _budget: ButtonGroup = null
var _items: ButtonGroup = null
var _timer: ButtonGroup = null
var _packs: ButtonGroup = null
var _players: ButtonGroup = null
var _provider: ButtonGroup = null
var _pack_box: VBoxContainer = null
var _scenario_edit: TextEdit = null
var _scenario_count: Label = null
var _key_edit: LineEdit = null
var _picker: VBoxContainer = null
var _action: Button = null


func _ready() -> void:
	_box = UI.page(self, "", 0.5)
	var back: Button = UI.button(_box, T.t("< Retour"), "BackButton")
	back.alignment = HORIZONTAL_ALIGNMENT_LEFT
	back.pressed.connect(_on_back)
	_content = VBoxContainer.new()
	_content.add_theme_constant_override("separation", 16)
	_box.add_child(_content)
	_error = UI.label(_box, "", "ErrorLabel")
	Session.net.http_done.connect(_on_http_done)
	_go("type")


func _exit_tree() -> void:
	# quitter l'écran en cours de création IA : on ne laisse pas un salon vide derrière nous
	if _ai_room and not _handed_off and Session.in_room():
		Session.leave_room()


# ------------------------------------------------------------ navigation
func _on_back() -> void:
	if _busy:
		return
	_error.text = ""
	_collect()
	match _step:
		"type":
			UI.goto(self, "res://menu.tscn")
		"classic", "scenario":
			_go("type")
		"picker":
			_go("scenario")
		"ai_key":
			_leave_ai_room()
			_go("scenario")
		"ai_picker":
			_go("ai_key")


func _go(step: String) -> void:
	_pending = step
	_error.text = ""
	if step == "classic" and _locations.is_empty():
		_show_loading("locations", "/locations")
		return
	if (step == "scenario" or step == "picker") and _catalog.is_empty():
		_show_loading("items", "/items")
		return
	_render(step)


func _show_loading(tag: String, path: String) -> void:
	_clear_step()
	UI.label(_content, T.t("Chargement..."), "MutedLabel")
	Session.net.request(tag, Session.server_url, HTTPClient.METHOD_GET, path)


func _clear_step() -> void:
	for c in _content.get_children():
		_content.remove_child(c)
		c.queue_free()
	_mode = null
	_mode_hint = null
	_theme = null
	_budget = null
	_items = null
	_timer = null
	_packs = null
	_players = null
	_provider = null
	_pack_box = null
	_scenario_edit = null
	_scenario_count = null
	_key_edit = null
	_picker = null
	_action = null


func _render(step: String) -> void:
	_clear_step()
	_step = step
	match step:
		"type":
			_build_type()
		"classic":
			_build_classic()
		"scenario":
			_build_scenario()
		"picker":
			_build_picker(false)
		"ai_key":
			_build_ai_key()
		"ai_picker":
			_build_picker(true)
	Fx.stagger_in(_content, 0.05)


## Lit les contrôles de l'étape courante et les range dans _state.
func _collect() -> void:
	if _mode != null:
		_state["mode"] = UI.choice_value(_mode)
	if _theme != null:
		_state["theme_id"] = UI.choice_value(_theme)
	if _budget != null:
		_state["budget"] = UI.choice_value(_budget)
	if _items != null:
		_state["item_count"] = UI.choice_value(_items)
	if _timer != null:
		_state["bid_timer"] = UI.choice_value(_timer)
	if _packs != null:
		_state["trial_pack"] = UI.choice_value(_packs)
	if _players != null:
		_state["max_players"] = UI.choice_value(_players)
	if _provider != null:
		_state["provider"] = UI.choice_value(_provider)
	if _scenario_edit != null:
		_state["description"] = _scenario_edit.text
	if _picker != null:
		var chosen: Dictionary = {}
		for sid in _picker.call("selected_ids"):
			chosen[str(sid)] = true
		_state["selected"] = chosen


# ------------------------------------------------------ étape : type de partie
func _build_type() -> void:
	UI.label(_content, T.t("Nouvelle partie"), "HeadingLabel")
	_type_card("PARTIE CLASSIQUE", "Choisissez un thème existant et jouez immédiatement.", "classic")
	_type_card("PARTIE PERSONNALISÉE", "Écrivez votre scénario et sélectionnez les objets.", "custom")
	_type_card("PARTIE AVEC IA", "Décrivez votre idée et laissez l'IA proposer une partie.", "ai")


func _type_card(title: String, hint: String, kind: String) -> void:
	var card: VBoxContainer = UI.section(_content, "", "HeroPanel")
	UI.label(card, T.t(title), "HeadingLabel")
	UI.label(card, T.t(hint), "MutedLabel")
	var go: Button = UI.button(card, T.t("Choisir"), "PrimaryButton")
	go.pressed.connect(_on_type_chosen.bind(kind))


func _on_type_chosen(kind: String) -> void:
	if str(_state["creation_type"]) != kind:
		_state["selected"] = {}
		_ai_items = []
	_state["creation_type"] = kind
	if kind != "ai":
		_state["max_players"] = 4
	if kind == "ai":
		for k in AI_DEFAULTS:
			_state[k] = AI_DEFAULTS[k]
	_go("classic" if kind == "classic" else "scenario")


# ------------------------------------------------- blocs de formulaire communs
func _build_mode(parent: Control) -> void:
	var mode_labels: Array = ["Construction", "Survie"]
	var mode_values: Array = ["construction", "survie"]
	if ENABLE_BLIND_MODE:
		mode_labels.insert(1, "Enchère à l'aveugle")
		mode_values.insert(1, "aveugle")
	var card: VBoxContainer = UI.section(parent, T.t("Mode"))
	_mode = UI.choice_row(card, "", mode_labels, mode_values, _state["mode"], _on_mode_selected)
	_mode_hint = UI.label(card, "", "MutedLabel")
	_on_mode_selected(_state["mode"])


func _on_mode_selected(mode: Variant) -> void:
	var hints := {
		"construction": "Enchères publiques : surenchérissez en temps réel, puis votez pour la meilleure collection.",
		"aveugle": "Enchère à l'aveugle : chacun mise en secret une seule fois, la plus haute mise gagne.",
		"survie": "Survie : achetez le matériel pour réussir 3 épreuves.",
	}
	if _mode_hint != null:
		_mode_hint.text = T.t(str(hints[str(mode)]))
	if _pack_box != null:
		_pack_box.visible = str(mode) == "survie"


func _build_settings(parent: Control) -> void:
	var rules: VBoxContainer = UI.section(parent, T.t("Réglages"))
	_budget = UI.choice_row(rules, "Budget", ["1 200 €", "2 200 €", "3 500 €"], [1200, 2200, 3500], _state["budget"])
	_items = UI.choice_row(rules, "Nombre d'objets", ["6", "8", "10"], [6, 8, 10], _state["item_count"])
	_timer = UI.choice_row(rules, "Chrono d'enchère", ["10 s", "15 s", "20 s", "30 s"], [10, 15, 20, 30], _state["bid_timer"])


# ------------------------------------------------------ étape : partie classique
func _build_classic() -> void:
	UI.label(_content, T.t("Partie classique"), "HeadingLabel")
	var names: Array = []
	var ids: Array = []
	for loc in _locations:
		var d: Dictionary = loc
		names.append(str(d["name"]))
		ids.append(str(d["id"]))
	_build_mode(_content)
	var place_card: VBoxContainer = UI.section(_content, T.t("Lieu"))
	var current: Variant = _state["theme_id"] if ids.has(_state["theme_id"]) else (ids[0] if ids.size() > 0 else "")
	_theme = UI.choice_row(place_card, "", names, ids, current)
	_build_settings(_content)
	_action = UI.button(_content, T.t("Créer le salon"), "PrimaryButton")
	_action.pressed.connect(_on_create_classic)


func _on_create_classic() -> void:
	_collect()
	_post_create("create", {
		"creation_type": "classic", "mode": _state["mode"], "theme_id": _state["theme_id"],
		"budget": _state["budget"], "item_count": _state["item_count"], "bid_timer": _state["bid_timer"],
	})


# ------------------------------------- étape : scénario (personnalisé et IA)
func _build_scenario() -> void:
	var is_ai: bool = str(_state["creation_type"]) == "ai"
	UI.label(_content, T.t("Partie avec IA") if is_ai else T.t("Partie personnalisée"), "HeadingLabel")
	var sc: VBoxContainer = UI.section(_content, T.t("Prompt") if is_ai else T.t("Situation"))
	if is_ai:
		UI.label(sc, T.t("Voici le prompt : écrivez la situation, puis les objets à intégrer obligatoirement avec leur prix."), "MutedLabel")
	else:
		UI.label(sc, T.t("Décrivez la situation de la partie. Elle sera affichée à tous les joueurs."), "MutedLabel")
	_scenario_edit = TextEdit.new()
	_scenario_edit.custom_minimum_size = Vector2(0, 260 if is_ai else 190)
	_scenario_edit.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	if is_ai:
		_scenario_edit.placeholder_text = T.t("Ex. : Construisez une base sur Mars. Objets obligatoires : Rover spatial (400 €), Jacuzzi spatial (250 €).")
	else:
		_scenario_edit.placeholder_text = T.t("Ex. : Organisez le mariage le plus extravagant possible.")
	_scenario_edit.text = str(_state["description"])
	_scenario_edit.text_changed.connect(_on_scenario_changed)
	sc.add_child(_scenario_edit)
	_scenario_count = UI.label(sc, "", "MutedLabel")
	_on_scenario_changed()
	if is_ai:
		# seul autre réglage : le nombre de joueurs (le reste est imposé par défaut)
		var pl: VBoxContainer = UI.section(_content, T.t("Joueurs"))
		_players = UI.choice_row(pl, "Nombre de joueurs maximum", ["2", "3", "4"], [2, 3, 4], _state["max_players"])
		_action = UI.button(_content, T.t("Suivant"), "PrimaryButton")
		_action.pressed.connect(_on_scenario_next)
		return
	_build_mode(_content)
	# série d'épreuves prédéfinies pour la Survie (le texte de la situation n'est jamais une règle)
	_pack_box = UI.section(_content, T.t("Épreuves de Survie"))
	var pack_labels: Array = []
	var pack_values: Array = []
	for p in _catalog.get("trial_packs", []):
		var pd: Dictionary = p
		pack_labels.append(str(pd["name"]))
		pack_values.append(str(pd["id"]))
	_packs = UI.choice_row(_pack_box, "", pack_labels, pack_values, _state["trial_pack"])
	_pack_box.visible = str(_state["mode"]) == "survie"
	_build_settings(_content)
	_action = UI.button(_content, T.t("Suivant"), "PrimaryButton")
	_action.pressed.connect(_on_scenario_next)


func _on_scenario_changed() -> void:
	var limit: int = MAX_AI_PROMPT if str(_state["creation_type"]) == "ai" else MAX_SCENARIO
	var content: String = _scenario_edit.text
	if content.length() > limit:
		_scenario_edit.text = content.substr(0, limit)
		var last: int = _scenario_edit.get_line_count() - 1
		_scenario_edit.set_caret_line(last)
		_scenario_edit.set_caret_column(_scenario_edit.get_line(last).length())
		content = _scenario_edit.text
	_scenario_count.text = "%d / %d" % [content.length(), limit]


func _on_scenario_next() -> void:
	_collect()
	var description: String = str(_state["description"]).strip_edges()
	if description.length() < MIN_SCENARIO:
		_error.text = T.t("Écrivez une situation (au moins %d caractères).") % MIN_SCENARIO
		return
	if str(_state["creation_type"]) == "custom":
		_go("picker")
		return
	# IA : le salon est créé maintenant (la génération et la sélection se font sur le serveur)
	if _ai_room:
		_leave_ai_room()
	_post_create("create_ai", _payload(false))


func _payload(with_items: bool) -> Dictionary:
	var ids: Array = []
	if with_items:
		for k in (_state["selected"] as Dictionary):
			ids.append(str(k))
	return {
		"creation_type": _state["creation_type"], "mode": _state["mode"],
		"budget": _state["budget"], "item_count": _state["item_count"],
		"bid_timer": _state["bid_timer"], "trial_pack": _state["trial_pack"],
		"max_players": _state["max_players"],
		"scenario": {"description": str(_state["description"]).strip_edges()},
		"item_ids": ids,
	}


# ------------------------------------------- étape : sélection d'objets
func _build_picker(is_ai: bool) -> void:
	UI.label(_content, T.t("Objets de la partie"), "HeadingLabel")
	var items: Array = []
	if is_ai:
		items.append_array(_ai_items)
	for it in _catalog.get("items", []):
		items.append(it)
	var need: int = int(_state["item_count"])
	if is_ai:
		UI.label(_content, T.t("Vérifiez les objets proposés par l'IA : retirez ceux dont vous ne voulez pas, ajoutez-en du catalogue, puis validez."), "MutedLabel")
	else:
		UI.label(_content, T.t("Choisissez librement des objets de tous les lieux. Le serveur en tirera %d au hasard.") % need, "MutedLabel")
	_picker = ItemPicker.new()
	_content.add_child(_picker)
	var pre: Array = []
	for k in (_state["selected"] as Dictionary):
		pre.append(str(k))
	_picker.call("setup", items, _catalog.get("categories", []), pre, need)
	_picker.connect("selection_changed", _on_selection_changed)
	_action = UI.button(_content, "", "PrimaryButton")
	if is_ai:
		_action.pressed.connect(_on_validate_selection)
		var again: Button = UI.button(_content, T.t("Générer de nouveaux objets"), "SmallButton")
		again.pressed.connect(func() -> void:
			_collect()
			_go("ai_key"))
	else:
		_action.pressed.connect(_on_create_custom)
	_update_action_button(is_ai)


func _on_selection_changed(_count: int) -> void:
	_update_action_button(str(_state["creation_type"]) == "ai")


func _update_action_button(is_ai: bool) -> void:
	if _action == null or _picker == null:
		return
	var n: int = (_picker.call("selected_ids") as Array).size()
	var need: int = int(_state["item_count"])
	_action.disabled = n < need
	if n < need:
		_action.text = T.t("Choisissez au moins %d objets") % need
	else:
		_action.text = T.t("Valider la sélection") if is_ai else T.t("Créer le salon")


func _on_create_custom() -> void:
	_collect()
	_post_create("create", _payload(true))


# --------------------------------------------------- étape : clé API (IA)
func _build_ai_key() -> void:
	UI.label(_content, T.t("Génération par IA"), "HeadingLabel")
	var info: VBoxContainer = UI.section(_content, T.t("Votre clé API"))
	UI.label(info, T.t("La clé est envoyée au serveur de jeu uniquement pour cette génération, en HTTPS. Elle n'est ni enregistrée, ni partagée avec les autres joueurs, ni conservée après l'appel."), "MutedLabel")
	UI.label(info, T.t("Votre fournisseur peut facturer chaque génération. Utilisez de préférence une clé dédiée, avec un plafond de dépenses."), "MutedLabel")
	_provider = UI.choice_row(info, "Fournisseur", ["Anthropic (Claude)", "OpenAI (GPT)", "Google Gemini"],
		["anthropic", "openai", "gemini"], _state["provider"])
	_key_edit = UI.field(info, "Clé API", "", 300)
	_key_edit.secret = true
	_key_edit.placeholder_text = T.t("Collez votre clé ici")
	UI.label(info, T.t("5 générations maximum par salon."), "MutedLabel")
	_action = UI.button(_content, T.t("Générer les objets"), "PrimaryButton")
	_action.pressed.connect(_on_generate)
	if not _ai_items.is_empty():
		var skip: Button = UI.button(_content, T.t("Revenir à la sélection"), "SmallButton")
		skip.pressed.connect(func() -> void: _go("ai_picker"))


func _transport_ok() -> bool:
	var url: String = Session.server_url.strip_edges().to_lower()
	if url.begins_with("https://"):
		return true
	if not url.begins_with("http://"):
		return false
	var host: String = url.substr(7).split("/")[0]
	if not host.begins_with("["):
		host = host.split(":")[0]
	return LOCAL_HOSTS.has(host)


func _on_generate() -> void:
	if _busy:
		return
	_collect()
	var api_key: String = _key_edit.text.strip_edges()
	if api_key.length() < 10:
		_error.text = T.t("Collez votre clé API.")
		return
	if not _transport_ok():
		_error.text = T.t("La clé API ne peut être envoyée qu'à un serveur en HTTPS.")
		return
	_error.text = ""
	_set_busy(true, T.t("Génération en cours (jusqu'à une minute)..."))
	Session.net.request("generate", Session.server_url, HTTPClient.METHOD_POST,
		"/rooms/%s/ai/generate" % Session.code, {"provider": str(_state["provider"]), "api_key": api_key},
		PackedStringArray(["Authorization: Bearer " + Session.token]), GENERATE_TIMEOUT)
	api_key = ""
	_key_edit.text = ""  # la clé ne reste pas à l'écran


func _on_validate_selection() -> void:
	if _busy:
		return
	_collect()
	var ids: Array = []
	for k in (_state["selected"] as Dictionary):
		ids.append(str(k))
	_set_busy(true, T.t("Validation..."))
	Session.net.request("selection", Session.server_url, HTTPClient.METHOD_PUT,
		"/rooms/%s/selection" % Session.code, {"item_ids": ids},
		PackedStringArray(["Authorization: Bearer " + Session.token]))


func _set_busy(on: bool, message: String = "") -> void:
	_busy = on
	if _action != null:
		_action.disabled = on
	if on:
		_error.text = message
		_error.theme_type_variation = "InfoLabel"
	else:
		_error.theme_type_variation = "ErrorLabel"


func _leave_ai_room() -> void:
	if _ai_room and Session.in_room():
		Session.leave_room()
	_ai_room = false
	_ai_items = []


# ------------------------------------------------------------------ réseau
func _post_create(tag: String, settings: Dictionary) -> void:
	if _busy:
		return
	_set_busy(true, "")
	Session.net.request(tag, Session.server_url, HTTPClient.METHOD_POST, "/rooms",
		{"pseudo": Session.pseudo, "settings": settings})


func _fail(data: Dictionary) -> void:
	_set_busy(false)
	_error.text = T.t(str(data.get("detail", "Erreur.")))


func _on_http_done(tag: String, ok: bool, data: Dictionary) -> void:
	match tag:
		"locations":
			if not ok:
				_fail(data)
				return
			_locations = data.get("locations", [])
			_go(_pending)
		"items":
			if not ok:
				_fail(data)
				return
			_catalog = data
			_go(_pending)
		"create":
			_set_busy(false)
			if not ok:
				_fail(data)
				return
			Session.enter_room(data)
			_open_lobby()
		"create_ai":
			_set_busy(false)
			if not ok:
				_fail(data)
				return
			Session.enter_room(data)
			_ai_room = true
			_go("ai_key")
		"generate":
			if _key_edit != null:
				_key_edit.text = ""
			_set_busy(false)
			if not ok:
				_fail(data)
				return
			_ai_items = data.get("items", [])
			_state["trials_source"] = str(data.get("trials_source", ""))
			var chosen: Dictionary = {}
			for it in _ai_items:
				chosen[str((it as Dictionary)["id"])] = true
			_state["selected"] = chosen  # tout est présélectionné : l'hôte retire ce qu'il ne veut pas
			_go("ai_picker")
		"selection":
			_set_busy(false)
			if not ok:
				_fail(data)
				return
			Session.room = data["room"]
			_open_lobby()


func _open_lobby() -> void:
	_handed_off = true
	if not UI.goto(self, "res://scenes/lobby.tscn"):
		_handed_off = false
		_error.text = T.t("Impossible d'ouvrir le salon.")
