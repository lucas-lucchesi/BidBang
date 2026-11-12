extends Control
## Création d'un salon en plusieurs étapes. Trois types de création (indépendants du mode de jeu) :
##   classic : un lieu du catalogue (comportement historique)
##   custom  : situation écrite par l'hôte + critères + sélection libre d'objets + aperçu des points
##   ai      : une phrase -> cartes (objets, joueurs, métiers, personnalités...) et leurs points,
##             attribués par une IA externe (clé API de l'hôte) ; pas de critères ; l'hôte choisit
##             les cartes à garder
## Classique / personnalisée : points calculés par le serveur. IA : points donnés par l'IA, validés
## puis figés par le serveur. Jamais calculés ici.
## Les choix sont conservés dans _state quand on change d'étape ou qu'on revient en arrière.

const UI = preload("res://scripts/ui.gd")
const T = preload("res://scripts/texts.gd")
const Fx = preload("res://scripts/fx.gd")
const ItemPicker = preload("res://scripts/item_picker.gd")
const ItemCard = preload("res://scripts/item_card.gd")

## Mode « Enchère à l'aveugle » : mettre à false pour le masquer de la création de salon.
const ENABLE_BLIND_MODE := true
const MAX_SCENARIO := 300
const MAX_AI_PROMPT := 600
const MIN_SCENARIO := 5
const MIN_CARDS := 6
const MAX_CARDS := 20  # nombre de cartes mises aux enchères, au choix de l'hôte (comme le serveur)
const LOCAL_HOSTS := ["127.0.0.1", "localhost", "10.0.2.2", "[::1]"]
const GENERATE_TIMEOUT := 75.0

var _box: VBoxContainer
var _content: VBoxContainer
var _error: Label
var _step: String = "type"
var _pending: String = "type"
var _locations: Array = []
var _provider_list: Array = []  # fournisseurs IA proposés par le serveur (GET /ai/providers)
var _catalog: Dictionary = {}
var _ai_items: Array = []
var _preview_items: Array = []
var _crit_box: VBoxContainer = null
var _crit_add: OptionButton = null
var _crit_next: Button = null
var _loc_hint: Label = null
var _count_label: Label = null
var _ai_room: bool = false
var _handed_off: bool = false
var _busy: bool = false
var _state: Dictionary = {
	"creation_type": "", "mode": "normal", "theme_id": "", "budget": 2200,
	"item_count": 8, "bid_timer": 15, "description": "", "criteria": [], "template": "polyvalent",
	"selected": {}, "max_players": 4, "provider": "gemini",
}
## Réglages imposés en partie IA (l'écran IA ne propose que le prompt et le nombre de joueurs).
const AI_DEFAULTS := {"mode": "normal", "budget": 2200, "item_count": 8, "bid_timer": 15}
# contrôles de l'étape courante (remis à null quand l'étape change)
var _mode: ButtonGroup = null
var _mode_hint: Label = null
var _theme: ButtonGroup = null
var _budget: ButtonGroup = null
var _items: ButtonGroup = null
var _timer: ButtonGroup = null
var _players: ButtonGroup = null
var _provider: ButtonGroup = null
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
		"criteria":
			_go("scenario")
		"picker":
			_go("criteria")
		"ai_picker":
			_go("ai_key")
		"preview":
			_go("ai_picker" if str(_state["creation_type"]) == "ai" else "picker")
		"ai_key":
			_leave_ai_room()
			_go("scenario")


func _go(step: String) -> void:
	_pending = step
	_error.text = ""
	if step == "classic" and _locations.is_empty():
		_show_loading("locations", "/locations")
		return
	if step == "ai_key" and _provider_list.is_empty():
		_show_loading("providers", "/ai/providers")
		return
	if (step == "scenario" or step == "picker" or step == "criteria") and _catalog.is_empty():
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
	_players = null
	_provider = null
	_crit_box = null
	_crit_add = null
	_crit_next = null
	_loc_hint = null
	_count_label = null
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
		"criteria":
			_build_criteria()
		"picker":
			_build_picker(false)
		"ai_key":
			_build_ai_key()
		"ai_picker":
			_build_picker(true)
		"preview":
			_build_preview()
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
	_type_card("PARTIE PERSONNALISÉE", "Écrivez votre situation, choisissez les critères et les objets.", "custom")
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
		_state["criteria"] = []
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
	var mode_labels: Array = ["Enchères normales"]
	var mode_values: Array = ["normal"]
	if ENABLE_BLIND_MODE:
		mode_labels.append("Enchère à l'aveugle")
		mode_values.append("aveugle")
	var card: VBoxContainer = UI.section(parent, T.t("Mode d'enchères"))
	_mode = UI.choice_row(card, "", mode_labels, mode_values, _state["mode"], _on_mode_selected)
	_mode_hint = UI.label(card, "", "MutedLabel")
	_on_mode_selected(_state["mode"])


