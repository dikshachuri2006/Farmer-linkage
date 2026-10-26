from decimal import Decimal

from fastapi.testclient import TestClient
import pytest

from app.main import app
import app.routes.price_discovery as price_discovery_route
import app.services.recommendation_service as recommendation_service

from app.schemas.price_discovery import (
    MarketOptionInput,
    PriceComparisonRequest,
    SupportedPriceUnit,
    SupportedQuantityUnit,
)

from app.services.recommendation_service import (
    calculate_market_realization,
    compare_market_options,
    round_inr,
)

from app.services.transport_service import (
    TransportDataSource,
    calculate_haversine_distance,
    estimate_transport_cost,
)


client = TestClient(app)


# ==============================================================================
# 1. Core Net-Realization Logic & Decimal Arithmetic Tests
# ==============================================================================

def test_decimal_rounding_rule():
    """Verify ROUND_HALF_UP rounding behavior for currency calculations."""
    assert round_inr(Decimal("100.054")) == Decimal("100.05")
    assert round_inr(Decimal("100.055")) == Decimal("100.06")
    assert round_inr(Decimal("100.000")) == Decimal("100.00")


def test_core_net_realization_calculation():
    """
    Test direct calculation:
    Quantity: 1000 kg (10 quintals)
    Price: ₹30/kg -> Gross: ₹30,000
    Transport: ₹2,000 (fixed)
    Cess: 1% (₹300)
    Fixed fee: ₹200
    Other deductions: ₹0
    Total deductions: ₹2,500
    Net Realization: ₹27,500
    Net per kg: ₹27.50
    """
    opt = MarketOptionInput(
        market_name="Lasalgaon APMC",
        offered_price=30.0,
        price_unit=SupportedPriceUnit.INR_PER_KG,
        supplied_transport_cost=2000.0,
        market_cess_rate_percent=1.0,
        fixed_market_charges=200.0,
    )

    result = calculate_market_realization(
        crop_name="Onion",
        quantity_kg=Decimal("1000.0"),
        original_quantity=Decimal("10.0"),
        original_unit=SupportedQuantityUnit.QUINTAL,
        option=opt,
    )

    assert result.is_complete is True
    assert result.gross_sale_value == 30000.0
    assert result.transport_cost == 2000.0
    assert result.market_cess_charges == 300.0
    assert result.fixed_market_charges == 200.0
    assert result.other_charges == 0.0
    assert result.total_deductions == 2500.0
    assert result.estimated_net_realization == 27500.0
    assert result.estimated_net_per_kg == 27.50
    assert result.estimated_net_per_original_unit == 2750.0


def test_sih_specification_comparison_example():
    """
    Directly tests the prompt's core example:
    Farmer sells 1000 kg of Onion.
    Buyer A: ₹30/kg, Transport: ₹4/kg (₹4000 total) -> Net: ₹26/kg
    Buyer B: ₹28/kg, Transport: ₹1/kg (₹1000 total) -> Net: ₹27/kg
    Buyer B MUST be ranked #1 despite Buyer A having a higher gross nominal price!
    """
    req = PriceComparisonRequest(
        crop_name="Onion",
        sale_quantity=1000.0,
        quantity_unit=SupportedQuantityUnit.KG,
        candidate_options=[
            MarketOptionInput(
                market_name="Buyer A (Distant Big Mandi)",
                offered_price=30.0,
                price_unit=SupportedPriceUnit.INR_PER_KG,
                supplied_transport_cost=4000.0,
            ),
            MarketOptionInput(
                market_name="Buyer B (Nearby Local Mandi)",
                offered_price=28.0,
                price_unit=SupportedPriceUnit.INR_PER_KG,
                supplied_transport_cost=1000.0,
            ),
        ],
    )

    response = compare_market_options(req)

    assert response.is_comparison_complete is True
    assert response.ranking_is_valid is True
    assert len(response.ranked_options) == 2

    # Best option MUST be Buyer B
    assert response.best_net_realization_option is not None
    assert (
        response.best_net_realization_option.market_name
        == "Buyer B (Nearby Local Mandi)"
    )
    assert response.best_net_realization_option.rank == 1
    assert response.best_net_realization_option.estimated_net_per_kg == 27.00
    assert (
        response.best_net_realization_option.estimated_net_realization
        == 27000.0
    )

    # Buyer A must be rank 2
    rank_2 = response.ranked_options[1]
    assert rank_2.market_name == "Buyer A (Distant Big Mandi)"
    assert rank_2.rank == 2
    assert rank_2.estimated_net_per_kg == 26.00
    assert rank_2.estimated_net_realization == 26000.0


