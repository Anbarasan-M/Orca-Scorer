"""Initial Orca Scorer schema: the nine core tables.

Enum value lists are written out literally rather than imported from
`app.db.models.enums`. A migration is a historical record - it must keep
producing the same schema even after the application's enums grow.

Revision ID: 0001
Revises:
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Tables whose updated_at is maintained by a trigger.
TIMESTAMPED_TABLES = ("teams", "players", "matches", "innings", "deliveries")

BATTING_STYLES = ("RIGHT_HAND", "LEFT_HAND")
BOWLING_STYLES = (
    "RIGHT_ARM_FAST",
    "RIGHT_ARM_MEDIUM",
    "RIGHT_ARM_OFF_SPIN",
    "RIGHT_ARM_LEG_SPIN",
    "LEFT_ARM_FAST",
    "LEFT_ARM_MEDIUM",
    "LEFT_ARM_ORTHODOX",
    "LEFT_ARM_WRIST_SPIN",
)
PLAYER_ROLES = (
    "BATTER",
    "BOWLER",
    "ALL_ROUNDER",
    "WICKET_KEEPER",
    "WICKET_KEEPER_BATTER",
)
MATCH_FORMATS = ("T10", "T20", "ODI", "TEST", "CUSTOM")
MATCH_STATUSES = ("SCHEDULED", "LIVE", "COMPLETED", "ABANDONED")
TOSS_DECISIONS = ("BAT", "BOWL")
RESULT_TYPES = ("WIN", "TIE", "DRAW", "NO_RESULT")
INNINGS_STATUSES = (
    "NOT_STARTED",
    "IN_PROGRESS",
    "COMPLETED",
    "DECLARED",
    "ABANDONED",
)
WICKET_TYPES = (
    "BOWLED",
    "CAUGHT",
    "LBW",
    "STUMPED",
    "RUN_OUT",
    "HIT_WICKET",
    "HIT_BALL_TWICE",
    "OBSTRUCTING_THE_FIELD",
    "TIMED_OUT",
    "RETIRED_HURT",
    "RETIRED_OUT",
)
BOWLER_CREDITED = ("BOWLED", "CAUGHT", "LBW", "STUMPED", "HIT_WICKET")
FIELDER_REQUIRED = ("CAUGHT", "STUMPED", "RUN_OUT")
MATCH_EVENT_TYPES = (
    "TOSS",
    "INNINGS_STARTED",
    "INNINGS_COMPLETED",
    "DRINKS_BREAK",
    "RAIN_DELAY",
    "INJURY",
    "SUBSTITUTION",
    "MATCH_COMPLETED",
    "MATCH_ABANDONED",
    "NOTE",
)


def _enum(values: Sequence[str], name: str) -> sa.Enum:
    """VARCHAR + CHECK, not a native PostgreSQL ENUM type."""
    return sa.Enum(
        *values, name=name, native_enum=False, create_constraint=True, length=32
    )


def _in_list(values: Sequence[str]) -> str:
    return ", ".join(f"'{v}'" for v in values)


def _ts_columns() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    # ------------------------------------------------------------------ teams
    op.create_table(
        "teams",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("short_name", sa.String(length=5), nullable=False),
        sa.Column("logo_url", sa.Text(), nullable=True),
        *_ts_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("short_name"),
        sa.CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        sa.CheckConstraint("short_name = upper(short_name)", name="short_name_upper"),
        sa.CheckConstraint("length(short_name) BETWEEN 2 AND 5", name="short_name_len"),
    )

    # ---------------------------------------------------------------- players
    op.create_table(
        "players",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("photo_url", sa.Text(), nullable=True),
        sa.Column("batting_style", _enum(BATTING_STYLES, "batting_style"), nullable=True),
        sa.Column("bowling_style", _enum(BOWLING_STYLES, "bowling_style"), nullable=True),
        sa.Column(
            "player_role",
            _enum(PLAYER_ROLES, "player_role"),
            server_default="BATTER",
            nullable=False,
        ),
        *_ts_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
    )
    op.create_index("ix_players_name", "players", ["name"])

    # ----------------------------------------------------------- team_players
    op.create_table(
        "team_players",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("team_id", sa.BigInteger(), nullable=False),
        sa.Column("player_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "joined_at",
            sa.Date(),
            server_default=sa.text("CURRENT_DATE"),
            nullable=False,
        ),
        sa.Column("left_at", sa.Date(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            sa.Computed("left_at IS NULL", persisted=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.CheckConstraint("left_at IS NULL OR left_at >= joined_at", name="date_order"),
    )
    op.create_index("ix_team_players_player_id", "team_players", ["player_id"])
    op.create_index(
        "uq_team_players_active",
        "team_players",
        ["team_id", "player_id"],
        unique=True,
        postgresql_where=sa.text("left_at IS NULL"),
    )

    # ---------------------------------------------------------------- matches
    op.create_table(
        "matches",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("team1_id", sa.BigInteger(), nullable=False),
        sa.Column("team2_id", sa.BigInteger(), nullable=False),
        sa.Column("match_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("venue", sa.String(length=150), nullable=True),
        sa.Column("format", _enum(MATCH_FORMATS, "match_format"), nullable=False),
        sa.Column("total_overs", sa.SmallInteger(), nullable=True),
        sa.Column("toss_winner_id", sa.BigInteger(), nullable=True),
        sa.Column("toss_decision", _enum(TOSS_DECISIONS, "toss_decision"), nullable=True),
        sa.Column("winner_team_id", sa.BigInteger(), nullable=True),
        sa.Column("result_type", _enum(RESULT_TYPES, "result_type"), nullable=True),
        sa.Column(
            "status",
            _enum(MATCH_STATUSES, "match_status"),
            server_default="SCHEDULED",
            nullable=False,
        ),
        *_ts_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["team1_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["team2_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["toss_winner_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["winner_team_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("team1_id <> team2_id", name="distinct_teams"),
        sa.CheckConstraint(
            "toss_winner_id IS NULL OR toss_winner_id IN (team1_id, team2_id)",
            name="toss_winner_is_playing",
        ),
        sa.CheckConstraint(
            "winner_team_id IS NULL OR winner_team_id IN (team1_id, team2_id)",
            name="winner_is_playing",
        ),
        sa.CheckConstraint(
            "(toss_winner_id IS NULL) = (toss_decision IS NULL)", name="toss_complete"
        ),
        sa.CheckConstraint(
            "(COALESCE(result_type, '') = 'WIN') = (winner_team_id IS NOT NULL)",
            name="winner_matches_result",
        ),
        sa.CheckConstraint(
            "total_overs IS NULL OR total_overs BETWEEN 1 AND 200", name="overs_range"
        ),
    )
    op.create_index("ix_matches_match_date", "matches", ["match_date"])
    op.create_index("ix_matches_status", "matches", ["status"])

    # ---------------------------------------------------------- match_players
    op.create_table(
        "match_players",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.BigInteger(), nullable=False),
        sa.Column("team_id", sa.BigInteger(), nullable=False),
        sa.Column("player_id", sa.BigInteger(), nullable=False),
        sa.Column("batting_position", sa.SmallInteger(), nullable=True),
        sa.Column(
            "is_captain", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column(
            "is_wicket_keeper", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column(
            "is_substitute", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("match_id", "player_id"),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "batting_position IS NULL OR batting_position BETWEEN 1 AND 15",
            name="batting_position_range",
        ),
    )
    op.create_index("ix_match_players_player_id", "match_players", ["player_id"])
    op.create_index(
        "uq_match_players_batting_position",
        "match_players",
        ["match_id", "team_id", "batting_position"],
        unique=True,
        postgresql_where=sa.text("batting_position IS NOT NULL"),
    )
    op.create_index(
        "uq_match_players_captain",
        "match_players",
        ["match_id", "team_id"],
        unique=True,
        postgresql_where=sa.text("is_captain"),
    )
    op.create_index(
        "uq_match_players_keeper",
        "match_players",
        ["match_id", "team_id"],
        unique=True,
        postgresql_where=sa.text("is_wicket_keeper"),
    )

    # ---------------------------------------------------------------- innings
    op.create_table(
        "innings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.BigInteger(), nullable=False),
        sa.Column("innings_number", sa.SmallInteger(), nullable=False),
        sa.Column("batting_team_id", sa.BigInteger(), nullable=False),
        sa.Column("bowling_team_id", sa.BigInteger(), nullable=False),
        sa.Column("max_overs", sa.SmallInteger(), nullable=True),
        sa.Column("target_runs", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            _enum(INNINGS_STATUSES, "innings_status"),
            server_default="NOT_STARTED",
            nullable=False,
        ),
        *_ts_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("match_id", "innings_number"),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["batting_team_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["bowling_team_id"], ["teams.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("innings_number BETWEEN 1 AND 4", name="innings_number_range"),
        sa.CheckConstraint("batting_team_id <> bowling_team_id", name="distinct_teams"),
        sa.CheckConstraint("target_runs IS NULL OR target_runs > 0", name="target_positive"),
        sa.CheckConstraint(
            "max_overs IS NULL OR max_overs BETWEEN 1 AND 200", name="overs_range"
        ),
    )

    # ------------------------------------------------------------- deliveries
    op.create_table(
        "deliveries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("innings_id", sa.BigInteger(), nullable=False),
        sa.Column("ball_seq", sa.Integer(), nullable=False),
        sa.Column("over_number", sa.SmallInteger(), nullable=False),
        sa.Column("ball_number", sa.SmallInteger(), nullable=False),
        sa.Column("batter_id", sa.BigInteger(), nullable=False),
        sa.Column("non_striker_id", sa.BigInteger(), nullable=False),
        sa.Column("bowler_id", sa.BigInteger(), nullable=False),
        sa.Column("runs_off_bat", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("wide_runs", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("no_ball_runs", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("bye_runs", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("leg_bye_runs", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("penalty_runs", sa.SmallInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "is_legal",
            sa.Boolean(),
            sa.Computed("wide_runs = 0 AND no_ball_runs = 0", persisted=True),
            nullable=False,
        ),
        sa.Column(
            "total_runs",
            sa.SmallInteger(),
            sa.Computed(
                "runs_off_bat + wide_runs + no_ball_runs + bye_runs "
                "+ leg_bye_runs + penalty_runs",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "counts_as_ball_faced",
            sa.Boolean(),
            sa.Computed("wide_runs = 0", persisted=True),
            nullable=False,
        ),
        sa.Column(
            "runs_conceded",
            sa.SmallInteger(),
            sa.Computed("runs_off_bat + wide_runs + no_ball_runs", persisted=True),
            nullable=False,
        ),
        sa.Column("commentary", sa.Text(), nullable=True),
        *_ts_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("innings_id", "ball_seq"),
        sa.ForeignKeyConstraint(["innings_id"], ["innings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["batter_id"], ["players.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["non_striker_id"], ["players.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["bowler_id"], ["players.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("over_number >= 1", name="over_number_positive"),
        sa.CheckConstraint("ball_number BETWEEN 1 AND 6", name="ball_number_range"),
        sa.CheckConstraint("ball_seq >= 1", name="ball_seq_positive"),
        sa.CheckConstraint("batter_id <> non_striker_id", name="distinct_batters"),
        sa.CheckConstraint("runs_off_bat BETWEEN 0 AND 12", name="runs_off_bat_range"),
        sa.CheckConstraint("wide_runs BETWEEN 0 AND 12", name="wide_runs_range"),
        sa.CheckConstraint("no_ball_runs IN (0, 1)", name="no_ball_penalty"),
        sa.CheckConstraint("bye_runs BETWEEN 0 AND 12", name="bye_runs_range"),
        sa.CheckConstraint("leg_bye_runs BETWEEN 0 AND 12", name="leg_bye_runs_range"),
        sa.CheckConstraint("penalty_runs BETWEEN 0 AND 12", name="penalty_runs_range"),
        sa.CheckConstraint(
            "wide_runs = 0 OR (runs_off_bat = 0 AND bye_runs = 0 AND leg_bye_runs = 0)",
            name="wide_excludes_bat_and_byes",
        ),
        sa.CheckConstraint("bye_runs = 0 OR leg_bye_runs = 0", name="byes_exclusive"),
        sa.CheckConstraint(
            "runs_off_bat = 0 OR (bye_runs = 0 AND leg_bye_runs = 0)",
            name="bat_runs_exclude_byes",
        ),
    )
    op.create_index("ix_deliveries_batter_id", "deliveries", ["batter_id"])
    op.create_index("ix_deliveries_bowler_id", "deliveries", ["bowler_id"])
    op.create_index(
        "ix_deliveries_innings_over",
        "deliveries",
        ["innings_id", "over_number", "ball_number"],
    )

    # ---------------------------------------------------------------- wickets
    op.create_table(
        "wickets",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("delivery_id", sa.BigInteger(), nullable=False),
        sa.Column("player_out_id", sa.BigInteger(), nullable=False),
        sa.Column("wicket_type", _enum(WICKET_TYPES, "wicket_type"), nullable=False),
        sa.Column("fielder_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "is_bowler_credited",
            sa.Boolean(),
            sa.Computed(
                f"wicket_type IN ({_in_list(BOWLER_CREDITED)})", persisted=True
            ),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("delivery_id", "player_out_id"),
        sa.ForeignKeyConstraint(["delivery_id"], ["deliveries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["player_out_id"], ["players.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["fielder_id"], ["players.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "fielder_id IS NULL OR fielder_id <> player_out_id",
            name="fielder_not_batter",
        ),
        sa.CheckConstraint(
            f"(wicket_type IN ({_in_list(FIELDER_REQUIRED)}))"
            " = (fielder_id IS NOT NULL)",
            name="fielder_required",
        ),
    )
    op.create_index("ix_wickets_player_out_id", "wickets", ["player_out_id"])

    # ----------------------------------------------------------- match_events
    op.create_table(
        "match_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.BigInteger(), nullable=False),
        sa.Column("innings_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "event_type", _enum(MATCH_EVENT_TYPES, "match_event_type"), nullable=False
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "event_data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["innings_id"], ["innings.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_match_events_match_occurred", "match_events", ["match_id", "occurred_at"]
    )

    # ------------------------------------------------ updated_at auto-refresh
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table in TIMESTAMPED_TABLES:
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
            """
        )


def downgrade() -> None:
    for table in TIMESTAMPED_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table};")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at();")

    op.drop_table("match_events")
    op.drop_table("wickets")
    op.drop_table("deliveries")
    op.drop_table("innings")
    op.drop_table("match_players")
    op.drop_table("matches")
    op.drop_table("team_players")
    op.drop_table("players")
    op.drop_table("teams")
