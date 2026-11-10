extends Control
## Fond animé dessiné en code. Sans lieu : dégradé + halos. Avec un lieu (cabane, appartement,
## plage, montagne, bureau, station) : paysage du lieu avec de petites animations.

const ORB_COUNT := 8
const FPS_STEP := 1.0 / 30.0
const VS := 2.0  # les paysages sont dessinés pour 720x1280, puis réduits (jeu en 360x640)

const HALL = preload("res://assets/ui/fond_360.png")

var scene_id: String = ""
var dim: float = 0.0  # assombrissement du fond image (0 = aucun)
var _orbs: Array[Dictionary] = []
var _t: float = 0.0
var _acc: float = 0.0
var _vs: Vector2 = Vector2(720, 1280)


func set_scene(id: String) -> void:
	scene_id = id
	queue_redraw()


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
	_acc += delta
	if _acc >= FPS_STEP:
		_acc = 0.0
		queue_redraw()


# ------------------------------------------------------------------ utilitaires
func _r(i: int) -> float:
	return fposmod(sin(float(i) * 12.9898) * 43758.5453, 1.0)


func _sky(y0: float, y1: float, top: Color, bottom: Color) -> void:
	draw_polygon(PackedVector2Array([Vector2(0, y0), Vector2(_vs.x, y0), Vector2(_vs.x, y1), Vector2(0, y1)]),
		PackedColorArray([top, top, bottom, bottom]))


func _glow(c: Vector2, radius: float, col: Color, layers: int = 6) -> void:
	for k in layers:
		var f: float = 1.0 - float(k) / float(layers)
		draw_circle(c, radius * f, Color(col.r, col.g, col.b, col.a * 0.35))


func _stars(count: int, max_y: float, seed_offset: int = 0) -> void:
	for i in count:
		var p := Vector2(_r(i + seed_offset) * _vs.x, _r(i * 3 + 11 + seed_offset) * max_y)
		var tw: float = 0.5 + 0.5 * sin(_t * (0.8 + _r(i) * 2.0) + float(i))
		draw_circle(p, 1.0 + _r(i + 5) * 1.6, Color(1, 1, 1, 0.25 + 0.6 * tw))


func _ridge(base_y: float, amp: float, seed_v: float, drift: float) -> PackedVector2Array:
	var pts := PackedVector2Array()
	var x: float = 0.0
	while x <= _vs.x + 24.0:
		var xs: float = x + drift
		var y: float = base_y - amp * (0.6 * absf(sin(xs * 0.0055 + seed_v)) + 0.25 * absf(sin(xs * 0.013 + seed_v * 1.7)) + 0.15 * sin(xs * 0.03 + seed_v))
		pts.append(Vector2(x, y))
		x += 24.0
	pts.append(Vector2(_vs.x + 24.0, _vs.y))
	pts.append(Vector2(0, _vs.y))
	return pts


func _shift(pts: PackedVector2Array, dy: float) -> PackedVector2Array:
	var out := PackedVector2Array()
	for p in pts:
		out.append(Vector2(p.x, p.y + dy))
	return out


func _cloud(c: Vector2, s: float, col: Color) -> void:
	for k in 5:
		draw_circle(c + Vector2((k - 2) * s * 0.55, absf(k - 2) * s * 0.12), s * (0.6 - absf(k - 2) * 0.1), col)


func _pine(x: float, base_y: float, height: float, col: Color) -> void:
	draw_rect(Rect2(x - height * 0.03, base_y - height * 0.12, height * 0.06, height * 0.14), col)
	for i in 3:
		var top: float = base_y - height + i * height * 0.28
		var bot: float = top + height * 0.45
		var half: float = height * 0.16 * (1.0 + i * 0.55)
		draw_colored_polygon(PackedVector2Array([Vector2(x, top), Vector2(x + half, bot), Vector2(x - half, bot)]), col)


func _skyline(base_y: float, seed_v: int, hmin: float, hmax: float, col: Color, lit: bool, win_col: Color) -> void:
	var x: float = -10.0
	var i: int = seed_v
	while x < _vs.x:
		var bw: float = 36.0 + _r(i) * 54.0
		var bh: float = _vs.y * (hmin + _r(i + 100) * (hmax - hmin))
		var top: float = base_y - bh
		draw_rect(Rect2(x, top, bw, bh + 4.0), col)
		if lit:
			var cy: float = top + 12.0
			var row: int = 0
			while cy < base_y - 14.0:
				var cx: float = x + 7.0
				var colm: int = 0
				while cx < x + bw - 10.0:
					var id: int = i * 131 + row * 17 + colm
					if _r(id) > 0.5:
						var tw: float = 0.75 + 0.25 * sin(_t * 0.6 + float(id))
						draw_rect(Rect2(cx, cy, 8.0, 11.0), Color(win_col.r, win_col.g, win_col.b, win_col.a * tw))
					cx += 15.0
					colm += 1
				cy += 20.0
				row += 1
		x += bw + 2.0
		i += 1