# ==============================================================================
# 2. Unit Conversion Tests (Quintal, Tonne, KG)
# ==============================================================================

def test_unit_conversions_and_equivalences():
    """
    50 Quintals = 5000 kg.
    Market 1: Quotes ₹3000/quintal (₹30/kg)
    Market 2: Quotes ₹30,000/tonne (₹30/kg)
    Both must yield identical gross sale values of ₹150,000.
    """
    req = PriceComparisonRequest(
        crop_name="Wheat",
        sale_quantity=50.0,
        quantity_unit=SupportedQuantityUnit.QUINTAL,
        candidate_options=[
            MarketOptionInput(
                market_name="Mandi 1",
                offered_price=3000.0,
                price_unit=SupportedPriceUnit.INR_PER_QUINTAL,
                supplied_transport_cost=5000.0,
            ),
            MarketOptionInput(
                market_name="Mandi 2",
                offered_price=30000.0,
                price_unit=SupportedPriceUnit.INR_PER_TONNE,
                supplied_transport_cost=5000.0,
            ),
        ],
    )

    res = compare_market_options(req)
    assert res.normalized_quantity_kg == 5000.0
    assert res.ranked_options[0].gross_sale_value == 150000.0
    assert res.ranked_options[1].gross_sale_value == 150000.0
    assert res.ranked_options[0].estimated_net_realization == 145000.0
    assert res.ranked_options[1].estimated_net_realization == 145000.0


# ==============================================================================
# 3. Transport Estimation Interface Tests
# ==============================================================================

def test_haversine_distance_calculation():
    # Distance between Nashik (20.00, 73.78) and Lasalgaon (20.14, 74.22)
    # is approx 50-60 km with tortuosity
    dist = calculate_haversine_distance(20.00, 73.78, 20.14, 74.22)
    assert 40.0 < dist < 80.0


def test_transport_cost_data_source_tagging():
    # User supplied
    est1 = estimate_transport_cost(
        "A", "B", 1000.0, supplied_fixed_cost=1500.0
    )
    assert est1.data_source == TransportDataSource.USER_SUPPLIED
    assert est1.total_transport_cost == 1500.0
    assert est1.is_confirmed is True

    # Estimated via coordinates
    est2 = estimate_transport_cost(
        "A",
        "B",
        1000.0,
        origin_lat=20.0,
        origin_lon=73.0,
        dest_lat=20.5,
        dest_lon=73.5,
    )
    assert est2.data_source == TransportDataSource.ESTIMATED_DEFAULT_RATE
    assert est2.total_transport_cost is not None
    assert est2.is_confirmed is False

    # Unavailable (no coordinates and no supplied distance)
    est3 = estimate_transport_cost("A", "B", 1000.0)
    assert est3.data_source == TransportDataSource.UNAVAILABLE
    assert est3.total_transport_cost is None


# ==============================================================================
# 4. Incomplete Comparisons & Missing Data Tests
# ==============================================================================

def test_incomplete_comparison_when_transport_unavailable():
    """
    If an option has missing distance and no quote, it must be flagged incomplete
    and must not produce a fabricated net realization.
    """
    req = PriceComparisonRequest(
        crop_name="Tomato",
        sale_quantity=20.0,
        quantity_unit=SupportedQuantityUnit.QUINTAL,
        candidate_options=[
            MarketOptionInput(
                market_name="Mandi Without Transport Info",
                offered_price=1500.0,
                price_unit=SupportedPriceUnit.INR_PER_QUINTAL,
                # No distance, no coordinates, no transport cost
            ),
        ],
    )

    res = compare_market_options(req)
    assert res.is_comparison_complete is False
    assert res.ranking_is_valid is False
    opt = res.ranked_options[0]
    assert opt.is_complete is False
    assert opt.total_deductions is None
    assert opt.estimated_net_realization is None
    assert opt.rank is None
    assert any("Transport cost unavailable" in m for m in opt.missing_data)


