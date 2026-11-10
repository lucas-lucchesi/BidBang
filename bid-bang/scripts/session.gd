extends Node
## Autoload : pseudo, adresse du serveur, salon courant et dernier état reçu.

signal room_updated(room: Dictionary)
signal game_updated(game: Dictionary)
signal error_received(message: String)
signal connection_lost()

const NetClient = preload("res://scripts/net_client.gd")
const CONFIG_PATH := "user://settings.cfg"
const DEFAULT_SERVER := "http://127.0.0.1:8000"

var pseudo: String = ""
var server_url: String = DEFAULT_SERVER
var code: String = ""
var player_id: String = ""
var token: String = ""
var room: Dictionary = {}
var game: Dictionary = {}
var net: Node = null
var _leaving: bool = false


func _ready() -> void:
	net = NetClient.new()
	add_child(net)
	net.room_state.connect(_on_room_state)
	net.game_state.connect(_on_game_state)
	net.server_error.connect(func(m: String) -> void: error_received.emit(m))
	net.socket_closed.connect(_on_socket_closed)
	_load_settings()


func _load_settings() -> void:
	var cfg := ConfigFile.new()
	if cfg.load(CONFIG_PATH) == OK:
		pseudo = str(cfg.get_value("player", "pseudo", ""))
		server_url = str(cfg.get_value("server", "url", DEFAULT_SERVER))


func save_settings() -> void:
	var cfg := ConfigFile.new()
	cfg.set_value("player", "pseudo", pseudo)
	cfg.set_value("server", "url", server_url)
	cfg.save(CONFIG_PATH)


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
