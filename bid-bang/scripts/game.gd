extends Control
## Écran de partie : enchères, vote, résultats. L'UI est reconstruite à chaque game_state.
## Le client n'envoie que des intentions ; le serveur décide de tout.

const UI = preload("res://scripts/ui.gd")
const ItemCard = preload("res://scripts/item_card.gd")
const Fx = preload("res://scripts/fx.gd")
const Confetti = preload("res://scripts/confetti.gd")

var _box: VBoxContainer
var _countdown: Label = null
var _bar: ProgressBar = null
var _deadline_s: float = -1.0
var _total_s: float = 1.0
var _toast: String = ""
var _bid_edit: LineEdit = null
var _bid_value: int = 0
var _bid_item_id: String = ""
var _anim_key: String = ""
var _last_bid: int = -1
var _confetti_done: bool = false


func _ready() -> void:
	if not Session.in_room() or Session.game.is_empty():
		UI.goto(self, "res://menu.tscn")
		return
	_box = UI.page(self)
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
	if _countdown != null:
		_countdown.text = "%d s" % int(ceil(left))
	if _bar != null:
		var fraction: float = left / maxf(_total_s, 0.1)
		UI.set_bar_fraction(_bar, fraction)
		if fraction < 0.25 and left > 0.0:
			_bar.modulate.a = 0.55 + 0.45 * absf(sin(_now() * 8.0))
		else:
			_bar.modulate.a = 1.0


func _on_error(message: String) -> void:
	_toast = message
	_render(Session.game)


func _on_connection_lost() -> void:
	_toast = "Connexion perdue avec le serveur."
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
		c.queue_free()
	_countdown = null
	_bar = null
	_bid_edit = null
	_deadline_s = -1.0
	var phase: String = str(game.get("phase", ""))
	var loc: Dictionary = game.get("location", {})
	var me: Dictionary = _me(game)
	var header := HBoxContainer.new()
	header.add_theme_constant_override("separation", 10)
	_box.add_child(header)
	UI.chip(header, str(loc.get("name", "")))
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(spacer)
	if not me.is_empty():
		UI.chip(header, ItemCard.format_money(int(me["budget"])), "MoneyChip", "MoneyLabel")
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
	var key: String = "%s_%d" % [phase, int(game.get("item_index", 0))]
	if key != _anim_key:
		_anim_key = key
		Fx.stagger_in(_box, 0.05)
	if phase == "finished" and not _confetti_done:
		_confetti_done = true
		if _is_winner(game):
			add_child(Confetti.new())


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
	ItemCard.make_label(_box, "Objet %d / %d" % [int(game["item_index"]), int(game["item_total"])], "FieldLabel")
	var last: Variant = game.get("last_result")
	if last is Dictionary:
		var lr: Dictionary = last
		if lr["winner"] == null:
			ItemCard.make_label(_box, "%s : invendu." % str(lr["item"]["name"]), "MutedLabel")
		else:
			ItemCard.make_label(_box, "%s remporté par %s pour %s." % [
				str(lr["item"]["name"]), str(lr["winner"]), ItemCard.format_money(int(lr["price"]))], "InfoLabel")
	_box.add_child(ItemCard.make_card(item))
	ItemCard.make_label(_box, "Valeur indicative : %s - vous misez le montant que vous voulez." % ItemCard.format_money(int(a["start_price"])), "MutedLabel")

	var leader_id: String = str(a["leader_id"]) if a["leader_id"] != null else ""
	var hero := PanelContainer.new()
	hero.theme_type_variation = "HeroPanel"
	_box.add_child(hero)
	var hbox := VBoxContainer.new()
	hbox.add_theme_constant_override("separation", 8)
	hero.add_child(hbox)
	if a["current_bid"] == null:
		ItemCard.make_label(hbox, "Aucune mise pour l'instant", "MutedLabel")
	else:
		ItemCard.make_label(hbox, "Mise actuelle - " + _pseudo_of(game, leader_id), "MutedLabel")
		var bid_label: Label = ItemCard.make_label(hbox, ItemCard.format_money(int(a["current_bid"])), "BigMoneyLabel")
		if int(a["current_bid"]) != _last_bid:
			Fx.pop(bid_label)
	_last_bid = int(a["current_bid"]) if a["current_bid"] != null else -1
	_bar = UI.timer_bar(hbox)
	_countdown = ItemCard.make_label(hbox, "", "MutedLabel")
	if a["seconds_left"] != null:
		_start_timer(float(a["seconds_left"]), float(settings["bid_timer"]))

	var folded: Array = a["folded"]
	var is_leader: bool = leader_id == Session.player_id
	var is_folded: bool = folded.has(Session.player_id)
	var budget: int = int(me.get("budget", 0))
	var required: int = int(a["required_bid"])
	if is_leader:
		ItemCard.make_label(_box, "Vous menez cette enchère.", "InfoLabel")
	elif is_folded:
		ItemCard.make_label(_box, "Vous êtes couché pour cet objet.", "MutedLabel")
	else:
		_render_bid_controls(a, budget, required)


