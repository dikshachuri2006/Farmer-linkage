# Database & Dataset Technical Requirements Specification

**Project:** FarmerLinkage — Farmer Market Linkage & Price Discovery  
**Smart India Hackathon Problem Statement:** SIH26132  
**Target Environment:** PostgreSQL 15+ / SQLAlchemy 2.0 / Alembic  

---

## 1. Existing Database Tables & Architectural Purpose

The application currently specifies and maps the following 12 core tables (defined in `backend/app/models/entities.py` and Alembic initial migration):

| Table Name | Entity Scope | Key Purpose & Business Invariants |
| :--- | :--- | :--- |
| **`users`** | Core IAM & Authentication | Stores unique telephone/mobile numbers, email addresses, password hashes (Argon2id/bcrypt), user roles (`FARMER`, `BUYER`, `ADMIN`), and account active state. |
| **`farmer_profiles`** | Identity / Farmer | 1-to-1 extension of `users` where `role = FARMER`. Tracks land holding (hectares), primary agricultural commodities grown, full farming address, state, district, pincode, and optional GPS coordinates. |
| **`buyer_profiles`** | Identity / Procurement | 1-to-1 extension of `users` where `role = BUYER`. Stores registered business trade name, APMC license numbers, GSTIN, business category (`TRADER`, `WHOLESALER`, `PROCESSOR`, `EXPORTER`, `RETAILER`), verified premises, and verification decision status (`PENDING`, `VERIFIED`, `REJECTED`, `SUSPENDED`). |
| **`crops`** | Master Commodity Directory | Central agricultural product catalog containing standardized crop names, commodity categories (`CEREAL`, `PULSE`, `VEGETABLE`, `FRUIT`, `OILSEED`, `SPICE`, `OTHER`), standard measurement trade unit (e.g., `kg`, `quintal`), and administrative description. |
| **`markets`** | Mandi Master Directory | Registered APMC mandis, sub-yards, and private market hubs across India. Stores unique mandi name, state, district, Agmarknet/APMC market code, and geographic coordinates (`latitude`, `longitude`). |
| **`market_prices`** | Historical & Daily Mandi Rates | Observation records of commodity arrivals across APMCs. Stores `crop_id`, `market_id`, `price_date`, variety, quality grade, arrival quantity, minimum price, maximum price, and `modal_price` per unit (`INR/quintal`). |
| **`farmer_lots`** | Supply Inventory | Farmgate produce listed for sale by farmers. Enforces positive quantity, positive expected reserve price, normalized trade units, location, quality grade (`GRADE_A`, `GRADE_B`, `GRADE_C`, `FAIR_AVERAGE`), and lifecycle availability (`AVAILABLE`, `COMMITTED`, `SOLD`, `WITHDRAWN`). |
| **`buyer_offers`** | Procurement Demand / Bids | Purchase bids placed by verified wholesale buyers against farmer produce lots. Tracks offered price per unit, requested quantity, delivery location, farmgate pickup terms, expiration date, and status (`ACTIVE`, `WITHDRAWN`, `EXPIRED`, `ACCEPTED`). |
| **`selling_requests`** | Bilateral Trade Negotiation | Formal negotiation channel linking farmer and buyer. Encapsulates agreed price, trade volume, estimated transport costs, mandi cess deductions, calculated net realization, counter-proposals, and lifecycle status (`PENDING`, `COUNTERED`, `ACCEPTED`, `REJECTED`, `CANCELLED`, `EXPIRED`, `COMPLETED`). |
| **`transactions`** | Settlement & Fulfillment | Binding digital trade contracts generated upon accepted selling requests. Tracks unique settlement voucher `transaction_id`, crop, transacted quantity, agreed unit price, gross amount, freight deductions, net realization, fulfillment status (`CONFIRMED`, `IN_TRANSIT`, `DELIVERED`, `COMPLETED`, `CANCELLED`), and payment state (`PENDING`, `PAYMENT_INITIATED`, `ESCROW_HELD`, `PAID`, `FAILED`, `REFUNDED`, `DISPUTED`). |
| **`complaints`** | Grievance Arbitration | Formal dispute tickets filed by farmers or buyers regarding trade fraud, quality mismatch, transport delay, payment defaults, or quantity shortages. Tracks ticket reference, status (`OPEN`, `UNDER_REVIEW`, `RESOLVED`, `DISMISSED`), against-party, and administrative investigation summary. |
| **`notifications`** | In-App Alerts | User-scoped notification queue for asynchronous events across offers, trade updates, transaction milestones, dispute outcomes, and KYC approvals. Supports unread filtering and read confirmations. |

