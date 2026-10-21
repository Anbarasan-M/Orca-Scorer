"""Pydantic schemas for ball-by-ball deliveries, wickets, and scoring feedback."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models.enums import FIELDER_REQUIRED_WICKETS, WicketType
from app.schemas.match import PlayerSummary


class WicketCreate(BaseModel):
    """A dismissal occurring on a delivery."""

    player_out_id: int = Field(gt=0, examples=[1])
    wicket_type: WicketType = Field(examples=[WicketType.CAUGHT])
    fielder_id: int | None = Field(default=None, gt=0, examples=[2])

    @model_validator(mode="after")
    def validate_fielder(self) -> "WicketCreate":
        requires_fielder = self.wicket_type in FIELDER_REQUIRED_WICKETS
        if requires_fielder and self.fielder_id is None:
            raise ValueError(f"{self.wicket_type.value} requires a fielder to be named")
        if not requires_fielder and self.fielder_id is not None:
            raise ValueError(f"{self.wicket_type.value} cannot have a fielder")
        if self.fielder_id is not None and self.fielder_id == self.player_out_id:
            raise ValueError("Fielder cannot be the dismissed batter")
        return self


class WicketRead(BaseModel):
    """What the API sends back for a dismissal."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    delivery_id: int
    player_out_id: int
    wicket_type: WicketType
    fielder_id: int | None
    is_bowler_credited: bool
    created_at: datetime

    player_out: PlayerSummary
    fielder: PlayerSummary | None = None


class DeliveryCreate(BaseModel):
    """Request body for POST /innings/{id}/deliveries."""

    batter_id: int = Field(gt=0, examples=[1])
    non_striker_id: int = Field(gt=0, examples=[2])
    bowler_id: int = Field(gt=0, examples=[3])

    runs_off_bat: int = Field(default=0, ge=0, le=12, examples=[1])
    wide_runs: int = Field(default=0, ge=0, le=12, examples=[0])
    no_ball_runs: int = Field(default=0, ge=0, le=1, examples=[0])
    bye_runs: int = Field(default=0, ge=0, le=12, examples=[0])
    leg_bye_runs: int = Field(default=0, ge=0, le=12, examples=[0])
    penalty_runs: int = Field(default=0, ge=0, le=12, examples=[0])

    commentary: str | None = Field(default=None, max_length=500, examples=["Single taken to mid-wicket"])
    wicket: WicketCreate | None = None
    wickets: list[WicketCreate] | None = None

    @model_validator(mode="after")
    def validate_delivery_laws(self) -> "DeliveryCreate":
        # Players distinct
        if self.batter_id == self.non_striker_id:
            raise ValueError("batter_id and non_striker_id cannot be the same player")
        if self.bowler_id in (self.batter_id, self.non_striker_id):
            raise ValueError("bowler cannot be one of the two batters")

        # Wide rules
        if self.wide_runs > 0:
            if self.runs_off_bat > 0:
                raise ValueError("Runs off the bat are not permitted on a wide")
            if self.bye_runs > 0 or self.leg_bye_runs > 0:
                raise ValueError("Byes and leg-byes are not permitted on a wide (scored as wides)")

        # Byes and leg-byes are mutually exclusive
        if self.bye_runs > 0 and self.leg_bye_runs > 0:
            raise ValueError("A ball cannot have both byes and leg byes")

        # Runs off bat excludes byes
        if self.runs_off_bat > 0 and (self.bye_runs > 0 or self.leg_bye_runs > 0):
            raise ValueError("A ball cannot have both runs off the bat and byes/leg-byes")

        # Unify single wicket and multiple wickets
        collected_wickets = list(self.wickets or [])
        if self.wicket is not None:
            collected_wickets.append(self.wicket)

        for w in collected_wickets:
            if w.player_out_id not in (self.batter_id, self.non_striker_id):
                raise ValueError(
                    f"Dismissed player {w.player_out_id} is neither the batter nor non-striker"
                )

        return self


class DeliveryRead(BaseModel):
    """What the API sends back for a delivery."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    innings_id: int
    ball_seq: int
    over_number: int
    ball_number: int
    batter_id: int
    non_striker_id: int
    bowler_id: int
    runs_off_bat: int
    wide_runs: int
    no_ball_runs: int
    bye_runs: int
    leg_bye_runs: int
    penalty_runs: int

    # Server-generated columns
    is_legal: bool
    total_runs: int
    counts_as_ball_faced: bool
    runs_conceded: int
    commentary: str | None

    batter: PlayerSummary
    non_striker: PlayerSummary
    bowler: PlayerSummary
    wickets: list[WicketRead]


class ScoringStateResponse(BaseModel):
    """Scoring engine feedback after processing a ball."""

    delivery: DeliveryRead
    next_striker_id: int | None = Field(
        description="The batter facing the next ball, after strike rotation"
    )
    next_non_striker_id: int | None = Field(
        description="The batter at the non-striker end, after strike rotation"
    )
    is_over_complete: bool = Field(description="True if this ball was the 6th legal ball of the over")
    is_innings_complete: bool = Field(description="True if all out, target chased, or overs exhausted")
    current_score: int = Field(description="Total runs scored in this innings so far")
    current_wickets: int = Field(description="Total wickets lost in this innings so far")
    overs_completed_display: str = Field(description="Formatted over display, e.g. '4.3'")