func _render_bid_controls(a: Dictionary, budget: int, required: int) -> void:
	var item_id: String = str(a["item"]["id"])
	if item_id != _bid_item_id or _bid_value < required:
		_bid_item_id = item_id
		_bid_value = required
	_bid_value = mini(_bid_value, maxi(budget, required))
	ItemCard.make_label(_box, "Votre mise (minimum %s)" % ItemCard.format_money(required), "FieldLabel")
	_bid_edit = LineEdit.new()
	_bid_edit.text = str(_bid_value)
	_bid_edit.alignment = HORIZONTAL_ALIGNMENT_CENTER
	_bid_edit.virtual_keyboard_type = LineEdit.KEYBOARD_TYPE_NUMBER
	_bid_edit.add_theme_font_size_override("font_size", 40)
	_bid_edit.text_changed.connect(_on_bid_text)
	_box.add_child(_bid_edit)
	var chips := HBoxContainer.new()
	chips.add_theme_constant_override("separation", 8)
	_box.add_child(chips)
	for delta in [10, 50, 100, 250]:
		var b := Button.new()
		b.text = "+%d" % delta
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		b.pressed.connect(_on_adjust.bind(delta, budget))
		chips.add_child(b)
	var max_b: Button = UI.button(_box, "Tout mon budget (%s)" % ItemCard.format_money(budget))
	max_b.disabled = budget < required
	max_b.pressed.connect(_on_set_bid.bind(budget))
	var bid_b: Button = UI.button(_box, "Miser", "PrimaryButton")
	bid_b.disabled = budget < required
	bid_b.pressed.connect(_on_bid)
	var f: Button = UI.button(_box, "Se coucher", "DangerButton")
	f.pressed.connect(_on_fold)


func _on_bid_text(t: String) -> void:
	_bid_value = int(t) if t.is_valid_int() else 0


func _on_adjust(delta: int, budget: int) -> void:
	_on_set_bid(mini(_bid_value + delta, budget))


func _on_set_bid(amount: int) -> void:
	_bid_value = amount
	if _bid_edit != null:
		_bid_edit.text = str(amount)


func _on_bid() -> void:
	Session.send({"type": "bid", "amount": _bid_value})


func _on_fold() -> void:
	Session.send({"type": "fold"})


# ------------------------------------------------------------------- joueurs
func _render_players(game: Dictionary) -> void:
	ItemCard.make_label(_box, "Joueurs", "HeadingLabel")
	var leader_id: String = ""
	var folded: Array = []
	if game.get("auction") is Dictionary:
		var a: Dictionary = game["auction"]
		leader_id = str(a["leader_id"]) if a["leader_id"] != null else ""
		folded = a["folded"]
	for p in game["players"]:
		var d: Dictionary = p
		var items: Array = d["items"]
		var line: String = "%s - %s - %d objet(s)" % [str(d["pseudo"]), ItemCard.format_money(int(d["budget"])), items.size()]
		if str(d["id"]) == leader_id:
			line += " - mène"
		elif folded.has(str(d["id"])):
			line += " - couché"
		var row := PanelContainer.new()
		var col := VBoxContainer.new()
		row.add_child(col)
		ItemCard.make_label(col, line)
		if items.size() > 0:
			var names: PackedStringArray = []
			for it in items:
				names.append(str(it["name"]))
			ItemCard.make_label(col, ", ".join(names), "MutedLabel")
		_box.add_child(row)


