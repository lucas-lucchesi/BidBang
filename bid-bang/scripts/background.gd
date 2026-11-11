extends Control
## Fond d'écran. Priorité : image du lieu (assets/backgrounds/<lieu>.png), puis assets/backgrounds/main.png,
## sinon fond dessiné en code (bleu pétrole, jetons colorés flottants).

const EXTENSIONS := ["png", "jpg", "webp"]
const FPS_STEP := 1.0 / 30.0
const BOKEH := 18
const CONFETTI := [Color(0.91, 0.627, 0.267), Color(0.447, 0.643, 0.541), Color(0.769, 0.408, 0.353), Color(0.953, 0.894, 0.788)]

var scene_id: String = ""  # id du lieu (facultatif)
var dim: float = 0.0       # assombrissement d'une image de fond (0 = aucun)
var _tex: Texture2D = null
var _bokeh: Array[Dictionary] = []
var _t: float = 0.0
var _acc: float = 0.0


func _find_image() -> Texture2D:
	var names: Array[String] = []
	if scene_id != "":
		names.append(scene_id)
	names.append("main")
	for n in names:
		for ext in EXTENSIONS:
			var path: String = "res://assets/backgrounds/%s.%s" % [n, ext]
			if ResourceLoader.exists(path):
				return load(path)
	return null


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_tex = _find_image()
	var rng := RandomNumberGenerator.new()
	rng.seed = 21
	for i in BOKEH:
		_bokeh.append({
			"x": rng.randf(), "y": rng.randf(), "r": rng.randf_range(0.015, 0.05),
			"sx": rng.randf_range(0.05, 0.14), "sy": rng.randf_range(0.03, 0.09),
			"ph": rng.randf() * TAU, "a": rng.randf_range(0.04, 0.11),
		})


func _process(delta: float) -> void:
	if _tex != null:
		return  # image fixe : pas de redessin
	_t += delta
	_acc += delta
	if _acc >= FPS_STEP:
		_acc = 0.0
		queue_redraw()


func _vignette(w: float, h: float, strength: float) -> void:
	var clear := Color(0, 0, 0, 0)
	var dark := Color(0, 0, 0, strength)
	var band: float = 0.28
	draw_polygon(PackedVector2Array([Vector2(0, 0), Vector2(w, 0), Vector2(w, h * band), Vector2(0, h * band)]), PackedColorArray([dark, dark, clear, clear]))
	draw_polygon(PackedVector2Array([Vector2(0, h * (1.0 - band)), Vector2(w, h * (1.0 - band)), Vector2(w, h), Vector2(0, h)]), PackedColorArray([clear, clear, dark, dark]))
	draw_polygon(PackedVector2Array([Vector2(0, 0), Vector2(w * 0.22, 0), Vector2(w * 0.22, h), Vector2(0, h)]), PackedColorArray([dark, clear, clear, dark]))
	draw_polygon(PackedVector2Array([Vector2(w * 0.78, 0), Vector2(w, 0), Vector2(w, h), Vector2(w * 0.78, h)]), PackedColorArray([clear, dark, dark, clear]))


func _draw() -> void:
	var area: Vector2 = get_viewport_rect().size
	var origin: Vector2 = -global_position
	if _tex != null:
		var ts: Vector2 = _tex.get_size()
		var k: float = maxf(area.x / ts.x, area.y / ts.y)
		var dest: Vector2 = ts * k
		draw_texture_rect(_tex, Rect2(origin + (area - dest) / 2.0, dest), false)
		if dim > 0.0:
			draw_rect(Rect2(origin, area), Color(0.96, 0.9, 0.78, dim) if Session.is_light() else Color(0.06, 0.15, 0.2, dim))
		return
	var w: float = area.x
	var h: float = area.y
	var light: bool = Session.is_light()
	var top := Color("#F8EDD5") if light else Color("#21495a")
	var bottom := Color("#E6D5B3") if light else Color("#142f3b")
	draw_set_transform(origin, 0.0, Vector2.ONE)
	draw_polygon(PackedVector2Array([Vector2(0, 0), Vector2(w, 0), Vector2(w, h), Vector2(0, h)]), PackedColorArray([top, top, bottom, bottom]))
	# grands disques doux (relief du « plateau de jeu »)
	draw_circle(Vector2(w * 0.85, h * 0.12), w * 0.55, Color(1, 1, 1, 0.35 if light else 0.025))
	draw_circle(Vector2(w * 0.1, h * 0.7), w * 0.7, Color(0.91, 0.627, 0.267, 0.03))
	draw_circle(Vector2(w * 0.8, h * 1.0), w * 0.6, Color(0.447, 0.643, 0.541, 0.05))
	# petits jetons colorés qui flottent lentement (ronds, anneaux, losanges)
	for i in _bokeh.size():
		var d: Dictionary = _bokeh[i]
		var px: float = (float(d["x"]) + sin(_t * float(d["sx"]) + float(d["ph"])) * 0.05) * w
		var py: float = (float(d["y"]) + cos(_t * float(d["sy"]) + float(d["ph"])) * 0.04) * h
		var r: float = float(d["r"]) * w * 0.8
		var col: Color = CONFETTI[i % CONFETTI.size()]
		col.a = float(d["a"]) * 1.6
		match i % 3:
			0:
				draw_circle(Vector2(px, py), r, col)
			1:
				draw_arc(Vector2(px, py), r, 0.0, TAU, 28, col, 4.0, true)
			_:
				draw_colored_polygon(PackedVector2Array([Vector2(px, py - r), Vector2(px + r * 0.8, py), Vector2(px, py + r), Vector2(px - r * 0.8, py)]), col)
	_vignette(w, h, 0.08 if light else 0.28)
