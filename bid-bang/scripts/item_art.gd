extends Control
## Illustration d'une carte. Si assets/items/<id>.png (ou .jpg / .webp) existe, il est affiché ;
## sinon un médaillon dessiné en code : halo, anneau, initiale en Cinzel et gemmes de rareté.

const FONT = preload("res://assets/fonts/Fredoka.ttf")
const EXTENSIONS := ["png", "jpg", "webp"]
const RARITY_COLORS := [
	Color("#A9BDC0"), Color("#5FA8D3"), Color("#A98BD8"), Color("#F2C14E"),
]
const INK := Color("#10262F")

var rarity: int = 0
var title: String = "?"
var tag: String = ""
var _tex: Texture2D = null
var _t: float = 0.0
var _font: FontVariation = null


func setup(item: Dictionary) -> void:
	_font = FontVariation.new()
	_font.base_font = FONT
	_font.variation_opentype = {2003265652: 700.0}
	rarity = clampi(int(item.get("rarity", 0)), 0, 3)
	title = str(item.get("name", "?"))
	tag = str(item.get("category", ""))
	custom_minimum_size = Vector2(0, 260)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	for ext in EXTENSIONS:
		var path: String = "res://assets/items/%s.%s" % [str(item.get("id", "")), ext]
		if ResourceLoader.exists(path):
			_tex = load(path)
			break
	set_process(_tex == null)


func _process(delta: float) -> void:
	_t += delta
	queue_redraw()


func _tint() -> Color:
	var h: float = float(posmod(hash(tag), 360)) / 360.0
	return Color.from_hsv(h, 0.42, 0.52)


func _gem(center: Vector2, r: float, col: Color) -> void:
	draw_colored_polygon(PackedVector2Array([center + Vector2(0, -r), center + Vector2(r * 0.8, 0), center + Vector2(0, r), center + Vector2(-r * 0.8, 0)]), col)
	draw_colored_polygon(PackedVector2Array([center + Vector2(0, -r), center + Vector2(r * 0.8, 0), center]), col.lightened(0.35))


func _draw() -> void:
	var w: float = size.x
	var h: float = size.y
	var accent: Color = RARITY_COLORS[rarity]
	if _tex != null:
		var ts: Vector2 = _tex.get_size()
		var k: float = maxf(w / ts.x, h / ts.y)
		var dest: Vector2 = ts * k
		draw_texture_rect_region(_tex, Rect2(Vector2.ZERO, Vector2(w, h)), Rect2((ts - Vector2(w, h) / k) / 2.0, Vector2(w, h) / k))
		draw_rect(Rect2(0, 0, w, h), INK, false, 3.0)
		return
	var k2: float = clampf(minf(w, h) / 260.0, 0.4, 1.0)  # échelle du médaillon
	var tint: Color = _tint()
	var sb := StyleBoxFlat.new()
	sb.bg_color = tint
	sb.set_corner_radius_all(18)
	sb.set_border_width_all(3)
	sb.border_color = INK
	draw_style_box(sb, Rect2(0, 0, w, h))
	var c := Vector2(w / 2.0, h / 2.0 - 12.0 * k2)
	for i in 8:
		draw_circle(c, h * 0.52 * (1.0 - i * 0.1), Color(tint.r, tint.g, tint.b, 0.14))
	for i in 10:
		var a0: float = _t * 0.2 + i * TAU / 10.0
		var a1: float = a0 + TAU / 10.0 * 0.35
		draw_colored_polygon(PackedVector2Array([c, c + Vector2(cos(a0), sin(a0)) * h * 0.55, c + Vector2(cos(a1), sin(a1)) * h * 0.55]), Color(accent.r, accent.g, accent.b, 0.06))
	var pulse: float = 1.0 + sin(_t * 2.0) * 0.02
	var radius: float = 84.0 * k2 * pulse
	draw_circle(c, radius + 10.0 * k2, Color(accent.r, accent.g, accent.b, 0.22))
	draw_circle(c, radius, Color("#173845"))
	draw_arc(c, radius, 0.0, TAU, 64, accent, maxf(3.0, 6.0 * k2), true)
	draw_arc(c, radius - 14.0 * k2, 0.0, TAU, 64, Color(accent.r, accent.g, accent.b, 0.35), 2.0, true)
	var letter: String = title.substr(0, 1).to_upper()
	draw_string(_font, Vector2(c.x - 50.0 * k2, c.y + 28.0 * k2), letter, HORIZONTAL_ALIGNMENT_CENTER, 100.0 * k2, int(84.0 * k2), Color("#F3E4C9"))
	var n: int = rarity + 1
	for i in n:
		_gem(Vector2(c.x + (i - (n - 1) / 2.0) * 38.0 * k2, h - 30.0 * k2), 13.0 * k2, accent)
	if rarity >= 2:
		for i in 4:
			var ph: float = _t * 1.3 + i * 1.7
			var sp := Vector2(w * (0.12 + 0.76 * fmod(i * 0.37 + 0.1, 1.0)), h * (0.18 + 0.55 * fmod(i * 0.53 + 0.2, 1.0)))
			var al: float = maxf(0.0, sin(ph))
			draw_circle(sp, 3.0 + 4.0 * al, Color(1, 0.95, 0.8, 0.8 * al))
