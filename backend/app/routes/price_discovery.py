from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.entities import Crop, Market, MarketPrice
from app.schemas.price_discovery import (
    AutoPriceDiscoveryRequest,
    MarketOptionInput,
    PriceComparisonRequest,
    PriceComparisonResponse,
    SupportedPriceUnit,
    SupportedQuantityUnit,
)
from app.services.recommendation_service import (
    QUANTITY_TO_KG_FACTORS,
    compare_market_options,
)

router = APIRouter(prefix="/price-discovery", tags=["Price Discovery & Realization"])


@router.post(
    "/compare",
    response_model=PriceComparisonResponse,
    status_code=status.HTTP_200_OK,
    summary="Compare farmer net realization across candidate markets and buyers",
)
def compare_market_price_options(request: PriceComparisonRequest):
    """
    Core SIH26132 Price Discovery Engine.
    Evaluates candidate markets or buyer offers by computing:
      Gross sale value = quantity × offered price
      Total deductions = transport cost + market cess + other charges
      Estimated Net Realization = Gross sale value − Total deductions

    Ranks options by net earnings per unit, identifying optimal net realization
    over nominal gross price.
    """
    try:
        response = compare_market_options(request)
        return response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to compute a comparison from the supplied values.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Price discovery is temporarily unavailable.",
        )


@router.post(
    "/auto-recommend",
    response_model=PriceComparisonResponse,
    status_code=status.HTTP_200_OK,
    summary="Automatically discover and rank candidate mandis for a crop using prevailing prices",
)
def auto_discover_market_recommendations(
    request: AutoPriceDiscoveryRequest,
    db: Session = Depends(get_db),
):
    """
    Automatic Market Price Discovery for SIH26132.
    Queries prevailing mandi arrival price records for the specified crop,
    populates candidate mandi options with actual coordinates and modal prices,
    and runs the net-realization engine to identify the optimal selling destination.
    """
    crop = db.get(Crop, request.crop_id)
    if not crop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Crop with ID {request.crop_id} not found.",
        )

    try:
        # Base query joining latest market price records with markets
        query = (
            select(MarketPrice, Market)
            .join(Market, Market.id == MarketPrice.market_id)
            .where(MarketPrice.crop_id == request.crop_id)
            .order_by(MarketPrice.price_date.desc(), MarketPrice.id.desc())
        )

        rows = []
        if request.farmer_state and request.farmer_state.strip():
            state_query = query.where(
                func.lower(Market.state) == request.farmer_state.strip().lower()
            )
            rows = db.execute(state_query).all()

        # If no state-filtered rows found, fall back to nationwide mandis for this crop
        if not rows:
            rows = db.execute(query).all()

        seen_markets = set()
        candidate_options = []

        for price_record, market in rows:
            if market.id in seen_markets:
                continue
            seen_markets.add(market.id)

            # Map price unit
            price_unit_str = price_record.price_unit.strip().lower() if price_record.price_unit else ""
            if "kg" in price_unit_str:
                p_unit = SupportedPriceUnit.INR_PER_KG
            elif "tonne" in price_unit_str:
                p_unit = SupportedPriceUnit.INR_PER_TONNE
            else:
                p_unit = SupportedPriceUnit.INR_PER_QUINTAL

            market_label = f"{market.name} APMC ({market.district}, {market.state})"
            candidate_options.append(
                MarketOptionInput(
                    market_name=market_label,
                    market_id=market.id,
                    offered_price=float(price_record.modal_price),
                    price_unit=p_unit,
                    market_latitude=float(market.latitude) if market.latitude is not None else None,
                    market_longitude=float(market.longitude) if market.longitude is not None else None,
                    market_cess_rate_percent=1.05,
                    fixed_market_charges=100.0,
                    other_deductions=0.0,
                )
            )

            if len(candidate_options) >= request.max_markets:
                break

        # Graceful handling when no historical price data exists for this crop
        if not candidate_options:
            norm_factor = QUANTITY_TO_KG_FACTORS.get(request.quantity_unit, Decimal("100.0"))
            norm_qty = float(Decimal(str(request.sale_quantity)) * norm_factor)
            return PriceComparisonResponse(
                crop_name=crop.name,
                sale_quantity=request.sale_quantity,
                quantity_unit=request.quantity_unit.value,
                normalized_quantity_kg=norm_qty,
                total_options_evaluated=0,
                is_comparison_complete=False,
                ranking_is_valid=False,
                ranked_options=[],
                best_net_realization_option=None,
                general_disclaimers=[
                    f"No prevailing mandi price records currently found for {crop.name}. "
                    "You can enter manual candidate market options or import daily Agmarknet price records."
                ],
            )

        location_str = request.farmer_location or ", ".join(
            filter(None, [request.farmer_district, request.farmer_state])
        ) or "Farmer Farmgate"

        comp_request = PriceComparisonRequest(
            crop_name=crop.name,
            sale_quantity=request.sale_quantity,
            quantity_unit=request.quantity_unit,
            farmer_location=location_str,
            farmer_latitude=request.farmer_latitude,
            farmer_longitude=request.farmer_longitude,
            candidate_options=candidate_options,
        )

        return compare_market_options(comp_request)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to calculate automatic market recommendations.",
        ) from e
