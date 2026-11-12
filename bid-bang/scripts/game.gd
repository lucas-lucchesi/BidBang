extends Control
## Écran de partie : enchères, résultats (le score est la somme des points des objets remportés). L'UI est reconstruite à chaque game_state.
## Le client n'envoie que des intentions ; le serveur décide de tout.

const UI = preload("res://scripts/ui.gd")
const T = preload("res://scripts/texts.gd")
const ItemCard = preload("res://scripts/item_card.gd")
const Fx = preload("res://scripts/fx.gd")
const Confetti = preload("res://scripts/confetti.gd")
const Results = preload("res://scripts/results_view.gd")
const RingTimer = preload("res://scripts/ring_timer.gd")

var _box: VBoxContainer
var _ring: Control = null
var _bid_button: Button = null
var _deadline_s: float = -1.0
var _total_s: float = 1.0
var _toast: String = ""
var _bid_edit: LineEdit = null
var _bid_value: int = 0
var _bid_required: int = 0
var _bid_item_id: String = ""
var _bid_label_base: String = ""
var _anim_key: String = ""
var _card_item_id: String = ""
var _last_bid: int = -1
var _confetti_done: bool = false
var _open: Dictionary = {}  # sections dépliées (clé -> bool), conservées entre deux mises à jour


func _ready() -> void:
	if not Session.in_room() or Session.game.is_empty():
		UI.goto(self, "res://menu.tscn")
		return
	_box = UI.page(self, str(Session.game.get("location", {}).get("id", "")), 0.55)
	Session.game_updated.connect(_render)
	Session.error_received.connect(_on_error)
	Session.connection_lost.connect(_on_connection_lost)
	Session.rematch_started.connect(_on_rematch_started)
	_render(Session.game)


func _now() -> float:
	return Time.get_ticks_msec() / 1000.0


func _process(_delta: float) -> void:
	if _deadline_s < 0.0:
		return
	var left: float = maxf(0.0, _deadline_s - _now())
	if _ring != null:
		var fraction: float = left / maxf(_total_s, 0.1)
		_ring.call("set_state", int(ceil(left)), fraction)
		if fraction < 0.25 and left > 0.0:
			_ring.modulate.a = 0.6 + 0.4 * absf(sin(_now() * 8.0))
		else:
			_ring.modulate.a = 1.0


func _new_ring(parent: Node, seconds: int) -> Control:
	var r: Control = RingTimer.new()
	parent.add_child(r)
	r.call("set_state", seconds, 1.0)
	_ring = r
	return r


func _on_error(message: String) -> void:
	_toast = T.t(message)
	_render(Session.game)


func _on_connection_lost() -> void:
	_toast = T.t("Connexion perdue avec le serveur.")
	_render(Session.game)


func _me(game: Dictionary) -> Dictionary:
	for p in game.get("players", []):
		var d: Dictionary = p
		if str(d["id"]) == Session.player_id:
			return d
	return {}


func _pseudo_of(game: Dictionary, pid: String) -> String:
	for p in game.get("players", []):
		var d: Dictionary = p
		if str(d["id"]) == pid:
			return str(d["pseudo"])
	return "?"


func _start_timer(seconds_left: float, total: float) -> void:
	_deadline_s = _now() + seconds_left
	_total_s = total


