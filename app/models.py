from typing import Literal

from pydantic import BaseModel, Field, field_validator

Category = Literal[
    "rescue",
    "medical",
    "food",
    "water",
    "shelter",
    "power",
    "transport",
    "supplies",
    "info",
    "other",
]
Status = Literal["new", "needs_location", "open", "matched", "fulfilled", "rejected", "duplicate"]


class Extraction(BaseModel):
    is_actionable: bool = False
    intent: Literal["need", "offer", "info", "ignore"] = "ignore"
    category: Category = "other"
    item: str = Field("", max_length=60)
    item_en: str = Field("", max_length=100)
    quantity: int | None = Field(None, ge=1, le=1000000)
    location_text: str = Field("", max_length=160)
    urgency: int = 1
    urgency_reason: str = Field("", max_length=80)
    vulnerable_flags: list[Literal["medical", "elderly", "child", "pregnant", "disabled"]] = []
    language: str = Field("en", max_length=8)
    romanized: bool = False
    message_en: str = Field("", max_length=200)
    contains_contact_info: bool = False
    possible_misinformation: bool = False
    confidence: float = 0.5
    ack_text: str = Field("", max_length=140)

    @field_validator("urgency", mode="before")
    @classmethod
    def clamp_urgency(cls, value: object) -> int:
        return max(1, min(5, int(value)))

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, value: object) -> float:
        return max(0, min(1, float(value)))


class Ingest(BaseModel):
    text: str = Field("", max_length=1000)
    chat_id: str = Field("demo", max_length=80)
    tg_message_id: int | None = None
    sender_id: str = Field("tester", max_length=80)
    sender_display: str | None = Field(None, max_length=80)
    simulated: bool = True
    edited: bool = False
    lat: float | None = Field(None, ge=-90, le=90)
    lng: float | None = Field(None, ge=-180, le=180)


class CardPatch(BaseModel):
    item: str | None = Field(None, min_length=1, max_length=60)
    item_en: str | None = Field(None, min_length=1, max_length=100)
    location_text: str | None = Field(None, max_length=160)
    urgency: int | None = Field(None, ge=1, le=5)
    status: Status | None = None


class Login(BaseModel):
    token: str = Field(max_length=512)


class Decision(BaseModel):
    note: str = Field("", max_length=500)


class DrillStart(BaseModel):
    speed: Literal[1, 3, 10] = 3


class Page(BaseModel):
    items: list[dict]
    next_cursor: int | None = None
