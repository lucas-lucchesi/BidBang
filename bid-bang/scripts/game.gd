extends Control
## Écran de partie : enchères, vote, résultats. L'UI est reconstruite à chaque game_state.
## Le client n'envoie que des intentions ; le serveur décide de tout.

const UI = preload("res://scripts/ui.gd")
const T = preload("res://scripts/texts.gd")
const ItemCard = preload("res://scripts/item_card.gd")
const Fx = preload("res://scripts/fx.gd")
const Confetti = preload("res://scripts/confetti.gd")
const Podium = preload("res://scripts/podium.gd")
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
		# partie personnalisée / IA : rappel discret de la situation
		var sit: Dictionary = situation
		var sl: Label = ItemCard.make_label(_box, str(sit.get("title", "")), "MutedLabel")
		sl.add_theme_font_size_override("font_size", 22)
	if _toast != "":
		ItemCard.make_label(_box, _toast, "ErrorLabel")
		_toast = ""
	match phase:
		"auction":
			_render_auction(game, me)
		"voting":
			_render_voting(game)
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
	for pu in purchases:
		var d2: Dictionary = pu
		var item: Dictionary = d2["item"].duplicate()
		item["price"] = d2["price"]
		spent += int(d2["price"])
		var card: Control = ItemCard.make_card(item, true, true, true, 110.0, true)
		content.add_child(card)
		Fx.pop(card, 1.05)
	var total: Label = ItemCard.make_label(content, T.t("%d objet(s) - %s dépensés") % [purchases.size(), ItemCard.format_money(spent)], "MutedLabel")
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
				str(lr["item"]["name"]), str(lr["winner"]), ItemCard.format_money(int(lr["price"]))], "InfoLabel")
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


# ---------------------------------------------------------------------- vote
func _render_voting(game: Dictionary) -> void:
	var vote: Dictionary = game["vote"]
	var hero := PanelContainer.new()
	hero.theme_type_variation = "HeroPanel"
	_box.add_child(hero)
	var hrow := HBoxContainer.new()
	hrow.add_theme_constant_override("separation", 22)
	hero.add_child(hrow)
	_new_ring(hrow, int(ceil(float(vote["seconds_left"]))))
	var info := VBoxContainer.new()
	info.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	info.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	hrow.add_child(info)
	ItemCard.make_label(info, T.t("Vote"), "HeadingLabel")
	ItemCard.make_label(info, T.t("Quelle collection est la meilleure ?"), "MutedLabel")
	_start_timer(float(vote["seconds_left"]), 45.0)
	var mine: Variant = vote.get("your_vote")
	for p in game["players"]:
		var d: Dictionary = p
		var pid: String = str(d["id"])
		if pid == Session.player_id:
			continue
		var chosen: bool = mine != null and str(mine) == pid
		var card := PanelContainer.new()
		_box.add_child(card)
		var col := VBoxContainer.new()
		col.add_theme_constant_override("separation", 12)
		card.add_child(col)
		var head := HBoxContainer.new()
		head.add_theme_constant_override("separation", 16)
		col.add_child(head)
		UI.avatar(head, str(d["pseudo"]), 68.0)
		var names := VBoxContainer.new()
		names.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		names.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		names.add_theme_constant_override("separation", 0)
		head.add_child(names)
		ItemCard.make_label(names, str(d["pseudo"]), "HeadingLabel")
		ItemCard.make_label(names, T.t("%d objet(s)") % d["purchases"].size(), "MutedLabel")
		var actions := HBoxContainer.new()
		actions.add_theme_constant_override("separation", 12)
		col.add_child(actions)
		var see: Button = UI.button(actions, T.t("Voir les objets"), "SmallButton")
		see.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		see.pressed.connect(func() -> void: _open_inventory(Session.game, pid))
		var b: Button = UI.button(actions, T.t("Votre choix") if chosen else T.t("Voter"), "SuccessButton" if chosen else "PrimaryButton")
		b.custom_minimum_size = Vector2(0, 88)
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		b.pressed.connect(_on_vote.bind(pid))
	var voted: Array = vote["voted_ids"]
	var vl: Label = ItemCard.make_label(_box, T.t("%d / %d votes") % [voted.size(), game["players"].size()], "MutedLabel")
	vl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER


func _on_vote(target: String) -> void:
	Session.send({"type": "vote", "target": target})


# ------------------------------------------------------------------ résultats
func _add_purchase_lines(parent: Node, purchases: Array) -> void:
	if purchases.is_empty():
		ItemCard.make_label(parent, T.t("Aucun achat."), "MutedLabel")
		return
	for pu in purchases:
		var d: Dictionary = pu
		var item: Dictionary = d["item"]
		var rarity: int = clampi(int(item.get("rarity", 0)), 0, 3)
		var line := HBoxContainer.new()
		parent.add_child(line)
		var n: Label = ItemCard.make_label(line, str(item["name"]))
		n.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		n.add_theme_color_override("font_color", ItemCard.RARITY_COLORS[rarity])
		var pr: Label = ItemCard.make_label(line, ItemCard.format_money(int(d["price"])), "MutedLabel")
		pr.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT


func _render_results(game: Dictionary) -> void:
	var banner: Label = ItemCard.make_label(_box, T.t("Victoire !") if _is_winner(game) else T.t("Podium"), "TitleLabel")
	banner.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	if _anim_key != "finished_done":
		Fx.pop(banner, 1.3)
	var scenario: Variant = game.get("scenario")
	var situation: Variant = game.get("situation")
	if scenario is Dictionary:
		var sc: Dictionary = scenario
		ItemCard.make_label(_box, str(sc["title"]) + " - " + str(sc["text"]), "MutedLabel")
	elif situation is Dictionary:
		var sit: Dictionary = situation
		ItemCard.make_label(_box, str(sit["description"]), "MutedLabel")
	Podium.build(_box, game["results"])
	ItemCard.make_label(_box, T.t("Détails"), "HeadingLabel")
	for r in game["results"]:
		var row: Dictionary = r
		var mine: bool = str(row["player_id"]) == Session.player_id
		var title: String = "%d. %s - %s" % [int(row["rank"]), str(row["pseudo"]), T.t("%d pts") % int(row["score"])]
		var key: String = "r_" + str(row["player_id"])
		var col: VBoxContainer = UI.collapsible(_box, title, bool(_open.get(key, mine)), _remember.bind(key))
		ItemCard.make_label(col, T.t("Objets %d - Synergies %d - Budget restant %s") % [
			int(row["items_points"]), int(row["synergy_points"]), ItemCard.format_money(int(row["budget"]))], "MutedLabel")
		if str(game["mode"]) != "survie":
			ItemCard.make_label(col, T.t("Votes reçus : %d (+%d)") % [int(row["votes"]), int(row["vote_points"])], "MutedLabel")
		for t in row["trials"]:
			var tr: Dictionary = t
			ItemCard.make_label(col, "%s : %d / %d - %s (+%d)" % [
				str(tr["name"]), int(tr["value"]), int(tr["threshold"]),
				T.t("réussie") if bool(tr["success"]) else T.t("échouée"), int(tr["points"])],
				"InfoLabel" if bool(tr["success"]) else "ErrorLabel")
		ItemCard.make_label(col, T.t("Achats (%s dépensés)") % ItemCard.format_money(int(row["spent"])), "FieldLabel")
		_add_purchase_lines(col, row["purchases"])
	var back: Button = UI.button(_box, T.t("Retour au menu"), "PrimaryButton")
	back.pressed.connect(_on_back)


func _on_back() -> void:
	Session.leave_room()
	UI.goto(self, "res://menu.tscn")