func _on_mode_selected(mode: Variant) -> void:
	var hints := {
		"normal": "Enchères en temps réel : surenchérissez. Le gagnant est celui dont les objets rapportent le plus de points.",
		"aveugle": "Enchère à l'aveugle : chacun mise en secret une seule fois, la plus haute mise gagne l'objet.",
	}
	if _mode_hint != null:
		_mode_hint.text = T.t(str(hints.get(str(mode), hints["normal"])))


## Choix libre du nombre de cartes (6 à 20) : boutons - et +.
func _build_count_stepper(parent: Control, caption: String) -> void:
	UI.label(parent, caption, "FieldLabel")
	var line := HBoxContainer.new()
	line.add_theme_constant_override("separation", 14)
	line.alignment = BoxContainer.ALIGNMENT_CENTER
	parent.add_child(line)
	var minus: TextureButton = UI.icon_button(line, UI.ICON_MINUS)
	minus.custom_minimum_size = Vector2(76, 76)
	minus.pressed.connect(_on_count_step.bind(-1))
	_count_label = UI.label(line, "", "BigMoneyLabel")
	_count_label.custom_minimum_size = Vector2(120, 0)
	_count_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var plus: TextureButton = UI.icon_button(line, UI.ICON_PLUS)
	plus.custom_minimum_size = Vector2(76, 76)
	plus.pressed.connect(_on_count_step.bind(1))
	UI.label(parent, T.t("De %d à %d cartes. L'IA en propose davantage pour que vous puissiez choisir.") % [MIN_CARDS, MAX_CARDS], "MutedLabel")
	_on_count_step(0)


func _on_count_step(delta: int) -> void:
	_state["item_count"] = clampi(int(_state["item_count"]) + delta, MIN_CARDS, MAX_CARDS)
	if _count_label != null:
		_count_label.text = str(int(_state["item_count"]))


func _build_settings(parent: Control, stepper: bool = false) -> void:
	var rules: VBoxContainer = UI.section(parent, T.t("Réglages"))
	_budget = UI.choice_row(rules, "Budget", ["1 200 €", "2 200 €", "3 500 €"], [1200, 2200, 3500], _state["budget"])
	if stepper:
		_build_count_stepper(rules, T.t("Nombre d'objets"))
	else:
		_items = UI.choice_row(rules, "Nombre d'objets", ["6", "8", "10", "11", "12"], [6, 8, 10, 11, 12], _state["item_count"])
	_timer = UI.choice_row(rules, "Chrono d'enchère", ["10 s", "15 s", "20 s", "30 s"], [10, 15, 20, 30], _state["bid_timer"])


# ------------------------------------------------------ étape : partie classique
func _build_classic() -> void:
	_state["item_count"] = mini(int(_state["item_count"]), 12)  # un lieu propose 12 objets
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
	_theme = UI.choice_row(place_card, "", names, ids, current, _on_location_selected)
	_loc_hint = UI.label(place_card, "", "MutedLabel")
	_on_location_selected(current)
	_build_settings(_content)
	_action = UI.button(_content, T.t("Créer le salon"), "PrimaryButton")
	_action.pressed.connect(_on_create_classic)


