import logging
from typing import Any, List, Optional, Protocol, Tuple
from sqlalchemy import desc, func, select, update
from sqlalchemy.orm import Session
from app.models.entities import Notification, User
from app.schemas.notification import NotificationCreate, NotificationResponse, NotificationType

logger = logging.getLogger(__name__)


class NotificationRecipientNotFoundError(ValueError):
    """Raised when a notification targets a user that does not exist."""


class NotificationRepository(Protocol):
    """
    Repository interface for in-app Notifications.
    Persists user-scoped in-app notifications.
    """
    def create_notification(
        self, db: Session, notification_in: NotificationCreate
    ) -> Any: ...

    def list_user_notifications(
        self, db: Session, user_id: int, unread_only: bool = False, skip: int = 0, limit: int = 50
    ) -> Tuple[List[Any], int, int]: ...

    def mark_as_read(
        self, db: Session, notification_id: int, user_id: int
    ) -> Optional[Any]: ...

    def mark_all_as_read(
        self, db: Session, user_id: int
    ) -> int: ...


class DefaultPostgresNotificationRepository:
    """PostgreSQL repository for in-app notifications."""
    def create_notification(
        self, db: Session, notification_in: NotificationCreate
    ) -> Any:
        try:
            if db.get(User, notification_in.user_id) is None:
                raise NotificationRecipientNotFoundError("Notification recipient not found.")
            notification = Notification(
                user_id=notification_in.user_id,
                notification_type=notification_in.notification_type,
                title=notification_in.title,
                message=notification_in.message,
                reference_id=notification_in.reference_id,
            )
            db.add(notification)
            db.flush()
            db.refresh(notification)
            db.commit()
            return notification
        except Exception:
            db.rollback()
            raise

    def list_user_notifications(
        self, db: Session, user_id: int, unread_only: bool = False, skip: int = 0, limit: int = 50
    ) -> Tuple[List[Any], int, int]:
        try:
            unread_count = db.scalar(
                select(func.count(Notification.id)).where(
                    Notification.user_id == user_id, Notification.is_read.is_(False)
                )
            ) or 0
            filters = [Notification.user_id == user_id]
            if unread_only:
                filters.append(Notification.is_read.is_(False))
            total = db.scalar(select(func.count(Notification.id)).where(*filters)) or 0
            items = db.scalars(
                select(Notification)
                .where(*filters)
                .order_by(desc(Notification.created_at), desc(Notification.id))
                .offset(skip)
                .limit(limit)
            ).all()
            return items, total, unread_count
        except Exception:
            db.rollback()
            raise

    def mark_as_read(
        self, db: Session, notification_id: int, user_id: int
    ) -> Optional[Any]:
        try:
            notification = db.scalar(
                select(Notification)
                .where(Notification.id == notification_id, Notification.user_id == user_id)
                .with_for_update()
            )
            if notification is None:
                return None
            if not notification.is_read:
                notification.is_read = True
                db.flush()
            db.commit()
            return notification
        except Exception:
            db.rollback()
            raise

    def mark_all_as_read(
        self, db: Session, user_id: int
    ) -> int:
        try:
            result = db.execute(
                update(Notification)
                .where(Notification.user_id == user_id, Notification.is_read.is_(False))
                .values(is_read=True)
            )
            marked_count = result.rowcount or 0
            db.commit()
            return marked_count
        except Exception:
            db.rollback()
            raise


_default_notification_repo = DefaultPostgresNotificationRepository()


def get_notification_repo() -> NotificationRepository:
    """FastAPI dependency injection for NotificationRepository."""
    return _default_notification_repo


def dispatch_in_app_notification(
    db: Session,
    notification_repo: NotificationRepository,
    user_id: int,
    notification_type: NotificationType,
    title: str,
    message: str,
    reference_id: Optional[str] = None,
) -> Optional[Any]:
    """
    Helper function to dispatch an in-app notification.
    Safely logs and continues if notification persistence fails, ensuring primary operations proceed.
    """
    try:
        notif_in = NotificationCreate(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            reference_id=reference_id,
        )
        return notification_repo.create_notification(db, notif_in)
    except Exception as e:
        logger.warning("Failed to dispatch notification for user %s: %s", user_id, type(e).__name__)
        return None
