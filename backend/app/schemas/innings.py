"""Pydantic schemas for innings."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models.enums import InningsStatus
from app.schemas.match import TeamSummary


class InningsBase(BaseModel):
    match_id: int = Field(gt=0, examples=[1])
    innings_number: int = Field(ge=1, le=4, examples=[1])
    batting_team_id: int = Field(gt=0, examples=[1])
    bowling_team_id: int = Field(gt=0, examples=[2])
    max_overs: int | None = Field(default=None, ge=1, le=200, examples=[20])
    target_runs: int | None = Field(default=None, gt=0, examples=[180])

    @model_validator(mode="after")
    def validate_teams_and_target(self) -> "InningsBase":
        if self.batting_team_id == self.bowling_team_id:
            raise ValueError("batting_team_id and bowling_team_id must be different teams")
        if self.innings_number == 1 and self.target_runs is not None:
            raise ValueError("target_runs cannot be set for the first innings")
        return self


class InningsCreate(InningsBase):
    """Request body for creating an innings."""


class InningsUpdate(BaseModel):
    """Request body for updating innings status or rain reduction."""

    max_overs: int | None = Field(default=None, ge=1, le=200)
    target_runs: int | None = Field(default=None, gt=0)
    status: InningsStatus | None = None


class InningsRead(BaseModel):
    """What the API sends back for an innings."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    match_id: int
    innings_number: int
    batting_team_id: int
    bowling_team_id: int
    max_overs: int | None
    target_runs: int | None
    status: InningsStatus
    created_at: datetime
    updated_at: datetime

    batting_team: TeamSummary
    bowling_team: TeamSummary
