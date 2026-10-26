"""Explicit, atomic CSV ingestion for externally sourced mandi price records.

This module is never invoked automatically. Callers must supply the source file,
an explicit price unit when the CSV does not include one, and a DB session.
"""

import csv
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import IO, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import Crop, Market, MarketPrice


class PriceImportError(ValueError):
    """CSV content is incomplete, ambiguous, or inconsistent."""


@dataclass(frozen=True)
class PriceImportSummary:
    rows_read: int
    rows_inserted: int
    duplicates_skipped: int


_ALIASES = {
    "commodity": "crop",
    "crop": "crop",
    "market": "market",
    "mandi": "market",
    "state": "state",
    "state_name": "state",
    "district": "district",
    "district_name": "district",
    "market_center": "market",
    "market_center_name": "market",
    "commodity_name": "crop",
    "report_date": "date",
    "arrival_date": "date",
    "price_date": "date",
    "date": "date",
    "min_price": "min_price",
    "minimum_price": "min_price",
    "min_x0020_price": "min_price",
    "max_price": "max_price",
    "maximum_price": "max_price",
    "max_x0020_price": "max_price",
    "modal_price": "modal_price",
    "modal_x0020_price": "modal_price",
    "variety": "variety",
    "grade": "grade",
    "arrival_quantity": "arrival_quantity",
    "arrivals": "arrival_quantity",
    "arrival_units": "arrival_unit",
    "price_unit": "price_unit",
    "arrival_unit": "arrival_unit",
    "source": "source",
}
_REQUIRED = {"crop", "market", "state", "district", "date", "min_price", "max_price", "modal_price"}
_PRICE_UNITS = {
    "inr/kg": "INR/kg",
    "inr/quintal": "INR/Quintal",
    "inr/tonne": "INR/tonne",
    "rs./quintal": "INR/Quintal",
}


def _header(value: str) -> str:
    return "_".join(value.strip().lower().replace("-", " ").split())


def _parse_date(value: str, row_number: int) -> date:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise PriceImportError(f"Row {row_number}: invalid date '{value}'.")


def _parse_decimal(
    value: Optional[str], column: str, row_number: int, required: bool = True,
    *, scale: Optional[int] = None, max_integral_digits: Optional[int] = None,
) -> Optional[Decimal]:
    if value is None or not value.strip():
        if required:
            raise PriceImportError(f"Row {row_number}: missing {column}.")
        return None
    try:
        result = Decimal(value.strip().replace(",", ""))
    except InvalidOperation as error:
        raise PriceImportError(f"Row {row_number}: invalid numeric {column}.") from error
    if not result.is_finite() or result < 0:
        raise PriceImportError(f"Row {row_number}: {column} must be a finite non-negative number.")
    if scale is not None:
        normalized = result.normalize()
        decimal_places = max(0, -normalized.as_tuple().exponent)
        if decimal_places > scale:
            raise PriceImportError(f"Row {row_number}: {column} has more than {scale} decimal places.")
        integral_digits = max(0, len(normalized.as_tuple().digits) + normalized.as_tuple().exponent)
        if max_integral_digits is not None and integral_digits > max_integral_digits:
            raise PriceImportError(f"Row {row_number}: {column} exceeds the supported range.")
    return result


