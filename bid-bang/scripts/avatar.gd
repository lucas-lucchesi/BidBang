extends Control
## Pastille de joueur : disque coloré (selon le pseudo) avec l'initiale. Option : couronne d'hôte.
## Usage : var a = Avatar.make("Lucas", 72); parent.add_child(a)

const FONT = preload("res://assets/fonts/Fredoka.ttf")
const COLORS := [
	Color("#E8A044"), Color("#72A48A"), Color("#C4685A"),
	Color("#6FA8C7"), Color("#A28CC9"), Color("#E3C15A"),
]
const INK := Color("#10262F")

var pseudo: String = "?"
var diameter: float = 72.0
var crown: bool = false
var _font: FontVariation = null


static func make(pseudo_text: String, d: float = 72.0, with_crown: bool = false) -> Control:
	var script: GDScript = load("res://scripts/avatar.gd")
	var a: Control = script.new()
	a.set("pseudo", pseudo_text)
	a.set("diameter", d)
	a.set("crown", with_crown)
	return a


static func color_for(pseudo_text: String) -> Color:
	return COLORS[posmod(hash(pseudo_text), COLORS.size())]


func _ready() -> void:
	custom_minimum_size = Vector2(diameter, diameter)
	size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	size_flags_vertical = Control.SIZE_SHRINK_CENTER
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_font = FontVariation.new()
	_font.base_font = FONT
	_font.variation_opentype = {2003265652: 700.0}


func _draw() -> void:
	var c := Vector2(diameter, diameter) / 2.0
	var col: Color = color_for(pseudo)
	draw_circle(c + Vector2(0, diameter * 0.06), diameter * 0.5, Color(0.04, 0.1, 0.13, 0.45))
	draw_circle(c, diameter * 0.5, INK)
	draw_circle(c, diameter * 0.5 - 4.0, col.darkened(0.25))
	draw_circle(c - Vector2(0, diameter * 0.03), diameter * 0.5 - 4.0, col)
	var fs: int = int(diameter * 0.52)
	var letter: String = pseudo.substr(0, 1).to_upper()
	var tw: Vector2 = _font.get_string_size(letter, HORIZONTAL_ALIGNMENT_LEFT, -1, fs)
	draw_string(_font, Vector2(c.x - tw.x / 2.0, c.y + fs * 0.34), letter, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, INK)
	if crown:
		var k: float = diameter / 72.0
		var p := Vector2(c.x - 15.0 * k, -2.0 * k)
		var pts := PackedVector2Array([p + Vector2(0, 22) * k, p + Vector2(0, 6) * k, p + Vector2(8, 14) * k,
			p + Vector2(15, 2) * k, p + Vector2(22, 14) * k, p + Vector2(30, 6) * k, p + Vector2(30, 22) * k])
		draw_colored_polygon(pts, Color("#F2C14E"))
		var ol := pts.duplicate()
		ol.append(pts[0])
		draw_polyline(ol, INK, 2.5, true)
