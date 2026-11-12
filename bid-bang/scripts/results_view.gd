extends RefCounted
## Écran de résultats : podium (points, puis budget restant), détail par joueur avec les objets
## remportés (prix estimé, prix payé, économie ou surcoût), classement des bonnes affaires et
## distinctions. Tout vient du serveur (game["results"], game["bargains"], game["awards"]) :
## le client n'additionne rien lui-même. Les distinctions sont informatives, jamais le gagnant.
## Usage : Results.build(parent, game, open_state, remember_callable)

const UI = preload("res://scripts/ui.gd")
const T = preload("res://scripts/texts.gd")
const ItemCard = preload("res://scripts/item_card.gd")
const Podium = preload("res://scripts/podium.gd")


static func build(parent: Node, game: Dictionary, open_state: Dictionary, remember: Callable) -> void:
	var results: Array = game.get("results", [])
	# A. Podium principal
	Podium.build(parent, results)
	# B + C. Tableau général : une carte dépliable par joueur, avec ses objets
	ItemCard.make_label(parent, T.t("Détail des joueurs"), "HeadingLabel")
	for r in results:
		_player_block(parent, r, open_state, remember)
	# E. Bonnes affaires
	_bargains(parent, game)


static func _stat_line(parent: Node, caption: String, value: String, color: Color = Color(0, 0, 0, 0)) -> void:
	var line := HBoxContainer.new()
	parent.add_child(line)
	var c: Label = ItemCard.make_label(line, caption, "MutedLabel")
	c.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var v: Label = ItemCard.make_label(line, value, "")
	v.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	# jamais de retour à la ligne dans la valeur : sinon la colonne de gauche (qui s'étire) l'écrase
	# jusqu'à un caractère de large
	v.autowrap_mode = TextServer.AUTOWRAP_OFF
	v.size_flags_horizontal = Control.SIZE_SHRINK_END
	if color.a > 0.0:
		v.add_theme_color_override("font_color", color)


static func _player_block(parent: Node, row: Dictionary, open_state: Dictionary, remember: Callable) -> void:
	var mine: bool = str(row["player_id"]) == Session.player_id
	var title: String = "%d. %s - %s" % [int(row["rank"]), str(row["pseudo"]), T.t("%d pts") % int(row["score"])]
	var key: String = "r_" + str(row["player_id"])
	var col: VBoxContainer = UI.collapsible(parent, title, bool(open_state.get(key, mine)), remember.bind(key))
	var savings: int = int(row["savings"])
	_stat_line(col, T.t("Points"), T.t("%d pts") % int(row["score"]))
	_stat_line(col, T.t("Valeur estimée"), ItemCard.format_money(int(row["estimated_value"])))
	_stat_line(col, T.t("Argent dépensé"), ItemCard.format_money(int(row["total_spent"])))
	# jamais seulement une couleur : le texte dit « économie » ou « surcoût »
	var sv_text: String = ItemCard.savings_text(savings) if int(row["items_count"]) > 0 else T.t("Aucun achat")
	var sv_color: Color = ItemCard.savings_color(savings) if int(row["items_count"]) > 0 else Color(0, 0, 0, 0)
	_stat_line(col, T.t("Économie"), sv_text, sv_color)
	_stat_line(col, T.t("Budget restant"), ItemCard.format_money(int(row["budget"])))
	# C. objets remportés
	var purchases: Array = row["purchases"]
	if purchases.is_empty():
		ItemCard.make_label(col, T.t("Aucun achat."), "MutedLabel")
		return
	ItemCard.make_label(col, T.t("Objets remportés (%d)") % purchases.size(), "FieldLabel")
	for pu in purchases:
		var d: Dictionary = pu
		col.add_child(ItemCard.make_card(d["item"], true, true, true, 96.0, int(d["purchase_price"])))


static func _bargains(parent: Node, game: Dictionary) -> void:
	var bargains: Array = game.get("bargains", [])
	if bargains.is_empty():
		return
	var box: VBoxContainer = UI.section(parent, T.t("Bonnes affaires"))
	ItemCard.make_label(box, T.t("Classement par économie : valeur estimée moins argent dépensé. Il ne change pas le gagnant."), "MutedLabel")
	for b in bargains:
		var d: Dictionary = b
		var value: String = T.t("aucun achat") if int(d["items_count"]) == 0 else _signed_money(int(d["savings"]))
		var color: Color = Color(0, 0, 0, 0) if int(d["items_count"]) == 0 else ItemCard.savings_color(int(d["savings"]))
		_stat_line(box, "%d. %s" % [int(d["rank"]), str(d["pseudo"])], value, color)
	var awards: Dictionary = game.get("awards", {})
	var lines: Array = []
	var best_bidder: Variant = awards.get("best_bidder")
	if best_bidder is Dictionary:
		var a: Dictionary = best_bidder
		lines.append([T.t("Meilleur enchérisseur"), "%s (%s)" % [str(a["pseudo"]), _signed_money(int(a["value"]))]])
	var best_deal: Variant = awards.get("best_deal")
	if best_deal is Dictionary:
		var a2: Dictionary = best_deal
		lines.append([T.t("Meilleure affaire"), "%s - %s (%s)" % [str(a2["pseudo"]), str((a2["item"] as Dictionary)["name"]), _signed_money(int(a2["value"]))]])
	var valuable: Variant = awards.get("most_valuable")
	if valuable is Dictionary:
		var a3: Dictionary = valuable
		lines.append([T.t("Collection la plus précieuse"), "%s (%s)" % [str(a3["pseudo"]), ItemCard.format_money(int(a3["value"]))]])
	var useful: Variant = awards.get("most_useful")
	if useful is Dictionary:
		var a4: Dictionary = useful
		lines.append([T.t("Collection la plus utile"), "%s (%s)" % [str(a4["pseudo"]), T.t("%d pts") % int(a4["value"])]])
	if lines.is_empty():
		return
	ItemCard.make_label(box, T.t("Distinctions"), "FieldLabel")
	for l in lines:
		var pair: Array = l
		ItemCard.make_label(box, "%s : %s" % [str(pair[0]), str(pair[1])], "InfoLabel")


static func _signed_money(amount: int) -> String:
	return ("+" if amount > 0 else "") + ItemCard.format_money(amount)