func _render(game: Dictionary) -> void:
	for c in _box.get_children():
		_box.remove_child(c)
		c.queue_free()
	_ring = null
	_bid_button = null
	_bid_edit = null
	_deadline_s = -1.0
	var phase: String = str(game.get("phase", ""))
	var loc: Dictionary = game.get("location", {})
	var me: Dictionary = _me(game)
	var header := HBoxContainer.new()
	header.add_theme_constant_override("separation", 12)
	_box.add_child(header)
	if phase == "auction":
		UI.chip(header, T.t("Objet %d / %d") % [int(game["item_index"]), int(game["item_total"])])
	else:
		UI.chip(header, str(loc.get("name", "")))
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(spacer)
	if not me.is_empty():
		UI.chip(header, ItemCard.format_money(int(me["budget"])), "MoneyChip", "MoneyLabel")
	var situation: Variant = game.get("situation")
	if phase == "auction" and situation is Dictionary:
		_render_situation(situation as Dictionary)
	if _toast != "":
		ItemCard.make_label(_box, _toast, "ErrorLabel")
		_toast = ""
	match phase:
		"auction":
			_render_auction(game, me)
		"finished":
			_render_results(game)
	if phase != "finished":
		_render_players(game)
	_render_footer(game, me, phase)
	var key: String = "%s_%d" % [phase, int(game.get("item_index", 0))]
	if phase == "finished":
		key = "finished_done"
	if key != _anim_key:
		_anim_key = key
		Fx.stagger_in(_box, 0.05)
	if phase == "finished" and not _confetti_done:
		_confetti_done = true
		if _is_winner(game):
			add_child(Confetti.new())


func _render_footer(game: Dictionary, me: Dictionary, phase: String) -> void:
	var foot := HBoxContainer.new()
	foot.add_theme_constant_override("separation", 12)
	_box.add_child(foot)
	if phase != "finished" and not me.is_empty():
		var n: int = me["purchases"].size()
		var inv: Button = UI.button(foot, T.t("Mon inventaire") + " (%d)" % n, "SmallButton")
		inv.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		inv.pressed.connect(func() -> void: _open_inventory(Session.game, Session.player_id))
	var st: Button = UI.settings_button(foot, self, "SmallButton")
	st.size_flags_horizontal = Control.SIZE_EXPAND_FILL


## Inventaire d'un joueur : cartes des objets remportés, dans une fenêtre superposée.
func _open_inventory(game: Dictionary, pid: String) -> void:
	var owner_data: Dictionary = {}
	for p in game.get("players", []):
		var d: Dictionary = p
		if str(d["id"]) == pid:
			owner_data = d
	if owner_data.is_empty():
		return
	var title: String = T.t("Mon inventaire") if pid == Session.player_id else T.t("Inventaire de %s") % str(owner_data["pseudo"])
	var content: VBoxContainer = UI.modal(self, title)
	var purchases: Array = owner_data["purchases"]
	if purchases.is_empty():
		var empty: Label = ItemCard.make_label(content, T.t("Aucun achat."), "MutedLabel")
		empty.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		return
	var spent: int = 0
	var estimated: int = 0
	var points: int = 0
	for pu in purchases:
		var d2: Dictionary = pu
		var item: Dictionary = d2["item"]
		spent += int(d2["purchase_price"])
		estimated += int(item["price"])
		points += int(item.get("points", 0))
		# le prix estimé reste celui de l'objet ; le prix payé est affiché à part
		var card: Control = ItemCard.make_card(item, true, true, true, 110.0, int(d2["purchase_price"]))
		content.add_child(card)
		Fx.pop(card, 1.05)
	var total: Label = ItemCard.make_label(content, T.t("%d objet(s) - %d pts - %s dépensés (estimés %s)") % [
		purchases.size(), points, ItemCard.format_money(spent), ItemCard.format_money(estimated)], "MutedLabel")
	total.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER


func _is_winner(game: Dictionary) -> bool:
	for r in game.get("results", []):
		var row: Dictionary = r
		if str(row["player_id"]) == Session.player_id and bool(row["winner"]):
			return true
	return false


