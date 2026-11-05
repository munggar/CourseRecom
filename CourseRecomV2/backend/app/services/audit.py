import json

from sqlalchemy.orm import Session

from app.models import AuditLog, User
from app.services.time_utils import utc_now_naive


def write_audit(
    db: Session,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: int | str,
    old_value: object | None = None,
    new_value: object | None = None,
) -> None:
    db.add(AuditLog(
        actor_id=actor.id if actor else None,
        actor_name=actor.full_name if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        old_value=json.dumps(old_value, ensure_ascii=False, default=str) if old_value is not None else None,
        new_value=json.dumps(new_value, ensure_ascii=False, default=str) if new_value is not None else None,
        created_at=utc_now_naive(),
    ))
