"""Rigorous unit and edge-case validation for the SIH26132 Price Discovery Engine.

Validates:
1. Hand-calculated expected math (Gross, Itemized Deductions, Net Realization, Net per Unit).
2. Mass and price unit conversions (Quintal <-> kg <-> Tonne).
3. Zero, negative, and invalid quantities and prices rejected via Pydantic & validation errors.
4. Missing cost data transparency (incomplete options excluded from ranking).
5. Net realization vs nominal price optimization.
"""

from decimal import Decimal
import pydantic
import pytest

from app.schemas.price_discovery import (
    MarketOptionInput,
    PriceComparisonRequest,
    SupportedPriceUnit,
    SupportedQuantityUnit,
)
from app.services.recommendation_service import (
    calculate_market_realization,
    compare_market_options,
)


def test_hand_calculated_net_realization_with_fixed_transport():
    """Validates formula with hand-calculated expected values using supplied transport cost.

    Input:
      Quantity: 50 quintals = 5,000 kg
      Offered price: ₹2,200 per quintal = ₹22.00 / kg
      Gross Sale Value = 5,000 kg * ₹22.00/kg = ₹110,000.00
      Supplied Transport Cost = ₹420.00
      Cess: 1.05% of Gross = ₹1,155.00
      Fixed charges: ₹50.00
      Total deductions = 420.00 + 1,155.00 + 50.00 = ₹1,625.00
      Expected Net Realization = 110,000.00 - 1,625.00 = ₹108,375.00
      Expected Net per kg = 108,375.00 / 5,000 = ₹21.68 / kg
      Expected Net per quintal = 21.68 * 100 = ₹2,168.00 / quintal
    """
    option = MarketOptionInput(
        market_name="Lasalgaon Mandi",
        market_id=101,
        offered_price=2200.0,
        price_unit=SupportedPriceUnit.INR_PER_QUINTAL,
        supplied_transport_cost=420.0,
        market_cess_rate_percent=1.05,
        fixed_market_charges=50.0,
    )

    req = PriceComparisonRequest(
        crop_name="Onion",
        sale_quantity=50.0,
        quantity_unit=SupportedQuantityUnit.QUINTAL,
        farmer_location="Nashik Farmgate",
        candidate_options=[option],
    )

    res = compare_market_options(req)

    assert len(res.ranked_options) == 1
    opt = res.ranked_options[0]

    assert opt.is_complete is True
    assert opt.normalized_price_per_kg == 22.00
    assert opt.gross_sale_value == 110000.00
    assert opt.transport_cost == 420.00
    assert opt.market_cess_charges == 1155.00
    assert opt.fixed_market_charges == 50.00
    assert opt.total_deductions == 1625.00
    assert opt.estimated_net_realization == 108375.00
    assert opt.estimated_net_per_kg == 21.68
    assert opt.estimated_net_per_original_unit == 2168.00


def test_hand_calculated_net_realization_with_weight_distance_rate():
    """Validates formula with default ton-km weight-distance transport model.

    Input:
      Quantity: 50 quintals = 5,000 kg
      Offered price: ₹2,200 per quintal = ₹22.00 / kg
      Gross Sale Value = ₹110,000.00
      Distance: 35 km
      Transport: 5,000 kg * 35 km * ₹0.05/km/kg + ₹150 base = ₹8,900.00
      Cess: 1.05% of Gross = ₹1,155.00
      Fixed charges: ₹50.00
      Total deductions = 8,900.00 + 1,155.00 + 50.00 = ₹10,105.00
      Expected Net Realization = 110,000.00 - 10,105.00 = ₹99,895.00
      Expected Net per kg = 99,895.00 / 5,000 = ₹19.98 / kg
      Expected Net per quintal = 19.98 * 100 = ₹1,998.00 / quintal
    """
    option = MarketOptionInput(
        market_name="Lasalgaon Mandi",
        market_id=101,
        offered_price=2200.0,
        price_unit=SupportedPriceUnit.INR_PER_QUINTAL,
        distance_km=35.0,
        market_cess_rate_percent=1.05,
        fixed_market_charges=50.0,
    )

    req = PriceComparisonRequest(
        crop_name="Onion",
        sale_quantity=50.0,
        quantity_unit=SupportedQuantityUnit.QUINTAL,
        farmer_location="Nashik Farmgate",
        candidate_options=[option],
    )

    res = compare_market_options(req)
    opt = res.ranked_options[0]

    assert opt.gross_sale_value == 110000.00
    assert opt.transport_cost == 8900.00
    assert opt.total_deductions == 10105.00
    assert opt.estimated_net_realization == 99895.00
    assert opt.estimated_net_per_kg == 19.98
    assert opt.estimated_net_per_original_unit == 1998.00


