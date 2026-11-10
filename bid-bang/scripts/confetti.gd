extends Control
## Confettis de victoire : pluie de petits rectangles colorés pendant quelques secondes.

const COUNT := 90
const DURATION := 5.0

var _parts: Array[Dictionary] = []
var _t: float = 0.0


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var rng := RandomNumberGenerator.new()
	rng.randomize()
	var palette: Array[Color] = [
		Color(0.96, 0.62, 0.12), Color(0.25, 0.8, 0.68), Color(0.95, 0.35, 0.5),
		Color(0.45, 0.55, 1.0), Color(1, 0.85, 0.3),
	]
	for i in COUNT:
		_parts.append({
			"x": rng.randf(), "y": -rng.randf() * 0.6,
			"vy": rng.randf_range(0.25, 0.6), "sway": rng.randf_range(0.02, 0.08),
			"ph": rng.randf() * TAU, "rot": rng.randf() * TAU, "spin": rng.randf_range(-6.0, 6.0),
			"w": rng.randf_range(8.0, 16.0), "h": rng.randf_range(5.0, 9.0),
			"c": palette[rng.randi() % palette.size()],
		})


func _process(delta: float) -> void:
	_t += delta
	if _t > DURATION:
		queue_free()
		return
	for p in _parts:
		var d: Dictionary = p
		d["y"] = float(d["y"]) + float(d["vy"]) * delta
		d["rot"] = float(d["rot"]) + float(d["spin"]) * delta
	queue_redraw()


func _draw() -> void:
	var fade: float = clampf((DURATION - _t) / 1.0, 0.0, 1.0)
	for p in _parts:
		var d: Dictionary = p
		var pos := Vector2((float(d["x"]) + sin(_t * 2.0 + float(d["ph"])) * float(d["sway"])) * size.x,
			float(d["y"]) * size.y)
		if pos.y < -20.0 or pos.y > size.y + 20.0:
			continue
		var col: Color = d["c"]
		col.a = fade
		draw_set_transform(pos, float(d["rot"]), Vector2.ONE)
		draw_rect(Rect2(-float(d["w"]) / 2.0, -float(d["h"]) / 2.0, float(d["w"]), float(d["h"])), col)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