## Critères de situation du lieu choisi (indication seulement : le serveur a les siens).
func _on_location_selected(loc_id: Variant) -> void:
	if _loc_hint == null:
		return
	var parts: PackedStringArray = []
	for loc in _locations:
		var d: Dictionary = loc
		if str(d["id"]) != str(loc_id):
			continue
		for c in d.get("criteria", []):
			var cd: Dictionary = c
			if bool(cd.get("necessary", false)):
				parts.append("%s %d" % [str(cd.get("label", cd["id"])), int(cd["importance"])])
	_loc_hint.text = (T.t("Critères de la situation : ") + ", ".join(parts)) if parts.size() > 0 else ""


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
		UI.label(sc, T.t("Décrivez votre partie en une ou deux phrases en précisant l'objectif (ex. « le meilleur onze de l'histoire de l'OM »). L'IA crée les cartes qui conviennent : objets, joueurs, métiers, personnalités, personnages... et attribue leurs points. Vous gardez celles que vous voulez."), "MutedLabel")
	else:
		UI.label(sc, T.t("Décrivez la situation de la partie. Elle sera affichée à tous les joueurs."), "MutedLabel")
	_scenario_edit = TextEdit.new()
	_scenario_edit.custom_minimum_size = Vector2(0, 260 if is_ai else 190)
	_scenario_edit.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	if is_ai:
		_scenario_edit.placeholder_text = T.t("Ex. : Composez un 11 de légende au football. Ou : recrutez l'équipe d'une startup (métiers). Ou : survivez 30 jours face à des zombies (objets).")
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
		var cards: VBoxContainer = UI.section(_content, T.t("Cartes mises aux enchères"))
		_build_count_stepper(cards, T.t("Nombre de cartes"))
		_action = UI.button(_content, T.t("Suivant"), "PrimaryButton")
		_action.pressed.connect(_on_scenario_next)
		return
	_build_mode(_content)
	_build_settings(_content, true)
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
		_go("criteria")
		return
	# IA : le salon est créé maintenant (la génération et la sélection se font sur le serveur)
	if _ai_room:
		_leave_ai_room()
	_post_create("create_ai", _payload(false))


func _payload(with_items: bool) -> Dictionary:
	var scenario: Dictionary = {"description": str(_state["description"]).strip_edges()}
	if with_items:
		scenario["criteria"] = _state["criteria"]
	var ids: Array = []
	if with_items:
		for k in (_state["selected"] as Dictionary):
			ids.append(str(k))
	return {
		"creation_type": _state["creation_type"], "mode": _state["mode"],
		"budget": _state["budget"], "item_count": _state["item_count"],
		"bid_timer": _state["bid_timer"], "max_players": _state["max_players"],
		"scenario": scenario, "item_ids": ids,
	}


# ------------------------------------------- étape : sélection d'objets
func _build_picker(is_ai: bool) -> void:
	UI.label(_content, T.t("Objets de la partie"), "HeadingLabel")
	var items: Array = []
	if is_ai:
		items.append_array(_ai_items)  # uniquement les cartes de l'IA (avec ses points)
	else:
		items.append_array(_catalog.get("items", []))
	var need: int = int(_state["item_count"])
	if is_ai:
		var head: VBoxContainer = UI.section(_content, str(_state.get("ai_title", "")))
		UI.label(head, str(_state.get("ai_description", "")), "MutedLabel")
		_show_ai_profile(head)
		UI.label(_content, T.t("L'IA a créé ces cartes et leur a attribué des points. Retirez celles dont vous ne voulez pas (il en faut au moins %d), puis validez.") % need, "MutedLabel")
	else:
		UI.label(_content, T.t("Choisissez librement des objets de tous les lieux. Le serveur en tirera %d au hasard.") % need, "MutedLabel")
	_picker = ItemPicker.new()
	_content.add_child(_picker)
	var pre: Array = []
	for k in (_state["selected"] as Dictionary):
		pre.append(str(k))
	_picker.call("setup", items, [] if is_ai else _catalog.get("locations", []), pre, need)
	_picker.connect("selection_changed", _on_selection_changed)
	_action = UI.button(_content, "", "PrimaryButton")
	if is_ai:
		_action.pressed.connect(_on_validate_selection)
		var again: Button = UI.button(_content, T.t("Générer de nouveaux objets"), "SmallButton")
		again.pressed.connect(func() -> void:
			_collect()
			_go("ai_key"))
	else:
		_action.pressed.connect(_on_preview_custom)
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
		_action.text = T.t("Valider la sélection") if is_ai else T.t("Prévisualiser les points")


