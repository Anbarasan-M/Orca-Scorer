"""Pydantic schemas for the /matches endpoints.

Describes the JSON crossing the wire for matches and match squad/XI submissions.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models.enums import MatchFormat, MatchStatus, ResultType, TossDecision


DEFAULT_OVERS_FOR_FORMAT: dict[MatchFormat, int | None] = {
    MatchFormat.T10: 10,
    MatchFormat.T20: 20,
    MatchFormat.ODI: 50,
    MatchFormat.TEST: None,
}


class TeamSummary(BaseModel):
    """Minimal team info embedded in match responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    short_name: str


class PlayerSummary(BaseModel):
    """Minimal player info embedded in match squad responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    player_role: str


class MatchBase(BaseModel):
    """Base fields supplied when scheduling a match."""

    team1_id: int = Field(gt=0, examples=[1])
    team2_id: int = Field(gt=0, examples=[2])
    match_date: datetime = Field(examples=["2026-10-25T14:30:00Z"])
    venue: str | None = Field(default=None, max_length=150, examples=["Chepauk, Chennai"])
    format: MatchFormat = Field(examples=[MatchFormat.T20])
    total_overs: int | None = Field(
        default=None,
        ge=1,
        le=200,
        description="Max overs per innings. Inferred from format if omitted (e.g. 20 for T20, 50 for ODI).",
        examples=[20],
    )

    @model_validator(mode="after")
    def validate_teams_and_overs(self) -> "MatchBase":
        if self.team1_id == self.team2_id:
            raise ValueError("team1_id and team2_id must be different teams")

        # Automatically fill default overs if omitted for standard formats
        if self.total_overs is None and self.format in DEFAULT_OVERS_FOR_FORMAT:
            self.total_overs = DEFAULT_OVERS_FOR_FORMAT[self.format]

        if self.format == MatchFormat.CUSTOM and self.total_overs is None:
            raise ValueError("total_overs is required for CUSTOM match format")

        if self.format == MatchFormat.TEST and self.total_overs is not None:
            raise ValueError("total_overs must be null for TEST matches")

        return self


class MatchCreate(MatchBase):
    """Request body for POST /matches."""


class MatchUpdate(BaseModel):
    """Request body for PATCH /matches/{id} - every field optional."""

    venue: str | None = Field(default=None, max_length=150)
    match_date: datetime | None = None
    status: MatchStatus | None = None
    total_overs: int | None = Field(default=None, ge=1, le=200)

    # Toss fields
    toss_winner_id: int | None = None
    toss_decision: TossDecision | None = None

    # Result fields
    winner_team_id: int | None = None
    result_type: ResultType | None = None

    @model_validator(mode="after")
    def validate_toss_and_result(self) -> "MatchUpdate":
        # Toss is one complete fact: both winner and decision, or neither.
        has_winner = self.toss_winner_id is not None
        has_decision = self.toss_decision is not None
        if has_winner != has_decision:
            raise ValueError(
                "toss_winner_id and toss_decision must both be provided together"
            )

        # Winner and result type invariant
        if self.result_type == ResultType.WIN and self.winner_team_id is None:
            raise ValueError("winner_team_id is required when result_type is WIN")
        if self.result_type != ResultType.WIN and self.winner_team_id is not None:
            raise ValueError(
                "winner_team_id can only be specified when result_type is WIN"
            )

        return self


class MatchRead(BaseModel):
    """What the API sends back for match details."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    team1_id: int
    team2_id: int
    match_date: datetime
    venue: str | None
    format: MatchFormat
    total_overs: int | None
    toss_winner_id: int | None
    toss_decision: TossDecision | None
    winner_team_id: int | None
    result_type: ResultType | None
    status: MatchStatus
    created_at: datetime
    updated_at: datetime

    team1: TeamSummary
    team2: TeamSummary
    toss_winner: TeamSummary | None = None
    winner_team: TeamSummary | None = None


# --- Match Players / Squad / XI schemas --------------------------------------


class MatchPlayerEntry(BaseModel):
    """One player entry in a match squad or XI submission."""

    player_id: int = Field(gt=0, examples=[1])
    batting_position: int | None = Field(
        default=None, ge=1, le=15, examples=[1], description="Batting order position (1-15)"
    )
    is_captain: bool = Field(default=False, examples=[False])
    is_wicket_keeper: bool = Field(default=False, examples=[False])
    is_substitute: bool = Field(default=False, examples=[False])


class MatchSquadCreate(BaseModel):
    """Request body for POST /matches/{id}/players.

    Names a team's playing XI and substitutes for the match.
    """

    team_id: int = Field(gt=0, examples=[1])
    players: list[MatchPlayerEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_squad_composition(self) -> "MatchSquadCreate":
        player_ids = [p.player_id for p in self.players]
        if len(player_ids) != len(set(player_ids)):
            raise ValueError("Duplicate player found in squad list")

        # Batting position uniqueness (excluding substitutes / unassigned)
        positions = [p.batting_position for p in self.players if p.batting_position is not None]
        if len(positions) != len(set(positions)):
            raise ValueError("Duplicate batting positions within the team squad")

        # Captain & Keeper checks
        captains = [p for p in self.players if p.is_captain]
        if len(captains) > 1:
            raise ValueError("A team cannot have more than one captain")

        keepers = [p for p in self.players if p.is_wicket_keeper]
        if len(keepers) > 1:
            raise ValueError("A team cannot have more than one wicket keeper")

        return self


class MatchPlayerRead(BaseModel):
    """Detailed squad member in match playing XI responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    match_id: int
    team_id: int
    player_id: int
    batting_position: int | None
    is_captain: bool
    is_wicket_keeper: bool
    is_substitute: bool
    player: PlayerSummary