# ==============================================================================
# 5. Invalid & Negative Input Validation Tests
# ==============================================================================

def test_zero_or_negative_quantity_raises_error():
    # Negative quantity in Pydantic schema -> 422 Unprocessable
    res = client.post(
        "/api/price-discovery/compare",
        json={
            "crop_name": "Onion",
            "sale_quantity": -5.0,
            "quantity_unit": "kg",
            "candidate_options": [
                {"market_name": "Market 1", "offered_price": 20.0}
            ],
        },
    )
    assert res.status_code == 422

    # Zero quantity in Pydantic schema -> 422 Unprocessable
    res2 = client.post(
        "/api/price-discovery/compare",
        json={
            "crop_name": "Onion",
            "sale_quantity": 0.0,
            "quantity_unit": "kg",
            "candidate_options": [
                {"market_name": "Market 1", "offered_price": 20.0}
            ],
        },
    )
    assert res2.status_code == 422


def test_negative_price_input_raises_error():
    # Negative offered price in Pydantic schema -> 422 Unprocessable
    res = client.post(
        "/api/price-discovery/compare",
        json={
            "crop_name": "Onion",
            "sale_quantity": 100.0,
            "quantity_unit": "kg",
            "candidate_options": [
                {"market_name": "Market 1", "offered_price": -20.0}
            ],
        },
    )
    assert res.status_code == 422


# ==============================================================================
# 6. Full API Endpoint Verification Test
# ==============================================================================

def test_api_price_discovery_compare_endpoint():
    payload = {
        "crop_name": "Soybean",
        "sale_quantity": 25.0,
        "quantity_unit": "quintal",
        "farmer_location": "Pimpalgaon",
        "candidate_options": [
            {
                "market_name": "Mandi Alpha",
                "offered_price": 4500.0,
                "price_unit": "INR/quintal",
                "distance_km": 30.0,
                "supplied_transport_cost": 2500.0,
                "market_cess_rate_percent": 1.05,
            },
            {
                "market_name": "Buyer Beta",
                "offered_price": 4600.0,
                "price_unit": "INR/quintal",
                "distance_km": 80.0,
                "supplied_transport_cost": 6500.0,
                "market_cess_rate_percent": 0.0,
            },
        ],
    }

    response = client.post("/api/price-discovery/compare", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["crop_name"] == "Soybean"
    assert data["normalized_quantity_kg"] == 2500.0
    assert data["total_options_evaluated"] == 2
    assert data["is_comparison_complete"] is True
    assert data["ranking_is_valid"] is True
    assert data["best_net_realization_option"] is not None
    assert len(data["general_disclaimers"]) > 0


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (
            ValueError("sensitive validation internals"),
            400,
            "Unable to compute a comparison from the supplied values.",
        ),
        (
            RuntimeError("database host and credentials"),
            500,
            "Price discovery is temporarily unavailable.",
        ),
    ],
)
def test_price_discovery_errors_do_not_expose_internal_details(
    monkeypatch, error, expected_status, expected_detail
):
    def fail(request):
        raise error

    monkeypatch.setattr(
        price_discovery_route, "compare_market_options", fail
    )
    response = client.post(
        "/api/price-discovery/compare",
        json={
            "crop_name": "Onion",
            "sale_quantity": 1,
            "candidate_options": [
                {"market_name": "Test market", "offered_price": 1}
            ],
        },
    )
    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}
    assert "sensitive validation internals" not in response.text
    assert "database host" not in response.text


def test_transport_failure_does_not_leak_exception_text(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("private transport provider endpoint")

    monkeypatch.setattr(
        recommendation_service, "estimate_transport_cost", fail
    )
    response = client.post(
        "/api/price-discovery/compare",
        json={
            "crop_name": "Onion",
            "sale_quantity": 1,
            "candidate_options": [
                {"market_name": "Test market", "offered_price": 10}
            ],
        },
    )
    assert response.status_code == 200
    assert "private transport provider endpoint" not in response.text
    assert response.json()["ranked_options"][0]["missing_data"] == [
        "Transport estimate unavailable due to an internal error."
    ]
