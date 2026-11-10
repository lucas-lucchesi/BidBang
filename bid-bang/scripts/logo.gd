extends Control
## Logo animé : médaillon "BB" entouré d'ondes qui rappellent le coup de marteau.

var _t: float = 0.0


func _ready() -> void:
	custom_minimum_size = Vector2(0, 240)
	mouse_filter = Control.MOUSE_FILTER_IGNORE


func _process(delta: float) -> void:
	_t += delta
	queue_redraw()


func _draw() -> void:
	var center := Vector2(size.x / 2.0, size.y / 2.0)
	var amber := Color(0.96, 0.62, 0.12, 1)
	for i in 3:
		var ph: float = fmod(_t * 0.6 + i / 3.0, 1.0)
		var r: float = 70.0 + ph * 80.0
		draw_arc(center, r, 0.0, TAU, 64, Color(amber.r, amber.g, amber.b, (1.0 - ph) * 0.5), 4.0, true)
	draw_circle(center, 84.0, Color(amber.r, amber.g, amber.b, 0.15))
	draw_circle(center, 66.0, Color(0.1, 0.09, 0.14, 1))
	draw_arc(center, 66.0, 0.0, TAU, 64, amber, 7.0, true)
	draw_arc(center, 54.0, 0.0, TAU, 64, Color(1, 0.85, 0.5, 0.4), 2.0, true)
	var squash: float = 1.0 + maxf(0.0, sin(_t * 3.77)) * 0.0
	var font: Font = ThemeDB.fallback_font
	draw_string(font, Vector2(center.x - 50.0, center.y + 22.0 * squash), "BB",
		HORIZONTAL_ALIGNMENT_CENTER, 100.0, 64, Color(1, 0.82, 0.4, 1))
