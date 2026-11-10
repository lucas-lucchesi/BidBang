from pydantic import BaseModel, Field


class CreateRoomRequest(BaseModel):
    pseudo: str = Field(min_length=1, max_length=40)
    settings: dict | None = None


class JoinRoomRequest(BaseModel):
    pseudo: str = Field(min_length=1, max_length=40)
