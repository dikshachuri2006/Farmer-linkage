"""SQLAlchemy mappings for the approved, non-deferred application schema."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum as PythonEnum
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    BigInteger,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    desc,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.security import UserRole
from app.database.base import Base
from app.schemas.buyer import BuyerBusinessType, BuyerVerificationStatus
from app.schemas.complaint import ComplaintIssueType, ComplaintStatus
from app.schemas.crop import CropCategory
from app.schemas.farmer_lot import LotQualityGrade, LotStatus
from app.schemas.notification import NotificationType
from app.schemas.offer import OfferStatus
from app.schemas.selling_request import SellingRequestStatus
from app.schemas.transaction import PaymentStatus, TransactionStatus


def _enum_type(enum_class: type[PythonEnum], name: str) -> SAEnum:
    """Persist the public enum values, which currently match their names."""
    return SAEnum(
        enum_class,
        name=name,
        native_enum=True,
        values_callable=lambda members: [member.value for member in members],
    )


class CreatedUpdatedMixin:
    """Server defaults plus ORM-side updated-at maintenance."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class User(Base, CreatedUpdatedMixin):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("length(trim(full_name)) > 0", name="ck_users_full_name_nonempty"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    role: Mapped[UserRole] = mapped_column(_enum_type(UserRole, "user_role"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class FarmerProfile(Base, CreatedUpdatedMixin):
    __tablename__ = "farmer_profiles"
    __table_args__ = (
        CheckConstraint("land_area_acres IS NULL OR land_area_acres >= 0", name="ck_farmer_profiles_land_area_nonnegative"),
        CheckConstraint("latitude IS NULL OR latitude BETWEEN -90 AND 90", name="ck_farmer_profiles_latitude_range"),
        CheckConstraint("longitude IS NULL OR longitude BETWEEN -180 AND 180", name="ck_farmer_profiles_longitude_range"),
        CheckConstraint("pincode ~ '^[0-9]{6}$'", name="ck_farmer_profiles_pincode_format"),
        Index("ix_farmer_profiles_state_district", "state", "district"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, unique=True)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    district: Mapped[str] = mapped_column(String(100), nullable=False)
    taluka: Mapped[Optional[str]] = mapped_column(String(100))
    village: Mapped[Optional[str]] = mapped_column(String(100))
    pincode: Mapped[str] = mapped_column(String(10), nullable=False)
    land_area_acres: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    preferred_language: Mapped[str] = mapped_column(String(10), nullable=False, default="en", server_default="en")
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7))


class BuyerProfile(Base, CreatedUpdatedMixin):
    __tablename__ = "buyer_profiles"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1.00 AND 5.00", name="ck_buyer_profiles_rating_range"),
        CheckConstraint("total_transactions >= 0", name="ck_buyer_profiles_total_transactions_nonnegative"),
        CheckConstraint("latitude IS NULL OR latitude BETWEEN -90 AND 90", name="ck_buyer_profiles_latitude_range"),
        CheckConstraint("longitude IS NULL OR longitude BETWEEN -180 AND 180", name="ck_buyer_profiles_longitude_range"),
        Index("ix_buyer_profiles_verification_status", "verification_status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, unique=True)
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    business_type: Mapped[BuyerBusinessType] = mapped_column(
        _enum_type(BuyerBusinessType, "buyer_business_type"), nullable=False, default=BuyerBusinessType.TRADER,
        server_default=BuyerBusinessType.TRADER.value,
    )
    license_number: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    district: Mapped[str] = mapped_column(String(100), nullable=False)
    market_address: Mapped[str] = mapped_column(Text, nullable=False)
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7))
    verification_status: Mapped[BuyerVerificationStatus] = mapped_column(
        _enum_type(BuyerVerificationStatus, "buyer_verification_status"), nullable=False,
        default=BuyerVerificationStatus.PENDING, server_default=BuyerVerificationStatus.PENDING.value,
    )
    verification_notes: Mapped[Optional[str]] = mapped_column(Text)
    documents_url: Mapped[Optional[str]] = mapped_column(Text)
    rating: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False, default=Decimal("5.00"), server_default="5.00")
    total_transactions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class Crop(Base):
    __tablename__ = "crops"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_crops_name_nonempty"),
        CheckConstraint("length(trim(standard_unit)) > 0", name="ck_crops_standard_unit_nonempty"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    category: Mapped[CropCategory] = mapped_column(
        _enum_type(CropCategory, "crop_category"), nullable=False, default=CropCategory.OTHER,
        server_default=CropCategory.OTHER.value,
    )
    standard_unit: Mapped[str] = mapped_column(String(20), nullable=False, default="kg", server_default="kg")
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Market(Base):
    __tablename__ = "markets"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_markets_name_nonempty"),
        CheckConstraint("length(trim(state)) > 0", name="ck_markets_state_nonempty"),
        CheckConstraint("length(trim(district)) > 0", name="ck_markets_district_nonempty"),
        CheckConstraint("latitude IS NULL OR latitude BETWEEN -90 AND 90", name="ck_markets_latitude_range"),
        CheckConstraint("longitude IS NULL OR longitude BETWEEN -180 AND 180", name="ck_markets_longitude_range"),
        Index("ix_markets_state_district", "state", "district"),
        Index("ix_markets_name", "name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    district: Mapped[str] = mapped_column(String(100), nullable=False)
    market_code: Mapped[Optional[str]] = mapped_column(String(100))
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7))


