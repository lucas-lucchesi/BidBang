from pydantic import BaseModel, Field, SecretStr, model_validator


class CreateRoomRequest(BaseModel):
    pseudo: str = Field(min_length=1, max_length=40)
    settings: dict | None = None


class JoinRoomRequest(BaseModel):
    pseudo: str = Field(min_length=1, max_length=40)


class SelectionRequest(BaseModel):
    item_ids: list[str] = Field(max_length=200)
    criteria: list[dict] | None = Field(default=None, max_length=40)  # critères modifiés par l'hôte


class PreviewRequest(BaseModel):
    """Aperçu des points : critères de situation + objets du catalogue. Sans rien créer."""
    criteria: list[dict] = Field(max_length=40)
    item_ids: list[str] = Field(max_length=200)


class GenerateRequest(BaseModel):
    """Demande de génération IA. La clé API est un SecretStr : absente des repr / logs.

    `use_env_key` : pour les essais locaux, utiliser la variable d'environnement
    GEMINI_API_KEY du serveur (voir main.py pour les conditions) au lieu d'envoyer une clé.
    """
    provider: str = Field(default="gemini", max_length=30)
    api_key: SecretStr | None = Field(default=None, min_length=10, max_length=300)
    use_env_key: bool = False

    @model_validator(mode="after")
    def _key_or_env(self):
        if self.api_key is None and not self.use_env_key:
            raise ValueError("clé manquante")
        return self
