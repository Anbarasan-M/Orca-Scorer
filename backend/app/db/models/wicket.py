from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin
from app.db.models.enums import (
    BOWLER_CREDITED_WICKETS,
    FIELDER_REQUIRED_WICKETS,
    WicketType,
)
from app.db.types import enum_col

if TYPE_CHECKING:
    from app.db.models.delivery import Delivery
    from app.db.models.player import Player


def _sql_list(values) -> str:
    return ", ".join(f"'{v.value}'" for v in values)


class Wicket(Base, IdMixin):
    """A dismissal, hanging off the delivery it happened on.

    Kept separate from `deliveries` because one ball can produce more than one
    dismissal (a run out on the same ball as a retirement, for instance), and
    because deleting a ball during an undo should take its wickets with it.
    """

    __tablename__ = "wickets"

    delivery_id: Mapped[int] = mapped_column(
        sa.ForeignKey("deliveries.id", ondelete="CASCADE"), nullable=False
    )
    player_out_id: Mapped[int] = mapped_column(
        sa.ForeignKey("players.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    wicket_type: Mapped[WicketType] = mapped_column(
        enum_col(WicketType, "wicket_type"), nullable=False
    )
    #: Catcher, stumper, or the fielder who effected the run out.
    fielder_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("players.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    #: Run outs and retirements do not go on the bowler's figures.
    is_bowler_credited: Mapped[bool] = mapped_column(
        sa.Boolean,
        sa.Computed(
            f"wicket_type IN ({_sql_list(BOWLER_CREDITED_WICKETS)})", persisted=True
        ),
    )

    delivery: Mapped["Delivery"] = relationship(back_populates="wickets")
    player_out: Mapped["Player"] = relationship(foreign_keys=[player_out_id])
    fielder: Mapped["Player | None"] = relationship(foreign_keys=[fielder_id])

    __table_args__ = (
        sa.UniqueConstraint("delivery_id", "player_out_id"),
        sa.CheckConstraint(
            "fielder_id IS NULL OR fielder_id <> player_out_id",
            name="fielder_not_batter",
        ),
        # A catch, stumping or run out needs a named fielder; nothing else may
        # have one.
        sa.CheckConstraint(
            f"(wicket_type IN ({_sql_list(FIELDER_REQUIRED_WICKETS)}))"
            " = (fielder_id IS NOT NULL)",
            name="fielder_required",
        ),
    )

    def __repr__(self) -> str:
        return f"<Wicket {self.wicket_type} delivery={self.delivery_id}>"
