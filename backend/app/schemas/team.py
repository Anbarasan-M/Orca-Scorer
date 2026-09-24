"""Pydantic schemas for the /teams endpoints.

These describe the JSON crossing the wire. They are separate from the
SQLAlchemy `Team` model on purpose: a client must not be able to set `id` or
`created_at`, and we do not want new database columns leaking into responses
by accident.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def clean_name(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("name must not be blank")
    return cleaned


def clean_short_name(value: str) -> str:
    # The database CHECKs that short_name is upper case. Normalising here means
    # "orc" is accepted as "ORC" instead of blowing up at the database.
    cleaned = value.strip().upper()
    if len(cleaned) < 2:
        raise ValueError("short_name must be at least 2 characters")
    return cleaned


class TeamBase(BaseModel):
    """Fields a client is allowed to supply."""

    name: str = Field(max_length=100, examples=["Orcas"])
    short_name: str = Field(min_length=2, max_length=5, examples=["ORC"])
    logo_url: str | None = Field(default=None, examples=[None])

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str) -> str:
        return clean_name(value)

    @field_validator("short_name")
    @classmethod
    def _check_short_name(cls, value: str) -> str:
        return clean_short_name(value)


class TeamCreate(TeamBase):
    """Request body for POST /teams."""


class TeamUpdate(BaseModel):
    """Request body for PATCH /teams/{id} - every field optional.

    The route uses `model_dump(exclude_unset=True)` so that a field the client
    left out is untouched, while `"logo_url": null` genuinely clears the logo.
    """

    name: str | None = Field(default=None, max_length=100)
    short_name: str | None = Field(default=None, min_length=2, max_length=5)
    logo_url: str | None = None

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str | None) -> str | None:
        return None if value is None else clean_name(value)

    @field_validator("short_name")
    @classmethod
    def _check_short_name(cls, value: str | None) -> str | None:
        return None if value is None else clean_short_name(value)


class TeamRead(TeamBase):
    """What the API sends back."""

    # Lets Pydantic build this from a SQLAlchemy object's attributes rather
    # than from a plain dict.
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class SquadMember(BaseModel):
    """One current player in a team's squad, for GET /teams/{id}/squad."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    player_role: str
    joined_at: date


class SquadAdd(BaseModel):
    """Request body for POST /teams/{id}/squad."""

    player_id: int = Field(gt=0, examples=[1])
    #: Defaults to today in the route if omitted.
    joined_at: date | None = None