---

## 2. Missing Fields & Tables Required by Remaining Features

The following database alterations and supplemental tables are required to scale advanced multi-round negotiation, dispute evidence handling, payment gateway integration, and spatial optimization:

### A. Enum Extensions
1. **`offer_status` Enum:**
   - **Current:** `'ACTIVE', 'WITHDRAWN', 'EXPIRED', 'ACCEPTED'`
   - **Required Migration:** `ALTER TYPE offer_status ADD VALUE 'REJECTED';`
   - *Rationale:* Currently, farmer offer rejections transition to `WITHDRAWN` with an explicit reason annotation in `terms_and_notes` to avoid enum violation. Adding `REJECTED` enables clean native status reporting.

### B. Negotiation History & Audit Trail (`selling_request_history`)
To preserve full multi-turn counter-offer history between buyers and farmers:
```sql
CREATE TABLE selling_request_history (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    selling_request_id BIGINT NOT NULL REFERENCES selling_requests(id) ON DELETE CASCADE,
    actor_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    action VARCHAR(30) NOT NULL, -- 'INITIATED', 'COUNTERED', 'ACCEPTED', 'REJECTED', 'CANCELLED'
    proposed_price NUMERIC(12, 2) NOT NULL,
    price_unit VARCHAR(30) NOT NULL DEFAULT 'INR/quintal',
    quantity NUMERIC(14, 3) NOT NULL,
    notes VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);
CREATE INDEX ix_request_history_request ON selling_request_history(selling_request_id, created_at ASC);
```

### C. Dispute Evidence Attachments & Arbitration Thread
To allow farmers and buyers to upload physical inspection photos, weighbridge slips, and dispute messages:
```sql
CREATE TABLE complaint_attachments (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    complaint_id BIGINT NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
    uploader_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    file_name VARCHAR(255) NOT NULL,
    file_url VARCHAR(500) NOT NULL,
    file_type VARCHAR(50) NOT NULL, -- 'IMAGE_JPEG', 'IMAGE_PNG', 'DOCUMENT_PDF'
    file_size_bytes BIGINT NOT NULL,
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);

CREATE TABLE complaint_messages (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    complaint_id BIGINT NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
    sender_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    message TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);
CREATE INDEX ix_complaint_messages_complaint ON complaint_messages(complaint_id, created_at ASC);
```

### D. Payment Gateway & Real Escrow Ledger (`payment_transactions`)
To integrate actual UPI / Escrow aggregators (RazorpayX, Cashfree, or ICICI E-Mandate) in Phase 2:
```sql
CREATE TABLE payment_transactions (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    transaction_id BIGINT NOT NULL REFERENCES transactions(id) ON DELETE RESTRICT,
    gateway_name VARCHAR(50) NOT NULL, -- 'RAZORPAY', 'CASHFREE', 'UPI_MERCHANT'
    gateway_order_id VARCHAR(100) UNIQUE,
    gateway_payment_id VARCHAR(100),
    amount NUMERIC(14, 2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'INR' NOT NULL,
    status VARCHAR(30) NOT NULL, -- 'PENDING', 'HELD_IN_ESCROW', 'SETTLED', 'REFUNDED', 'FAILED'
    escrow_released_at TIMESTAMP WITH TIME ZONE,
    raw_webhook_payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
);
CREATE INDEX ix_payment_transactions_trade ON payment_transactions(transaction_id);
```

