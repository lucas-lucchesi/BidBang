extends Control
## Fond animé : dégradé vertical + halos lumineux qui dérivent lentement.

const ORB_COUNT := 8

var _orbs: Array[Dictionary] = []
var _t: float = 0.0


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	var palette: Array[Color] = [
		Color(0.96, 0.62, 0.12), Color(0.25, 0.8, 0.68),
		Color(0.45, 0.4, 0.95), Color(0.95, 0.35, 0.5),
	]
	for i in ORB_COUNT:
		_orbs.append({
			"x": rng.randf(), "y": rng.randf(),
			"r": rng.randf_range(0.12, 0.3),
			"sx": rng.randf_range(0.03, 0.08), "sy": rng.randf_range(0.02, 0.06),
			"ph": rng.randf() * TAU,
			"c": palette[i % palette.size()],
		})


func _process(delta: float) -> void:
	_t += delta
	queue_redraw()


func _draw() -> void:
	var w: float = size.x
	var h: float = size.y
	var top := Color(0.10, 0.10, 0.20, 1)
	var bottom := Color(0.03, 0.04, 0.08, 1)
	draw_polygon(PackedVector2Array([Vector2(0, 0), Vector2(w, 0), Vector2(w, h), Vector2(0, h)]),
		PackedColorArray([top, top, bottom, bottom]))
	var base: float = minf(w, h)
	for o in _orbs:
		var d: Dictionary = o
		var px: float = (float(d["x"]) + sin(_t * float(d["sx"]) + float(d["ph"])) * 0.15) * w
		var py: float = (float(d["y"]) + cos(_t * float(d["sy"]) + float(d["ph"])) * 0.12) * h
		var col: Color = d["c"]
		var radius: float = float(d["r"]) * base * 1.6
		for k in 5:
			var f: float = 1.0 - k * 0.18
			draw_circle(Vector2(px, py), radius * f, Color(col.r, col.g, col.b, 0.018))