# ------------------------------------------------------------------ enchères
func _render_auction(game: Dictionary, me: Dictionary) -> void:
	var a: Dictionary = game["auction"]
	var item: Dictionary = a["item"]
	var settings: Dictionary = game["settings"]
	var last: Variant = game.get("last_result")
	if last is Dictionary:
		var lr: Dictionary = last
		if lr["winner"] == null:
			ItemCard.make_label(_box, T.t("%s : invendu.") % str(lr["item"]["name"]), "MutedLabel")
		else:
			ItemCard.make_label(_box, T.t("%s remporté par %s pour %s.") % [
				str(lr["item"]["name"]), str(lr["winner"]), ItemCard.format_money(int(lr["purchase_price"]))], "InfoLabel")
		if lr.get("bids") is Array:
			_render_bids(lr["bids"], str(lr.get("winner_id", "")))
	var card: Control = ItemCard.make_card(item, true, true, false, 170.0)
	_box.add_child(card)
	if str(item.get("id", "")) != _card_item_id:
		_card_item_id = str(item.get("id", ""))
		Fx.pop(card, 1.05)
	if bool(a.get("blind", false)):
		_render_blind(game, me, a, settings)
		return
	var leader_id: String = str(a["leader_id"]) if a["leader_id"] != null else ""
	var hero := PanelContainer.new()
	hero.theme_type_variation = "HeroPanel"
	_box.add_child(hero)
	var hrow := HBoxContainer.new()
	hrow.add_theme_constant_override("separation", 22)
	hero.add_child(hrow)
	_new_ring(hrow, int(settings["bid_timer"]))
	var info := VBoxContainer.new()
	info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	info.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	info.add_theme_constant_override("separation", 2)
	hrow.add_child(info)
	if a["current_bid"] == null:
		ItemCard.make_label(info, T.t("Aucune mise pour l'instant"), "MutedLabel")
		ItemCard.make_label(info, T.t("À vous d'ouvrir !"), "HeadingLabel")
	else:
		ItemCard.make_label(info, T.t("Mise actuelle - ") + _pseudo_of(game, leader_id), "MutedLabel")
		var bid_label: Label = ItemCard.make_label(info, ItemCard.format_money(int(a["current_bid"])), "BigMoneyLabel")
		bid_label.add_theme_font_size_override("font_size", 60)
		if int(a["current_bid"]) != _last_bid:
			Fx.pop(bid_label)
	_last_bid = int(a["current_bid"]) if a["current_bid"] != null else -1
	if a["seconds_left"] != null:
		_start_timer(float(a["seconds_left"]), float(settings["bid_timer"]))

	var folded: Array = a["folded"]
	var is_leader: bool = leader_id == Session.player_id
	var is_folded: bool = folded.has(Session.player_id)
	var budget: int = int(me.get("budget", 0))
	var required: int = int(a["required_bid"])
	if is_leader:
		pass  # le meneur est déjà indiqué dans la carte de mise
	elif is_folded:
		var fo: Label = ItemCard.make_label(_box, T.t("Vous êtes couché pour cet objet."), "MutedLabel")
		fo.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	else:
		_render_bid_controls(a, budget, required)


func _render_bid_controls(a: Dictionary, budget: int, required: int, blind: bool = false) -> void:
	var item_id: String = str(a["item"]["id"])
	_bid_required = required
	if item_id != _bid_item_id or _bid_value < required:
		_bid_item_id = item_id
		_bid_value = required
	_bid_value = mini(_bid_value, maxi(budget, required))
	var line := HBoxContainer.new()
	line.add_theme_constant_override("separation", 10)
	_box.add_child(line)
	var minus: TextureButton = UI.icon_button(line, UI.ICON_MINUS)
	minus.custom_minimum_size = Vector2(76, 76)
	minus.pressed.connect(_on_adjust.bind(-10, budget))
	_bid_edit = LineEdit.new()
	_bid_edit.text = str(_bid_value)
	_bid_edit.placeholder_text = T.t("min. %s") % ItemCard.format_money(required)
	_bid_edit.alignment = HORIZONTAL_ALIGNMENT_CENTER
	_bid_edit.virtual_keyboard_type = LineEdit.KEYBOARD_TYPE_NUMBER
	_bid_edit.add_theme_font_size_override("font_size", 44)
	_bid_edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_bid_edit.text_changed.connect(_on_bid_text)
	line.add_child(_bid_edit)
	var plus: TextureButton = UI.icon_button(line, UI.ICON_PLUS)
	plus.custom_minimum_size = Vector2(76, 76)
	plus.pressed.connect(_on_adjust.bind(10, budget))
	var chips := HBoxContainer.new()
	chips.add_theme_constant_override("separation", 10)
	_box.add_child(chips)
	for delta in [50, 100]:
		var cb: Button = UI.button(chips, "+%d" % delta, "SmallButton")
		cb.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		cb.pressed.connect(_on_adjust.bind(delta, budget))
	var max_b: Button = UI.button(chips, "Max", "SmallButton")
	max_b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	max_b.disabled = budget < required
	max_b.pressed.connect(_on_set_bid.bind(budget))
	var actions := HBoxContainer.new()
	actions.add_theme_constant_override("separation", 12)
	_box.add_child(actions)
	var f := Button.new()
	f.text = T.t("Passer") if blind else T.t("Se coucher")
	f.theme_type_variation = "DangerButton"
	f.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	f.pressed.connect(_on_fold)
	Fx.squish(f)
	actions.add_child(f)
	var bid_b := Button.new()
	bid_b.text = T.t("Valider la mise") if blind else T.t("Miser")
	bid_b.theme_type_variation = "PrimaryButton" if not blind else "SuccessButton"
	bid_b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	bid_b.size_flags_stretch_ratio = 1.7
	bid_b.disabled = budget < required
	bid_b.pressed.connect(_on_bid)
	Fx.squish(bid_b)
	actions.add_child(bid_b)
	_bid_button = bid_b
	_bid_label_base = bid_b.text
	_refresh_bid_button()


