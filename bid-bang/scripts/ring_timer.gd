extends Control
## Chronomètre circulaire : anneau qui se vide, secondes au centre.
## Vert > 50 %, orange > 25 %, rouge ensuite. set_state(secondes_restantes, fraction).

const FONT = preload("res://assets/fonts/Fredoka.ttf")
const INK := Color("#10262F")

var seconds: int = 0
var fraction: float = 1.0
var _font: FontVariation = null


func _ready() -> void:
	custom_minimum_size = Vector2(132, 132)
	size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	size_flags_vertical = Control.SIZE_SHRINK_CENTER
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	pivot_offset = custom_minimum_size / 2.0
	_font = FontVariation.new()
	_font.base_font = FONT
	_font.variation_opentype = {2003265652: 700.0}


func set_state(secs: int, frac: float) -> void:
	var f: float = clampf(frac, 0.0, 1.0)
	if secs != seconds or absf(f - fraction) > 0.004:
		seconds = secs
		fraction = f
		queue_redraw()


func ring_color() -> Color:
	if fraction > 0.5:
		return Color("#72A48A")
	if fraction > 0.25:
		return Color("#E8A044")
	return Color("#C4685A")


func _draw() -> void:
	var c: Vector2 = size / 2.0
	var r: float = minf(size.x, size.y) / 2.0 - 6.0
	draw_circle(c + Vector2(0, 4), r + 4.0, Color(0.04, 0.1, 0.13, 0.45))
	draw_circle(c, r + 4.0, INK)
	draw_circle(c, r, Color("#173845"))
	var w: float = 16.0
	draw_arc(c, r - w / 2.0 - 4.0, 0.0, TAU, 48, Color("#10262F"), w, true)
	if fraction > 0.0:
		draw_arc(c, r - w / 2.0 - 4.0, -PI / 2.0, -PI / 2.0 + TAU * fraction, 48, ring_color(), w - 4.0, true)
	var txt: String = str(seconds)
	var fs: int = 54
	var tw: Vector2 = _font.get_string_size(txt, HORIZONTAL_ALIGNMENT_LEFT, -1, fs)
	draw_string(_font, Vector2(c.x - tw.x / 2.0, c.y + fs * 0.22), txt, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, Color("#F3E4C9"))
	var tag: String = "s"
	var tw2: Vector2 = _font.get_string_size(tag, HORIZONTAL_ALIGNMENT_LEFT, -1, 22)
	draw_string(_font, Vector2(c.x - tw2.x / 2.0, c.y + 38.0), tag, HORIZONTAL_ALIGNMENT_LEFT, -1, 22, Color("#B0C2C2"))
