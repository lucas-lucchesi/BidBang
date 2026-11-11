"""Erreurs métier : les messages sont renvoyés tels quels au joueur (en français)."""


class GameError(Exception):
    """Action refusée par les règles ou l'état de la partie.

    `status` : code HTTP utilisé quand l'erreur remonte d'une route HTTP (400 par défaut).
    """

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status
