"""Action endpoints. No live device calls here; payload shape
validation already happened in app.schemas, and the partial-update
cross-field check is in app.validation."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Action, Schedule
from app.schemas import ActionCreate, ActionRead, ActionUpdate
from app.validation import merge_and_validate_action

router = APIRouter(prefix="/api/actions", tags=["actions"])


def _get_action_or_404(db: Session, action_id: str) -> Action:
    action = db.get(Action, action_id)
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")
    return action


@router.post("", response_model=ActionRead, status_code=201)
def create_action(payload: ActionCreate, db: Session = Depends(get_db)) -> Action:
    action = Action(
        name=payload.name,
        type=payload.type,
        payload=payload.payload,
        transition_ms=payload.transition_ms,
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action


@router.get("", response_model=list[ActionRead])
def list_actions(db: Session = Depends(get_db)) -> list[Action]:
    return list(db.execute(select(Action).order_by(Action.name)).scalars())


@router.get("/{action_id}", response_model=ActionRead)
def get_action(action_id: str, db: Session = Depends(get_db)) -> Action:
    return _get_action_or_404(db, action_id)


@router.patch("/{action_id}", response_model=ActionRead)
def update_action(action_id: str, payload: ActionUpdate, db: Session = Depends(get_db)) -> Action:
    action = _get_action_or_404(db, action_id)
    try:
        validated = merge_and_validate_action(action, payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    action.name = validated.name
    action.type = validated.type
    action.payload = validated.payload
    action.transition_ms = validated.transition_ms
    db.commit()
    db.refresh(action)
    return action


@router.delete("/{action_id}", status_code=204)
def delete_action(action_id: str, db: Session = Depends(get_db)) -> None:
    action = _get_action_or_404(db, action_id)

    blocking = list(
        db.execute(select(Schedule.name).where(Schedule.action_id == action_id)).scalars()
    )
    if blocking:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot delete an action that schedules still reference. "
                f"In use by: {', '.join(blocking)}"
            ),
        )

    db.delete(action)
    try:
        db.commit()
    except IntegrityError as exc:
        # Defensive: covers a schedule created in the moment between the
        # check above and this commit. Same RESTRICT constraint, just a
        # less specific message since we don't know who won the race.
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Cannot delete an action that a schedule still references"
        ) from exc
