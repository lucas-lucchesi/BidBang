extends RefCounted
## Animations réutilisables. Usage : const Fx = preload("res://scripts/fx.gd")


## Fait apparaître les enfants un par un (fondu), sans toucher à leur position.
static func stagger_in(parent: Node, step: float = 0.06, duration: float = 0.35) -> void:
	var i: int = 0
	for c in parent.get_children():
		if c is CanvasItem and not c.is_queued_for_deletion():
			var ci: CanvasItem = c
			ci.modulate.a = 0.0
			var tw: Tween = ci.create_tween()
			tw.tween_property(ci, "modulate:a", 1.0, duration).set_delay(i * step)
			i += 1


## Petit rebond (agrandissement puis retour) autour du centre du contrôle.
static func pop(node: Control, strength: float = 1.18) -> void:
	await node.get_tree().process_frame
	if not is_instance_valid(node):
		return
	node.pivot_offset = node.size / 2.0
	node.scale = Vector2(strength, strength)
	var tw: Tween = node.create_tween()
	tw.tween_property(node, "scale", Vector2.ONE, 0.3).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)


## Pulsation d'opacité en boucle (alerte).
static func pulse(node: CanvasItem, low: float = 0.55, period: float = 0.5) -> void:
	var tw: Tween = node.create_tween().set_loops()
	tw.tween_property(node, "modulate:a", low, period)
	tw.tween_property(node, "modulate:a", 1.0, period)
