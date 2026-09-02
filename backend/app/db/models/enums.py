"""Domain enumerations.

These are stored as VARCHAR + CHECK constraint rather than native PostgreSQL
ENUM types. Adding a value to a native enum is fine, but removing or renaming
one requires rebuilding the type; a CHECK constraint is a one-line migration.
"""

from enum import StrEnum


class BattingStyle(StrEnum):
    RIGHT_HAND = "RIGHT_HAND"
    LEFT_HAND = "LEFT_HAND"


class BowlingStyle(StrEnum):
    RIGHT_ARM_FAST = "RIGHT_ARM_FAST"
    RIGHT_ARM_MEDIUM = "RIGHT_ARM_MEDIUM"
    RIGHT_ARM_OFF_SPIN = "RIGHT_ARM_OFF_SPIN"
    RIGHT_ARM_LEG_SPIN = "RIGHT_ARM_LEG_SPIN"
    LEFT_ARM_FAST = "LEFT_ARM_FAST"
    LEFT_ARM_MEDIUM = "LEFT_ARM_MEDIUM"
    LEFT_ARM_ORTHODOX = "LEFT_ARM_ORTHODOX"
    LEFT_ARM_WRIST_SPIN = "LEFT_ARM_WRIST_SPIN"


class PlayerRole(StrEnum):
    BATTER = "BATTER"
    BOWLER = "BOWLER"
    ALL_ROUNDER = "ALL_ROUNDER"
    WICKET_KEEPER = "WICKET_KEEPER"
    WICKET_KEEPER_BATTER = "WICKET_KEEPER_BATTER"


class MatchFormat(StrEnum):
    T10 = "T10"
    T20 = "T20"
    ODI = "ODI"
    TEST = "TEST"
    CUSTOM = "CUSTOM"


class MatchStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    LIVE = "LIVE"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"


class TossDecision(StrEnum):
    BAT = "BAT"
    BOWL = "BOWL"


class ResultType(StrEnum):
    WIN = "WIN"
    TIE = "TIE"
    DRAW = "DRAW"
    NO_RESULT = "NO_RESULT"


class InningsStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    DECLARED = "DECLARED"
    ABANDONED = "ABANDONED"


class WicketType(StrEnum):
    BOWLED = "BOWLED"
    CAUGHT = "CAUGHT"
    LBW = "LBW"
    STUMPED = "STUMPED"
    RUN_OUT = "RUN_OUT"
    HIT_WICKET = "HIT_WICKET"
    HIT_BALL_TWICE = "HIT_BALL_TWICE"
    OBSTRUCTING_THE_FIELD = "OBSTRUCTING_THE_FIELD"
    TIMED_OUT = "TIMED_OUT"
    RETIRED_HURT = "RETIRED_HURT"
    RETIRED_OUT = "RETIRED_OUT"


#: Dismissals credited to the bowler's figures.
BOWLER_CREDITED_WICKETS = (
    WicketType.BOWLED,
    WicketType.CAUGHT,
    WicketType.LBW,
    WicketType.STUMPED,
    WicketType.HIT_WICKET,
)

#: Dismissals that require a fielder to be named.
FIELDER_REQUIRED_WICKETS = (
    WicketType.CAUGHT,
    WicketType.STUMPED,
    WicketType.RUN_OUT,
)


class MatchEventType(StrEnum):
    TOSS = "TOSS"
    INNINGS_STARTED = "INNINGS_STARTED"
    INNINGS_COMPLETED = "INNINGS_COMPLETED"
    DRINKS_BREAK = "DRINKS_BREAK"
    RAIN_DELAY = "RAIN_DELAY"
    INJURY = "INJURY"
    SUBSTITUTION = "SUBSTITUTION"
    MATCH_COMPLETED = "MATCH_COMPLETED"
    MATCH_ABANDONED = "MATCH_ABANDONED"
    NOTE = "NOTE"
