from typing import Any, List, Optional, Protocol, Union
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import ValidationError
from app.models.entities import BuyerProfile, FarmerProfile, User
from app.core.security import UserRole
from app.schemas.buyer import (
    AdminBuyerActionRequest,
    BuyerProfileCreate,
    BuyerProfileUpdate,
    BuyerVerificationRequest,
    BuyerVerificationStatus,
)
from app.schemas.farmer import FarmerProfileCreate, FarmerProfileUpdate
from app.services.auth_service import DatabaseSchemaPendingError


class FarmerProfileCreationDataError(ValueError):
    """Raised when a profile upsert lacks the fields required for creation."""


class BuyerProfileCreationDataError(ValueError):
    """Raised when a buyer profile upsert lacks the fields required for creation."""


class FarmerProfileRepository(Protocol):
    """Repository interface for Farmer Profile persistence."""
    def get_by_user_id(self, db: Session, user_id: int) -> Optional[Any]:
        ...

    def get_by_id(self, db: Session, profile_id: int) -> Optional[Any]:
        ...

    def save_or_update(
        self, db: Session, user_id: int, profile_in: Union[FarmerProfileCreate, FarmerProfileUpdate]
    ) -> Optional[Any]:
        ...

    def list_farmers(
        self, db: Session, skip: int = 0, limit: int = 50, state: Optional[str] = None, district: Optional[str] = None
    ) -> List[Any]:
        ...


class BuyerProfileRepository(Protocol):
    """Repository interface for Buyer Profile & Verification persistence."""
    def get_by_user_id(self, db: Session, user_id: int) -> Optional[Any]:
        ...

    def get_by_id(self, db: Session, profile_id: int) -> Optional[Any]:
        ...

    def save_or_update(
        self, db: Session, user_id: int, profile_in: Union[BuyerProfileCreate, BuyerProfileUpdate]
    ) -> Any:
        ...

    def submit_verification(
        self, db: Session, user_id: int, req: BuyerVerificationRequest
    ) -> Any:
        ...

    def list_buyers(
        self, db: Session, status: Optional[BuyerVerificationStatus] = None, skip: int = 0, limit: int = 50
    ) -> List[Any]:
        ...

    def update_verification_status(
        self, db: Session, profile_id: int, new_status: BuyerVerificationStatus, notes: Optional[str] = None
    ) -> Any:
        ...


