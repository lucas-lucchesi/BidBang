extends Control
## Logo BidBang dessiné en code : explosion colorée, « BID » crème et « BANG! » orange avec contour.
## Légère oscillation en boucle (Tween), rebond à l'apparition.

const FONT = preload("res://assets/fonts/Fredoka.ttf")
const INK := Color("#10262F")
const RAYS := 16

var _font: FontVariation = null


func _ready() -> void:
	custom_minimum_size = Vector2(620, 340)
	size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_font = FontVariation.new()
	_font.base_font = FONT
	_font.variation_opentype = {2003265652: 700.0}
	pivot_offset = custom_minimum_size / 2.0
	rotation_degrees = -3.0
	scale = Vector2(0.4, 0.4)
	modulate.a = 0.0
	var tw: Tween = create_tween()
	tw.set_parallel(true)
	tw.tween_property(self, "scale", Vector2.ONE, 0.6).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tw.tween_property(self, "modulate:a", 1.0, 0.25)
	var wob: Tween = create_tween().set_loops()
	wob.tween_property(self, "rotation_degrees", 2.5, 1.8).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	wob.tween_property(self, "rotation_degrees", -3.0, 1.8).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)


func _burst(c: Vector2, outer: float, inner: float, col: Color, rot: float) -> void:
	var pts := PackedVector2Array()
	for i in RAYS * 2:
		var a: float = rot + i * PI / RAYS
		var rad: float = outer if i % 2 == 0 else inner
		pts.append(c + Vector2(cos(a), sin(a)) * rad)
	draw_colored_polygon(pts, col)


func _title(text: String, base: float, fs: int, fill: Color, outline: int) -> void:
	var tw: Vector2 = _font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, fs)
	var pos := Vector2((size.x - tw.x) / 2.0, base)
	draw_string(_font, pos + Vector2(0, 8), text, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, INK)
	draw_string_outline(_font, pos + Vector2(0, 8), text, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, outline, INK)
	draw_string_outline(_font, pos, text, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, outline, INK)
	draw_string(_font, pos, text, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, fill)


func _draw() -> void:
	var c := Vector2(size.x / 2.0, size.y * 0.5)
	_burst(c + Vector2(0, 8), 168.0, 128.0, Color(0.04, 0.1, 0.13, 0.4), 0.1)
	_burst(c, 168.0, 128.0, INK, 0.1)
	_burst(c, 160.0, 124.0, Color("#C4685A"), 0.1)
	_burst(c, 140.0, 112.0, Color("#72A48A"), 0.3)
	draw_circle(c, 112.0, INK)
	draw_circle(c, 106.0, Color("#2C5362"))
	_title("BID", c.y - 8.0, 104, Color("#F3E4C9"), 14)
	_title("BANG!", c.y + 110.0, 124, Color("#E8A044"), 16)
