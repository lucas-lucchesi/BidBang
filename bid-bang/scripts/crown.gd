extends Control
## Petite couronne pixel pour le vainqueur du podium.


func _ready() -> void:
	custom_minimum_size = Vector2(28, 14)
	size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	mouse_filter = Control.MOUSE_FILTER_IGNORE


func _draw() -> void:
	var gold := Color(1, 0.8, 0.25)
	var dark := Color(0.5, 0.3, 0.05)
	draw_colored_polygon(PackedVector2Array([
		Vector2(2, 13), Vector2(2, 4), Vector2(8, 8), Vector2(14, 1), Vector2(20, 8), Vector2(26, 4), Vector2(26, 13)]), gold)
	draw_rect(Rect2(2, 11, 24, 2), dark)
	draw_rect(Rect2(13, 3, 2, 2), Color(1, 0.4, 0.4))