class DefaultPostgresProfileRepository:
    """
    Default production repository for approved profile persistence.
    """
    def get_by_user_id(self, db: Session, user_id: int) -> Optional[Any]:
        result = db.execute(
            select(FarmerProfile, User.full_name, User.email, User.phone_number)
            .join(User, FarmerProfile.user_id == User.id)
            .where(FarmerProfile.user_id == user_id)
        ).one_or_none()
        if result is None:
            return None

        profile, full_name, email, phone_number = result
        response_data = {
            column.key: getattr(profile, column.key)
            for column in FarmerProfile.__table__.columns
        }
        response_data.update(
            full_name=full_name,
            email=email,
            phone_number=phone_number,
        )
        return response_data

    def get_by_id(self, db: Session, profile_id: int) -> Optional[Any]:
        try:
            result = db.execute(
                select(FarmerProfile, User.full_name, User.email, User.phone_number)
                .join(User, FarmerProfile.user_id == User.id)
                .where(FarmerProfile.id == profile_id, User.role == UserRole.FARMER)
            ).one_or_none()
            if result is None:
                return None
            profile, full_name, email, phone_number = result
            data = {column.key: getattr(profile, column.key) for column in FarmerProfile.__table__.columns}
            data.update(full_name=full_name, email=email, phone_number=phone_number)
            return data
        except Exception:
            db.rollback()
            raise

    def save_or_update(
        self, db: Session, user_id: int, profile_in: Any
    ) -> Optional[Any]:
        try:
            result = db.execute(
                select(FarmerProfile, User.full_name, User.email, User.phone_number)
                .join(User, FarmerProfile.user_id == User.id)
                .where(FarmerProfile.user_id == user_id)
            ).one_or_none()
            updates = profile_in.model_dump(exclude_unset=True, exclude_none=True)

            if result is None:
                user = db.scalar(select(User).where(User.id == user_id))
                if user is None:
                    return None
                try:
                    creation_data = FarmerProfileCreate.model_validate(updates)
                except ValidationError as error:
                    raise FarmerProfileCreationDataError from error

                profile = FarmerProfile(
                    user_id=user_id,
                    **creation_data.model_dump(),
                )
                full_name, email, phone_number = user.full_name, user.email, user.phone_number
                db.add(profile)
                db.flush()
            else:
                profile, full_name, email, phone_number = result
                for field, value in updates.items():
                    setattr(profile, field, value)

            db.commit()
            db.refresh(profile)

            response_data = {
                column.key: getattr(profile, column.key)
                for column in FarmerProfile.__table__.columns
            }
            response_data.update(
                full_name=full_name,
                email=email,
                phone_number=phone_number,
            )
            return response_data
        except Exception:
            db.rollback()
            raise

    def list_farmers(
        self, db: Session, skip: int = 0, limit: int = 50, state: Optional[str] = None, district: Optional[str] = None
    ) -> List[Any]:
        try:
            filters = [User.role == UserRole.FARMER]
            if state:
                filters.append(FarmerProfile.state.ilike(f"%{state}%"))
            if district:
                filters.append(FarmerProfile.district.ilike(f"%{district}%"))
            rows = db.execute(
                select(FarmerProfile, User.full_name, User.email, User.phone_number)
                .join(User, FarmerProfile.user_id == User.id)
                .where(*filters)
                .order_by(FarmerProfile.id.asc())
                .offset(skip)
                .limit(limit)
            ).all()
            profiles = []
            for profile, full_name, email, phone_number in rows:
                data = {column.key: getattr(profile, column.key) for column in FarmerProfile.__table__.columns}
                data.update(full_name=full_name, email=email, phone_number=phone_number)
                profiles.append(data)
            return profiles
        except Exception:
            db.rollback()
            raise

    def submit_verification(
        self, db: Session, user_id: int, req: Any
    ) -> Any:
        try:
            result = db.execute(
                select(BuyerProfile, User.full_name, User.email, User.phone_number)
                .join(User, BuyerProfile.user_id == User.id)
                .where(BuyerProfile.user_id == user_id, User.role == UserRole.BUYER)
                .with_for_update()
            ).one_or_none()
            if result is None:
                return None
            profile, full_name, email, phone_number = result
            profile.license_number = req.license_number
            profile.business_name = req.business_name
            profile.business_type = req.business_type
            profile.market_address = req.market_address
            profile.documents_url = req.documents_url
            profile.verification_notes = req.verification_notes
            profile.verification_status = BuyerVerificationStatus.PENDING
            db.commit()
            db.refresh(profile)
            return self._profile_data(profile, full_name, email, phone_number)
        except Exception:
            db.rollback()
            raise

    def list_buyers(
        self, db: Session, status: Optional[BuyerVerificationStatus] = None, skip: int = 0, limit: int = 50
    ) -> List[Any]:
        try:
            filters = [User.role == UserRole.BUYER]
            if status is not None:
                filters.append(BuyerProfile.verification_status == status)
            rows = db.execute(
                select(BuyerProfile, User.full_name, User.email, User.phone_number)
                .join(User, BuyerProfile.user_id == User.id)
                .where(*filters)
                .order_by(BuyerProfile.id.asc())
                .offset(skip)
                .limit(limit)
            ).all()
            return [self._profile_data(*row) for row in rows]
        except Exception:
            db.rollback()
            raise

    def update_verification_status(
        self, db: Session, profile_id: int, new_status: BuyerVerificationStatus, notes: Optional[str] = None
    ) -> Any:
        try:
            result = db.execute(
                select(BuyerProfile, User)
                .join(User, BuyerProfile.user_id == User.id)
                .where(BuyerProfile.id == profile_id, User.role == UserRole.BUYER)
                .with_for_update()
            ).one_or_none()
            if result is None:
                return None
            profile, user = result
            full_name, email, phone_number = user.full_name, user.email, user.phone_number
            was_suspended = profile.verification_status == BuyerVerificationStatus.SUSPENDED
            profile.verification_status = new_status
            profile.verification_notes = notes
            if new_status == BuyerVerificationStatus.SUSPENDED:
                user.is_active = False
            elif new_status == BuyerVerificationStatus.VERIFIED and was_suspended:
                user.is_active = True
            db.commit()
            db.refresh(profile)
            return DefaultPostgresBuyerProfileRepository._profile_data(
                profile, full_name, email, phone_number
            )
        except Exception:
            db.rollback()
            raise