### E. Machine Learning Model Registry & Forecast Store
To persist retrained regression models, exponential smoothing parameters, and precomputed price forecasts:
```sql
CREATE TABLE price_prediction_models (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    crop_id BIGINT NOT NULL REFERENCES crops(id) ON DELETE RESTRICT,
    market_id BIGINT NOT NULL REFERENCES markets(id) ON DELETE RESTRICT,
    variety VARCHAR(100),
    model_algorithm VARCHAR(50) NOT NULL, -- 'CHRONOLOGICAL_LINEAR_TREND', 'SARIMAX', 'PROPHET'
    mae NUMERIC(10, 2),
    mape_percent NUMERIC(6, 2),
    training_sample_count INT NOT NULL,
    trained_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    parameters JSONB NOT NULL
);

CREATE TABLE saved_price_predictions (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    crop_id BIGINT NOT NULL REFERENCES crops(id) ON DELETE RESTRICT,
    market_id BIGINT NOT NULL REFERENCES markets(id) ON DELETE RESTRICT,
    forecast_date DATE NOT NULL,
    horizon_days INT NOT NULL,
    predicted_modal_price NUMERIC(12, 2) NOT NULL,
    lower_bound_price NUMERIC(12, 2),
    upper_bound_price NUMERIC(12, 2),
    price_unit VARCHAR(30) DEFAULT 'INR/quintal' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    UNIQUE(crop_id, market_id, forecast_date, horizon_days)
);
```

---

## 3. Required Foreign-Key Relationships & Constraints

### Referential Integrity Constraints:
1. `farmer_profiles.user_id` -> `users.id` (`ON DELETE CASCADE`)
2. `buyer_profiles.user_id` -> `users.id` (`ON DELETE CASCADE`)
3. `farmer_lots.farmer_id` -> `users.id` (`ON DELETE RESTRICT`)
4. `farmer_lots.crop_id` -> `crops.id` (`ON DELETE RESTRICT`)
5. `buyer_offers.buyer_id` -> `users.id` (`ON DELETE RESTRICT`)
6. `buyer_offers.lot_id` -> `farmer_lots.id` (`ON DELETE RESTRICT`)
7. `selling_requests.farmer_id` -> `users.id` (`ON DELETE RESTRICT`)
8. `selling_requests.buyer_id` -> `users.id` (`ON DELETE RESTRICT`)
9. `selling_requests.lot_id` -> `farmer_lots.id` (`ON DELETE RESTRICT`)
10. `selling_requests.buyer_offer_id` -> `buyer_offers.id` (`ON DELETE RESTRICT`, `UNIQUE`)
11. `transactions.selling_request_id` -> `selling_requests.id` (`ON DELETE RESTRICT`, `UNIQUE`)
12. `transactions.farmer_id` -> `users.id` (`ON DELETE RESTRICT`)
13. `transactions.buyer_id` -> `users.id` (`ON DELETE RESTRICT`)
14. `transactions.crop_id` -> `crops.id` (`ON DELETE RESTRICT`)
15. `complaints.complainant_user_id` -> `users.id` (`ON DELETE RESTRICT`)
16. `complaints.against_user_id` -> `users.id` (`ON DELETE SET NULL`)
17. `complaints.transaction_id` -> `transactions.id` (`ON DELETE SET NULL`)
18. `notifications.user_id` -> `users.id` (`ON DELETE CASCADE`)
19. `market_prices.crop_id` -> `crops.id` (`ON DELETE RESTRICT`)
20. `market_prices.market_id` -> `markets.id` (`ON DELETE RESTRICT`)

### Check & Range Constraints:
- `ck_crops_name_nonempty`: `length(trim(name)) > 0`
- `ck_markets_latitude_range`: `latitude IS NULL OR latitude BETWEEN -90 AND 90`
- `ck_markets_longitude_range`: `longitude IS NULL OR longitude BETWEEN -180 AND 180`
- `ck_market_prices_modal_positive`: `modal_price > 0`
- `ck_market_prices_min_le_modal`: `min_price <= modal_price`
- `ck_market_prices_modal_le_max`: `modal_price <= max_price`
- `ck_farmer_lots_quantity_positive`: `quantity > 0`
- `ck_farmer_lots_price_positive`: `expected_price_per_unit > 0`
- `ck_buyer_offers_price_positive`: `offered_price_per_unit > 0`
- `ck_buyer_offers_quantity_positive`: `quantity_requested > 0`
- `ck_transactions_quantity_positive`: `quantity > 0`
- `ck_transactions_agreed_price_positive`: `agreed_price_per_unit > 0`
- `ck_transactions_gross_amount_positive`: `gross_amount > 0`

