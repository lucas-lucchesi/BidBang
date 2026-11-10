extends Control

const FONT = preload("res://assets/fonts/PressStart2P-Regular.ttf")
const VS := 2.0
## Logo animé : médaillon "BB" entouré d'ondes qui rappellent le coup de marteau.

var _t: float = 0.0


func _ready() -> void:
	custom_minimum_size = Vector2(0, 120)
	mouse_filter = Control.MOUSE_FILTER_IGNORE


func _process(delta: float) -> void:
	_t += delta
	queue_redraw()


func _draw() -> void:
	var center := Vector2(size.x * VS / 2.0, size.y * VS / 2.0)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2(1.0 / VS, 1.0 / VS))
	var amber := Color(0.96, 0.62, 0.12, 1)
	for i in 3:
		var ph: float = fmod(_t * 0.6 + i / 3.0, 1.0)
		var r: float = 70.0 + ph * 80.0
		draw_arc(center, r, 0.0, TAU, 64, Color(amber.r, amber.g, amber.b, (1.0 - ph) * 0.5), 4.0, false)
	draw_circle(center, 84.0, Color(amber.r, amber.g, amber.b, 0.15))
	draw_circle(center, 66.0, Color(0.1, 0.09, 0.14, 1))
	draw_arc(center, 66.0, 0.0, TAU, 64, amber, 7.0, false)
	draw_arc(center, 54.0, 0.0, TAU, 64, Color(1, 0.85, 0.5, 0.4), 2.0, false)
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
	var rc: Vector2 = center / VS
	draw_string(FONT, Vector2(rc.x - 24.0, rc.y + 12.0), "BB", HORIZONTAL_ALIGNMENT_CENTER, 48.0, 32, Color(1, 0.82, 0.4, 1))
