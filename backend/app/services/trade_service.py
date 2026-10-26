from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, List, Optional, Protocol, Tuple
from uuid import uuid4
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, aliased
from app.core.security import UserRole
from app.models.entities import BuyerOffer, BuyerProfile, Crop, FarmerLot, SellingRequest, User
from app.schemas.buyer import BuyerVerificationStatus
from app.schemas.farmer_lot import FarmerLotCreate, FarmerLotUpdate, LotQualityGrade, LotStatus
from app.schemas.offer import BuyerOfferCreate, BuyerOfferUpdate, OfferStatus
from app.schemas.selling_request import (
    RequestActionType,
    SellingRequestActionRequest,
    SellingRequestCreate,
    SellingRequestStatus,
)
from app.services.auth_service import DatabaseSchemaPendingError


class TradeWorkflowError(Exception):
    """Business rule or state machine violation during trade negotiation."""
    pass


class CropNotFoundError(LookupError):
    """Raised when a lot references a crop absent from the crop catalog."""


class BuyerNotFoundError(LookupError):
    """Raised when a selling request targets a missing or non-buyer account."""


_QUANTITY_UNITS = {
    "kg": "kg", "kgs": "kg", "kilogram": "kg", "kilograms": "kg",
    "quintal": "quintal", "quintals": "quintal", "qtl": "quintal",
    "tonne": "tonne", "tonnes": "tonne", "metric tonne": "tonne", "metric tonnes": "tonne",
}
_PRICE_UNITS = {
    "inr/kg": "kg", "inr/quintal": "quintal", "inr/tonne": "tonne",
    "inr/metric tonne": "tonne", "rs./quintal": "quintal",
}


def _validate_trade_units(price_unit: str, quantity_unit: str, lot_unit: Optional[str] = None) -> None:
    quantity_key = _QUANTITY_UNITS.get(quantity_unit.strip().casefold())
    price_key = _PRICE_UNITS.get(price_unit.strip().casefold())
    if quantity_key is None or price_key is None:
        raise TradeWorkflowError("Trade must use a supported kg, quintal, or tonne quantity and price unit.")
    if quantity_key != price_key:
        raise TradeWorkflowError("Price unit denominator must match the trade quantity unit.")
    if lot_unit is not None and _QUANTITY_UNITS.get(lot_unit.strip().casefold()) != quantity_key:
        raise TradeWorkflowError("Trade quantity unit must match the farmer lot quantity unit.")


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _lot_response(db: Session, lot: FarmerLot) -> dict:
    crop = db.get(Crop, lot.crop_id)
    farmer = db.get(User, lot.farmer_id)
    data = {column.key: getattr(lot, column.key) for column in FarmerLot.__table__.columns}
    data.update(crop_name=crop.name if crop else "", farmer_name=farmer.full_name if farmer else "")
    return data


def _selling_request_response(row: tuple) -> dict:
    request, farmer_name, buyer_name, crop_name = row
    data = {column.key: getattr(request, column.key) for column in SellingRequest.__table__.columns}
    data.update(farmer_name=farmer_name, buyer_name=buyer_name, crop_name=crop_name)
    return data


def _selling_request_query():
    farmer = aliased(User)
    buyer = aliased(User)
    return (
        select(SellingRequest, farmer.full_name, buyer.full_name, Crop.name)
        .join(farmer, SellingRequest.farmer_id == farmer.id)
        .join(buyer, SellingRequest.buyer_id == buyer.id)
        .join(FarmerLot, SellingRequest.lot_id == FarmerLot.id)
        .join(Crop, FarmerLot.crop_id == Crop.id)
    )


