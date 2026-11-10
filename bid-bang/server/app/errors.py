"""Erreurs métier : les messages sont renvoyés tels quels au joueur (en français)."""


class GameError(Exception):
    """Action refusée par les règles ou l'état de la partie."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
