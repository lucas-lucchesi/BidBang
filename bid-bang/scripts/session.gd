extends Node
## Autoload : pseudo, adresse du serveur, salon courant et dernier état reçu.
##
## Adresse du serveur :
##  - application native (PC, Android, iOS) et développement : valeur des Paramètres, par défaut
##    http://127.0.0.1:8000 (émulateur Android : http://10.0.2.2:8000) ;
##  - version Web servie depuis localhost / 127.0.0.1 (test local) : idem, le paramètre `?server=`
##    de l'URL est accepté ;
##  - version Web publique : l'adresse HTTPS du serveur vient du fichier `config.json` servi à côté de
##    `index.html` (voir DEPLOY_WEB.md). Elle n'est ni modifiable, ni sauvegardée, ni remplaçable par
##    l'URL de la page : sinon un lien piégé enverrait le jeu (et une clé API) vers un autre serveur.
##    Le navigateur ne contacte jamais 127.0.0.1.

signal room_updated(room: Dictionary)
signal game_updated(game: Dictionary)
signal error_received(message: String)
signal connection_lost()
signal kicked()
signal rematch_started()
signal server_config_ready()

const NetClient = preload("res://scripts/net_client.gd")
const T = preload("res://scripts/texts.gd")
const CLICK_PATH := "res://assets/sounds/click.wav"
const THEMES := {"dark": "res://theme/main_theme.tres", "light": "res://theme/light_theme.tres"}
const CONFIG_PATH := "user://settings.cfg"
const DEFAULT_SERVER := "http://127.0.0.1:8000"
const WEB_CONFIG_PATH := "/config.json"
const LOCAL_PAGE_HOSTS := ["localhost", "127.0.0.1", "[::1]", "::1"]

var pseudo: String = ""
var server_url: String = DEFAULT_SERVER
var server_locked: bool = false  # Web public : adresse imposée par config.json
var server_ready: bool = true  # false tant que config.json n'est pas lu (Web public)
var server_problem: String = ""  # raison si le serveur n'est pas utilisable (Web public)
var code: String = ""
var player_id: String = ""
var token: String = ""
var room: Dictionary = {}
var game: Dictionary = {}
var net: NetClient = null
var notice: String = ""  # message à afficher au menu (ex. exclusion)
var language: String = "fr"
var theme_mode: String = "dark"  # "dark" ou "light"
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
	net.kicked.connect(_on_kicked)
	net.rematch.connect(_on_rematch)
	_load_settings()
	apply_settings()
	_setup_click_sound()
	if OS.has_feature("web"):
		_init_web_server()


func _load_settings() -> void:
	var cfg := ConfigFile.new()
	if cfg.load(CONFIG_PATH) == OK:
		pseudo = str(cfg.get_value("player", "pseudo", ""))
		if not OS.has_feature("web"):  # sur le Web, l'adresse enregistrée est ignorée (voir _init_web_server)
			server_url = str(cfg.get_value("server", "url", DEFAULT_SERVER))
		language = str(cfg.get_value("settings", "language", "fr"))
		theme_mode = str(cfg.get_value("settings", "theme", "dark"))
		if not THEMES.has(theme_mode):
			theme_mode = "dark"
		volume = clampf(float(cfg.get_value("settings", "volume", 0.8)), 0.0, 1.0)
		max_fps = int(cfg.get_value("settings", "max_fps", 60))


func save_settings() -> void:
	var cfg := ConfigFile.new()
	cfg.set_value("player", "pseudo", pseudo)
	if not server_locked:
		cfg.set_value("server", "url", server_url)
	cfg.set_value("settings", "language", language)
	cfg.set_value("settings", "theme", theme_mode)
	cfg.set_value("settings", "volume", volume)
	cfg.set_value("settings", "max_fps", max_fps)
	cfg.save(CONFIG_PATH)


## Applique langue, volume général et limite de FPS (0 = illimité).
func apply_settings() -> void:
	T.language = language
	AudioServer.set_bus_volume_db(0, linear_to_db(maxf(volume, 0.0001)))
	AudioServer.set_bus_mute(0, volume <= 0.001)
	Engine.max_fps = max_fps
	get_window().theme = load(str(THEMES[theme_mode]))


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


func is_light() -> bool:
	return theme_mode == "light"


func server_url_valid() -> bool:
	if server_locked:  # Web public : HTTPS obligatoire, jamais d'adresse locale
		return server_url.begins_with("https://")
	return server_url.begins_with("http://") or server_url.begins_with("https://")


## Texte à afficher si le serveur n'est pas encore utilisable (vide quand tout va bien).
func server_status_text() -> String:
	if not server_ready:
		return "Connexion au serveur de jeu en cours, réessayez dans un instant."
	if server_locked and server_problem != "":
		return server_problem
	return ""


# ------------------------------------------------------------------ version Web
func _init_web_server() -> void:
	var host: String = str(JavaScriptBridge.eval("window.location.hostname", true))
	if LOCAL_PAGE_HOSTS.has(host):
		# test local (python -m http.server) : serveur FastAPI local, ou `?server=` dans l'URL
		var wanted: String = str(JavaScriptBridge.eval("new URLSearchParams(window.location.search).get('server') || ''", true)).strip_edges()
		if wanted.begins_with("http://") or wanted.begins_with("https://"):
			server_url = wanted
		return
	server_locked = true
	server_ready = false
	server_url = ""
	var origin: String = str(JavaScriptBridge.eval("window.location.origin", true))
	var req := HTTPRequest.new()
	req.timeout = 10.0
	add_child(req)
	req.request_completed.connect(_on_web_config.bind(req))
	var err: int = req.request(origin + WEB_CONFIG_PATH + "?t=" + str(Time.get_ticks_msec()))
	if err != OK:
		_on_web_config(HTTPRequest.RESULT_CANT_CONNECT, 0, PackedStringArray(), PackedByteArray(), req)


func _on_web_config(result: int, code: int, _headers: PackedStringArray, body: PackedByteArray, req: HTTPRequest) -> void:
	req.queue_free()
	server_ready = true
	if result == HTTPRequest.RESULT_SUCCESS and code == 200:
		var parsed: Variant = JSON.parse_string(body.get_string_from_utf8())
		if parsed is Dictionary:
			var url: String = str((parsed as Dictionary).get("server_url", "")).strip_edges().rstrip("/")
			if url.begins_with("https://"):
				server_url = url
	if server_url == "":
		server_problem = "Le serveur de jeu n'est pas configuré (config.json). Prévenez l'organisateur."
	server_config_ready.emit()


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


## L'hôte relance une partie dans le même salon : l'ancien état de partie est oublié, sinon le
## salon d'attente retournerait aussitôt à l'écran de partie.
func _on_rematch() -> void:
	game = {}
	rematch_started.emit()


func _on_kicked() -> void:
	_leaving = true
	net.close_socket()
	code = ""
	player_id = ""
	token = ""
	room = {}
	game = {}
	notice = "Vous avez été exclu du salon par l'hôte."
	kicked.emit()


func _on_socket_closed() -> void:
	if not _leaving and in_room():
		connection_lost.emit()