class FarmerLotRepository(Protocol):
    def create_lot(
        self, db: Session, farmer_id: int, farmer_name: str, lot_in: FarmerLotCreate
    ) -> Any: ...

    def get_lot_by_id(
        self, db: Session, lot_id: int, farmer_id: Optional[int] = None
    ) -> Optional[Any]: ...

    def list_farmer_lots(
        self, db: Session, farmer_id: int, skip: int = 0, limit: int = 50
    ) -> Tuple[List[Any], int]: ...

    def update_lot(
        self, db: Session, lot_id: int, farmer_id: int, lot_update: FarmerLotUpdate
    ) -> Optional[Any]: ...

    def withdraw_lot(
        self, db: Session, lot_id: int, farmer_id: int
    ) -> Optional[Any]: ...

    def list_marketplace_lots(
        self,
        db: Session,
        crop_id: Optional[int] = None,
        state: Optional[str] = None,
        district: Optional[str] = None,
        grade: Optional[LotQualityGrade] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Any], int]: ...


class BuyerOfferRepository(Protocol):
    def create_offer(
        self, db: Session, buyer_id: int, buyer_name: str, lot: Any, offer_in: BuyerOfferCreate
    ) -> Any: ...

    def get_offer_by_id(self, db: Session, offer_id: int) -> Optional[Any]: ...

    def list_buyer_offers(
        self, db: Session, buyer_id: int, skip: int = 0, limit: int = 50
    ) -> Tuple[List[Any], int]: ...

    def list_offers_for_lot(
        self, db: Session, lot_id: int, farmer_id: int
    ) -> List[Any]: ...

    def withdraw_offer(
        self, db: Session, offer_id: int, buyer_id: int
    ) -> Optional[Any]: ...

    def accept_offer(self, db: Session, offer_id: int, farmer_id: int) -> Optional[Any]: ...

    def reject_offer(
        self, db: Session, offer_id: int, farmer_id: int, reason: Optional[str] = None
    ) -> Optional[Any]: ...


class SellingRequestRepository(Protocol):
    def create_request(
        self,
        db: Session,
        farmer_id: int,
        farmer_name: str,
        buyer_id: int,
        buyer_name: str,
        lot: Any,
        req_in: SellingRequestCreate,
    ) -> Any: ...

    def get_request_by_id(
        self,
        db: Session,
        request_id: int,
        farmer_id: Optional[int] = None,
        buyer_id: Optional[int] = None,
    ) -> Optional[Any]: ...

    def list_farmer_requests(
        self, db: Session, farmer_id: int, skip: int = 0, limit: int = 50
    ) -> Tuple[List[Any], int]: ...

    def list_buyer_requests(
        self, db: Session, buyer_id: int, skip: int = 0, limit: int = 50
    ) -> Tuple[List[Any], int]: ...

    def execute_action(
        self,
        db: Session,
        request_id: int,
        actor_id: int,
        actor_role: str,
        action_in: SellingRequestActionRequest,
    ) -> Any: ...