def test_unit_conversion_kg_vs_quintal_equivalence():
    """50 quintals @ ₹2,200/quintal must yield identical gross and net realization
    as 5,000 kg @ ₹22/kg."""
    opt_quintal = MarketOptionInput(
        market_name="Mandi A",
        offered_price=2200.0,
        price_unit=SupportedPriceUnit.INR_PER_QUINTAL,
        supplied_transport_cost=500.0,
        market_cess_rate_percent=1.0,
    )
    req_quintal = PriceComparisonRequest(
        crop_name="Tomato",
        sale_quantity=50.0,
        quantity_unit=SupportedQuantityUnit.QUINTAL,
        candidate_options=[opt_quintal],
    )

    opt_kg = MarketOptionInput(
        market_name="Mandi A",
        offered_price=22.0,
        price_unit=SupportedPriceUnit.INR_PER_KG,
        supplied_transport_cost=500.0,
        market_cess_rate_percent=1.0,
    )
    req_kg = PriceComparisonRequest(
        crop_name="Tomato",
        sale_quantity=5000.0,
        quantity_unit=SupportedQuantityUnit.KG,
        candidate_options=[opt_kg],
    )

    res_quintal = compare_market_options(req_quintal).ranked_options[0]
    res_kg = compare_market_options(req_kg).ranked_options[0]

    assert res_quintal.gross_sale_value == res_kg.gross_sale_value
    assert res_quintal.total_deductions == res_kg.total_deductions
    assert res_quintal.estimated_net_realization == res_kg.estimated_net_realization
    assert res_quintal.estimated_net_per_kg == res_kg.estimated_net_per_kg


def test_net_realization_recommends_closer_mandi_over_nominal_gross():
    """Market A has higher nominal price (₹2,500 vs ₹2,300) but is 400 km away.
    Market B has lower nominal price (₹2,300) but is 20 km away.
    The engine must recommend Market B because its net realization is higher."""
    opt_distant = MarketOptionInput(
        market_name="Distant High-Price Mandi",
        offered_price=2500.0,
        price_unit=SupportedPriceUnit.INR_PER_QUINTAL,
        distance_km=400.0,
        market_cess_rate_percent=1.5,
    )

    opt_local = MarketOptionInput(
        market_name="Nearby Moderate-Price Mandi",
        offered_price=2300.0,
        price_unit=SupportedPriceUnit.INR_PER_QUINTAL,
        distance_km=20.0,
        market_cess_rate_percent=1.5,
    )

    req = PriceComparisonRequest(
        crop_name="Wheat",
        sale_quantity=30.0, # 3,000 kg
        quantity_unit=SupportedQuantityUnit.QUINTAL,
        candidate_options=[opt_distant, opt_local],
    )

    res = compare_market_options(req)

    # Best recommendation MUST be the Nearby Mandi despite lower nominal rate
    assert res.best_net_realization_option is not None
    assert res.best_net_realization_option.market_name == "Nearby Moderate-Price Mandi"
    assert res.ranked_options[0].rank == 1
    assert res.ranked_options[0].market_name == "Nearby Moderate-Price Mandi"
    assert res.ranked_options[1].rank == 2
    assert res.ranked_options[1].market_name == "Distant High-Price Mandi"


def test_zero_and_negative_quantity_raises_validation_error():
    """Pydantic schema validation rejects sale_quantity <= 0."""
    opt = MarketOptionInput(market_name="Mandi A", offered_price=2000.0)

    with pytest.raises(pydantic.ValidationError):
        PriceComparisonRequest(
            crop_name="Onion",
            sale_quantity=0.0,
            quantity_unit=SupportedQuantityUnit.QUINTAL,
            candidate_options=[opt],
        )

    with pytest.raises(pydantic.ValidationError):
        PriceComparisonRequest(
            crop_name="Onion",
            sale_quantity=-5.0,
            quantity_unit=SupportedQuantityUnit.QUINTAL,
            candidate_options=[opt],
        )


def test_negative_price_raises_validation_error():
    """Pydantic schema validation rejects negative offered prices."""
    with pytest.raises(pydantic.ValidationError):
        MarketOptionInput(market_name="Mandi Neg", offered_price=-100.0)


def test_missing_transport_data_handled_transparently():
    """When transport data is unavailable, option is marked incomplete,
    net realization is None, and it is excluded from rank ordering."""
    opt_incomplete = MarketOptionInput(
        market_name="Incomplete Mandi",
        offered_price=2400.0,
        price_unit=SupportedPriceUnit.INR_PER_QUINTAL,
        distance_km=None,
        transport_cost_per_km=None,
    )
    opt_complete = MarketOptionInput(
        market_name="Complete Mandi",
        offered_price=2200.0,
        price_unit=SupportedPriceUnit.INR_PER_QUINTAL,
        supplied_transport_cost=300.0,
    )

    req = PriceComparisonRequest(
        crop_name="Tomato",
        sale_quantity=20.0,
        quantity_unit=SupportedQuantityUnit.QUINTAL,
        candidate_options=[opt_incomplete, opt_complete],
    )

    res = compare_market_options(req)

    assert res.is_comparison_complete is False
    assert res.best_net_realization_option.market_name == "Complete Mandi"

    complete_res = next(o for o in res.ranked_options if o.market_name == "Complete Mandi")
    incomplete_res = next(o for o in res.ranked_options if o.market_name == "Incomplete Mandi")

    assert complete_res.is_complete is True
    assert complete_res.rank == 1

    assert incomplete_res.is_complete is False
    assert incomplete_res.rank is None
    assert incomplete_res.estimated_net_realization is None
    assert len(incomplete_res.missing_data) > 0
