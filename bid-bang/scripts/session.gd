extends Node
## Autoload : pseudo, adresse du serveur, salon courant et dernier état reçu.

signal room_updated(room: Dictionary)
signal game_updated(game: Dictionary)
signal error_received(message: String)
signal connection_lost()

const NetClient = preload("res://scripts/net_client.gd")
const T = preload("res://scripts/texts.gd")
const CLICK_PATH := "res://assets/sounds/click.wav"
const CONFIG_PATH := "user://settings.cfg"
const DEFAULT_SERVER := "http://127.0.0.1:8000"

var pseudo: String = ""
var server_url: String = DEFAULT_SERVER
var code: String = ""
var player_id: String = ""
var token: String = ""
var room: Dictionary = {}
var game: Dictionary = {}
var net: NetClient = null
var language: String = "fr"
var volume: float = 0.8
var max_fps: int = 60
var _click: AudioStreamPlayer = null
var _leaving: bool = false


func _ready() -> void:
	net = NetClient.new()
	add_child(net)
	net.room_state.connect(_on_room_state)
	net.game_state.connect(_on_game_state)
	net.server_error.connect(func(m: String) -> void: error_received.emit(m))
	net.socket_closed.connect(_on_socket_closed)
	_load_settings()
	apply_settings()
	_setup_click_sound()


func _load_settings() -> void:
	var cfg := ConfigFile.new()
	if cfg.load(CONFIG_PATH) == OK:
		pseudo = str(cfg.get_value("player", "pseudo", ""))
		server_url = str(cfg.get_value("server", "url", DEFAULT_SERVER))
		language = str(cfg.get_value("settings", "language", "fr"))
		volume = clampf(float(cfg.get_value("settings", "volume", 0.8)), 0.0, 1.0)
		max_fps = int(cfg.get_value("settings", "max_fps", 60))


func save_settings() -> void:
	var cfg := ConfigFile.new()
	cfg.set_value("player", "pseudo", pseudo)
	cfg.set_value("server", "url", server_url)
	cfg.set_value("settings", "language", language)
	cfg.set_value("settings", "volume", volume)
	cfg.set_value("settings", "max_fps", max_fps)
	cfg.save(CONFIG_PATH)


## Applique langue, volume général et limite de FPS (0 = illimité).
func apply_settings() -> void:
	T.language = language
	AudioServer.set_bus_volume_db(0, linear_to_db(maxf(volume, 0.0001)))
	AudioServer.set_bus_mute(0, volume <= 0.001)
	Engine.max_fps = max_fps


## Son de clic joué pour tout bouton (connecté automatiquement à chaque bouton créé).
func _setup_click_sound() -> void:
	if not ResourceLoader.exists(CLICK_PATH):
		return
	_click = AudioStreamPlayer.new()
	_click.stream = load(CLICK_PATH)
	add_child(_click)
	get_tree().node_added.connect(_on_node_added)


func _on_node_added(node: Node) -> void:
	if node is BaseButton:
		var b: BaseButton = node
		if not b.pressed.is_connected(_play_click):
			b.pressed.connect(_play_click)


func _play_click() -> void:
	if _click != null:
		_click.play()


func is_host() -> bool:
	return str(room.get("host_id", "")) == player_id


func in_room() -> bool:
	return code != ""


## Enregistre la réponse de POST /rooms ou /rooms/{code}/join et ouvre le WebSocket.
func enter_room(payload: Dictionary) -> void:
	code = str(payload["code"])
	player_id = str(payload["player_id"])
	token = str(payload["token"])
	room = payload["room"]
	game = {}
	_leaving = false
	net.connect_socket(server_url, code, token)


func send(message: Dictionary) -> void:
	net.send(message)


func leave_room() -> void:
	_leaving = true
	net.send({"type": "leave"})
	net.close_socket()
	code = ""
	player_id = ""
	token = ""
	room = {}
	game = {}


func _on_room_state(r: Dictionary) -> void:
	room = r
	room_updated.emit(r)


func _on_game_state(g: Dictionary) -> void:
	game = g
	game_updated.emit(g)


func _on_socket_closed() -> void:
	if not _leaving and in_room():
		connection_lost.emit()
