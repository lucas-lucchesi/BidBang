extends Control
## Illustration d'une carte dessinée en code : halo, rayons tournants, médaillon
## avec monogramme et étoiles de rareté. La teinte dépend du premier tag.

const RARITY_COLORS := [
	Color(0.7, 0.72, 0.8, 1), Color(0.4, 0.7, 1, 1),
	Color(0.75, 0.5, 1, 1), Color(1, 0.75, 0.25, 1),
]

var rarity: int = 0
var title: String = "?"
var tag: String = ""
var _t: float = 0.0


func setup(item: Dictionary) -> void:
	rarity = clampi(int(item.get("rarity", 0)), 0, 3)
	title = str(item.get("name", "?"))
	var tags: Array = item.get("tags", [])
	tag = str(tags[0]) if tags.size() > 0 else ""
	custom_minimum_size = Vector2(0, 170)
	mouse_filter = Control.MOUSE_FILTER_IGNORE


func _process(delta: float) -> void:
	_t += delta
	queue_redraw()


func _tint() -> Color:
	var h: float = float(hash(tag) % 360) / 360.0
	return Color.from_hsv(h, 0.55, 0.45)


func _star(center: Vector2, r: float, col: Color) -> void:
	var pts := PackedVector2Array()
	for i in 10:
		var rad: float = r if i % 2 == 0 else r * 0.45
		var a: float = -PI / 2.0 + i * PI / 5.0
		pts.append(center + Vector2(cos(a), sin(a)) * rad)
	draw_colored_polygon(pts, col)


func _draw() -> void:
	var w: float = size.x
	var h: float = size.y
	var center := Vector2(w / 2.0, h / 2.0 - 8.0)
	var tint: Color = _tint()
	var accent: Color = RARITY_COLORS[rarity]
	var bg := StyleBoxFlat.new()
	bg.bg_color = tint.darkened(0.55)
	bg.set_corner_radius_all(14)
	draw_style_box(bg, Rect2(0, 0, w, h))
	for k in 7:
		var f: float = 1.0 - k * 0.12
		draw_circle(center, h * 0.52 * f, Color(tint.r, tint.g, tint.b, 0.12))
	var rays: int = 10
	for i in rays:
		var a0: float = _t * 0.25 + i * TAU / rays
		var a1: float = a0 + TAU / rays * 0.4
		var rr: float = h * 0.5
		draw_colored_polygon(PackedVector2Array([
			center, center + Vector2(cos(a0), sin(a0)) * rr, center + Vector2(cos(a1), sin(a1)) * rr,
		]), Color(accent.r, accent.g, accent.b, 0.07))
	var pulse: float = 1.0 + sin(_t * 2.0) * 0.02
	draw_circle(center, 50.0 * pulse + 6.0, Color(accent.r, accent.g, accent.b, 0.25))
	draw_circle(center, 50.0 * pulse, Color(0.08, 0.09, 0.15, 1))
	draw_arc(center, 50.0 * pulse, 0.0, TAU, 48, accent, 5.0, true)
	draw_arc(center, 41.0 * pulse, 0.0, TAU, 48, Color(accent.r, accent.g, accent.b, 0.35), 2.0, true)
	var font: Font = ThemeDB.fallback_font
	var letter: String = title.substr(0, 1).to_upper()
	draw_string(font, Vector2(center.x - 40.0, center.y + 22.0), letter,
		HORIZONTAL_ALIGNMENT_CENTER, 80.0, 64, accent)
	var n: int = rarity + 1
	for i in n:
		var sx: float = center.x + (i - (n - 1) / 2.0) * 24.0
		_star(Vector2(sx, h - 18.0), 9.0, accent)
	if rarity >= 2:
		for i in 4:
			var ph: float = _t * 1.3 + i * 1.7
			var sp := Vector2(w * (0.15 + 0.7 * fmod(i * 0.37 + 0.1, 1.0)), h * (0.2 + 0.5 * fmod(i * 0.53 + 0.2, 1.0)))
			var al: float = maxf(0.0, sin(ph))
			_star(sp, 5.0 + 4.0 * al, Color(1, 1, 1, 0.8 * al))
