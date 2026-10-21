"""Pydantic schemas for scorecards and player career statistics."""

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.enums import InningsStatus
from app.schemas.match import MatchRead, TeamSummary


class BattingEntry(BaseModel):
    """Batting figures for one player in an innings."""

    player_id: int
    player_name: str
    runs: int = 0
    balls_faced: int = 0
    fours: int = 0
    sixes: int = 0
    strike_rate: float = 0.0
    is_out: bool = False
    dismissal_text: str = "not out"


class BowlingEntry(BaseModel):
    """Bowling analysis for one player in an innings."""

    player_id: int
    player_name: str
    overs: str = "0.0"
    maidens: int = 0
    runs_conceded: int = 0
    wickets: int = 0
    economy_rate: float = 0.0
    dots: int = 0
    wides: int = 0
    no_balls: int = 0


class ExtrasBreakdown(BaseModel):
    """Categorised extras for an innings."""

    byes: int = 0
    leg_byes: int = 0
    wides: int = 0
    no_balls: int = 0
    penalty: int = 0
    total: int = 0


class InningsScorecard(BaseModel):
    """Full scorecard for one innings."""

    innings_id: int
    innings_number: int
    status: InningsStatus
    batting_team: TeamSummary
    bowling_team: TeamSummary
    total_runs: int
    wickets_lost: int
    overs: str
    run_rate: float
    batting: list[BattingEntry]
    bowling: list[BowlingEntry]
    extras: ExtrasBreakdown


class MatchScorecard(BaseModel):
    """Complete match scorecard across both innings."""

    match: MatchRead
    innings: list[InningsScorecard]
    summary_text: str | None = None


# --- Player Career / All-Time Statistics ------------------------------------


class BattingStats(BaseModel):
    innings: int = 0
    runs: int = 0
    balls_faced: int = 0
    highest_score: int = 0
    average: float | None = None
    strike_rate: float = 0.0
    fours: int = 0
    sixes: int = 0
    not_outs: int = 0
    fifties: int = 0
    hundreds: int = 0


class BowlingStats(BaseModel):
    innings: int = 0
    overs: str = "0.0"
    maidens: int = 0
    runs_conceded: int = 0
    wickets: int = 0
    average: float | None = None
    economy: float = 0.0
    strike_rate: float | None = None
    best_bowling: str | None = None


class FieldingStats(BaseModel):
    catches: int = 0
    stumpings: int = 0
    run_outs: int = 0


class PlayerStatistics(BaseModel):
    """Aggregated career statistics for a player."""

    player_id: int
    player_name: str
    batting: BattingStats
    bowling: BowlingStats
    fielding: FieldingStats