# Default production implementations for approved database schemas
class DefaultFarmerLotRepository:
    def create_lot(self, db: Session, farmer_id: int, farmer_name: str, lot_in: FarmerLotCreate) -> Any:
        try:
            crop = db.get(Crop, lot_in.crop_id)
            if crop is None:
                raise CropNotFoundError(f"Crop {lot_in.crop_id} does not exist.")
            farmer = db.get(User, farmer_id)
            if farmer is None or _enum_value(farmer.role) != UserRole.FARMER.value:
                raise TradeWorkflowError("Authenticated farmer account is unavailable.")

            lot = FarmerLot(
                farmer_id=farmer_id,
                crop_id=lot_in.crop_id,
                quantity=Decimal(str(lot_in.quantity)),
                unit=lot_in.unit,
                quality_grade=lot_in.quality_grade,
                expected_price_per_unit=Decimal(str(lot_in.expected_price_per_unit)),
                price_unit=lot_in.price_unit,
                harvest_date=lot_in.harvest_date,
                location_state=lot_in.location_state,
                location_district=lot_in.location_district,
                location_pincode=lot_in.location_pincode,
            )
            db.add(lot)
            db.flush()
            db.refresh(lot)
            response_data = {
                column.key: getattr(lot, column.key)
                for column in FarmerLot.__table__.columns
            }
            response_data.update(
                crop_name=crop.name,
                farmer_name=farmer.full_name,
            )
            db.commit()
            return response_data
        except Exception:
            db.rollback()
            raise

    def get_lot_by_id(
        self, db: Session, lot_id: int, farmer_id: Optional[int] = None
    ) -> Optional[Any]:
        try:
            query = select(FarmerLot).where(FarmerLot.id == lot_id)
            if farmer_id is not None:
                query = query.where(FarmerLot.farmer_id == farmer_id)
            lot = db.scalar(query)
            return _lot_response(db, lot) if lot is not None else None
        except Exception:
            db.rollback()
            raise

    def list_farmer_lots(self, db: Session, farmer_id: int, skip: int = 0, limit: int = 50) -> Tuple[List[Any], int]:
        try:
            total = db.scalar(
                select(func.count(FarmerLot.id)).where(FarmerLot.farmer_id == farmer_id)
            ) or 0
            rows = db.execute(
                select(FarmerLot, Crop.name, User.full_name)
                .join(Crop, FarmerLot.crop_id == Crop.id)
                .join(User, FarmerLot.farmer_id == User.id)
                .where(FarmerLot.farmer_id == farmer_id)
                .order_by(desc(FarmerLot.created_at), desc(FarmerLot.id))
                .offset(skip)
                .limit(limit)
            ).all()

            items = []
            for lot, crop_name, farmer_name in rows:
                item = {
                    column.key: getattr(lot, column.key)
                    for column in FarmerLot.__table__.columns
                }
                item.update(crop_name=crop_name, farmer_name=farmer_name)
                items.append(item)
            return items, total
        except Exception:
            db.rollback()
            raise

    def update_lot(self, db: Session, lot_id: int, farmer_id: int, lot_update: FarmerLotUpdate) -> Optional[Any]:
        try:
            lot = db.scalar(
                select(FarmerLot)
                .where(FarmerLot.id == lot_id, FarmerLot.farmer_id == farmer_id)
                .with_for_update()
            )
            if lot is None:
                return None
            updates = lot_update.model_dump(exclude_unset=True, exclude_none=True)
            for field, value in updates.items():
                if field == "status" and value in (LotStatus.COMMITTED, LotStatus.SOLD):
                    raise TradeWorkflowError("Lot status is managed by the selling workflow.")
                setattr(lot, field, value)
            db.flush()
            db.refresh(lot)
            response = _lot_response(db, lot)
            db.commit()
            return response
        except Exception:
            db.rollback()
            raise

    def withdraw_lot(self, db: Session, lot_id: int, farmer_id: int) -> Optional[Any]:
        try:
            lot = db.scalar(
                select(FarmerLot)
                .where(FarmerLot.id == lot_id, FarmerLot.farmer_id == farmer_id)
                .with_for_update()
            )
            if lot is None:
                return None
            if lot.status in (LotStatus.COMMITTED, LotStatus.SOLD):
                raise TradeWorkflowError("Cannot withdraw a lot already committed or sold.")
            lot.status = LotStatus.WITHDRAWN
            db.flush()
            db.refresh(lot)
            response = _lot_response(db, lot)
            db.commit()
            return response
        except Exception:
            db.rollback()
            raise

    def list_marketplace_lots(
        self,
        db: Session,
        crop_id: Optional[int] = None,
        state: Optional[str] = None,
        district: Optional[str] = None,
        grade: Optional[LotQualityGrade] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Any], int]:
        try:
            conditions = [FarmerLot.status == LotStatus.AVAILABLE]

            if crop_id is not None:
                conditions.append(FarmerLot.crop_id == crop_id)
            if state is not None and state.strip():
                conditions.append(func.lower(FarmerLot.location_state) == state.strip().lower())
            if district is not None and district.strip():
                conditions.append(func.lower(FarmerLot.location_district) == district.strip().lower())
            if grade is not None:
                conditions.append(FarmerLot.quality_grade == grade)
            if min_price is not None:
                conditions.append(FarmerLot.expected_price_per_unit >= Decimal(str(min_price)))
            if max_price is not None:
                conditions.append(FarmerLot.expected_price_per_unit <= Decimal(str(max_price)))

            total = db.scalar(
                select(func.count(FarmerLot.id)).where(*conditions)
            ) or 0

            rows = db.execute(
                select(FarmerLot, Crop.name, User.full_name)
                .join(Crop, FarmerLot.crop_id == Crop.id)
                .join(User, FarmerLot.farmer_id == User.id)
                .where(*conditions)
                .order_by(desc(FarmerLot.created_at), desc(FarmerLot.id))
                .offset(skip)
                .limit(limit)
            ).all()

            items = []
            for lot, crop_name, farmer_name in rows:
                item = {
                    "id": lot.id,
                    "farmer_id": lot.farmer_id,
                    "farmer_name": farmer_name,
                    "crop_id": lot.crop_id,
                    "crop_name": crop_name,
                    "quantity": float(lot.quantity),
                    "unit": lot.unit,
                    "quality_grade": lot.quality_grade,
                    "expected_price_per_unit": float(lot.expected_price_per_unit),
                    "price_unit": lot.price_unit,
                    "harvest_date": lot.harvest_date,
                    "location_state": lot.location_state,
                    "location_district": lot.location_district,
                    "status": lot.status,
                    "created_at": lot.created_at,
                    "updated_at": lot.updated_at,
                }
                items.append(item)
            return items, total
        except Exception:
            db.rollback()
            raise