# --------------------------------------------------------------------- paysages
func _base_transform() -> void:
	draw_set_transform(Vector2.ZERO, 0.0, Vector2(1.0 / VS, 1.0 / VS))


func _draw() -> void:
	_vs = size * VS
	_base_transform()
	match scene_id:
		"montagne":
			_draw_mountain()
		"cabane":
			_draw_cabin()
		"plage":
			_draw_beach()
		"appartement":
			_draw_city(Color(0.1, 0.06, 0.25), Color(0.5, 0.22, 0.42), Color(1, 0.85, 0.5, 0.7), Color(0.14, 0.09, 0.26), Color(0.06, 0.04, 0.13), false)
		"bureau":
			_draw_city(Color(0.04, 0.2, 0.28), Color(0.55, 0.78, 0.72), Color(0.7, 0.95, 1, 0.7), Color(0.1, 0.3, 0.38), Color(0.04, 0.14, 0.2), true)
		"station":
			_draw_station()
		"orbes":
			_draw_default()
		_:
			_draw_hall()
			return
	draw_rect(Rect2(Vector2.ZERO, _vs), Color(0, 0, 0, 0.22))


func _draw_hall() -> void:
	draw_set_transform(Vector2.ZERO, 0.0, Vector2.ONE)
	var tex_size: Vector2 = HALL.get_size()
	var k: float = maxf(size.x / tex_size.x, size.y / tex_size.y)
	var dest: Vector2 = tex_size * k
	draw_texture_rect(HALL, Rect2((size - dest) / 2.0, dest), false)
	if dim > 0.0:
		draw_rect(Rect2(Vector2.ZERO, size), Color(0.03, 0.01, 0.02, dim))


func _draw_default() -> void:
	var w: float = _vs.x
	var h: float = _vs.y
	_sky(0, h, Color(0.10, 0.10, 0.20, 1), Color(0.03, 0.04, 0.08, 1))
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


func _draw_mountain() -> void:
	var w: float = _vs.x
	var h: float = _vs.y
	_sky(0, h, Color(0.07, 0.11, 0.3), Color(0.9, 0.58, 0.5))
	_stars(40, h * 0.4)
	var moon := Vector2(w * 0.78, h * 0.16)
	_glow(moon, 90.0, Color(1, 0.95, 0.85, 0.5))
	draw_circle(moon, 30.0, Color(1, 0.97, 0.9))
	for k in 3:
		var cx: float = fposmod(w * (0.2 + k * 0.35) + _t * (6.0 + k * 3.0), w + 300.0) - 150.0
		_cloud(Vector2(cx, h * (0.2 + k * 0.08)), 38.0, Color(1, 1, 1, 0.14))
	var far: PackedVector2Array = _ridge(h * 0.66, h * 0.36, 1.3, _t * 2.0)
	draw_colored_polygon(far, Color(0.93, 0.96, 1.0))
	draw_colored_polygon(_shift(far, 26.0), Color(0.3, 0.36, 0.58))
	var mid: PackedVector2Array = _ridge(h * 0.78, h * 0.28, 4.1, _t * 4.0)
	draw_colored_polygon(mid, Color(0.85, 0.9, 1.0))
	draw_colored_polygon(_shift(mid, 18.0), Color(0.16, 0.21, 0.38))
	draw_colored_polygon(_ridge(h * 0.93, h * 0.2, 7.7, _t * 6.0), Color(0.06, 0.09, 0.18))
	for k in 24:
		var sx: float = fposmod(_r(k) * w + _t * 14.0, w)
		var sy: float = fposmod(_r(k + 40) * h + _t * (30.0 + _r(k) * 20.0), h)
		draw_circle(Vector2(sx, sy), 1.8, Color(1, 1, 1, 0.55))


