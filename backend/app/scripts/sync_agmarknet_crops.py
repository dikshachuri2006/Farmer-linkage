import argparse
import csv
import re
from sqlalchemy import func, select
from app.database.connection import SessionLocal
from app.models.entities import Crop
from app.schemas.crop import CropCategory

CATEGORIES = {
    "CEREAL": {
        "Wheat", "Bajra(Pearl Millet/Cumbu)", "Jowar(Sorghum)",
        "Maize", "Ragi(Finger Millet)", "Rajgir",
    },
    "PULSE": {
        "Bengal Gram(Gram)(Whole)", "Black Gram(Urd Beans)(Whole)",
        "Green Gram(Moong)(Whole)", "Red gram/Arhar/Tur(whole)",
        "Lentil(Masur)(Whole)", "Beans", "Peas Wet", "Green Peas",
    },
    "OILSEED": {"Soyabean", "Ground Nut Seed"},
    "SPICE": {
        "Chilly Capsicum", "Green Chilli", "Corriander seed",
        "Coriander(Leaves)", "Garlic", "Ginger(Green)", "Mint(Pudina)",
        "Methi(Leaves)",
    },
    "FRUIT": {
        "Apple", "Banana", "Chikoos(Sapota)", "Guava", "Lime",
        "Mousambi(Sweet Lime)", "Orange", "Papaya", "Pineapple",
        "Pomegranate", "Seetapal", "Water Melon",
    },
    "VEGETABLE": {
        "Beetroot", "Bhindi(Ladies Finger)", "Bitter gourd",
        "Bottle gourd", "Brinjal", "Cabbage", "Carrot", "Cauliflower",
        "Cucumbar(Kheera)", "Drumstick", "Green Chilli", "Green Peas",
        "Little gourd(Kundru)", "Onion", "Onion Green", "Potato",
        "Raddish", "Ridgeguard(Tori)", "Spinach", "Tomato", "Guar",
    },
}

def category_for(name):
    for category, names in CATEGORIES.items():
        if name.casefold() in {n.casefold() for n in names}:
            return CropCategory(category)
    return CropCategory.OTHER

parser = argparse.ArgumentParser()
parser.add_argument("--apply", action="store_true",
                    help="Commit missing crops; default is dry-run")
args = parser.parse_args()

names = set()
with open("agmarknet_prices.csv", encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f):
        state = (row.get("State") or "").strip()
        market = (row.get("Market") or "").strip()
        commodity = (row.get("Commodity") or "").strip()
        if (state.casefold() == "maharashtra"
                and re.search(r"Lasalgaon|Pimpalgaon|Pune", market, re.I)
                and commodity):
            names.add(commodity)

db = SessionLocal()
try:
    added = []
    for name in sorted(names, key=str.casefold):
        existing = db.scalar(
            select(Crop.id).where(func.lower(Crop.name) == name.casefold())
        )
        if existing is None:
            db.add(Crop(
                name=name,
                category=category_for(name),
                standard_unit="kg",
                description="Commodity listed in the AGMARKNET source dataset",
            ))
            added.append(name)

    if args.apply:
        db.commit()
        print(f"COMMITTED: {len(added)} new crops")
    else:
        db.rollback()
        print(f"DRY RUN: {len(added)} crops would be added")
    for name in added:
        print(" -", name)
finally:
    db.close()