---

## 4. Database Indexes for High-Traffic Queries

To ensure sub-50ms latency across marketplace filtering, mandi price history, transaction records, and administrative aggregations:

```sql
-- Marketplace filtering by status, crop, and location
CREATE INDEX IF NOT EXISTS ix_farmer_lots_marketplace_lookup 
ON farmer_lots (status, crop_id, location_state, location_district) 
WHERE status = 'AVAILABLE';

-- APMC market prices time-series query index
CREATE INDEX IF NOT EXISTS ix_market_prices_crop_mandi_series 
ON market_prices (crop_id, market_id, price_date DESC, variety, grade);

-- Buyer offers lookup on farmer produce lots
CREATE INDEX IF NOT EXISTS ix_buyer_offers_lot_active 
ON buyer_offers (lot_id, status) 
WHERE status = 'ACTIVE';

-- Unread notifications counter index
CREATE INDEX IF NOT EXISTS ix_notifications_user_unread 
ON notifications (user_id, is_read) 
WHERE is_read = FALSE;

-- Digital transactions audit trail index
CREATE INDEX IF NOT EXISTS ix_transactions_users_status 
ON transactions (farmer_id, buyer_id, transaction_status, payment_status);

-- Geographic APMC Mandi lookup
CREATE INDEX IF NOT EXISTS ix_markets_state_district_name 
ON markets (state, district, name);
```

---

## 5. Required Crop & Market Reference Master Data

### Standard Commodity Baseline:
The platform requires pre-seeding the national standard commodity list aligned with the Ministry of Agriculture & Farmers Welfare (Agmarknet):

- **Vegetables:** Onion (Nashik Red, Garwa, Pol), Potato (Jyoti, Kufri, Chipsona), Tomato (Hybrid, Local), Green Chilli, Ginger, Garlic.
- **Cereals:** Wheat (Sharbati, Lokwan, Mill Quality), Paddy/Rice (Basmati 1121, Sona Masoori, IR-64), Maize, Bajra, Jowar.
- **Pulses:** Chickpea/Chana (Desi, Kabuli), Pigeon Pea/Tur (Gajapati, Maruti), Moong (Green Gram), Urad (Black Gram), Soyabean.
- **Fruits:** Banana (Grand Naine, Robusta), Pomegranate (Bhagwa), Grapes (Thompson Seedless), Mango (Alphonso, Kesar), Orange (Nagpur).
- **Spices & Cash Crops:** Cotton (Medium Staple, Long Staple), Sugarcane, Turmeric, Cumin (Jeera), Coriander.

### Mandi Hub Baseline:
Minimum 100 major APMC Mandis covering primary agricultural clusters in Maharashtra, Madhya Pradesh, Gujarat, Punjab, Haryana, Karnataka, and Uttar Pradesh:
- **Maharashtra:** Lasalgaon, Pimpalgaon Baswant, Pune APMC (Gultekdi), Nashik, Vashi (Navi Mumbai), Ahmednagar, Solapur, Nagpur APMC, Kolhapur, Jalgaon.
- **Madhya Pradesh:** Neemuch, Mandsaur, Indore, Ujjain, Dewas, Harda.
- **Gujarat:** Unjha, Gondal, Rajkot, Surat, Mahuva, Deesa.
- **Punjab & Haryana:** Khanna, Karnal, Sirsa, Bathinda, Ambala.

---

## 6. Agricultural Market Price Datasets & Provenance

### Primary Dataset Sources:
1. **Open Government Data (OGD) Platform India (`data.gov.in`):**
   - *Resource:* Daily Mandi Arrivals & Prices from Agmarknet.
   - *API Endpoint:* `https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070`
   - *License:* Government Open Data License - India (GODL).