class DefaultPostgresBuyerProfileRepository(DefaultPostgresProfileRepository):
    """PostgreSQL persistence for authenticated buyer profiles."""

    @staticmethod
    def _profile_data(profile, full_name, email, phone_number):
        data = {column.key: getattr(profile, column.key) for column in BuyerProfile.__table__.columns}
        data.update(full_name=full_name, email=email, phone_number=phone_number)
        return data

    def get_by_user_id(self, db: Session, user_id: int) -> Optional[Any]:
        result = db.execute(
            select(BuyerProfile, User.full_name, User.email, User.phone_number)
            .join(User, BuyerProfile.user_id == User.id)
            .where(BuyerProfile.user_id == user_id)
        ).one_or_none()
        if result is None:
            return None
        return self._profile_data(*result)

    def get_by_id(self, db: Session, profile_id: int) -> Optional[Any]:
        try:
            result = db.execute(
                select(BuyerProfile, User.full_name, User.email, User.phone_number)
                .join(User, BuyerProfile.user_id == User.id)
                .where(BuyerProfile.id == profile_id, User.role == UserRole.BUYER)
            ).one_or_none()
            return self._profile_data(*result) if result is not None else None
        except Exception:
            db.rollback()
            raise

    def save_or_update(self, db: Session, user_id: int, profile_in: Any) -> Optional[Any]:
        try:
            result = db.execute(
                select(BuyerProfile, User.full_name, User.email, User.phone_number)
                .join(User, BuyerProfile.user_id == User.id)
                .where(BuyerProfile.user_id == user_id)
            ).one_or_none()
            updates = profile_in.model_dump(exclude_unset=True, exclude_none=True)

            if result is None:
                user = db.scalar(select(User).where(User.id == user_id))
                if user is None:
                    return None
                try:
                    creation_data = BuyerProfileCreate.model_validate(updates)
                except ValidationError as error:
                    raise BuyerProfileCreationDataError from error
                profile = BuyerProfile(user_id=user_id, **creation_data.model_dump())
                full_name, email, phone_number = user.full_name, user.email, user.phone_number
                db.add(profile)
                db.flush()
            else:
                profile, full_name, email, phone_number = result
                for field, value in updates.items():
                    setattr(profile, field, value)

            db.commit()
            db.refresh(profile)
            return self._profile_data(profile, full_name, email, phone_number)
        except Exception:
            db.rollback()
            raise


_default_profile_repo = DefaultPostgresProfileRepository()
_default_buyer_profile_repo = DefaultPostgresBuyerProfileRepository()


def get_farmer_profile_repo() -> FarmerProfileRepository:
    """Dependency injection for FarmerProfileRepository."""
    return _default_profile_repo


def get_buyer_profile_repo() -> BuyerProfileRepository:
    """Dependency injection for BuyerProfileRepository."""
    return _default_buyer_profile_repo
