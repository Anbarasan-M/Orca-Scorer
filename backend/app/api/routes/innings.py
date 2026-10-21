"""Endpoints for innings management and ball-by-ball scoring."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.models import Delivery, Innings
from app.db.session import get_db
from app.schemas.delivery import DeliveryCreate, DeliveryRead, ScoringStateResponse
from app.schemas.innings import InningsCreate, InningsRead
from app.schemas.scorecard import InningsScorecard
from app.services import scorecard as scorecard_service
from app.services import scoring as scoring_service

router = APIRouter(prefix="/innings", tags=["scoring"])


@router.post("", response_model=InningsRead, status_code=status.HTTP_201_CREATED)
def create_innings(
    payload: InningsCreate, db: Session = Depends(get_db)
) -> Innings:
    """Start or schedule an innings for a match."""
    return scoring_service.create_innings(db, payload)


@router.get("/{innings_id}", response_model=InningsRead)
def get_innings(innings_id: int, db: Session = Depends(get_db)) -> Innings:
    """Get details of an innings."""
    return scoring_service.get_innings_or_404(db, innings_id)


@router.get("/{innings_id}/scorecard", response_model=InningsScorecard)
def get_innings_scorecard(
    innings_id: int, db: Session = Depends(get_db)
) -> InningsScorecard:
    """Get complete batting and bowling scorecard for an innings."""
    return scorecard_service.get_innings_scorecard(db, innings_id)


@router.post(
    "/{innings_id}/deliveries",
    response_model=ScoringStateResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_delivery(
    innings_id: int, payload: DeliveryCreate, db: Session = Depends(get_db)
) -> ScoringStateResponse:
    """Record one ball bowled.

    Computes ball_seq, over_number, ball_number, runs conceded, dismissals,
    and strike rotation.
    """
    return scoring_service.record_delivery(db, innings_id, payload)


@router.delete(
    "/{innings_id}/deliveries/last",
    response_model=DeliveryRead,
    status_code=status.HTTP_200_OK,
)
def undo_last_delivery(
    innings_id: int, db: Session = Depends(get_db)
) -> DeliveryRead:
    """Undo the most recent ball bowled in this innings. Cascades wickets."""
    return scoring_service.undo_last_delivery(db, innings_id)


@router.get(
    "/{innings_id}/deliveries",
    response_model=list[DeliveryRead],
)
def list_deliveries(
    innings_id: int,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[Delivery]:
    """List deliveries in an innings in chronological ball sequence."""
    return scoring_service.list_deliveries(
        db, innings_id=innings_id, limit=limit, offset=offset
    )