2. **Directorate of Marketing & Inspection (DMI) / Agmarknet Portal:**
   - *Website:* `agmarknet.gov.in`
   - *Frequency:* Daily updates across ~3,000 regulated agricultural mandis.
3. **National Agriculture Market (e-NAM):**
   - *Portal:* `enam.gov.in`
   - *Reference:* Grade-specific trade settlement records.

---

## 7. Expected Dataset Schema & Normalization Rules

### Raw Agmarknet Ingestion Columns:
| Raw Column Name | Target Data Type | Target Column | Transformation / Cleaning Rule |
| :--- | :--- | :--- | :--- |
| `State` | `VARCHAR(100)` | `markets.state` | Title-cased; strip whitespace, map abbreviations (e.g., "M.P." -> "Madhya Pradesh"). |
| `District` | `VARCHAR(100)` | `markets.district` | Title-cased; strip sub-district qualifiers. |
| `Market` | `VARCHAR(150)` | `markets.name` | Normalized to APMC name (e.g., "Lasalgaon(APMC)" -> "Lasalgaon"). |
| `Commodity` | `VARCHAR(100)` | `crops.name` | Fuzzy match to master `crops.name` table. If absent, map to category. |
| `Variety` | `VARCHAR(100)` | `market_prices.variety` | Default to `"Other"` if null or whitespace. |
| `Grade` | `VARCHAR(50)` | `market_prices.grade` | Map to enum `[GRADE_A, GRADE_B, GRADE_C, FAIR_AVERAGE]`. ("FAQ" -> `FAIR_AVERAGE`). |
| `Arrival_Date` | `DATE` | `market_prices.price_date`| Parse `DD/MM/YYYY` or `YYYY-MM-DD` ISO-8601. |
| `Min_Price` | `NUMERIC(12, 2)` | `market_prices.min_price` | Ensure positive float; if `Min_Price > Modal_Price`, swap values. |
| `Max_Price` | `NUMERIC(12, 2)` | `market_prices.max_price` | Ensure `Max_Price >= Modal_Price`. |
| `Modal_Price` | `NUMERIC(12, 2)` | `market_prices.modal_price`| Mandatory positive float. Target unit: `INR/quintal`. |

### Unit Standardization & Deduplication:
- **Unit Conversion:** Agmarknet rates are natively quoted in `Rs./Quintal`. If local mandis quote in `Rs./kg`, multiply by `100.0`. If quoted in `Rs./Tonne`, divide by `10.0`.
- **Deduplication Key:** Enforce `UNIQUE(crop_id, market_id, price_date, variety, grade)` using an `ON CONFLICT DO UPDATE` upsert policy during ingestion.

---

## 8. Dataset Import & ETL Procedure

1. **Pre-requisite:** Master `crops` and `markets` tables must be populated before inserting `market_prices`.
2. **ETL Pipeline Script Structure (`backend/scripts/import_agmarknet.py`):**
   ```python
   # Step 1: Read daily JSON/CSV from data.gov.in or local file
   # Step 2: Validate and upsert Mandi records in `markets`
   # Step 3: Match Commodity against `crops` catalog
   # Step 4: Clean variety, grade, date, and prices
   # Step 5: Bulk upsert via SQLAlchemy execute(insert(...).on_conflict_do_update(...))
   ```
3. **Idempotency:** Bulk operations must execute inside database transactions with batch sizes of 1,000 records per commit.

---

## 9. PostgreSQL Configuration & Infrastructure Specifications

### Connection Pool Configuration:
```ini
# PostgreSQL Recommended Settings (postgresql.conf)
shared_buffers = 256MB
work_mem = 16MB
maintenance_work_mem = 64MB
effective_cache_size = 768MB
max_connections = 100
timezone = 'UTC'
```

### Application Connection String:
```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/farmerlinkage_db
```

### Alembic Migration Command Sequence (To be run by User during DB Setup Phase):
```bash
# 1. Check current migration state
alembic current

# 2. Upgrade schema to latest revision
alembic upgrade head

# 3. Verify tables generated
psql -U postgres -d farmerlinkage_db -c "\dt"
```