def import_market_prices_csv(
    db: Session,
    file: IO[str] | Path | str,
    *,
    price_unit: Optional[str] = None,
    source: str,
    arrival_unit: Optional[str] = None,
    commit: bool = True,
) -> PriceImportSummary:
    """Import one CSV as an atomic unit, skipping identical existing records.

    Required columns: Commodity/Crop, Market, State, District, date,
    min_price, max_price, modal_price, and a declared price unit (in the CSV
    or argument). Variety and grade are part of the record identity, so distinct
    source series on the same market/date remain separate; conflicting records
    for an identical crop/market/date/variety/grade key are rejected.
    """
    if not source or not source.strip() or len(source.strip()) > 150:
        raise PriceImportError("A non-empty source label of at most 150 characters is required.")
    if price_unit is not None and (not price_unit.strip() or len(price_unit.strip()) > 30):
        raise PriceImportError("price_unit must be a non-empty label of at most 30 characters.")
    close_file = False
    if isinstance(file, (str, Path)):
        stream = Path(file).open("r", encoding="utf-8-sig", newline="")
        close_file = True
    else:
        stream = file
    rows_read = inserted = skipped = 0
    staged: dict[
        tuple[int, int, date, Optional[str], Optional[str]],
        tuple[Decimal, Decimal, Decimal, Optional[Decimal], str, Optional[str], str],
    ] = {}
    try:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise PriceImportError("CSV has no header row.")
        mapped: dict[str, str] = {}
        for original in reader.fieldnames:
            key = _ALIASES.get(_header(original))
            if key:
                if key in mapped:
                    raise PriceImportError(f"CSV has multiple columns for '{key}'.")
                mapped[key] = original
        missing = sorted(_REQUIRED - mapped.keys())
        if missing:
            raise PriceImportError("CSV is missing required columns: " + ", ".join(missing))

        for row_number, raw in enumerate(reader, start=2):
            rows_read += 1
            values = {key: (raw.get(column) or "").strip() for key, column in mapped.items()}
            for field in ("crop", "market", "state", "district"):
                if not values[field]:
                    raise PriceImportError(f"Row {row_number}: missing {field}.")
            crop = db.scalar(select(Crop).where(func.lower(Crop.name) == values["crop"].lower()))
            markets = db.scalars(select(Market).where(
                func.lower(Market.name) == values["market"].lower(),
                func.lower(Market.state) == values["state"].lower(),
                func.lower(Market.district) == values["district"].lower(),
            )).all()
            if crop is None:
                raise PriceImportError(f"Row {row_number}: crop '{values['crop']}' does not exist in the catalog.")
            if len(markets) != 1:
                raise PriceImportError(f"Row {row_number}: market/state/district must match exactly one catalog market.")
            record_date = _parse_date(values["date"], row_number)
            min_price = _parse_decimal(values["min_price"], "min_price", row_number, scale=2, max_integral_digits=10)
            max_price = _parse_decimal(values["max_price"], "max_price", row_number, scale=2, max_integral_digits=10)
            modal_price = _parse_decimal(values["modal_price"], "modal_price", row_number, scale=2, max_integral_digits=10)
            arrival = _parse_decimal(
                values.get("arrival_quantity"), "arrival_quantity", row_number,
                required=False, scale=3, max_integral_digits=11,
            )
            assert min_price is not None and max_price is not None and modal_price is not None
            if max_price < min_price or not min_price <= modal_price <= max_price:
                raise PriceImportError(f"Row {row_number}: modal_price must be between min_price and max_price.")
            unit = (values.get("price_unit") or price_unit or "").strip()
            if not unit:
                raise PriceImportError(f"Row {row_number}: price_unit is required in the CSV or as an argument.")
            unit = _PRICE_UNITS.get(unit.lower(), "")
            if not unit:
                raise PriceImportError(f"Row {row_number}: unsupported price_unit; use INR/kg, INR/Quintal, or INR/tonne.")
            row_arrival_unit = values.get("arrival_unit") or arrival_unit
            if row_arrival_unit and len(row_arrival_unit) > 30:
                raise PriceImportError(f"Row {row_number}: arrival_unit exceeds 30 characters.")
            row_source = values.get("source") or source.strip()
            if not row_source or len(row_source) > 150:
                raise PriceImportError(f"Row {row_number}: source must contain at most 150 characters.")
            row_variety = values.get("variety") or None
            row_grade = values.get("grade") or None
            if row_variety is not None and len(row_variety) > 100:
                raise PriceImportError(f"Row {row_number}: variety exceeds 100 characters.")
            if row_grade is not None and len(row_grade) > 100:
                raise PriceImportError(f"Row {row_number}: grade exceeds 100 characters.")
            key = (crop.id, markets[0].id, record_date, row_variety, row_grade)
            data = (min_price, max_price, modal_price, arrival, unit, row_arrival_unit, row_source)
            previous = staged.get(key)
            if previous is not None:
                if previous != data:
                    raise PriceImportError(f"Row {row_number}: conflicting records for the same crop, market and date.")
                skipped += 1
                continue
            staged[key] = data

        # Resolve existing keys in one read per record; do not overwrite sourced data.
        if rows_read == 0:
            raise PriceImportError("CSV contains no data rows.")

        for (crop_id, market_id, record_date, row_variety, row_grade), values in staged.items():
            existing_rows = db.scalars(select(MarketPrice).where(
                MarketPrice.crop_id == crop_id,
                MarketPrice.market_id == market_id,
                MarketPrice.price_date == record_date,
                MarketPrice.variety == row_variety,
                MarketPrice.grade == row_grade,
            )).all()
            if existing_rows:
                old_values = {
                    (record.min_price, record.max_price, record.modal_price,
                     record.arrival_quantity, record.price_unit, record.arrival_unit, record.source)
                    for record in existing_rows
                }
                imported_values = values
                if old_values != {imported_values}:
                    raise PriceImportError("CSV conflicts with an existing crop/market/date price record.")
                skipped += 1
                continue
            min_price, max_price, modal_price, arrival, unit, row_arrival_unit, row_source = values
            db.add(MarketPrice(
                crop_id=crop_id, market_id=market_id, price_date=record_date,
                min_price=min_price, max_price=max_price, modal_price=modal_price,
                variety=row_variety, grade=row_grade,
                arrival_quantity=arrival, price_unit=unit,
                arrival_unit=row_arrival_unit,
                source=row_source,
            ))
            inserted += 1
        if commit:
            db.commit()
        else:
            db.flush()
        return PriceImportSummary(rows_read=rows_read, rows_inserted=inserted, duplicates_skipped=skipped)
    except Exception:
        db.rollback()
        raise
    finally:
        if close_file:
            stream.close()