## Objectif compris par l'IA (profil validé par le serveur) : l'hôte voit tout de suite si c'est le bon.
func _show_ai_profile(parent: Control) -> void:
	var prof: Variant = _state.get("ai_profile")
	if not (prof is Dictionary):
		return
	var p: Dictionary = prof
	UI.label(parent, T.t("Objectif compris : ") + str(p.get("goal", "")), "InfoLabel")
	var org: Variant = p.get("organization")
	if org != null and str(org) != "":
		UI.label(parent, T.t("Univers : ") + str(org), "MutedLabel")
	var roles: PackedStringArray = []
	for r in p.get("required_roles", []):
		roles.append(str(r))
	if roles.size() > 0:
		UI.label(parent, T.t("Rôles couverts : ") + ", ".join(roles), "MutedLabel")
	if bool(p.get("real_entities_only", false)):
		UI.label(parent, T.t("Cartes réelles : vérifiez-les, l'IA peut se tromper."), "MutedLabel")


func _selected_ids() -> Array:
	var ids: Array = []
	for k in (_state["selected"] as Dictionary):
		ids.append(str(k))
	return ids


## Aperçu des points : le serveur calcule (rien n'est créé ni figé à ce stade).
func _on_preview_custom() -> void:
	if _busy:
		return
	_collect()
	_set_busy(true, T.t("Calcul des points..."))
	Session.net.request("preview", Session.server_url, HTTPClient.METHOD_POST, "/scoring/preview",
		{"criteria": _state["criteria"], "item_ids": _selected_ids()})


func _on_create_custom() -> void:
	_post_create("create", _payload(true))


# ------------------------------------------- étape : critères de la situation
## Retire les libellés : le serveur ne reçoit que {id, necessary, importance}.
func _plain_criteria(list: Array) -> Array:
	var out: Array = []
	for c in list:
		var d: Dictionary = c
		var necessary: bool = bool(d.get("necessary", false))
		out.append({"id": str(d["id"]), "necessary": necessary, "importance": int(d.get("importance", 0)) if necessary else 0})
	return out


func _apply_template(template_id: String) -> void:
	for t in _catalog.get("templates", []):
		var td: Dictionary = t
		if str(td["id"]) == template_id:
			_state["criteria"] = _plain_criteria(td["criteria"])
			_state["template"] = template_id


func _build_criteria() -> void:
	var is_ai: bool = false  # l'étape « critères » n'existe que pour les parties personnalisées
	UI.label(_content, T.t("Critères de la situation"), "HeadingLabel")
	if (_state["criteria"] as Array).is_empty():
		_apply_template(str(_state["template"]))
	var info: VBoxContainer = UI.section(_content, T.t("Ce dont les joueurs ont besoin"))
	UI.label(info, T.t("Un objet rapporte des points s'il répond à un critère nécessaire, d'autant plus que son importance est grande. Choisissez « Non » pour un critère sans intérêt dans cette situation."), "MutedLabel")
	var names: Array = []
	var ids: Array = []
	for t in _catalog.get("templates", []):
		var td: Dictionary = t
		names.append(str(td["name"]))
		ids.append(str(td["id"]))
	if names.size() > 0:
		UI.label(info, T.t("Modèles"), "FieldLabel")
		UI.choice_row(info, "", names, ids, "" if is_ai else _state["template"], _on_template_chosen)
	_crit_box = VBoxContainer.new()
	_crit_box.add_theme_constant_override("separation", 14)
	_content.add_child(_crit_box)
	var add_row := HBoxContainer.new()
	add_row.add_theme_constant_override("separation", 12)
	_content.add_child(add_row)
	_crit_add = OptionButton.new()
	_crit_add.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	add_row.add_child(_crit_add)
	var add_btn: Button = UI.button(add_row, T.t("Ajouter un critère"), "SmallButton")
	add_btn.pressed.connect(_on_add_criterion)
	_crit_next = UI.button(_content, T.t("Suivant"), "PrimaryButton")
	_crit_next.pressed.connect(_on_criteria_next)
	_action = _crit_next
	_refresh_criteria()


func _on_template_chosen(template_id: Variant) -> void:
	_apply_template(str(template_id))
	_refresh_criteria()


