from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.engine import get_session
from app.deps import require_authenticated
from app.repositories import event_repo
from app.repositories.event_repo import EventInput
from app.schemas import EventCreate, EventOut

router = APIRouter(prefix="/events", tags=["events"], dependencies=[Depends(require_authenticated)])


@router.get("", response_model=list[EventOut])
def list_events(db: Session = Depends(get_session)):
    return event_repo.list_all(db)


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def create_event(
    body: EventCreate,
    db: Session = Depends(get_session),
    session: dict = Depends(require_authenticated),
):
    data = EventInput(created_by=session["user"], **body.model_dump())
    try:
        return event_repo.create(db, data)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: str, db: Session = Depends(get_session)):
    event = event_repo.get_by_id(db, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "event not found")
    return event


@router.put("/{event_id}", response_model=EventOut)
def update_event(
    event_id: str,
    body: EventCreate,
    db: Session = Depends(get_session),
    session: dict = Depends(require_authenticated),
):
    event = event_repo.get_by_id(db, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "event not found")
    data = EventInput(created_by=event.created_by, **body.model_dump())
    try:
        return event_repo.update(db, event, data)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: str, db: Session = Depends(get_session)):
    event = event_repo.get_by_id(db, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "event not found")
    event_repo.delete(db, event)