func _refresh_bid_button() -> void:
	if _bid_button != null:
		_bid_button.text = "%s %s" % [_bid_label_base, ItemCard.format_money(_bid_value)]


func _on_bid_text(t: String) -> void:
	_bid_value = int(t) if t.is_valid_int() else 0
	_refresh_bid_button()


func _on_adjust(delta: int, budget: int) -> void:
	if budget < _bid_required:
		return
	_on_set_bid(clampi(_bid_value + delta, _bid_required, budget))


func _on_set_bid(amount: int) -> void:
	_bid_value = amount
	if _bid_edit != null:
		_bid_edit.text = str(amount)
	_refresh_bid_button()


func _on_bid() -> void:
	Session.send({"type": "bid", "amount": _bid_value})


func _on_fold() -> void:
	Session.send({"type": "fold"})


# ----------------------------------------------------------- enchère à l'aveugle
func _render_blind(game: Dictionary, me: Dictionary, a: Dictionary, settings: Dictionary) -> void:
	var hero := PanelContainer.new()
	hero.theme_type_variation = "HeroPanel"
	_box.add_child(hero)
	var hrow := HBoxContainer.new()
	hrow.add_theme_constant_override("separation", 22)
	hero.add_child(hrow)
	_new_ring(hrow, int(settings["bid_timer"]))
	var info := VBoxContainer.new()
	info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	info.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	hrow.add_child(info)
	ItemCard.make_label(info, T.t("Enchère à l'aveugle"), "HeadingLabel")
	var submitted: Array = a["submitted"]
	ItemCard.make_label(info, T.t("%d / %d joueurs ont joué") % [submitted.size(), game["players"].size()], "MutedLabel")
	if a["seconds_left"] != null:
		_start_timer(float(a["seconds_left"]), float(settings["bid_timer"]))
	var mine: Variant = a.get("your_bid")
	if mine == null:
		_render_bid_controls(a, int(me.get("budget", 0)), int(a["required_bid"]), true)
	elif int(mine) > 0:
		var l1: Label = ItemCard.make_label(_box, T.t("Votre mise secrète : %s") % ItemCard.format_money(int(mine)), "InfoLabel")
		l1.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		var l2: Label = ItemCard.make_label(_box, T.t("En attente des autres joueurs..."), "MutedLabel")
		l2.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	else:
		var l3: Label = ItemCard.make_label(_box, T.t("Vous passez pour cet objet."), "MutedLabel")
		l3.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		var l4: Label = ItemCard.make_label(_box, T.t("En attente des autres joueurs..."), "MutedLabel")
		l4.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER


