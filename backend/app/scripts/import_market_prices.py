"""Explicit, dry-run-by-default CSV import command for market_prices."""

import argparse
import sys

from sqlalchemy.exc import SQLAlchemyError

from app.database.connection import SessionLocal
from app.services.price_importer import PriceImportError, import_market_prices_csv


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="CSV path")
    parser.add_argument("--source", required=True, help="Source/provenance label (max 150 chars)")
    parser.add_argument(
        "--price-unit", choices=("INR/kg", "INR/Quintal", "INR/tonne"),
        help="Required only when the CSV has no Price_Unit column",
    )
    parser.add_argument("--arrival-unit", help="Fallback arrival unit when the CSV has no Arrival_Unit column")
    parser.add_argument(
        "--apply", action="store_true",
        help="Commit the import. Without this flag the command flushes and rolls back (dry run).",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        summary = import_market_prices_csv(
            db,
            args.file,
            source=args.source,
            price_unit=args.price_unit,
            arrival_unit=args.arrival_unit,
            commit=args.apply,
        )
        if not args.apply:
            db.rollback()
        print(
            f"rows_read={summary.rows_read} rows_inserted={summary.rows_inserted} "
            f"duplicates_skipped={summary.duplicates_skipped} "
            f"mode={'apply' if args.apply else 'dry-run'}"
        )
        return 0
    except PriceImportError as error:
        db.rollback()
        print(f"Import rejected: {error}", file=sys.stderr)
        return 2
    except SQLAlchemyError:
        db.rollback()
        print("Import failed because the database operation failed.", file=sys.stderr)
        return 3
    except Exception:
        db.rollback()
        print("Import failed; no records were committed by this command.", file=sys.stderr)
        return 4
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