func _refresh_criteria() -> void:
	if _crit_box == null:
		return
	for c in _crit_box.get_children():
		_crit_box.remove_child(c)
		c.queue_free()
	var crit: Array = _state["criteria"]
	var used: Dictionary = {}
	var any_needed: bool = false
	for entry in crit:
		var d: Dictionary = entry
		used[str(d["id"])] = true
		var cid: String = str(d["id"])
		var current: int = int(d["importance"]) if bool(d["necessary"]) else 0
		any_needed = any_needed or current > 0
		var card: VBoxContainer = UI.section(_crit_box, "")
		var head := HBoxContainer.new()
		card.add_child(head)
		var nm: Label = UI.label(head, ItemCard.criterion_label(cid), "HeadingLabel")
		nm.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var rm: Button = UI.button(head, T.t("Retirer"), "SmallButton")
		rm.pressed.connect(_on_remove_criterion.bind(cid))
		UI.choice_row(card, "", ["Non", "1", "2", "3", "4", "5"], [0, 1, 2, 3, 4, 5], current, _on_importance.bind(cid))
	# critères restants
	_crit_add.clear()
	var registry: Array = _catalog.get("criteria", [])
	for r in registry:
		var rd: Dictionary = r
		if not used.has(str(rd["id"])):
			_crit_add.add_item(T.t(str(rd["label"])))
			_crit_add.set_item_metadata(_crit_add.item_count - 1, str(rd["id"]))
	_crit_add.disabled = _crit_add.item_count == 0
	if _crit_next != null:
		_crit_next.disabled = not any_needed
		_crit_next.text = T.t("Suivant") if any_needed else T.t("Choisissez au moins un critère nécessaire")


## Appelé avec (valeur, id du critère) : la valeur 0 = non nécessaire, 1 à 5 = importance.
func _on_importance(value: Variant, cid: String) -> void:
	for entry in (_state["criteria"] as Array):
		var d: Dictionary = entry
		if str(d["id"]) == cid:
			d["necessary"] = int(value) > 0
			d["importance"] = int(value)
	var any_needed: bool = false
	for entry in (_state["criteria"] as Array):
		any_needed = any_needed or bool((entry as Dictionary)["necessary"])
	if _crit_next != null:
		_crit_next.disabled = not any_needed
		_crit_next.text = T.t("Suivant") if any_needed else T.t("Choisissez au moins un critère nécessaire")


func _on_remove_criterion(cid: String) -> void:
	var kept: Array = []
	for entry in (_state["criteria"] as Array):
		if str((entry as Dictionary)["id"]) != cid:
			kept.append(entry)
	_state["criteria"] = kept
	_refresh_criteria()


func _on_add_criterion() -> void:
	if _crit_add == null or _crit_add.item_count == 0 or _crit_add.selected < 0:
		return
	var cid: String = str(_crit_add.get_item_metadata(_crit_add.selected))
	(_state["criteria"] as Array).append({"id": cid, "necessary": true, "importance": 3})
	_refresh_criteria()


func _on_criteria_next() -> void:
	_go("picker")


# ----------------------------------------- étape : aperçu des points
func _build_preview() -> void:
	var is_ai: bool = str(_state["creation_type"]) == "ai"
	UI.label(_content, T.t("Aperçu des points"), "HeadingLabel")
	var info: VBoxContainer = UI.section(_content, "")
	UI.label(info, T.t("Voici ce que chaque carte rapportera. Les points sont figés au lancement de la partie.") if is_ai else T.t("Voici ce que chaque objet rapportera dans cette situation. Les points sont calculés par le serveur et figés au lancement de la partie."), "MutedLabel")
	UI.label(info, T.t("%d objets sélectionnés, %d seront mis aux enchères.") % [_preview_items.size(), int(_state["item_count"])], "MutedLabel")
	var sorted_items: Array = _preview_items.duplicate()
	sorted_items.sort_custom(func(x: Dictionary, y: Dictionary) -> bool: return int(x.get("points", 0)) > int(y.get("points", 0)))
	for it in sorted_items:
		_content.add_child(ItemCard.make_card(it, true, false, true, 96.0))
	if not is_ai:  # une partie IA n'a pas de critères
		var edit_c: Button = UI.button(_content, T.t("Modifier les critères"), "SmallButton")
		edit_c.pressed.connect(func() -> void: _go("criteria"))
	var edit_i: Button = UI.button(_content, T.t("Modifier la sélection"), "SmallButton")
	edit_i.pressed.connect(func() -> void: _go("ai_picker" if is_ai else "picker"))
	if is_ai:
		_action = UI.button(_content, T.t("Continuer vers le salon"), "PrimaryButton")
		_action.pressed.connect(_open_lobby)
	else:
		_action = UI.button(_content, T.t("Créer le salon"), "PrimaryButton")
		_action.pressed.connect(_on_create_custom)