class DefaultBuyerOfferRepository:
    def create_offer(self, db: Session, buyer_id: int, buyer_name: str, lot: Any, offer_in: BuyerOfferCreate) -> Any:
        try:
            buyer = db.scalar(select(User).where(User.id == buyer_id, User.role == UserRole.BUYER))
            locked_lot = db.scalar(
                select(FarmerLot).where(FarmerLot.id == offer_in.lot_id).with_for_update()
            )
            if buyer is None:
                raise TradeWorkflowError("Authenticated buyer account is unavailable.")
            if locked_lot is None or locked_lot.status != LotStatus.AVAILABLE:
                raise TradeWorkflowError("Target farmer lot is unavailable or does not exist.")
            _validate_trade_units(offer_in.price_unit, offer_in.quantity_unit, locked_lot.unit)
            quantity = Decimal(str(offer_in.quantity_requested))
            if quantity > locked_lot.quantity:
                raise TradeWorkflowError("Requested quantity exceeds available lot stock.")

            crop = db.get(Crop, locked_lot.crop_id)
            offer = BuyerOffer(
                buyer_id=buyer_id,
                lot_id=locked_lot.id,
                offered_price_per_unit=Decimal(str(offer_in.offered_price_per_unit)),
                price_unit=offer_in.price_unit,
                quantity_requested=quantity,
                quantity_unit=offer_in.quantity_unit,
                pickup_included=offer_in.pickup_included,
                delivery_location=offer_in.delivery_location,
                valid_until=offer_in.valid_until,
                terms_and_notes=offer_in.terms_and_notes,
            )
            db.add(offer)
            db.flush()
            db.refresh(offer)
            response = self._response_data(offer, buyer_name, crop.name if crop else "")
            db.commit()
            return response
        except Exception:
            db.rollback()
            raise

    def get_offer_by_id(self, db: Session, offer_id: int) -> Optional[Any]:
        try:
            row = db.execute(self._offer_query().where(BuyerOffer.id == offer_id)).one_or_none()
            return self._response_data(*row) if row is not None else None
        except Exception:
            db.rollback()
            raise

    def list_buyer_offers(self, db: Session, buyer_id: int, skip: int = 0, limit: int = 50) -> Tuple[List[Any], int]:
        try:
            total = db.scalar(
                select(func.count(BuyerOffer.id)).where(BuyerOffer.buyer_id == buyer_id)
            ) or 0
            rows = db.execute(
                self._offer_query()
                .where(BuyerOffer.buyer_id == buyer_id)
                .order_by(desc(BuyerOffer.created_at), desc(BuyerOffer.id))
                .offset(skip)
                .limit(limit)
            ).all()
            return [self._response_data(*row) for row in rows], total
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def _offer_query():
        return (
            select(BuyerOffer, func.coalesce(BuyerProfile.business_name, User.full_name), Crop.name)
            .join(User, BuyerOffer.buyer_id == User.id)
            .outerjoin(BuyerProfile, BuyerProfile.user_id == User.id)
            .join(FarmerLot, BuyerOffer.lot_id == FarmerLot.id)
            .join(Crop, FarmerLot.crop_id == Crop.id)
        )

    @staticmethod
    def _response_data(offer: BuyerOffer, buyer_name: str, crop_name: str) -> dict:
        data = {column.key: getattr(offer, column.key) for column in BuyerOffer.__table__.columns}
        data.update(
            buyer_name=buyer_name,
            crop_name=crop_name,
            total_offer_value=float(
                (offer.offered_price_per_unit * offer.quantity_requested).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            ),
        )
        return data

    def list_offers_for_lot(self, db: Session, lot_id: int, farmer_id: int) -> List[Any]:
        try:
            rows = db.execute(
                select(BuyerOffer, User.full_name, BuyerProfile.business_name, Crop.name)
                .join(FarmerLot, BuyerOffer.lot_id == FarmerLot.id)
                .join(User, BuyerOffer.buyer_id == User.id)
                .outerjoin(BuyerProfile, BuyerProfile.user_id == User.id)
                .join(Crop, FarmerLot.crop_id == Crop.id)
                .where(
                    FarmerLot.id == lot_id,
                    FarmerLot.farmer_id == farmer_id,
                    BuyerOffer.status == OfferStatus.ACTIVE,
                    or_(BuyerOffer.valid_until.is_(None), BuyerOffer.valid_until >= date.today()),
                )
                .order_by(desc(BuyerOffer.created_at), desc(BuyerOffer.id))
            ).all()
            result = []
            for offer, full_name, business_name, crop_name in rows:
                item = {column.key: getattr(offer, column.key) for column in BuyerOffer.__table__.columns}
                item.update(
                    buyer_name=business_name or full_name,
                    crop_name=crop_name,
                    total_offer_value=float(
                        (offer.offered_price_per_unit * offer.quantity_requested).quantize(
                            Decimal("0.01"), rounding=ROUND_HALF_UP
                        )
                    ),
                )
                result.append(item)
            return result
        except Exception:
            db.rollback()
            raise

    def withdraw_offer(self, db: Session, offer_id: int, buyer_id: int) -> Optional[Any]:
        try:
            offer = db.scalar(
                select(BuyerOffer)
                .where(BuyerOffer.id == offer_id, BuyerOffer.buyer_id == buyer_id)
                .with_for_update()
            )
            if offer is None:
                return None
            if offer.status == OfferStatus.ACCEPTED:
                raise TradeWorkflowError("Cannot withdraw an accepted offer.")
            row = db.execute(self._offer_query().where(BuyerOffer.id == offer_id)).one()
            offer.status = OfferStatus.WITHDRAWN
            db.flush()
            db.refresh(offer)
            response = self._response_data(offer, row[1], row[2])
            db.commit()
            return response
        except Exception:
            db.rollback()
            raise

    def accept_offer(self, db: Session, offer_id: int, farmer_id: int) -> Optional[Any]:
        """Atomically accept an offer and create the accepted request used by transactions."""
        try:
            offer = db.scalar(
                select(BuyerOffer).where(BuyerOffer.id == offer_id).with_for_update()
            )
            if offer is None:
                return None
            lot = db.scalar(
                select(FarmerLot)
                .where(FarmerLot.id == offer.lot_id, FarmerLot.farmer_id == farmer_id)
                .with_for_update()
            )
            if lot is None:
                return None
            if offer.status != OfferStatus.ACTIVE:
                raise TradeWorkflowError("Only active buyer offers can be accepted.")
            if offer.valid_until is not None and offer.valid_until < date.today():
                raise TradeWorkflowError("This buyer offer has expired.")
            if lot.status != LotStatus.AVAILABLE:
                raise TradeWorkflowError("The farmer lot is no longer available.")
            _validate_trade_units(offer.price_unit, offer.quantity_unit, lot.unit)
            if offer.quantity_requested > lot.quantity:
                raise TradeWorkflowError("Offer quantity exceeds the available lot stock.")
            buyer = db.scalar(
                select(User).where(User.id == offer.buyer_id, User.role == UserRole.BUYER).with_for_update()
            )
            buyer_profile = db.scalar(
                select(BuyerProfile).where(BuyerProfile.user_id == offer.buyer_id).with_for_update()
            )
            if (
                buyer is None or not buyer.is_active or buyer_profile is None
                or buyer_profile.verification_status != BuyerVerificationStatus.VERIFIED
            ):
                raise TradeWorkflowError("The buyer account is no longer active and verified.")
            if db.get(Crop, lot.crop_id) is None:
                raise TradeWorkflowError("The farmer lot references an unavailable crop.")

            gross = (offer.offered_price_per_unit * offer.quantity_requested).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            request = SellingRequest(
                request_code=f"REQ-{datetime.now(timezone.utc):%Y%m%d}-{uuid4().hex[:12].upper()}",
                farmer_id=farmer_id,
                buyer_id=offer.buyer_id,
                lot_id=lot.id,
                buyer_offer_id=offer.id,
                quantity=offer.quantity_requested,
                quantity_unit=offer.quantity_unit,
                proposed_price=offer.offered_price_per_unit,
                price_unit=offer.price_unit,
                estimated_gross_amount=gross,
                estimated_transport_cost=Decimal("0.00"),
                estimated_other_charges=Decimal("0.00"),
                estimated_net_realization=gross,
                status=SellingRequestStatus.ACCEPTED,
                message=f"Created by acceptance of buyer offer {offer.id}.",
            )
            offer.status = OfferStatus.ACCEPTED
            lot.status = LotStatus.COMMITTED
            db.add(request)
            db.flush()
            offer_row = db.execute(self._offer_query().where(BuyerOffer.id == offer.id)).one()
            request_row = db.execute(_selling_request_query().where(SellingRequest.id == request.id)).one()
            response = {
                "offer": self._response_data(*offer_row),
                "selling_request": _selling_request_response(request_row),
            }
            db.commit()
            return response
        except Exception:
            db.rollback()
            raise

    def reject_offer(
        self, db: Session, offer_id: int, farmer_id: int, reason: Optional[str] = None
    ) -> Optional[Any]:
        """Farmer declines a buyer offer."""
        try:
            offer = db.scalar(
                select(BuyerOffer).where(BuyerOffer.id == offer_id).with_for_update()
            )
            if offer is None:
                return None
            lot = db.scalar(
                select(FarmerLot)
                .where(FarmerLot.id == offer.lot_id, FarmerLot.farmer_id == farmer_id)
                .with_for_update()
            )
            if lot is None:
                return None
            if offer.status != OfferStatus.ACTIVE:
                raise TradeWorkflowError("Only active buyer offers can be rejected.")
            offer.status = OfferStatus.WITHDRAWN
            rejection_note = f"[DECLINED BY FARMER]: {reason}" if reason else "[DECLINED BY FARMER]"
            if offer.terms_and_notes:
                offer.terms_and_notes = f"{offer.terms_and_notes} | {rejection_note}"[:500]
            else:
                offer.terms_and_notes = rejection_note[:500]
            db.flush()
            db.refresh(offer)
            row = db.execute(self._offer_query().where(BuyerOffer.id == offer.id)).one()
            response = self._response_data(offer, row[1], row[2])
            db.commit()
            return response
        except Exception:
            db.rollback()
            raise