func _draw_cabin() -> void:
	var w: float = _vs.x
	var h: float = _vs.y
	_sky(0, h, Color(0.02, 0.05, 0.11), Color(0.07, 0.2, 0.2))
	_stars(50, h * 0.45, 200)
	var moon := Vector2(w * 0.25, h * 0.14)
	_glow(moon, 100.0, Color(0.85, 0.95, 1, 0.45))
	draw_circle(moon, 32.0, Color(0.95, 0.98, 1))
	var x: float = -20.0
	var i: int = 0
	while x < w + 40.0:
		_pine(x, h * 0.74, h * (0.2 + _r(i) * 0.1), Color(0.04, 0.14, 0.14))
		x += 38.0 + _r(i + 9) * 22.0
		i += 1
	var gx: float = w * 0.6
	var gy: float = h * 0.9
	draw_rect(Rect2(gx - 70.0, gy - 80.0, 140.0, 80.0), Color(0.12, 0.07, 0.04))
	draw_colored_polygon(PackedVector2Array([Vector2(gx - 90.0, gy - 78.0), Vector2(gx, gy - 140.0), Vector2(gx + 90.0, gy - 78.0)]), Color(0.07, 0.04, 0.03))
	draw_rect(Rect2(gx + 40.0, gy - 140.0, 16.0, 40.0), Color(0.07, 0.04, 0.03))
	var flick: float = 0.8 + 0.2 * sin(_t * 9.0) * sin(_t * 5.3)
	_glow(Vector2(gx - 20.0, gy - 42.0), 70.0, Color(1, 0.7, 0.25, 0.55 * flick))
	draw_rect(Rect2(gx - 40.0, gy - 60.0, 40.0, 36.0), Color(1, 0.78, 0.35, flick))
	for k in 6:
		var ph: float = fposmod(_t * 0.25 + k / 6.0, 1.0)
		draw_circle(Vector2(gx + 48.0 + sin(ph * 6.0 + k) * 10.0, gy - 145.0 - ph * 110.0), 8.0 + ph * 18.0, Color(0.8, 0.82, 0.85, (1.0 - ph) * 0.2))
	x = -10.0
	i = 40
	while x < w + 40.0:
		_pine(x, h * 0.96, h * (0.3 + _r(i) * 0.12), Color(0.015, 0.06, 0.06))
		x += 70.0 + _r(i + 9) * 50.0
		i += 1
	for k in 16:
		var fx: float = fposmod(_r(k) * w + sin(_t * 0.5 + k) * 40.0, w)
		var fy: float = h * (0.55 + 0.4 * _r(k + 70)) + cos(_t * 0.7 + k) * 20.0
		var a: float = 0.3 + 0.7 * absf(sin(_t * 1.5 + k))
		_glow(Vector2(fx, fy), 14.0, Color(0.9, 1, 0.4, a), 3)
		draw_circle(Vector2(fx, fy), 2.2, Color(1, 1, 0.7, a))


func _draw_beach() -> void:
	var w: float = _vs.x
	var h: float = _vs.y
	var hz: float = h * 0.58
	_sky(0, hz * 0.6, Color(0.2, 0.17, 0.42), Color(0.9, 0.4, 0.35))
	_sky(hz * 0.6, hz, Color(0.9, 0.4, 0.35), Color(1, 0.78, 0.42))
	var sun := Vector2(w * 0.5, hz - 20.0)
	_glow(sun, 200.0, Color(1, 0.7, 0.3, 0.6))
	draw_circle(sun, 62.0, Color(1, 0.9, 0.55))
	_cloud(Vector2(fposmod(w * 0.2 + _t * 8.0, w + 300.0) - 150.0, h * 0.2), 40.0, Color(1, 0.7, 0.6, 0.35))
	_sky(hz, h * 0.82, Color(0.1, 0.45, 0.6), Color(0.02, 0.2, 0.35))
	for k in 7:
		var y0: float = hz + 14.0 + k * (h * 0.034)
		var pts := PackedVector2Array()
		var x: float = 0.0
		while x <= w + 20.0:
			pts.append(Vector2(x, y0 + sin(x * 0.02 + _t * (1.2 + k * 0.15) + k) * (3.0 + k)))
			x += 20.0
		draw_polyline(pts, Color(1, 0.95, 0.85, 0.16), 2.0)
	for k in 6:
		var rw: float = 120.0 - k * 16.0
		draw_rect(Rect2(sun.x - rw / 2.0 + sin(_t * 2.0 + k) * 6.0, hz + 10.0 + k * 22.0, rw, 5.0), Color(1, 0.8, 0.4, 0.4 - k * 0.05))
	var sand := PackedVector2Array([Vector2(0, h * 0.84), Vector2(w * 0.5, h * 0.79), Vector2(w, h * 0.83), Vector2(w, h), Vector2(0, h)])
	draw_colored_polygon(sand, Color(0.62, 0.46, 0.28))
	var sway: float = sin(_t * 0.8) * 6.0
	var trunk := PackedVector2Array()
	var base := Vector2(w * 0.18, h * 0.97)
	var top := Vector2(w * 0.27 + sway, h * 0.52)
	for k in 13:
		var f: float = float(k) / 12.0
		var bend: float = sin(f * PI) * -28.0
		trunk.append(base.lerp(top, f) + Vector2(bend, 0))
	draw_polyline(trunk, Color(0.12, 0.08, 0.05), 12.0, false)
	for k in 8:
		var ang: float = -PI + k * PI / 7.0 + sin(_t * 0.9 + k) * 0.05
		var leaf := PackedVector2Array()
		for j in 9:
			var f2: float = float(j) / 8.0
			var dir := Vector2(cos(ang), sin(ang))
			leaf.append(top + dir * f2 * 110.0 + Vector2(0, f2 * f2 * 50.0))
		draw_polyline(leaf, Color(0.03, 0.2, 0.1), 7.0, false)