# --------------------------------------------------- étape : clé API (IA)
func _build_ai_key() -> void:
	UI.label(_content, T.t("Génération par IA"), "HeadingLabel")
	var info: VBoxContainer = UI.section(_content, T.t("Votre clé API"))
	UI.label(info, T.t("La clé est envoyée au serveur de jeu uniquement pour cette génération, en HTTPS. Elle n'est ni enregistrée, ni partagée avec les autres joueurs, ni conservée après l'appel."), "MutedLabel")
	UI.label(info, T.t("Votre fournisseur peut facturer chaque génération. Utilisez de préférence une clé dédiée, avec un plafond de dépenses."), "MutedLabel")
	var provider_labels: Array = []
	var provider_values: Array = []
	for pid in ["gemini", "openai", "anthropic", "mock"]:  # ordre d'affichage ; le serveur décide de ce qui existe
		for entry in _provider_list:
			var pd: Dictionary = entry
			if str(pd["id"]) == pid:
				provider_labels.append(str(pd.get("label", pid)))
				provider_values.append(pid)
	if provider_values.is_empty():
		provider_labels = ["Google Gemini (gratuit)", "OpenAI (GPT)", "Anthropic (Claude)"]
		provider_values = ["gemini", "openai", "anthropic"]
	if not provider_values.has(_state["provider"]):
		_state["provider"] = provider_values[0]
	_provider = UI.choice_row(info, "Fournisseur", provider_labels, provider_values, _state["provider"])
	_key_edit = UI.field(info, "Clé API", "", 300)
	_key_edit.secret = true
	_key_edit.placeholder_text = T.t("Collez votre clé ici")
	UI.label(info, T.t("Gemini : une clé gratuite se crée sur Google AI Studio (voir server/README.md). Pour un test en local, laissez vide si le serveur a GEMINI_API_KEY."), "MutedLabel")
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
	var payload: Dictionary = {"provider": str(_state["provider"])}
	if api_key.length() >= 10:
		if not _transport_ok():
			_error.text = T.t("La clé API ne peut être envoyée qu'à un serveur en HTTPS.")
			return
		payload["api_key"] = api_key
	elif str(_state["provider"]) == "gemini" and api_key == "":
		payload["use_env_key"] = true  # essai local : clé GEMINI_API_KEY du serveur (refusée sinon)
	else:
		_error.text = T.t("Collez votre clé API.")
		return
	_error.text = ""
	_set_busy(true, T.t("Génération en cours (jusqu'à une minute)..."))
	Session.net.request("generate", Session.server_url, HTTPClient.METHOD_POST,
		"/rooms/%s/ai/generate" % Session.code, payload,
		PackedStringArray(["Authorization: Bearer " + Session.token]), GENERATE_TIMEOUT)
	api_key = ""
	_key_edit.text = ""  # la clé ne reste pas à l'écran


func _on_validate_selection() -> void:
	if _busy:
		return
	_collect()
	var ids: Array = _selected_ids()
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
	_state["selected"] = {}  # rien de la situation précédente ne reste sélectionné


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
		"providers":
			# en cas d'échec, l'écran utilise la liste par défaut (le serveur refusera un fournisseur inconnu)
			_provider_list = data.get("providers", []) if ok else [{"id": "gemini", "label": "Google Gemini (gratuit)"}]
			_go(_pending)
		"items":
			if not ok:
				_fail(data)
				return
			_catalog = data
			ItemCard.register_criteria(data.get("criteria", []))
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
			_state["ai_profile"] = data.get("profile", {})
			_state["ai_title"] = str((data.get("situation", {}) as Dictionary).get("title", ""))
			_state["ai_description"] = str((data.get("situation", {}) as Dictionary).get("description", ""))
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
			_preview_items = data.get("items", [])
			_go("preview")
		"preview":
			_set_busy(false)
			if not ok:
				_fail(data)
				return
			_preview_items = data.get("items", [])
			_go("preview")


func _open_lobby() -> void:
	_handed_off = true
	if not UI.goto(self, "res://scenes/lobby.tscn"):
		_handed_off = false
		_error.text = T.t("Impossible d'ouvrir le salon.")
