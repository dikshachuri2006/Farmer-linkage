
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional

from app.schemas.price_discovery import (
    MarketOptionInput,
    MarketRealizationOption,
    PriceComparisonRequest,
    PriceComparisonResponse,
    SupportedPriceUnit,
    SupportedQuantityUnit,
)
from app.services.transport_service import (
    TransportDataSource,
    estimate_transport_cost,
)

# Standard mass conversion factors to base unit kilograms (kg)
QUANTITY_TO_KG_FACTORS = {
    SupportedQuantityUnit.KG: Decimal("1.0"),
    SupportedQuantityUnit.QUINTAL: Decimal("100.0"),
    SupportedQuantityUnit.TONNE: Decimal("1000.0"),
}

# Standard price conversion divisors to normalize to INR/kg
PRICE_UNIT_TO_KG_DIVISORS = {
    SupportedPriceUnit.INR_PER_KG: Decimal("1.0"),
    SupportedPriceUnit.INR_PER_QUINTAL: Decimal("100.0"),
    SupportedPriceUnit.INR_PER_TONNE: Decimal("1000.0"),
}


def round_inr(val: Decimal) -> Decimal:
    """Rounds currency decimal to 2 decimal places using ROUND_HALF_UP."""
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_market_realization(
    crop_name: str,
    quantity_kg: Decimal,
    original_quantity: Decimal,
    original_unit: SupportedQuantityUnit,
    option: MarketOptionInput,
    farmer_location: Optional[str] = None,
    farmer_lat: Optional[float] = None,
    farmer_lon: Optional[float] = None,
) -> MarketRealizationOption:
    """
    Computes gross sale value, itemized deductions, and estimated net realization
    for a single candidate market or buyer offer.
    """
    missing_data = []
    notes = []
    is_complete = True

    # 1. Price Validation & Normalization
    if option.offered_price is None:
        missing_data.append("Offered price per unit is missing.")
        is_complete = False
        norm_price_per_kg = None
        gross_value = None
    elif option.offered_price <= 0:
        raise ValueError(
            f"Offered price for market '{option.market_name}' must be strictly positive."
        )
    else:
        divisor = PRICE_UNIT_TO_KG_DIVISORS.get(
            option.price_unit or SupportedPriceUnit.INR_PER_QUINTAL,
            Decimal("100.0"),
        )
        norm_price_per_kg = round_inr(
            Decimal(str(option.offered_price)) / divisor
        )
        gross_value = round_inr(quantity_kg * norm_price_per_kg)

    # 2. Transport Cost Calculation
    transport_cost_dec: Optional[Decimal] = None
    transport_source = TransportDataSource.UNAVAILABLE.value

    try:
        transport_est = estimate_transport_cost(
            origin=farmer_location or "Farmer Farmgate",
            destination=option.market_name,
            quantity_kg=float(quantity_kg),
            origin_lat=farmer_lat,
            origin_lon=farmer_lon,
            dest_lat=option.market_latitude,
            dest_lon=option.market_longitude,
            supplied_distance_km=option.distance_km,
            supplied_rate_per_km_per_kg=option.transport_rate_per_km_per_kg,
            supplied_fixed_cost=option.supplied_transport_cost,
        )
        transport_source = transport_est.data_source.value

        if transport_est.total_transport_cost is not None:
            transport_cost_dec = Decimal(
                str(transport_est.total_transport_cost)
            )
            notes.append(transport_est.assumptions_and_notes)
        else:
            missing_data.append(
                "Transport cost unavailable (missing distance and rate)."
            )
            is_complete = False

    except Exception:
        missing_data.append(
            "Transport estimate unavailable due to an internal error."
        )
        is_complete = False

    # 3. Market Fees & Deductions
    cess_charge_dec = Decimal("0.00")

    if gross_value is not None and option.market_cess_rate_percent is not None:
        cess_rate = (
            Decimal(str(option.market_cess_rate_percent))
            / Decimal("100.0")
        )
        cess_charge_dec = round_inr(gross_value * cess_rate)

    fixed_charges_dec = (
        Decimal(str(option.fixed_market_charges))
        if option.fixed_market_charges is not None
        else Decimal("0.00")
    )

    other_deductions_dec = (
        Decimal(str(option.other_deductions))
        if option.other_deductions is not None
        else Decimal("0.00")
    )

    # Combined fees are used only for the total-deductions calculation.
    other_charges_total = round_inr(
        cess_charge_dec + fixed_charges_dec + other_deductions_dec
    )

    # 4. Total Deductions & Net Realization
    if not is_complete or gross_value is None or transport_cost_dec is None:
        return MarketRealizationOption(
            market_name=option.market_name,
            market_id=option.market_id,
            source_price=option.offered_price,
            source_price_unit=(
                option.price_unit.value if option.price_unit else None
            ),
            normalized_price_per_kg=(
                float(norm_price_per_kg)
                if norm_price_per_kg is not None
                else None
            ),
            gross_sale_value=(
                float(gross_value) if gross_value is not None else None
            ),
            transport_cost=(
                float(transport_cost_dec)
                if transport_cost_dec is not None
                else None
            ),
            transport_data_source=transport_source,
            market_cess_charges=float(cess_charge_dec),
            fixed_market_charges=float(fixed_charges_dec),
            other_charges=float(other_deductions_dec),
            total_deductions=None,
            estimated_net_realization=None,
            estimated_net_per_original_unit=None,
            estimated_net_per_kg=None,
            is_complete=False,
            missing_data=missing_data,
            notes="Incomplete comparison: " + " ".join(notes),
        )

    total_deductions_dec = round_inr(
        transport_cost_dec + other_charges_total
    )
    net_realization_dec = round_inr(gross_value - total_deductions_dec)
    net_per_kg_dec = round_inr(net_realization_dec / quantity_kg)
    unit_factor = QUANTITY_TO_KG_FACTORS[original_unit]
    net_per_original_unit_dec = round_inr(net_per_kg_dec * unit_factor)

    return MarketRealizationOption(
        market_name=option.market_name,
        market_id=option.market_id,
        source_price=option.offered_price,
        source_price_unit=(
            option.price_unit.value if option.price_unit else None
        ),
        normalized_price_per_kg=float(norm_price_per_kg),
        gross_sale_value=float(gross_value),
        transport_cost=float(transport_cost_dec),
        transport_data_source=transport_source,
        market_cess_charges=float(cess_charge_dec),
        fixed_market_charges=float(fixed_charges_dec),
        other_charges=float(other_deductions_dec),
        total_deductions=float(total_deductions_dec),
        estimated_net_realization=float(net_realization_dec),
        estimated_net_per_original_unit=float(net_per_original_unit_dec),
        estimated_net_per_kg=float(net_per_kg_dec),
        is_complete=True,
        missing_data=[],
        notes="Complete net-realization calculation. " + " ".join(notes),
    )


