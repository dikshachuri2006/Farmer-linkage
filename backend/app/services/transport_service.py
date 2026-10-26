import math
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class TransportDataSource(str, Enum):
    USER_SUPPLIED = "USER_SUPPLIED"
    ESTIMATED_HAVERSINE = "ESTIMATED_HAVERSINE"
    ESTIMATED_DEFAULT_RATE = "ESTIMATED_DEFAULT_RATE"
    UNAVAILABLE = "UNAVAILABLE"


class TransportCostEstimate(BaseModel):
    origin: str
    destination: str
    distance_km: Optional[float] = None
    transport_rate: Optional[float] = None
    rate_unit: Optional[str] = None
    base_charge: Optional[float] = None
    total_transport_cost: Optional[float] = None
    data_source: TransportDataSource
    is_confirmed: bool = False
    assumptions_and_notes: str


def calculate_haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float, winding_factor: float = 1.25
) -> float:
    """
    Computes approximate road distance in kilometers using the Haversine formula
    with a standard road tortuosity / winding multiplier (default 1.25).
    NOTE: This is a geometric estimate, NOT an actual navigation routing engine.
    """
    R = 6371.0  # Earth's radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    straight_distance = R * c
    estimated_road_distance = straight_distance * winding_factor
    return round(estimated_road_distance, 2)


def estimate_transport_cost(
    origin: str,
    destination: str,
    quantity_kg: float,
    origin_lat: Optional[float] = None,
    origin_lon: Optional[float] = None,
    dest_lat: Optional[float] = None,
    dest_lon: Optional[float] = None,
    supplied_distance_km: Optional[float] = None,
    supplied_rate_per_km_per_kg: Optional[float] = None,
    supplied_fixed_cost: Optional[float] = None,
    base_handling_charge: float = 150.0,
) -> TransportCostEstimate:
    """
    Modular transport-cost calculation interface.
    Explicitly tags whether costs are user-supplied, estimated, or unavailable.
    Does NOT fabricate actual road distances or claim external routing confirmation.
    """
    if quantity_kg <= 0:
        raise ValueError("quantity_kg must be strictly greater than 0.")

    # Case 1: User explicitly provided fixed transport cost
    if supplied_fixed_cost is not None:
        if supplied_fixed_cost < 0:
            raise ValueError("supplied_fixed_cost cannot be negative.")
        cost_dec = Decimal(str(supplied_fixed_cost)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return TransportCostEstimate(
            origin=origin,
            destination=destination,
            distance_km=supplied_distance_km,
            total_transport_cost=float(cost_dec),
            data_source=TransportDataSource.USER_SUPPLIED,
            is_confirmed=True,
            assumptions_and_notes="Transport cost explicitly provided by user/quote. Confirmed value.",
        )

    # Determine distance
    distance_km: Optional[float] = None
    source = TransportDataSource.UNAVAILABLE
    notes = []

    if supplied_distance_km is not None:
        if supplied_distance_km < 0:
            raise ValueError("supplied_distance_km cannot be negative.")
        distance_km = round(supplied_distance_km, 2)
        source = TransportDataSource.USER_SUPPLIED
        notes.append(f"Distance of {distance_km} km supplied by user.")
    elif (
        origin_lat is not None
        and origin_lon is not None
        and dest_lat is not None
        and dest_lon is not None
    ):
        distance_km = calculate_haversine_distance(
            origin_lat, origin_lon, dest_lat, dest_lon
        )
        source = TransportDataSource.ESTIMATED_HAVERSINE
        notes.append(
            f"Distance ({distance_km} km) estimated via geometric coordinates with 1.25x tortuosity factor. Not actual road route."
        )

    if distance_km is None:
        return TransportCostEstimate(
            origin=origin,
            destination=destination,
            distance_km=None,
            total_transport_cost=None,
            data_source=TransportDataSource.UNAVAILABLE,
            is_confirmed=False,
            assumptions_and_notes="Distance could not be calculated. Missing GPS coordinates and supplied distance.",
        )

    # Determine rate
    rate = supplied_rate_per_km_per_kg
    if rate is None:
        rate = 0.05  # Standard heuristic ₹0.05 per km per kg
        source = TransportDataSource.ESTIMATED_DEFAULT_RATE
        notes.append(f"Using default rate of ₹{rate}/km/kg + base fee ₹{base_handling_charge}.")
    else:
        if rate < 0:
            raise ValueError("supplied_rate_per_km_per_kg cannot be negative.")
        notes.append(f"Using supplied rate of ₹{rate}/km/kg.")

    # Calculate total: base_charge + (distance_km * quantity_kg * rate)
    cost = Decimal(str(base_handling_charge)) + (
        Decimal(str(distance_km)) * Decimal(str(quantity_kg)) * Decimal(str(rate))
    )
    cost_rounded = cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return TransportCostEstimate(
        origin=origin,
        destination=destination,
        distance_km=distance_km,
        transport_rate=rate,
        rate_unit="INR/km/kg",
        base_charge=base_handling_charge,
        total_transport_cost=float(cost_rounded),
        data_source=source,
        is_confirmed=(source == TransportDataSource.USER_SUPPLIED),
        assumptions_and_notes=" ".join(notes),
    )
