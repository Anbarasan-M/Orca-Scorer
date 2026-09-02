from datetime import datetime
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin
from app.db.models.enums import MatchEventType
from app.db.types import enum_col

if TYPE_CHECKING:
    from app.db.models.match import Match


class MatchEvent(Base, IdMixin):
    """Anything that happens in a match but is not a delivery.

    `event_data` is JSONB so new event kinds can carry their own fields
    without a migration - for example a rain delay recording overs lost.
    """

    __tablename__ = "match_events"

    match_id: Mapped[int] = mapped_column(
        sa.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False
    )
    #: Set when the event belongs to a particular innings.
    innings_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("innings.id", ondelete="CASCADE")
    )
    event_type: Mapped[MatchEventType] = mapped_column(
        enum_col(MatchEventType, "match_event_type"), nullable=False
    )
    description: Mapped[str | None] = mapped_column(sa.Text)
    event_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    #: When it happened on the field, which can differ from when it was typed in.
    occurred_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="events")

    __table_args__ = (
        sa.Index("ix_match_events_match_occurred", "match_id", "occurred_at"),
    )

    def __repr__(self) -> str:
        return f"<MatchEvent {self.event_type} match={self.match_id}>"