func _draw_city(top_c: Color, bot_c: Color, win: Color, far_c: Color, near_c: Color, blinds: bool) -> void:
	var w: float = _vs.x
	var h: float = _vs.y
	_sky(0, h, top_c, bot_c)
	_stars(35, h * 0.35, 300)
	var moon := Vector2(w * 0.8, h * 0.13)
	_glow(moon, 70.0, Color(1, 0.95, 0.9, 0.35))
	draw_circle(moon, 24.0, Color(1, 0.97, 0.92))
	_skyline(h * 0.78, 1, 0.18, 0.42, far_c, true, Color(win.r, win.g, win.b, win.a * 0.6))
	_skyline(h * 0.95, 60, 0.1, 0.3, near_c, true, win)
	if blinds:
		for k in 14:
			draw_rect(Rect2(0, k * 16.0, w, 6.0), Color(0, 0, 0, 0.28))
		draw_rect(Rect2(w * 0.33 - 7.0, 0, 14.0, h), Color(0, 0, 0, 0.4))
		draw_rect(Rect2(w * 0.66 - 7.0, 0, 14.0, h), Color(0, 0, 0, 0.4))
		draw_rect(Rect2(0, h * 0.9, w, h * 0.1), Color(0.03, 0.06, 0.08))
		draw_rect(Rect2(w * 0.55, h * 0.8, 120.0, 80.0), Color(0.1, 0.16, 0.2))
		draw_rect(Rect2(w * 0.55 + 8.0, h * 0.8 + 8.0, 104.0, 56.0), Color(0.3, 0.7, 0.8, 0.5 + 0.1 * sin(_t * 2.0)))
	else:
		for k in 4:
			var ph: float = fposmod(_t * 0.04 + k / 4.0, 1.0)
			_cloud(Vector2(ph * (w + 300.0) - 150.0, h * (0.12 + k * 0.05)), 34.0, Color(0.9, 0.6, 0.8, 0.1))


func _draw_station() -> void:
	var w: float = _vs.x
	var h: float = _vs.y
	_sky(0, h, Color(0.01, 0.01, 0.05), Color(0.05, 0.04, 0.14))
	_stars(110, h, 500)
	var pc := Vector2(w * 0.5, h * 1.42)
	var pr: float = w * 0.95
	_glow(pc, pr + 40.0, Color(0.3, 0.7, 1, 0.5), 5)
	draw_circle(pc, pr, Color(0.06, 0.22, 0.55))
	draw_arc(pc, pr, PI * 1.1, PI * 1.9, 80, Color(0.5, 0.85, 1, 0.8), 6.0, false)
	for k in 8:
		var a: float = PI * 1.2 + k * 0.1 + _t * 0.01
		var p: Vector2 = pc + Vector2(cos(a), sin(a)) * (pr - 30.0 - _r(k) * 40.0)
		draw_circle(p, 26.0 + _r(k + 3) * 26.0, Color(0.2, 0.6, 0.35, 0.5))
		draw_circle(p + Vector2(12, -8), 18.0, Color(1, 1, 1, 0.25))
	var sp := Vector2(w * 0.68 - fposmod(_t * 3.0, 40.0), h * 0.28 + sin(_t * 0.4) * 8.0)
	draw_set_transform(sp / VS, 0.12 + sin(_t * 0.3) * 0.03, Vector2(1.0 / VS, 1.0 / VS))
	draw_rect(Rect2(-50, -13, 100, 26), Color(0.8, 0.82, 0.88))
	draw_rect(Rect2(-6, -34, 12, 68), Color(0.6, 0.62, 0.7))
	for side in [-1, 1]:
		var x0: float = 56.0 if side > 0 else -56.0 - 84.0
		draw_rect(Rect2(x0, -22, 84, 44), Color(0.08, 0.18, 0.5))
		for g in 4:
			draw_line(Vector2(x0 + g * 21.0, -22), Vector2(x0 + g * 21.0, 22), Color(0.4, 0.6, 1, 0.5), 1.5)
		draw_line(Vector2(x0, 0), Vector2(x0 + 84, 0), Color(0.4, 0.6, 1, 0.5), 1.5)
	draw_circle(Vector2(40, 0), 3.0, Color(1, 0.3, 0.3, 0.5 + 0.5 * sin(_t * 4.0)))
	_base_transform()