func _render_bids(bids: Array, winner_id: String) -> void:
	var inner: VBoxContainer = UI.collapsible(_box, T.t("Mises révélées"), bool(_open.get("bids", false)), _remember.bind("bids"))
	var sorted_bids: Array = bids.duplicate()
	sorted_bids.sort_custom(func(x: Dictionary, y: Dictionary) -> bool: return int(x["amount"]) > int(y["amount"]))
	for b in sorted_bids:
		var d: Dictionary = b
		var txt: String = ItemCard.format_money(int(d["amount"])) if int(d["amount"]) > 0 else T.t("passe")
		if str(d["player_id"]) == winner_id:
			txt += T.t(" (gagnant)")
		ItemCard.make_label(inner, "%s : %s" % [str(d["pseudo"]), txt], "MutedLabel")


func _remember(expanded: bool, key: String) -> void:
	_open[key] = expanded


# ------------------------------------------------------------------- joueurs
func _render_players(game: Dictionary) -> void:
	var leader_id: String = ""
	var folded: Array = []
	var submitted: Array = []
	if game.get("auction") is Dictionary:
		var a: Dictionary = game["auction"]
		leader_id = str(a["leader_id"]) if a["leader_id"] != null else ""
		folded = a["folded"]
		submitted = a.get("submitted", [])
	var grid := GridContainer.new()
	grid.columns = 2
	grid.add_theme_constant_override("h_separation", 12)
	grid.add_theme_constant_override("v_separation", 12)
	_box.add_child(grid)
	for p in game["players"]:
		var d: Dictionary = p
		var pid: String = str(d["id"])
		var tile := PanelContainer.new()
		tile.theme_type_variation = "RowPanel"
		tile.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		tile.mouse_filter = Control.MOUSE_FILTER_STOP
		tile.gui_input.connect(_on_tile_input.bind(pid))
		grid.add_child(tile)
		var h := HBoxContainer.new()
		h.add_theme_constant_override("separation", 12)
		tile.add_child(h)
		UI.avatar(h, str(d["pseudo"]), 56.0, false)
		var col := VBoxContainer.new()
		col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		col.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		col.add_theme_constant_override("separation", -2)
		h.add_child(col)
		var nm: Label = ItemCard.make_label(col, str(d["pseudo"]), "")
		nm.autowrap_mode = TextServer.AUTOWRAP_OFF
		nm.clip_text = true
		nm.add_theme_font_size_override("font_size", 26)
		ItemCard.make_label(col, ItemCard.format_money(int(d["budget"])), "MutedLabel")
		var status: String = ""
		var status_var: String = "MutedLabel"
		if pid == leader_id:
			status = T.t("mène")
			status_var = "InfoLabel"
		elif submitted.has(pid):
			status = T.t("a joué")
			status_var = "InfoLabel"
		elif folded.has(pid):
			status = T.t("couché")
			status_var = "ErrorLabel"
		if status != "":
			var sl: Label = ItemCard.make_label(col, status, status_var)
			sl.add_theme_font_size_override("font_size", 20)


func _on_tile_input(event: InputEvent, pid: String) -> void:
	var mb := event as InputEventMouseButton
	if mb != null and mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT:
		_open_inventory(Session.game, pid)


# ------------------------------------------------------------------ situation
## Rappel de la situation : titre, description et critères nécessaires (dépliable).
func _render_situation(situation: Dictionary) -> void:
	var title: String = str(situation.get("title", ""))
	var inner: VBoxContainer = UI.collapsible(_box, T.t("Situation : ") + title, bool(_open.get("situation", false)), _remember.bind("situation"))
	ItemCard.make_label(inner, str(situation.get("description", "")), "MutedLabel")
	for c in situation.get("criteria", []):
		var d: Dictionary = c
		if bool(d.get("necessary", false)):
			ItemCard.make_label(inner, T.t("%s : importance %d / 5") % [str(d.get("label", d["id"])), int(d["importance"])], "InfoLabel")
	var others: PackedStringArray = []
	for c2 in situation.get("criteria", []):
		var d2: Dictionary = c2
		if not bool(d2.get("necessary", false)):
			others.append(str(d2.get("label", d2["id"])))
	if others.size() > 0:
		ItemCard.make_label(inner, T.t("Sans intérêt ici : ") + ", ".join(others), "MutedLabel")