# ---------------------------------------------------------------------- vote
func _render_voting(game: Dictionary) -> void:
	var vote: Dictionary = game["vote"]
	ItemCard.make_label(_box, "Vote : quelle collection est la meilleure ?", "HeadingLabel")
	_bar = UI.timer_bar(_box)
	_countdown = ItemCard.make_label(_box, "", "MutedLabel")
	_start_timer(float(vote["seconds_left"]), 45.0)
	var mine: Variant = vote.get("your_vote")
	for p in game["players"]:
		var d: Dictionary = p
		if str(d["id"]) == Session.player_id:
			continue
		var chosen: bool = mine != null and str(mine) == str(d["id"])
		var card := PanelContainer.new()
		var col := VBoxContainer.new()
		col.add_theme_constant_override("separation", 6)
		card.add_child(col)
		ItemCard.make_label(col, str(d["pseudo"]), "HeadingLabel")
		_add_purchase_lines(col, d["purchases"])
		var b: Button = UI.button(col, "Voter pour " + str(d["pseudo"]) + (" (votre choix)" if chosen else ""), "PrimaryButton" if chosen else "")
		b.pressed.connect(_on_vote.bind(str(d["id"])))
		_box.add_child(card)
	var voted: Array = vote["voted_ids"]
	ItemCard.make_label(_box, "%d / %d votes" % [voted.size(), game["players"].size()], "MutedLabel")


func _on_vote(target: String) -> void:
	Session.send({"type": "vote", "target": target})


# ------------------------------------------------------------------ résultats
func _add_purchase_lines(parent: Node, purchases: Array) -> void:
	if purchases.is_empty():
		ItemCard.make_label(parent, "Aucun achat.", "MutedLabel")
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
	ItemCard.make_label(_box, "Résultats", "TitleLabel")
	var scenario: Variant = game.get("scenario")
	if scenario is Dictionary:
		var sc: Dictionary = scenario
		ItemCard.make_label(_box, str(sc["title"]) + " - " + str(sc["text"]), "MutedLabel")
	for r in game["results"]:
		var row: Dictionary = r
		var card := PanelContainer.new()
		if bool(row["winner"]):
			card.theme_type_variation = "HeroPanel"
		var col := VBoxContainer.new()
		col.add_theme_constant_override("separation", 6)
		card.add_child(col)
		var title: String = "%d. %s" % [int(row["rank"]), str(row["pseudo"])]
		if bool(row["winner"]):
			title += " - gagnant"
		ItemCard.make_label(col, title, "HeadingLabel")
		ItemCard.make_label(col, "%d pts" % int(row["score"]), "BigMoneyLabel")
		ItemCard.make_label(col, "Objets %d - Synergies %d - Budget restant %s" % [
			int(row["items_points"]), int(row["synergy_points"]), ItemCard.format_money(int(row["budget"]))], "MutedLabel")
		if str(game["mode"]) == "construction":
			ItemCard.make_label(col, "Votes reçus : %d (+%d)" % [int(row["votes"]), int(row["vote_points"])], "MutedLabel")
		for t in row["trials"]:
			var tr: Dictionary = t
			ItemCard.make_label(col, "%s : %d / %d - %s (+%d)" % [
				str(tr["name"]), int(tr["value"]), int(tr["threshold"]),
				"réussie" if bool(tr["success"]) else "échouée", int(tr["points"])],
				"InfoLabel" if bool(tr["success"]) else "ErrorLabel")
		ItemCard.make_label(col, "Achats (%s dépensés)" % ItemCard.format_money(int(row["spent"])), "FieldLabel")
		_add_purchase_lines(col, row["purchases"])
		_box.add_child(card)
	var back: Button = UI.button(_box, "Retour au menu", "PrimaryButton")
	back.pressed.connect(_on_back)


func _on_back() -> void:
	Session.leave_room()
	UI.goto(self, "res://menu.tscn")