class DefaultSellingRequestRepository:
    def create_request(self, db: Session, farmer_id: int, farmer_name: str, buyer_id: int, buyer_name: str, lot: Any, req_in: SellingRequestCreate) -> Any:
        try:
            buyer = db.scalar(
                select(User).where(User.id == buyer_id, User.role == UserRole.BUYER)
            )
            if buyer is None:
                raise BuyerNotFoundError("Buyer not found.")
            farmer = db.get(User, farmer_id)
            locked_lot = db.scalar(
                select(FarmerLot)
                .where(FarmerLot.id == req_in.lot_id, FarmerLot.farmer_id == farmer_id)
                .with_for_update()
            )
            if farmer is None or locked_lot is None:
                raise TradeWorkflowError("Lot not found in your inventory.")
            if locked_lot.status != LotStatus.AVAILABLE:
                raise TradeWorkflowError("Cannot initiate request on an unavailable, committed, or sold lot.")
            _validate_trade_units(req_in.price_unit, req_in.quantity_unit, locked_lot.unit)
            quantity = Decimal(str(req_in.quantity))
            if quantity > locked_lot.quantity:
                raise TradeWorkflowError("Requested quantity exceeds available lot stock.")

            price = Decimal(str(req_in.proposed_price))
            transport = Decimal(str(req_in.estimated_transport_cost or 0)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            other = Decimal(str(req_in.estimated_other_charges or 0)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            gross = (price * quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            net = gross - transport - other
            request = SellingRequest(
                request_code=f"REQ-{datetime.now(timezone.utc):%Y%m%d}-{uuid4().hex[:12].upper()}",
                farmer_id=farmer_id,
                buyer_id=buyer_id,
                lot_id=locked_lot.id,
                quantity=quantity,
                quantity_unit=req_in.quantity_unit,
                proposed_price=price,
                price_unit=req_in.price_unit,
                estimated_gross_amount=gross,
                estimated_transport_cost=transport,
                estimated_other_charges=other,
                estimated_net_realization=net,
                status=SellingRequestStatus.PENDING,
                message=req_in.message,
            )
            db.add(request)
            db.flush()
            row = db.execute(_selling_request_query().where(SellingRequest.id == request.id)).one()
            response = _selling_request_response(row)
            db.commit()
            return response
        except Exception:
            db.rollback()
            raise

    def get_request_by_id(
        self,
        db: Session,
        request_id: int,
        farmer_id: Optional[int] = None,
        buyer_id: Optional[int] = None,
    ) -> Optional[Any]:
        try:
            query = _selling_request_query().where(SellingRequest.id == request_id)
            if farmer_id is not None:
                query = query.where(SellingRequest.farmer_id == farmer_id)
            if buyer_id is not None:
                query = query.where(SellingRequest.buyer_id == buyer_id)
            row = db.execute(query).one_or_none()
            return _selling_request_response(row) if row is not None else None
        except Exception:
            db.rollback()
            raise

    def list_farmer_requests(self, db: Session, farmer_id: int, skip: int = 0, limit: int = 50) -> Tuple[List[Any], int]:
        return self._list_requests(db, SellingRequest.farmer_id == farmer_id, skip, limit)

    def list_buyer_requests(self, db: Session, buyer_id: int, skip: int = 0, limit: int = 50) -> Tuple[List[Any], int]:
        return self._list_requests(db, SellingRequest.buyer_id == buyer_id, skip, limit)

    def _list_requests(self, db: Session, filter_clause: Any, skip: int, limit: int) -> Tuple[List[Any], int]:
        try:
            total = db.scalar(select(func.count(SellingRequest.id)).where(filter_clause)) or 0
            rows = db.execute(
                _selling_request_query()
                .where(filter_clause)
                .order_by(desc(SellingRequest.created_at), desc(SellingRequest.id))
                .offset(skip)
                .limit(limit)
            ).all()
            return [_selling_request_response(row) for row in rows], total
        except Exception:
            db.rollback()
            raise

    def execute_action(self, db: Session, request_id: int, actor_id: int, actor_role: str, action_in: SellingRequestActionRequest) -> Any:
        try:
            request = db.scalar(
                select(SellingRequest)
                .where(SellingRequest.id == request_id)
                .with_for_update()
            )
            if request is None:
                raise TradeWorkflowError("Selling request not found.")
            role = actor_role.upper()
            if (role == UserRole.FARMER.value and actor_id != request.farmer_id) or (
                role == UserRole.BUYER.value and actor_id != request.buyer_id
            ) or role not in {UserRole.FARMER.value, UserRole.BUYER.value}:
                raise TradeWorkflowError("You are not a participant in this selling request.")
            terminal = {
                SellingRequestStatus.ACCEPTED,
                SellingRequestStatus.REJECTED,
                SellingRequestStatus.CANCELLED,
                SellingRequestStatus.EXPIRED,
                SellingRequestStatus.COMPLETED,
            }
            if request.status in terminal:
                raise TradeWorkflowError(
                    f"Request is in terminal state '{request.status.value}' and cannot undergo further actions."
                )

            action = action_in.action
            lot = None
            if action in {RequestActionType.ACCEPT, RequestActionType.COUNTER}:
                lot = db.scalar(
                    select(FarmerLot)
                    .where(FarmerLot.id == request.lot_id)
                    .with_for_update()
                )
                if lot is None:
                    raise TradeWorkflowError("Underlying farmer lot no longer exists.")

            if action == RequestActionType.ACCEPT:
                if role == UserRole.FARMER.value and request.status != SellingRequestStatus.COUNTERED:
                    raise TradeWorkflowError("A farmer can accept only a buyer counteroffer.")
                if lot.status != LotStatus.AVAILABLE or request.quantity > lot.quantity:
                    raise TradeWorkflowError("Underlying farmer lot is no longer available.")
                lot.status = LotStatus.COMMITTED
                request.status = SellingRequestStatus.ACCEPTED
            elif action == RequestActionType.REJECT:
                if role == UserRole.FARMER.value and request.status != SellingRequestStatus.COUNTERED:
                    raise TradeWorkflowError("A farmer can reject only a buyer counteroffer.")
                request.status = SellingRequestStatus.REJECTED
                request.rejection_reason = action_in.reason_or_notes or "Rejected by counterparty."
            elif action == RequestActionType.COUNTER:
                if action_in.counter_price is None and action_in.counter_quantity is None:
                    raise TradeWorkflowError("A counter action requires a counter price or quantity.")
                next_quantity = (
                    Decimal(str(action_in.counter_quantity))
                    if action_in.counter_quantity is not None
                    else request.quantity
                )
                if next_quantity > lot.quantity:
                    raise TradeWorkflowError("Counter quantity exceeds available lot stock.")
                if action_in.counter_price is not None:
                    request.proposed_price = Decimal(str(action_in.counter_price))
                request.quantity = next_quantity
                request.status = SellingRequestStatus.COUNTERED
                if action_in.reason_or_notes is not None:
                    request.message = action_in.reason_or_notes
            elif action == RequestActionType.CANCEL:
                if role != UserRole.FARMER.value:
                    raise TradeWorkflowError("Only the farmer who created the request can cancel it.")
                request.status = SellingRequestStatus.CANCELLED
                request.rejection_reason = action_in.reason_or_notes or "Cancelled by creator."
            else:
                raise TradeWorkflowError("Unsupported selling request action.")

            if action == RequestActionType.COUNTER:
                request.estimated_gross_amount = (
                    request.proposed_price * request.quantity
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                request.estimated_net_realization = (
                    request.estimated_gross_amount
                    - request.estimated_transport_cost
                    - request.estimated_other_charges
                )

            db.flush()
            row = db.execute(
                _selling_request_query().where(SellingRequest.id == request_id)
            ).one()
            response = _selling_request_response(row)
            db.commit()
            return response
        except Exception:
            db.rollback()
            raise


_default_lot_repo = DefaultFarmerLotRepository()
_default_offer_repo = DefaultBuyerOfferRepository()
_default_request_repo = DefaultSellingRequestRepository()


def get_farmer_lot_repo() -> FarmerLotRepository:
    return _default_lot_repo


def get_buyer_offer_repo() -> BuyerOfferRepository:
    return _default_offer_repo


def get_selling_request_repo() -> SellingRequestRepository:
    return _default_request_repo
