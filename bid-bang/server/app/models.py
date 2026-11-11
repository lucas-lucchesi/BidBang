from pydantic import BaseModel, Field, SecretStr


class CreateRoomRequest(BaseModel):
    pseudo: str = Field(min_length=1, max_length=40)
    settings: dict | None = None


class JoinRoomRequest(BaseModel):
    pseudo: str = Field(min_length=1, max_length=40)


class SelectionRequest(BaseModel):
    item_ids: list[str] = Field(max_length=200)


class GenerateRequest(BaseModel):
    """Demande de génération IA. La clé API est un SecretStr : absente des repr / logs."""
    provider: str = Field(default="anthropic", max_length=30)
    api_key: SecretStr = Field(min_length=10, max_length=300)