class MarketPrice(Base):
    __tablename__ = "market_prices"
    __table_args__ = (
        CheckConstraint("min_price >= 0", name="ck_market_prices_min_nonnegative"),
        CheckConstraint("max_price >= min_price", name="ck_market_prices_max_gte_min"),
        CheckConstraint("modal_price >= 0", name="ck_market_prices_modal_nonnegative"),
        CheckConstraint("arrival_quantity IS NULL OR arrival_quantity >= 0", name="ck_market_prices_arrival_nonnegative"),
        Index("ix_market_prices_crop_market_date", "crop_id", "market_id", desc("price_date")),
        Index("ix_market_prices_crop_market_variant_date", "crop_id", "market_id", "variety", "grade", desc("price_date")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id", ondelete="RESTRICT"), nullable=False)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id", ondelete="RESTRICT"), nullable=False)
    price_date: Mapped[date] = mapped_column(Date, nullable=False)
    min_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    max_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    modal_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    variety: Mapped[Optional[str]] = mapped_column(String(100))
    grade: Mapped[Optional[str]] = mapped_column(String(100))
    arrival_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 3))
    price_unit: Mapped[str] = mapped_column(String(30), nullable=False, default="INR/Quintal", server_default="INR/Quintal")
    arrival_unit: Mapped[Optional[str]] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(String(150), nullable=False, default="Agmarknet", server_default="Agmarknet")


class FarmerLot(Base, CreatedUpdatedMixin):
    __tablename__ = "farmer_lots"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_farmer_lots_quantity_positive"),
        CheckConstraint("expected_price_per_unit > 0", name="ck_farmer_lots_expected_price_positive"),
        Index("ix_farmer_lots_crop_status", "crop_id", "status"),
        Index("ix_farmer_lots_farmer_created", "farmer_id", desc("created_at")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="quintal", server_default="quintal")
    quality_grade: Mapped[LotQualityGrade] = mapped_column(
        _enum_type(LotQualityGrade, "lot_quality_grade"), nullable=False, default=LotQualityGrade.GRADE_A,
        server_default=LotQualityGrade.GRADE_A.value,
    )
    expected_price_per_unit: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    price_unit: Mapped[str] = mapped_column(String(30), nullable=False, default="INR/quintal", server_default="INR/quintal")
    harvest_date: Mapped[Optional[date]] = mapped_column(Date)
    location_state: Mapped[str] = mapped_column(String(100), nullable=False)
    location_district: Mapped[str] = mapped_column(String(100), nullable=False)
    location_pincode: Mapped[Optional[str]] = mapped_column(String(10))
    status: Mapped[LotStatus] = mapped_column(
        _enum_type(LotStatus, "lot_status"), nullable=False, default=LotStatus.AVAILABLE,
        server_default=LotStatus.AVAILABLE.value,
    )