def compare_market_options(
    request: PriceComparisonRequest,
) -> PriceComparisonResponse:
    """
    Compares candidate markets and buyers for farmer price discovery.
    Calculates net realization after transport and market fees.
    Ranks options strictly by Net Realization rather than gross nominal price.
    """
    if request.sale_quantity <= 0:
        raise ValueError("sale_quantity must be strictly greater than zero.")

    # Convert quantity to base kg
    factor = QUANTITY_TO_KG_FACTORS[request.quantity_unit]
    quantity_kg = Decimal(str(request.sale_quantity)) * factor

    evaluated_options: List[MarketRealizationOption] = []

    for opt in request.candidate_options:
        res = calculate_market_realization(
            crop_name=request.crop_name,
            quantity_kg=quantity_kg,
            original_quantity=Decimal(str(request.sale_quantity)),
            original_unit=request.quantity_unit,
            option=opt,
            farmer_location=request.farmer_location,
            farmer_lat=request.farmer_latitude,
            farmer_lon=request.farmer_longitude,
        )
        evaluated_options.append(res)

    # Check if all options are complete
    all_complete = all(o.is_complete for o in evaluated_options)

    # Sort options: complete options ranked by net realization descending
    complete_options = [o for o in evaluated_options if o.is_complete]
    incomplete_options = [o for o in evaluated_options if not o.is_complete]

    complete_options.sort(
        key=lambda x: (x.estimated_net_realization or 0.0),
        reverse=True,
    )

    ranked_list: List[MarketRealizationOption] = []
    current_rank = 1

    for opt in complete_options:
        opt.rank = current_rank
        current_rank += 1
        ranked_list.append(opt)

    for opt in incomplete_options:
        opt.rank = None
        ranked_list.append(opt)

    best_option = complete_options[0] if complete_options else None

    disclaimers = [
        "Net realization is calculated as: Gross Value - Transport Cost - Mandi Charges - Other Deductions.",
        "Calculations provide decision-support estimates and do NOT constitute a guaranteed trade quote or price insurance.",
        "Transport rates are heuristic estimates unless explicitly supported by quotes or verified routing.",
    ]

    return PriceComparisonResponse(
        crop_name=request.crop_name,
        sale_quantity=request.sale_quantity,
        quantity_unit=request.quantity_unit.value,
        normalized_quantity_kg=float(round_inr(quantity_kg)),
        total_options_evaluated=len(evaluated_options),
        is_comparison_complete=all_complete,
        ranking_is_valid=(len(complete_options) > 0),
        ranked_options=ranked_list,
        best_net_realization_option=best_option,
        general_disclaimers=disclaimers,
    )