# ------------------------------------------------------------------ résultats
func _render_results(game: Dictionary) -> void:
	var banner: Label = ItemCard.make_label(_box, T.t("Victoire !") if _is_winner(game) else T.t("Résultats"), "TitleLabel")
	banner.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	if _anim_key != "finished_done":
		Fx.pop(banner, 1.3)
	var situation: Variant = game.get("situation")
	if situation is Dictionary:
		var sit: Dictionary = situation
		ItemCard.make_label(_box, str(sit.get("title", "")) + " - " + str(sit.get("description", "")), "MutedLabel")
	Results.build(_box, game, _open, _remember)
	if Session.is_host():
		# rejouer avec le même groupe, sans recréer de salon
		var again: Button = UI.button(_box, T.t("Rejouer"), "PrimaryButton")
		again.pressed.connect(_on_replay)
		var change: Button = UI.button(_box, T.t("Changer de mode ou de réglages"), "SmallButton")
		change.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		change.pressed.connect(_open_replay_settings)
	else:
		var wait: Label = ItemCard.make_label(_box, T.t("L'hôte peut relancer une partie avec le même groupe : vous reviendrez automatiquement au salon d'attente."), "MutedLabel")
		wait.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var back: Button = UI.button(_box, T.t("Retour au menu"), "BackButton" if Session.is_host() else "SmallButton")
	back.pressed.connect(_on_back)


func _on_back() -> void:
	Session.leave_room()
	UI.goto(self, "res://menu.tscn")


# ------------------------------------------------------------------ revanche
## Tous les joueurs reviennent au salon d'attente quand l'hôte relance une partie.
func _on_rematch_started() -> void:
	UI.goto(self, "res://scenes/lobby.tscn")


func _on_replay() -> void:
	Session.send({"type": "rematch"})


## Fenêtre « Changer de mode ou de réglages » : l'hôte choisit, puis relance dans le même salon.
func _open_replay_settings() -> void:
	var s: Dictionary = Session.room.get("settings", Session.game.get("settings", {}))
	var content: VBoxContainer = UI.modal(self, T.t("Nouvelle partie"))
	var mode_labels: Array = ["Enchères normales", "Enchère à l'aveugle"]
	var mode_values: Array = ["normal", "aveugle"]
	var current_mode: String = "aveugle" if str(s.get("mode", "normal")) == "aveugle" else "normal"
	var mode_group: ButtonGroup = UI.choice_row(content, T.t("Mode d'enchères"), mode_labels, mode_values, current_mode)
	var budget_group: ButtonGroup = UI.choice_row(content, "Budget", ["1 200 €", "2 200 €", "3 500 €"], [1200, 2200, 3500], int(s.get("budget", 2200)))
	var timer_group: ButtonGroup = UI.choice_row(content, "Chrono d'enchère", ["10 s", "15 s", "20 s", "30 s"], [10, 15, 20, 30], int(s.get("bid_timer", 15)))
	# nombre de cartes : limité par les cartes disponibles (lieu classique : 12 ; sinon la sélection validée)
	var available: int = 12
	if str(s.get("creation_type", "classic")) != "classic":
		available = (s.get("item_ids", []) as Array).size()
	var counts: Array = []
	var labels: Array = []
	for n in [6, 8, 10, 12, 15, 20]:
		if n <= available:
			counts.append(n)
			labels.append(str(n))
	var current_count: int = int(s.get("item_count", 8))
	var count_group: ButtonGroup = null
	if counts.size() > 1:
		count_group = UI.choice_row(content, "Nombre de cartes", labels, counts, current_count if counts.has(current_count) else counts[0])
	var go: Button = UI.button(content, T.t("Lancer avec ces réglages"), "PrimaryButton")
	go.pressed.connect(func() -> void:
		var changes: Dictionary = {
			"mode": UI.choice_value(mode_group), "budget": UI.choice_value(budget_group),
			"bid_timer": UI.choice_value(timer_group)}
		if count_group != null:
			changes["item_count"] = UI.choice_value(count_group)
		Session.send({"type": "rematch", "settings": changes})
		UI.close_modal(content.get_meta("modal_root")))
