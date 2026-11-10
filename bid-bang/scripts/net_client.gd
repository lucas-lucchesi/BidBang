extends Node
## Client réseau : HTTP (créer / rejoindre un salon) + WebSocket temps réel.

signal http_done(tag: String, ok: bool, data: Dictionary)
signal room_state(room: Dictionary)
signal game_state(game: Dictionary)
signal server_error(message: String)
signal socket_closed()

var _socket: WebSocketPeer = null
var _socket_open: bool = false


func _ws_url(base: String, code: String, token: String) -> String:
	var url: String = base.strip_edges().rstrip("/")
	if url.begins_with("https://"):
		url = "wss://" + url.substr(8)
	elif url.begins_with("http://"):
		url = "ws://" + url.substr(7)
	return "%s/ws/%s?token=%s" % [url, code, token.uri_encode()]


func request(tag: String, base: String, method: int, path: String, body: Dictionary = {}) -> void:
	var req := HTTPRequest.new()
	req.timeout = 10.0
	add_child(req)
	req.request_completed.connect(_on_request_completed.bind(req, tag))
	var headers: PackedStringArray = ["Content-Type: application/json"]
	var payload: String = JSON.stringify(body) if method != HTTPClient.METHOD_GET else ""
	var err: int = req.request(base.strip_edges().rstrip("/") + path, headers, method, payload)
	if err != OK:
		req.queue_free()
		http_done.emit(tag, false, {"detail": "Impossible de contacter le serveur."})


func _on_request_completed(result: int, code: int, _headers: PackedStringArray, body: PackedByteArray, req: HTTPRequest, tag: String) -> void:
	req.queue_free()
	if result != HTTPRequest.RESULT_SUCCESS:
		http_done.emit(tag, false, {"detail": "Impossible de contacter le serveur."})
		return
	var parsed: Variant = JSON.parse_string(body.get_string_from_utf8())
	var data: Dictionary = parsed if parsed is Dictionary else {}
	if code >= 200 and code < 300:
		http_done.emit(tag, true, data)
	else:
		if not data.has("detail"):
			data["detail"] = "Erreur du serveur (%d)." % code
		http_done.emit(tag, false, data)


func connect_socket(base: String, code: String, token: String) -> void:
	close_socket()
	_socket = WebSocketPeer.new()
	_socket.inbound_buffer_size = 1 << 20
	var err: int = _socket.connect_to_url(_ws_url(base, code, token))
	if err != OK:
		_socket = null
		socket_closed.emit()
		return
	_socket_open = false
	set_process(true)


func close_socket() -> void:
	if _socket != null:
		_socket.close()
	_socket = null
	_socket_open = false


func send(message: Dictionary) -> void:
	if _socket != null and _socket_open:
		_socket.send_text(JSON.stringify(message))


func _process(_delta: float) -> void:
	if _socket == null:
		return
	_socket.poll()
	var state: int = _socket.get_ready_state()
	if state == WebSocketPeer.STATE_OPEN:
		_socket_open = true
		while _socket.get_available_packet_count() > 0:
			_handle_packet(_socket.get_packet().get_string_from_utf8())
	elif state == WebSocketPeer.STATE_CLOSED:
		_socket = null
		_socket_open = false
		socket_closed.emit()


func _handle_packet(text: String) -> void:
	var parsed: Variant = JSON.parse_string(text)
	if not (parsed is Dictionary):
		return
	var msg: Dictionary = parsed
	var kind: String = str(msg.get("type", ""))
	match kind:
		"room_state":
			room_state.emit(msg["room"])
		"game_state":
			game_state.emit(msg["game"])
		"error":
			server_error.emit(str(msg.get("message", "Erreur.")))
