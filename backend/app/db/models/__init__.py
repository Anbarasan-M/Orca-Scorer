"""Import every model here.

Alembic's autogenerate and SQLAlchemy's relationship resolution both need all
mapped classes registered on `Base.metadata`, so this module is the single
place that pulls them in.
"""

from app.db.base import Base
from app.db.models.delivery import Delivery
from app.db.models.innings import Innings
from app.db.models.match import Match
from app.db.models.match_event import MatchEvent
from app.db.models.match_player import MatchPlayer
from app.db.models.player import Player
from app.db.models.team import Team
from app.db.models.team_player import TeamPlayer
from app.db.models.wicket import Wicket

__all__ = [
    "Base",
    "Delivery",
    "Innings",
    "Match",
    "MatchEvent",
    "MatchPlayer",
    "Player",
    "Team",
    "TeamPlayer",
    "Wicket",
]
