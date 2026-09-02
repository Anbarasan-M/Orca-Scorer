from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.innings import Innings
    from app.db.models.player import Player
    from app.db.models.wicket import Wicket


class Delivery(Base, IdMixin, TimestampMixin):
    """One ball bowled. The heart of the scoring engine.

    Extras are stored as separate counters rather than a single `extra_type`
    column, because they combine: a no-ball can be hit for six, and a wide can
    run away for four byes. Each column holds the *runs* attributed to that
    category, so `no_ball_runs`/`wide_runs` are at least 1 when they apply.

    Over notation: `over_number` is 1-based (the first over of an innings is
    1). Cricket's display form "4.3" means 4 completed overs plus 3 balls, so
    the UI renders `(over_number - 1).(legal balls so far in the over)`.
    """

    __tablename__ = "deliveries"

    innings_id: Mapped[int] = mapped_column(
        sa.ForeignKey("innings.id", ondelete="CASCADE"), nullable=False
    )
    #: Strictly increasing within an innings. This - not (over, ball) - is the
    #: true ordering key, because a wide repeats the same (over, ball) pair.
    ball_seq: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    over_number: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    #: Which legal ball of the over this attempt is for (1-6).
    ball_number: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)

    batter_id: Mapped[int] = mapped_column(
        sa.ForeignKey("players.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    non_striker_id: Mapped[int] = mapped_column(
        sa.ForeignKey("players.id", ondelete="RESTRICT"), nullable=False
    )
    bowler_id: Mapped[int] = mapped_column(
        sa.ForeignKey("players.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    runs_off_bat: Mapped[int] = mapped_column(
        sa.SmallInteger, nullable=False, server_default=sa.text("0")
    )
    wide_runs: Mapped[int] = mapped_column(
        sa.SmallInteger, nullable=False, server_default=sa.text("0")
    )
    #: Always exactly 1 when a no-ball is called; runs scored off the no-ball
    #: go to runs_off_bat or bye_runs.
    no_ball_runs: Mapped[int] = mapped_column(
        sa.SmallInteger, nullable=False, server_default=sa.text("0")
    )
    bye_runs: Mapped[int] = mapped_column(
        sa.SmallInteger, nullable=False, server_default=sa.text("0")
    )
    leg_bye_runs: Mapped[int] = mapped_column(
        sa.SmallInteger, nullable=False, server_default=sa.text("0")
    )
    penalty_runs: Mapped[int] = mapped_column(
        sa.SmallInteger, nullable=False, server_default=sa.text("0")
    )

    # --- Derived columns: computed by PostgreSQL, never written by the app ---

    #: A legal delivery counts towards the over. Wides and no-balls do not.
    is_legal: Mapped[bool] = mapped_column(
        sa.Boolean, sa.Computed("wide_runs = 0 AND no_ball_runs = 0", persisted=True)
    )
    #: Every run this ball added to the batting side.
    total_runs: Mapped[int] = mapped_column(
        sa.SmallInteger,
        sa.Computed(
            "runs_off_bat + wide_runs + no_ball_runs + bye_runs "
            "+ leg_bye_runs + penalty_runs",
            persisted=True,
        ),
    )
    #: A wide is not a ball faced; a no-ball is. Used for strike rate.
    counts_as_ball_faced: Mapped[bool] = mapped_column(
        sa.Boolean, sa.Computed("wide_runs = 0", persisted=True)
    )
    #: Runs charged to the bowler's analysis: byes and leg byes are not.
    runs_conceded: Mapped[int] = mapped_column(
        sa.SmallInteger,
        sa.Computed("runs_off_bat + wide_runs + no_ball_runs", persisted=True),
    )

    commentary: Mapped[str | None] = mapped_column(sa.Text)

    innings: Mapped["Innings"] = relationship(back_populates="deliveries")
    batter: Mapped["Player"] = relationship(foreign_keys=[batter_id])
    non_striker: Mapped["Player"] = relationship(foreign_keys=[non_striker_id])
    bowler: Mapped["Player"] = relationship(foreign_keys=[bowler_id])
    wickets: Mapped[list["Wicket"]] = relationship(
        back_populates="delivery", cascade="all, delete-orphan"
    )

    __table_args__ = (
        sa.UniqueConstraint("innings_id", "ball_seq"),
        sa.Index("ix_deliveries_innings_over", "innings_id", "over_number", "ball_number"),
        sa.CheckConstraint("over_number >= 1", name="over_number_positive"),
        sa.CheckConstraint("ball_number BETWEEN 1 AND 6", name="ball_number_range"),
        sa.CheckConstraint("ball_seq >= 1", name="ball_seq_positive"),
        sa.CheckConstraint("batter_id <> non_striker_id", name="distinct_batters"),
        # Overthrows make large values possible, so the ceilings are generous.
        sa.CheckConstraint("runs_off_bat BETWEEN 0 AND 12", name="runs_off_bat_range"),
        sa.CheckConstraint("wide_runs BETWEEN 0 AND 12", name="wide_runs_range"),
        sa.CheckConstraint("no_ball_runs IN (0, 1)", name="no_ball_penalty"),
        sa.CheckConstraint("bye_runs BETWEEN 0 AND 12", name="bye_runs_range"),
        sa.CheckConstraint("leg_bye_runs BETWEEN 0 AND 12", name="leg_bye_runs_range"),
        sa.CheckConstraint("penalty_runs BETWEEN 0 AND 12", name="penalty_runs_range"),
        # --- Laws of cricket, enforced by the database ---
        # The bat cannot touch a wide, so no runs off bat and no byes off it;
        # everything that results from a wide is scored as wides.
        sa.CheckConstraint(
            "wide_runs = 0 OR (runs_off_bat = 0 AND bye_runs = 0 AND leg_bye_runs = 0)",
            name="wide_excludes_bat_and_byes",
        ),
        # Byes and leg byes are alternatives, never both on one ball.
        sa.CheckConstraint(
            "bye_runs = 0 OR leg_bye_runs = 0", name="byes_exclusive"
        ),
        # If the batter hit it, the runs are off the bat, not byes.
        sa.CheckConstraint(
            "runs_off_bat = 0 OR (bye_runs = 0 AND leg_bye_runs = 0)",
            name="bat_runs_exclude_byes",
        ),
    )

    def __repr__(self) -> str:
        return f"<Delivery innings={self.innings_id} seq={self.ball_seq}>"
