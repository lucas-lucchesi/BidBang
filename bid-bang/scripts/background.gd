extends Control
## Fond d'écran. Priorité : image du lieu (assets/backgrounds/<lieu>.png), puis assets/backgrounds/main.png,
## sinon fond dessiné en code (velours bordeaux, rayon de lumière dorée, bokeh).

const EXTENSIONS := ["png", "jpg", "webp"]
const FPS_STEP := 1.0 / 30.0
const BOKEH := 16

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
			draw_rect(Rect2(origin, area), Color(0.04, 0.01, 0.02, dim))
		return
	var w: float = area.x
	var h: float = area.y
	var top := Color(0.2, 0.06, 0.1, 1)
	var bottom := Color(0.04, 0.02, 0.04, 1)
	draw_set_transform(origin, 0.0, Vector2.ONE)
	draw_polygon(PackedVector2Array([Vector2(0, 0), Vector2(w, 0), Vector2(w, h), Vector2(0, h)]), PackedColorArray([top, top, bottom, bottom]))
	# rayon de lumière dorée venant du haut
	var beam := Color(1, 0.8, 0.45, 0.10)
	var none := Color(1, 0.8, 0.45, 0.0)
	draw_polygon(PackedVector2Array([Vector2(w * 0.42, 0), Vector2(w * 0.58, 0), Vector2(w * 0.95, h * 0.85), Vector2(w * 0.05, h * 0.85)]), PackedColorArray([beam, beam, none, none]))
	for k in 6:
		var f: float = 1.0 - k * 0.15
		draw_circle(Vector2(w * 0.5, 0), w * 0.9 * f, Color(1, 0.75, 0.4, 0.018))
	for o in _bokeh:
		var d: Dictionary = o
		var px: float = (float(d["x"]) + sin(_t * float(d["sx"]) + float(d["ph"])) * 0.06) * w
		var py: float = (float(d["y"]) + cos(_t * float(d["sy"]) + float(d["ph"])) * 0.05) * h
		var r: float = float(d["r"]) * w
		var a: float = float(d["a"]) * (0.7 + 0.3 * sin(_t * 0.8 + float(d["ph"])))
		draw_circle(Vector2(px, py), r, Color(1, 0.78, 0.4, a))
		draw_arc(Vector2(px, py), r, 0.0, TAU, 32, Color(1, 0.88, 0.6, a * 1.6), 2.0, true)
	_vignette(w, h, 0.65)
