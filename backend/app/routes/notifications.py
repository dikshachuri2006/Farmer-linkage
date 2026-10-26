from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session
from app.core.dependencies import AuthenticatedUser, get_current_user_claims
from app.database.connection import get_db
from app.schemas.notification import (
    NotificationListResponse,
    NotificationResponse,
)
from app.services.auth_service import DatabaseSchemaPendingError
from app.services.notification_service import (
    NotificationRepository,
    get_notification_repo,
)

router = APIRouter(prefix="/notifications", tags=["In-App Notifications"])


@router.get(
    "",
    response_model=NotificationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List in-app notifications for authenticated user",
)
def list_notifications(
    unread_only: bool = Query(False, description="Filter only unread notifications"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
    notif_repo: NotificationRepository = Depends(get_notification_repo),
):
    """
    Retrieves in-app notification alerts for the authenticated farmer, buyer, or admin.
    Returns total count, unread count, and paginated items.
    """
    try:
        items, total, unread_count = notif_repo.list_user_notifications(
            db, user_id=current_user.id, unread_only=unread_only, skip=skip, limit=limit
        )
        return NotificationListResponse(
            total=total,
            unread_count=unread_count,
            items=items,
            skip=skip,
            limit=limit,
        )
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database notifications schema is pending approval by Ankita: {str(e)}",
        )


@router.put(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark specific notification as read",
)
def mark_notification_as_read(
    notification_id: int = Path(..., ge=1, description="Notification ID"),
    current_user: AuthenticatedUser = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
    notif_repo: NotificationRepository = Depends(get_notification_repo),
):
    """
    Marks an individual notification as read.
    Enforces privacy: users can only mark their own notifications as read.
    """
    try:
        updated = notif_repo.mark_as_read(db, notification_id=notification_id, user_id=current_user.id)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notification with ID {notification_id} not found in your inbox.",
            )
        return updated
    except HTTPException:
        raise
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database notifications schema is pending approval by Ankita: {str(e)}",
        )


@router.put(
    "/mark-all-read",
    status_code=status.HTTP_200_OK,
    summary="Mark all inbox notifications as read",
)
def mark_all_notifications_as_read(
    current_user: AuthenticatedUser = Depends(get_current_user_claims),
    db: Session = Depends(get_db),
    notif_repo: NotificationRepository = Depends(get_notification_repo),
):
    """
    Marks all unread notifications for the authenticated user as read.
    """
    try:
        count = notif_repo.mark_all_as_read(db, user_id=current_user.id)
        return {
            "status": "success",
            "message": "All notifications marked as read.",
            "marked_count": count,
        }
    except DatabaseSchemaPendingError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database notifications schema is pending approval by Ankita: {str(e)}",
        )
