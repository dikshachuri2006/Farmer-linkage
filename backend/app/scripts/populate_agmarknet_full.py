"""Populate crops, markets, and market-prices from the verified AGMARKNET dataset.

Source: agmarknet_prices.csv (Directorate of Marketing & Inspection, Ministry of Agriculture)
Date Coverage: 2026-10-24
Units: INR/Quintal
"""

import csv
import sys
from datetime import datetime
from decimal import Decimal
from sqlalchemy import func, select

from app.database.connection import SessionLocal
from app.models.entities import Crop, Market, MarketPrice
from app.scripts.sync_agmarknet_crops import category_for


def run_full_ingestion(csv_path: str = "agmarknet_prices.csv"):
    print("================================================================================")
    print("                 FARMERLINKAGE AGMARKNET DATA INGESTION ENGINE                  ")
    print("================================================================================")
    print(f"Reading dataset: {csv_path}")

    with open(csv_path, encoding="utf-8-sig", errors="replace") as f:
        reader = list(csv.DictReader(f))

    total_rows = len(reader)
    print(f"Total raw rows read: {total_rows:,}")

    db = SessionLocal()
    try:
        # ----------------------------------------------------------------------
        # 1. CROPS SYNC
        # ----------------------------------------------------------------------
        print("\n[Step 1/3] Synchronizing Crop Catalog...")
        existing_crops = {c.name.casefold(): c for c in db.query(Crop).all()}
        print(f"Existing crops in database: {len(existing_crops)}")

        raw_commodities = sorted(list(set(r["Commodity"].strip() for r in reader if r.get("Commodity"))), key=str.casefold)
        added_crops = 0
        for commodity in raw_commodities:
            if commodity.casefold() not in existing_crops:
                new_crop = Crop(
                    name=commodity,
                    category=category_for(commodity),
                    standard_unit="kg",
                    description="Government of India AGMARKNET agricultural commodity standard",
                )
                db.add(new_crop)
                existing_crops[commodity.casefold()] = new_crop
                added_crops += 1

        db.commit()
        # Refresh map with newly generated IDs
        crop_id_map = {c.name.casefold(): c.id for c in db.query(Crop).all()}
        print(f"Crops added: {added_crops} | Total crops in database: {len(crop_id_map)}")

        # ----------------------------------------------------------------------
        # 2. MARKETS SYNC
        # ----------------------------------------------------------------------
        print("\n[Step 2/3] Synchronizing APMC Mandis Directory...")
        existing_markets = {
            (m.name.casefold(), m.state.casefold(), m.district.casefold()): m.id
            for m in db.query(Market).all()
        }
        print(f"Existing markets in database: {len(existing_markets)}")

        raw_markets = set(
            (r["Market"].strip(), r["State"].strip(), r["District"].strip())
            for r in reader
            if r.get("Market") and r.get("State") and r.get("District")
        )
        print(f"Distinct markets identified in CSV: {len(raw_markets)}")

        added_markets = 0
        market_batch = []
        for m_name, s_name, d_name in raw_markets:
            key = (m_name.casefold(), s_name.casefold(), d_name.casefold())
            if key not in existing_markets:
                m_obj = Market(name=m_name, state=s_name, district=d_name)
                market_batch.append(m_obj)
                added_markets += 1

        if market_batch:
            db.add_all(market_batch)
            db.commit()

        market_id_map = {
            (m.name.casefold(), m.state.casefold(), m.district.casefold()): m.id
            for m in db.query(Market).all()
        }
        print(f"Markets added: {added_markets} | Total markets in database: {len(market_id_map)}")

        # ----------------------------------------------------------------------
        # 3. MARKET PRICES INGESTION
        # ----------------------------------------------------------------------
        print("\n[Step 3/3] Ingesting Daily Agmarknet Market Prices...")
        staged_prices = {}
        duplicates_in_csv = 0

        for row_idx, r in enumerate(reader, start=1):
            c_name = r["Commodity"].strip().casefold()
            m_key = (r["Market"].strip().casefold(), r["State"].strip().casefold(), r["District"].strip().casefold())

            crop_id = crop_id_map.get(c_name)
            market_id = market_id_map.get(m_key)

            if not crop_id or not market_id:
                continue

            # Parse date
            d_str = r["Arrival_Date"].strip()
            p_date = None
            for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                try:
                    p_date = datetime.strptime(d_str, fmt).date()
                    break
                except ValueError:
                    pass

            if not p_date:
                continue

            variety = r.get("Variety", "").strip() or None
            grade = r.get("Grade", "").strip() or None
            dedup_key = (crop_id, market_id, p_date, variety, grade)

            min_p = Decimal(r["Min_x0020_Price"].strip().replace(",", ""))
            max_p = Decimal(r["Max_x0020_Price"].strip().replace(",", ""))
            modal_p = Decimal(r["Modal_x0020_Price"].strip().replace(",", ""))

            # Validation: modal price must be between min and max
            if modal_p < min_p:
                min_p = modal_p
            if modal_p > max_p:
                max_p = modal_p

            if dedup_key in staged_prices:
                duplicates_in_csv += 1
                continue

            staged_prices[dedup_key] = MarketPrice(
                crop_id=crop_id,
                market_id=market_id,
                price_date=p_date,
                min_price=min_p,
                max_price=max_p,
                modal_price=modal_p,
                variety=variety,
                grade=grade,
                price_unit="INR/Quintal",
                source="Agmarknet (2026-10-24)",
            )

        print(f"Staged unique price records: {len(staged_prices):,} (Duplicates skipped: {duplicates_in_csv})")

        # Check existing records in DB to prevent duplicates
        existing_price_keys = set(
            db.execute(
                select(
                    MarketPrice.crop_id,
                    MarketPrice.market_id,
                    MarketPrice.price_date,
                    MarketPrice.variety,
                    MarketPrice.grade,
                )
            ).all()
        )
        print(f"Existing price records in database: {len(existing_price_keys):,}")

        to_insert = [
            price_obj for key, price_obj in staged_prices.items()
            if key not in existing_price_keys
        ]
        print(f"New price records to insert: {len(to_insert):,}")

        # Batch insert
        batch_size = 2000
        total_inserted = 0
        for i in range(0, len(to_insert), batch_size):
            chunk = to_insert[i : i + batch_size]
            db.add_all(chunk)
            db.flush()
            total_inserted += len(chunk)
            print(f"  Inserted {total_inserted:,} / {len(to_insert):,} records...")

        db.commit()
        print(f"Committed {total_inserted:,} records to market_prices successfully.")

        # ----------------------------------------------------------------------
        # FINAL VERIFICATION COUNTS
        # ----------------------------------------------------------------------
        final_crops = db.scalar(select(func.count(Crop.id)))
        final_markets = db.scalar(select(func.count(Market.id)))
        final_prices = db.scalar(select(func.count(MarketPrice.id)))

        print("\n================================================================================")
        print("                         FINAL DATABASE VERIFICATION                            ")
        print("================================================================================")
        print(f"Total Crops in Catalog:       {final_crops:,}")
        print(f"Total APMC Mandis in Directory: {final_markets:,}")
        print(f"Total Prevailing Price Records: {final_prices:,}")
        print("================================================================================\n")

    except Exception as e:
        db.rollback()
        print(f"ERROR: Ingestion aborted due to exception: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_full_ingestion()