class BuyerOffer(Base, CreatedUpdatedMixin):
    __tablename__ = "buyer_offers"
    __table_args__ = (
        CheckConstraint("offered_price_per_unit > 0", name="ck_buyer_offers_price_positive"),
        CheckConstraint("quantity_requested > 0", name="ck_buyer_offers_quantity_positive"),
        Index("ix_buyer_offers_buyer_status_created", "buyer_id", "status", desc("created_at")),
        Index("ix_buyer_offers_lot_status", "lot_id", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    lot_id: Mapped[int] = mapped_column(ForeignKey("farmer_lots.id", ondelete="RESTRICT"), nullable=False)
    offered_price_per_unit: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    price_unit: Mapped[str] = mapped_column(String(30), nullable=False, default="INR/quintal", server_default="INR/quintal")
    quantity_requested: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    quantity_unit: Mapped[str] = mapped_column(String(20), nullable=False, default="quintal", server_default="quintal")
    pickup_included: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    delivery_location: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[OfferStatus] = mapped_column(
        _enum_type(OfferStatus, "offer_status"), nullable=False, default=OfferStatus.ACTIVE,
        server_default=OfferStatus.ACTIVE.value,
    )
    valid_until: Mapped[Optional[date]] = mapped_column(Date)
    terms_and_notes: Mapped[Optional[str]] = mapped_column(String(500))


class SellingRequest(Base, CreatedUpdatedMixin):
    __tablename__ = "selling_requests"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_selling_requests_quantity_positive"),
        CheckConstraint("proposed_price > 0", name="ck_selling_requests_price_positive"),
        CheckConstraint("estimated_transport_cost >= 0", name="ck_selling_requests_transport_nonnegative"),
        CheckConstraint("estimated_other_charges >= 0", name="ck_selling_requests_charges_nonnegative"),
        Index("ix_selling_requests_farmer_status_created", "farmer_id", "status", desc("created_at")),
        Index("ix_selling_requests_buyer_status_created", "buyer_id", "status", desc("created_at")),
        Index("ix_selling_requests_lot_status", "lot_id", "status"),
        UniqueConstraint("buyer_offer_id", name="uq_selling_requests_buyer_offer_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    request_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    lot_id: Mapped[int] = mapped_column(ForeignKey("farmer_lots.id", ondelete="RESTRICT"), nullable=False)
    buyer_offer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("buyer_offers.id", ondelete="RESTRICT"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    quantity_unit: Mapped[str] = mapped_column(String(20), nullable=False, default="quintal", server_default="quintal")
    proposed_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    price_unit: Mapped[str] = mapped_column(String(30), nullable=False, default="INR/quintal", server_default="INR/quintal")
    estimated_gross_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    estimated_transport_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"), server_default="0")
    estimated_other_charges: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"), server_default="0")
    estimated_net_realization: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    status: Mapped[SellingRequestStatus] = mapped_column(
        _enum_type(SellingRequestStatus, "selling_request_status"), nullable=False,
        default=SellingRequestStatus.PENDING, server_default=SellingRequestStatus.PENDING.value,
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text)
    message: Mapped[Optional[str]] = mapped_column(String(500))


class Transaction(Base, CreatedUpdatedMixin):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("selling_request_id", name="uq_transactions_selling_request_id"),
        CheckConstraint("quantity > 0", name="ck_transactions_quantity_positive"),
        CheckConstraint("agreed_price > 0", name="ck_transactions_agreed_price_positive"),
        CheckConstraint("transport_cost >= 0", name="ck_transactions_transport_nonnegative"),
        CheckConstraint("other_charges >= 0", name="ck_transactions_charges_nonnegative"),
        Index("ix_transactions_created_at", desc("created_at")),
        Index("ix_transactions_farmer_created", "farmer_id", desc("created_at")),
        Index("ix_transactions_buyer_created", "buyer_id", desc("created_at")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    transaction_id: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    selling_request_id: Mapped[int] = mapped_column(ForeignKey("selling_requests.id", ondelete="RESTRICT"), nullable=False)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    crop_id: Mapped[int] = mapped_column(ForeignKey("crops.id", ondelete="RESTRICT"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    quantity_unit: Mapped[str] = mapped_column(String(20), nullable=False)
    agreed_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    price_unit: Mapped[str] = mapped_column(String(30), nullable=False)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    transport_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"), server_default="0")
    other_charges: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0"), server_default="0")
    net_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    payment_status: Mapped[PaymentStatus] = mapped_column(
        _enum_type(PaymentStatus, "payment_status"), nullable=False, default=PaymentStatus.PENDING,
        server_default=PaymentStatus.PENDING.value,
    )
    transaction_status: Mapped[TransactionStatus] = mapped_column(
        _enum_type(TransactionStatus, "transaction_status"), nullable=False, default=TransactionStatus.CONFIRMED,
        server_default=TransactionStatus.CONFIRMED.value,
    )
    payment_method: Mapped[Optional[str]] = mapped_column(String(50), default="ESCROW", server_default="ESCROW")
    notes: Mapped[Optional[str]] = mapped_column(String(500))


class Complaint(Base):
    __tablename__ = "complaints"
    __table_args__ = (
        CheckConstraint("resolved_at IS NULL OR resolved_at >= created_at", name="ck_complaints_resolution_after_creation"),
        Index("ix_complaints_complainant_created", "complainant_user_id", desc("created_at")),
        Index("ix_complaints_status_issue_created", "status", "issue_type", desc("created_at")),
        Index("ix_complaints_transaction_id", "transaction_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    ticket_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    complainant_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    transaction_id: Mapped[Optional[int]] = mapped_column(ForeignKey("transactions.id", ondelete="RESTRICT"))
    against_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    issue_type: Mapped[ComplaintIssueType] = mapped_column(_enum_type(ComplaintIssueType, "complaint_issue_type"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ComplaintStatus] = mapped_column(
        _enum_type(ComplaintStatus, "complaint_status"), nullable=False,
        default=ComplaintStatus.OPEN, server_default=ComplaintStatus.OPEN.value,
    )
    admin_notes: Mapped[Optional[str]] = mapped_column(String(1000))
    resolution_summary: Mapped[Optional[str]] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_read_created", "user_id", "is_read", desc("created_at")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    notification_type: Mapped[NotificationType] = mapped_column(
        _enum_type(NotificationType, "notification_type"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    reference_id: Mapped[Optional[str]] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
