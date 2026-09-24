"""Pydantic schemas for the /players endpoints.

Same split as team.py: these describe the JSON crossing the wire, kept
separate from the SQLAlchemy `Player` model so a client cannot set `id` or
the timestamps, and so new database columns do not leak into responses.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models.enums import BattingStyle, BowlingStyle, PlayerRole


def clean_name(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("name must not be blank")
    return cleaned


class PlayerBase(BaseModel):
    """Fields a client is allowed to supply.

    The three style/role fields are typed as the StrEnums themselves, not as
    plain strings. Pydantic then rejects anything outside the allowed values
    with a 422, and FastAPI renders them as dropdowns in /docs - all for free.
    """

    name: str = Field(max_length=100, examples=["Anbu"])
    photo_url: str | None = Field(default=None, examples=[None])
    batting_style: BattingStyle | None = Field(
        default=None, examples=[BattingStyle.RIGHT_HAND]
    )
    bowling_style: BowlingStyle | None = Field(
        default=None, examples=[BowlingStyle.RIGHT_ARM_MEDIUM]
    )
    # Matches the database default, so a client can leave it out entirely.
    player_role: PlayerRole = Field(
        default=PlayerRole.BATTER, examples=[PlayerRole.ALL_ROUNDER]
    )

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str) -> str:
        return clean_name(value)


class PlayerCreate(PlayerBase):
    """Request body for POST /players."""


class PlayerUpdate(BaseModel):
    """Request body for PATCH /players/{id} - every field optional.

    This deliberately does NOT inherit PlayerBase. Inheriting would carry over
    `name: str` as required, which is the opposite of what PATCH needs. Every
    field is restated as `| None = None` so the route can use
    `model_dump(exclude_unset=True)` and touch only what was actually sent.
    """

    name: str | None = Field(default=None, max_length=100)
    photo_url: str | None = None
    batting_style: BattingStyle | None = None
    bowling_style: BowlingStyle | None = None
    player_role: PlayerRole | None = None

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str | None) -> str | None:
        return None if value is None else clean_name(value)


class PlayerRead(PlayerBase):
    """What the API sends back."""

    # Lets Pydantic build this from a SQLAlchemy object's attributes rather
    # than from a plain dict, so a route can `return player` directly.
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
