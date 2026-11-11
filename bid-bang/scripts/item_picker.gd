extends VBoxContainer
## Sélecteur d'objets réutilisable (parties personnalisées et parties avec IA).
## Recherche, filtres (catégories / choisis / générés par l'IA), compteur, liste d'objets avec
## bouton Ajouter / Retirer. Les lignes sont construites une seule fois, puis seulement
## masquées ou affichées (rapide sur téléphone).
## Usage :
##   const ItemPicker = preload("res://scripts/item_picker.gd")
##   var picker: VBoxContainer = ItemPicker.new()
##   parent.add_child(picker)
##   picker.call("setup", items, categories, selected_ids, required_count)
##   picker.connect("selection_changed", _on_count)
##   var ids: Array = picker.call("selected_ids")

signal selection_changed(count: int)

const UI = preload("res://scripts/ui.gd")
const ItemCard = preload("res://scripts/item_card.gd")
const T = preload("res://scripts/texts.gd")
const ART_EXTENSIONS := ["png", "jpg", "webp"]

var selected: Dictionary = {}  # id -> true
var required: int = 1
var _by_id: Dictionary = {}
var _rows: Dictionary = {}  # id -> {"line": Control, "button": Button}
var _search: LineEdit = null
var _filter: String = "all"
var _list: VBoxContainer = null
var _counter: Label = null
var _chosen_flow: HFlowContainer = null
var _empty: Label = null


func setup(items: Array, categories: Array, selected_ids: Array, required_count: int) -> void:
	required = required_count
	add_theme_constant_override("separation", 14)
	for sid in selected_ids:
		selected[str(sid)] = true
	_counter = UI.label(self, "", "HeadingLabel")
	var chosen: VBoxContainer = UI.section(self, T.t("Objets choisis"))
	_chosen_flow = HFlowContainer.new()
	_chosen_flow.add_theme_constant_override("h_separation", 8)
	_chosen_flow.add_theme_constant_override("v_separation", 8)
	chosen.add_child(_chosen_flow)
	_search = LineEdit.new()
	_search.placeholder_text = T.t("Rechercher un objet...")
	_search.clear_button_enabled = true
	_search.text_changed.connect(func(_t: String) -> void: _apply_filter())
	add_child(_search)
	var has_ai: bool = false
	for it in items:
		var d: Dictionary = it
		if str(d.get("source", "")) == "ai":
			has_ai = true
	var labels: Array = ["Tous", "Choisis"]
	var values: Array = ["all", "selected"]
	for c in categories:
		labels.append(str(c))
		values.append("cat:" + str(c))
	if has_ai:
		labels.insert(2, "Générés par l'IA")
		values.insert(2, "ai")
	UI.choice_row(self, "", labels, values, "all", _on_filter)
	_list = VBoxContainer.new()
	_list.add_theme_constant_override("separation", 12)
	add_child(_list)
	_empty = UI.label(self, T.t("Aucun objet ne correspond."), "MutedLabel")
	_empty.visible = false
	for it in items:
		var item: Dictionary = it
		_by_id[str(item["id"])] = item
		_build_row(item)
	_refresh_summary()
	_apply_filter()


func selected_ids() -> Array:
	var out: Array = []
	for k in selected:
		out.append(str(k))
	return out


func _has_art(item_id: String) -> bool:
	for ext in ART_EXTENSIONS:
		if ResourceLoader.exists("res://assets/items/%s.%s" % [item_id, ext]):
			return true
	return false


func _build_row(item: Dictionary) -> void:
	var item_id: String = str(item["id"])
	var line := HBoxContainer.new()
	line.add_theme_constant_override("separation", 10)
	_list.add_child(line)
	var col := VBoxContainer.new()
	col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	col.add_theme_constant_override("separation", 4)
	line.add_child(col)
	# illustration seulement si une image existe (sinon le médaillon animé alourdit la liste)
	col.add_child(ItemCard.make_card(item, true, _has_art(item_id), true, 96.0))
	var sub: String = str(item.get("category", ""))
	var desc: String = str(item.get("description", ""))
	if desc != "":
		sub += " - " + desc
	if sub != "":
		var sl: Label = ItemCard.make_label(col, sub, "MutedLabel")
		sl.add_theme_font_size_override("font_size", 20)
	var btn: Button = UI.button(line, "Ajouter", "SmallButton")
	btn.custom_minimum_size = Vector2(150, 64)
	btn.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	btn.pressed.connect(_toggle.bind(item_id))
	_rows[item_id] = {"line": line, "button": btn}
	_style_button(item_id)


func _style_button(item_id: String) -> void:
	var btn: Button = (_rows[item_id] as Dictionary)["button"]
	if selected.has(item_id):
		btn.text = T.t("Retirer")
		btn.theme_type_variation = "SuccessButton"
	else:
		btn.text = T.t("Ajouter")
		btn.theme_type_variation = "SmallButton"


func _toggle(item_id: String) -> void:
	if selected.has(item_id):
		selected.erase(item_id)
	else:
		selected[item_id] = true
	_style_button(item_id)
	_refresh_summary()
	if _filter == "selected":
		_apply_filter()
	selection_changed.emit(selected.size())


func _on_filter(value: Variant) -> void:
	_filter = str(value)
	_apply_filter()


func _matches(item: Dictionary, needle: String) -> bool:
	var item_id: String = str(item["id"])
	if _filter == "selected" and not selected.has(item_id):
		return false
	if _filter == "ai" and str(item.get("source", "")) != "ai":
		return false
	if _filter.begins_with("cat:") and str(item.get("category", "")) != _filter.substr(4):
		return false
	if needle == "":
		return true
	var hay: String = "%s %s %s" % [str(item.get("name", "")), str(item.get("category", "")),
		" ".join(PackedStringArray(item.get("tags", [])))]
	return hay.to_lower().contains(needle)


func _apply_filter() -> void:
	var needle: String = _search.text.strip_edges().to_lower()
	var shown: int = 0
	for item_id in _rows:
		var ok: bool = _matches(_by_id[item_id], needle)
		((_rows[item_id] as Dictionary)["line"] as Control).visible = ok
		if ok:
			shown += 1
	_empty.visible = shown == 0


func _refresh_summary() -> void:
	var n: int = selected.size()
	_counter.text = T.t("Sélection : %d objet(s) - minimum %d") % [n, required]
	_counter.theme_type_variation = "HeadingLabel" if n >= required else "ErrorLabel"
	for c in _chosen_flow.get_children():
		_chosen_flow.remove_child(c)
		c.queue_free()
	if n == 0:
		UI.label(_chosen_flow, T.t("Aucun objet choisi."), "MutedLabel")
		return
	for k in selected:
		UI.chip(_chosen_flow, str((_by_id[str(k)] as Dictionary).get("name", "?")))
