# FarmerLinkage Backend Technical Handoff

**Audit basis:** current source under `backend/app`, the checked-in Alembic migration, project schema documents, tests, and the previous safe regression run. No PostgreSQL connection, migration, or write was performed for this handoff. A local ORM model or migration describes the intended database structure; it does not prove that a particular live database has applied it.

## 1. Source code and repository

### Project layout

```text
D:\Farmerlinkage\
  requirements.txt                  # root duplicate of backend requirements
  .env.example                      # variable template; contains no runtime proof
  backend\
    app\
      core\                         # Settings, JWT/password helpers, auth dependencies
      database\                     # SQLAlchemy Base, engine and request sessions
      models\entities.py            # 12 SQLAlchemy table mappings
      routes\                       # FastAPI routers mounted by app/main.py
      schemas\                       # Pydantic v2 API contracts
      services\                      # repositories and workflow/business logic
      ml\price_forecast.py          # chronological linear trend baseline
    migrations\                     # Alembic environment and static initial revision
    tests\                          # pytest tests; isolated SQLite/mocks for safe workflows
    requirements.txt
    alembic.ini
    .env.example
    DATABASE_SCHEMA_SPEC.md          # proposed/review specification, not DDL
    ANKITA_DATABASE_PROPOSAL.md      # conceptual proposal, not evidence of live tables
    ADMIN_PROVISIONING.md
```

No frontend source was present in the inspected project file inventory. The backend is FastAPI, SQLAlchemy 2, Pydantic v2, PostgreSQL via `psycopg`, and Alembic. Dependencies are pinned in both requirements files: FastAPI/Uvicorn, Pydantic and pydantic-settings, SQLAlchemy, Alembic, `psycopg[binary]`, bcrypt, PyJWT, pytest/httpx, and numpy/scikit-learn/joblib. The current forecast implementation itself uses a small Python least-squares calculation; it does not load those ML libraries or a saved artifact.

### Git and safe source sharing

Neither `D:\Farmerlinkage` nor `D:\Farmerlinkage\backend` is a Git working tree (`git rev-parse` reported no repository), so no configured Git remote could be verified. No remote URL is known or asserted here.

Share a reviewed source copy or archive containing the application, migrations, tests, requirements, Alembic config, and documentation. Exclude `.env` files, credentials, tokens, `.venv`/`venv`, Python/test caches, database dumps, logs, local exports, and machine-specific files. `.env.example` is a template, not a secret store; inspect it before sharing. Do not publish or push the repository automatically.

### Local setup (PowerShell)

From the backend directory:

```powershell
cd D:\Farmerlinkage\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edit the local `.env` using a private editor/secret manager. Set the `POSTGRES_SERVER`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` fields, or set `DATABASE_URL` (which takes precedence). Configure `SECRET_KEY` to a private random value of at least 32 characters, set `ENVIRONMENT` appropriately, and set `DEBUG=false` for demo/staging/production. Never paste a real `.env` into chat, logs, tickets, or source control. Start the API only after the database owner confirms the database/schema is available:

```powershell
uvicorn app.main:app --reload
```

Interactive docs are mounted at `/api/docs`; OpenAPI JSON is `/api/openapi.json`. A `.env.example` exists at both project root and backend root. The settings loader reads `.env` and `backend/.env` relative to its process environment. Development replaces the published placeholder signing key with a random process-local secret; development JWTs will stop validating after process restart if no stable key is configured. Outside development, configuration rejects the placeholder/short secret and rejects `DEBUG=true`.

Do not run Alembic merely as a setup experiment against a shared database. The one checked-in migration is static and its downgrade drops the application tables and enum types. Have the database owner review/approve `alembic upgrade head` before applying it to any persistent database. This audit did not run migrations.

## 2. Database schema

### What is and is not proven

The repository contains concrete ORM mappings in `app/models/entities.py` and one static Alembic revision, `migrations/versions/20261024_0001_initial_schema.py` (`revision = 20261024_0001`). Its `upgrade()` creates the twelve tables below and named PostgreSQL enum types. This is actual checked-in DDL, but **the migration's presence does not prove it has been applied to the live PostgreSQL database**. No live schema inspection or SQL export was made.

`DATABASE_SCHEMA_SPEC.md` labels itself a proposed-for-review specification, not DDL. `ANKITA_DATABASE_PROPOSAL.md` is also conceptual. In particular, its proposed `price_predictions` table is **not** an ORM entity or migration table. No prediction table or saved-model table exists in the implementation. The migration and ORM are the source of truth for this listing; where the proposal differs, the proposal is not implemented schema. ORM classes define scalar columns and FK constraints; no SQLAlchemy `relationship()` properties were found.

Notation below: `PK` = primary key; `FK` target is shown; `UQ` = unique; `NULL` means nullable; otherwise fields are `NOT NULL`. `BIGINT ID` means `BIGINT GENERATED BY DEFAULT AS IDENTITY`, primary key. SQLAlchemy `DateTime(timezone=True)` is PostgreSQL `TIMESTAMP WITH TIME ZONE`. Enum types are PostgreSQL named enums.

### Implemented ORM/Alembic tables

1. **`users`** — `id BIGINT ID`; `email VARCHAR(255) NOT NULL UQ`; `phone_number VARCHAR(20) NOT NULL UQ`; `hashed_password VARCHAR(255) NOT NULL`; `full_name VARCHAR(150) NOT NULL`; `role user_role NOT NULL`; `is_active BOOLEAN NOT NULL DEFAULT TRUE`; `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`; `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`. Check: `ck_users_full_name_nonempty`. No FKs. Indexes are the unique indexes created for email and phone.

2. **`farmer_profiles`** — `id BIGINT ID`; `user_id BIGINT NOT NULL FK users.id ON DELETE RESTRICT UQ`; `state VARCHAR(100) NOT NULL`; `district VARCHAR(100) NOT NULL`; `taluka VARCHAR(100) NULL`; `village VARCHAR(100) NULL`; `pincode VARCHAR(10) NOT NULL`; `land_area_acres NUMERIC(8,2) NULL`; `preferred_language VARCHAR(10) NOT NULL DEFAULT 'en'`; `latitude NUMERIC(10,7) NULL`; `longitude NUMERIC(10,7) NULL`; `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`; `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`. Checks: nonnegative/null land area; latitude and longitude ranges; six-digit pincode regex. Index: `ix_farmer_profiles_state_district` on `(state,district)`. Unique user FK gives one profile per user.

3. **`buyer_profiles`** — `id BIGINT ID`; `user_id BIGINT NOT NULL FK users.id ON DELETE RESTRICT UQ`; `business_name VARCHAR(200) NOT NULL`; `business_type buyer_business_type NOT NULL DEFAULT 'TRADER'`; `license_number VARCHAR(100) NULL`; `state VARCHAR(100) NOT NULL`; `district VARCHAR(100) NOT NULL`; `market_address TEXT NOT NULL`; `latitude NUMERIC(10,7) NULL`; `longitude NUMERIC(10,7) NULL`; `verification_status buyer_verification_status NOT NULL DEFAULT 'PENDING'`; `verification_notes TEXT NULL`; `documents_url TEXT NULL`; `rating NUMERIC(3,2) NOT NULL DEFAULT 5.00`; `total_transactions INTEGER NOT NULL DEFAULT 0`; `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`; `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`. Checks: rating 1–5; transaction count nonnegative; coordinate ranges. Index: `ix_buyer_profiles_verification_status`. Unique user FK gives one profile per user.

4. **`crops`** — `id BIGINT ID`; `name VARCHAR(100) NOT NULL UQ`; `category crop_category NOT NULL DEFAULT 'OTHER'`; `standard_unit VARCHAR(20) NOT NULL DEFAULT 'kg'`; `description TEXT NULL`; `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`. Checks: non-empty trimmed name and standard unit. No FKs or separate non-unique indexes.

5. **`markets`** — `id BIGINT ID`; `name VARCHAR(150) NOT NULL`; `state VARCHAR(100) NOT NULL`; `district VARCHAR(100) NOT NULL`; `market_code VARCHAR(100) NULL`; `latitude NUMERIC(10,7) NULL`; `longitude NUMERIC(10,7) NULL`. Checks: non-empty trimmed name/state/district and coordinate ranges. Indexes: `ix_markets_name` on `name`; `ix_markets_state_district` on `(state,district)`. No unique market code is defined.

6. **`market_prices`** — `id BIGINT ID`; `crop_id BIGINT NOT NULL FK crops.id ON DELETE RESTRICT`; `market_id BIGINT NOT NULL FK markets.id ON DELETE RESTRICT`; `price_date DATE NOT NULL`; `min_price NUMERIC(12,2) NOT NULL`; `max_price NUMERIC(12,2) NOT NULL`; `modal_price NUMERIC(12,2) NOT NULL`; `arrival_quantity NUMERIC(14,3) NULL`; `price_unit VARCHAR(30) NOT NULL DEFAULT 'INR/Quintal'`; `arrival_unit VARCHAR(30) NULL`; `source VARCHAR(150) NOT NULL DEFAULT 'Agmarknet'`. Checks: min/modal nonnegative, max at least min, arrival null or nonnegative. Index: `ix_market_prices_crop_market_date` on `(crop_id,market_id,price_date DESC)`. **There is no unique constraint on crop/market/date.**

7. **`farmer_lots`** — `id BIGINT ID`; `farmer_id BIGINT NOT NULL FK users.id ON DELETE RESTRICT`; `crop_id BIGINT NOT NULL FK crops.id ON DELETE RESTRICT`; `quantity NUMERIC(14,3) NOT NULL`; `unit VARCHAR(20) NOT NULL DEFAULT 'quintal'`; `quality_grade lot_quality_grade NOT NULL DEFAULT 'GRADE_A'`; `expected_price_per_unit NUMERIC(12,2) NOT NULL`; `price_unit VARCHAR(30) NOT NULL DEFAULT 'INR/quintal'`; `harvest_date DATE NULL`; `location_state VARCHAR(100) NOT NULL`; `location_district VARCHAR(100) NOT NULL`; `location_pincode VARCHAR(10) NULL`; `status lot_status NOT NULL DEFAULT 'AVAILABLE'`; `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`; `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`. Checks: quantity and expected price positive. Indexes: `ix_farmer_lots_crop_status` on `(crop_id,status)`; `ix_farmer_lots_farmer_created` on `(farmer_id,created_at DESC)`.

8. **`buyer_offers`** — `id BIGINT ID`; `buyer_id BIGINT NOT NULL FK users.id ON DELETE RESTRICT`; `lot_id BIGINT NOT NULL FK farmer_lots.id ON DELETE RESTRICT`; `offered_price_per_unit NUMERIC(12,2) NOT NULL`; `price_unit VARCHAR(30) NOT NULL DEFAULT 'INR/quintal'`; `quantity_requested NUMERIC(14,3) NOT NULL`; `quantity_unit VARCHAR(20) NOT NULL DEFAULT 'quintal'`; `pickup_included BOOLEAN NOT NULL DEFAULT FALSE`; `delivery_location VARCHAR(200) NOT NULL`; `status offer_status NOT NULL DEFAULT 'ACTIVE'`; `valid_until DATE NULL`; `terms_and_notes VARCHAR(500) NULL`; `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`; `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`. Checks: offered price and requested quantity positive. Indexes: `ix_buyer_offers_buyer_status_created` on `(buyer_id,status,created_at DESC)`; `ix_buyer_offers_lot_status` on `(lot_id,status)`.

9. **`selling_requests`** — `id BIGINT ID`; `request_code VARCHAR(50) NOT NULL UQ`; `farmer_id BIGINT NOT NULL FK users.id ON DELETE RESTRICT`; `buyer_id BIGINT NOT NULL FK users.id ON DELETE RESTRICT`; `lot_id BIGINT NOT NULL FK farmer_lots.id ON DELETE RESTRICT`; `quantity NUMERIC(14,3) NOT NULL`; `quantity_unit VARCHAR(20) NOT NULL DEFAULT 'quintal'`; `proposed_price NUMERIC(12,2) NOT NULL`; `price_unit VARCHAR(30) NOT NULL DEFAULT 'INR/quintal'`; `estimated_gross_amount NUMERIC(16,2) NOT NULL`; `estimated_transport_cost NUMERIC(14,2) NOT NULL DEFAULT 0`; `estimated_other_charges NUMERIC(14,2) NOT NULL DEFAULT 0`; `estimated_net_realization NUMERIC(16,2) NOT NULL`; `status selling_request_status NOT NULL DEFAULT 'PENDING'`; `rejection_reason TEXT NULL`; `message VARCHAR(500) NULL`; `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`; `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`. Checks: positive quantity/price and nonnegative transport/other charges. Indexes: `ix_selling_requests_farmer_status_created` on `(farmer_id,status,created_at DESC)`; `ix_selling_requests_buyer_status_created` on `(buyer_id,status,created_at DESC)`; `ix_selling_requests_lot_status` on `(lot_id,status)`.

10. **`transactions`** — `id BIGINT ID`; `transaction_id VARCHAR(60) NOT NULL UQ`; `selling_request_id BIGINT NOT NULL FK selling_requests.id ON DELETE RESTRICT UQ`; `farmer_id BIGINT NOT NULL FK users.id ON DELETE RESTRICT`; `buyer_id BIGINT NOT NULL FK users.id ON DELETE RESTRICT`; `crop_id BIGINT NOT NULL FK crops.id ON DELETE RESTRICT`; `quantity NUMERIC(14,3) NOT NULL`; `quantity_unit VARCHAR(20) NOT NULL`; `agreed_price NUMERIC(12,2) NOT NULL`; `price_unit VARCHAR(30) NOT NULL`; `gross_amount NUMERIC(16,2) NOT NULL`; `transport_cost NUMERIC(14,2) NOT NULL DEFAULT 0`; `other_charges NUMERIC(14,2) NOT NULL DEFAULT 0`; `net_amount NUMERIC(16,2) NOT NULL`; `payment_status payment_status NOT NULL DEFAULT 'PENDING'`; `transaction_status transaction_status NOT NULL DEFAULT 'CONFIRMED'`; `payment_method VARCHAR(50) NULL DEFAULT 'ESCROW'`; `notes VARCHAR(500) NULL`; `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`; `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`. Checks: positive quantity/agreed price and nonnegative charges. Indexes: `ix_transactions_created_at` on `(created_at DESC)`; `ix_transactions_farmer_created` on `(farmer_id,created_at DESC)`; `ix_transactions_buyer_created` on `(buyer_id,created_at DESC)`. The unique selling-request FK prevents duplicate transactions per request.

11. **`complaints`** — `id BIGINT ID`; `ticket_number VARCHAR(50) NOT NULL UQ`; `complainant_user_id BIGINT NOT NULL FK users.id ON DELETE RESTRICT`; `transaction_id BIGINT NULL FK transactions.id ON DELETE RESTRICT`; `against_user_id BIGINT NULL FK users.id ON DELETE RESTRICT`; `issue_type complaint_issue_type NOT NULL`; `title VARCHAR(200) NOT NULL`; `description TEXT NOT NULL`; `status complaint_status NOT NULL DEFAULT 'OPEN'`; `admin_notes VARCHAR(1000) NULL`; `resolution_summary VARCHAR(1000) NULL`; `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`; `resolved_at TIMESTAMPTZ NULL`. Check: resolved time is null or not before creation. Indexes: `ix_complaints_complainant_created` on `(complainant_user_id,created_at DESC)`; `ix_complaints_status_issue_created` on `(status,issue_type,created_at DESC)`; `ix_complaints_transaction_id` on `transaction_id`.

12. **`notifications`** — `id BIGINT ID`; `user_id BIGINT NOT NULL FK users.id ON DELETE RESTRICT`; `notification_type notification_type NOT NULL`; `title VARCHAR(200) NOT NULL`; `message VARCHAR(1000) NOT NULL`; `is_read BOOLEAN NOT NULL DEFAULT FALSE`; `reference_id VARCHAR(60) NULL`; `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`. Index: `ix_notifications_user_read_created` on `(user_id,is_read,created_at DESC)`.

Enum values are defined by schemas and persisted by named PG enum types: `user_role` (FARMER, BUYER, ADMIN); `buyer_business_type` (TRADER, WHOLESALER, PROCESSOR, EXPORTER, RETAILER); `buyer_verification_status` (PENDING, VERIFIED, REJECTED, SUSPENDED); `crop_category` (CEREAL, PULSE, VEGETABLE, FRUIT, OILSEED, SPICE, OTHER); `lot_quality_grade` (GRADE_A, GRADE_B, GRADE_C, FAIR_AVERAGE); `lot_status` (AVAILABLE, COMMITTED, SOLD, WITHDRAWN); `offer_status` (ACTIVE, WITHDRAWN, EXPIRED, ACCEPTED); `selling_request_status` (PENDING, COUNTERED, ACCEPTED, REJECTED, CANCELLED, EXPIRED, COMPLETED); `payment_status` (PENDING, PAYMENT_INITIATED, ESCROW_HELD, PAID, FAILED, REFUNDED, DISPUTED); `transaction_status` (CONFIRMED, IN_TRANSIT, DELIVERED, COMPLETED, CANCELLED); `complaint_issue_type` (PAYMENT_ISSUE, WRONG_QUANTITY, BUYER_NO_SHOW, PRICE_DISPUTE, FRAUD, QUALITY_MISMATCH, TRANSPORT_DELAY, OTHER); `complaint_status` (OPEN, UNDER_REVIEW, RESOLVED, DISMISSED); `notification_type` (BUYER_VERIFICATION, NEW_REQUEST, REQUEST_ACCEPTED, REQUEST_REJECTED, TRANSACTION_CREATED, TRANSACTION_STATUS, COMPLAINT_FILED, COMPLAINT_UPDATE, GENERAL).

## 3. Database connectivity and lifecycle

`app/core/config.py` uses Pydantic Settings and environment variables, with `.env` and `backend/.env` as configured file locations. `DATABASE_URL` overrides the assembled `postgresql+psycopg://...` URL based on `POSTGRES_*`. `app/database/connection.py` creates a SQLAlchemy engine with `pool_pre_ping=True`, pool size 10 and overflow 20. SQL echo is enabled only when both development and debug are enabled. `SessionLocal` binds request sessions; `get_db()` yields one session and closes it at the end of the request. Repositories commit writes and roll back on exceptions where implemented. Alembic imports `Base.metadata` and uses the same settings URL.

**Live connection status:** not checked for this handoff. No live PostgreSQL access or migration command was used. SQLite and mock tests are not proof of production schema/application compatibility. Current health handlers return JSON status/configuration and do not execute a DB probe.

## 4. Authentication and authorization

- Passwords are hashed and verified with bcrypt; hashing uses cost 12. The helper clips UTF-8 password bytes to bcrypt's 72-byte limit. Registration schema permits up to 72 characters, so a multibyte password may exceed 72 encoded bytes and be clipped; avoid relying on bytes beyond that boundary.
- JWTs are signed with configured `ALGORITHM` (default HS256) and include `sub` (user ID), `role`, `iat`, `nbf`, and `exp`. Login also puts email/full name claims in the token. Default expiry is 24 hours. Decode requires expiry/subject/role and PyJWT validates expiry/signature.
- `get_current_user_claims` loads the current `User` from SQLAlchemy on each authenticated request. It rejects invalid/expired tokens, missing/inactive accounts, invalid role claims, and a token role that differs from the current DB role. DB errors fail closed with 503. Role dependencies return 403 when the authenticated role is wrong.
- Public registration is FARMER or BUYER; public ADMIN registration is rejected. Admin provisioning is a separate script/documented operation and must be protected.
- `require_farmer`, `require_buyer`, and `require_admin` gate their route groups. Transaction/complaint paths allow authenticated participants and admins as specified in the API reference; notifications are scoped to the current recipient. Buyer offers require a verified buyer for creation and buyer ownership for read/withdraw. Farmer lot operations scope rows to the authenticated farmer.
- Common codes: 401 for missing/invalid/expired credentials; 403 for wrong role or forbidden operation; 404 for missing/owner-scoped records; 409 for conflicting workflow/state; 422 for request/schema validation; 503 for selected DB/auth pending/unavailable handlers; and generic 500 for selected database failures. Codes are endpoint-specific below.
- Production/demo config validates a non-placeholder secret with at least 32 characters and requires debug off. Keep credentials in private environment/secret storage. No secret values are included in this handoff.

## 5. Feature status

| Area | Source status | Test/live evidence |
|---|---|---|
| Authentication and RBAC | Implemented against SQLAlchemy `users`; JWT expiry, active-account and current-role checks present. | Unit/security/dependency tests exist. Auth route tests exist but were not part of the latest safe suite. Live login and `/auth/me` were previously reported by the user as working; not rechecked here. |
| Farmer/buyer profiles and buyer verification | SQLAlchemy-backed create/read/update, verification submission and admin decisions; buyer suspension also deactivates the user. | Isolated profile tests cover persistence, validation, ownership and admin flows. User previously reported buyer create/read/update live success; not rechecked. |
| Admin | DB-backed farmer/buyer listing and review, transaction listing, complaint review. | SQLite workflow/profile tests. No live admin/PostgreSQL verification in this handoff. |
| Crop and market catalog | DB-backed crop list/detail and admin create; market list/detail. | Isolated SQLite tests cover filters, pagination, missing rows, errors and admin gating. Live state unverified here. |
| Market prices and importer | DB-backed list/latest/detail. Manual atomic CSV import helper; no automatic import or HTTP upload. Uses existing crop/market/market-price tables. | Isolated SQLite tests cover empty/list/latest/detail, import validation, duplicate handling and generic read errors. No real CSV file was found in project inventory; no live DB import or request was performed. |
| Price discovery | Calculation/service compares caller-supplied prices, units, quantities and transport/deduction inputs; it is not a historical-data forecast. | `test_price_discovery.py` checks calculations, unit conversions and generic errors. No DB required. |
| Price prediction | Endpoint calls a chronological linear-trend baseline over stored modal prices; minimum 60 observations spanning 90 days, with newest 20% held out for evaluation. No saved model artifact. | Tests exercise insufficient-history behavior. No genuine price dataset/artifact exists in the project inventory, so successful forecasts and metrics are unavailable until historical rows are imported. |
| Farmer lots, buyer offers, selling requests | SQLAlchemy-backed lot CRUD/status, buyer offer create/list/ownership/withdraw, farmer request negotiation and buyer accept/reject. | Selling-workflow tests cover persistence, ownership, state transitions and failures; user previously reported buyer offers/requests live as empty lists, not rechecked. |
| Transactions | DB-backed creation from accepted selling request, participant access/status workflow, duplicate prevention via unique selling-request FK. | SQLite tests cover lifecycle, ownership, invalid states and DB failures; `test_module8_workflows.py` includes mock workflow tests. Live persistence unverified. |
| Complaints | DB-backed participant complaint filing/list/detail and admin status/notes handling. | SQLite workflow tests cover creation, privacy, invalid references, admin resolution and errors. Live persistence unverified. |
| Notifications | DB-backed recipient list/read/unread operations; internal workflow helper creates notifications. There is no public notification-create endpoint. | SQLite tests cover recipient scope, read behavior, invalid recipient and DB failures. Live persistence unverified. |

Do not treat a green isolated test suite as a live integration result. The project contains no actual historical price dataset or trained model; local price test fixtures are test-only examples and were not used for forecasts.

## 6. Testing status

The latest verified safe regression run recorded during the preceding audit was:

```text
python -m pytest -p no:cacheprovider tests/test_security.py tests/test_price_discovery.py tests/test_module8_workflows.py tests/test_selling_workflow.py tests/test_profiles.py tests/test_crops_markets_prices.py tests/test_main.py -q
152 passed, 1 warning
```

The warning was Starlette's deprecation notice about using `httpx` with `starlette.testclient`. This was an isolated automated run, not PostgreSQL or frontend verification. This documentation task did not rerun tests. `tests/test_auth.py`, `tests/test_config.py`, `tests/test_database.py`, `tests/test_dependencies.py`, and `tests/test_provision_admin.py` were not part of that run; test files exist for them. No live DB check was made.

## 7. Handoff priorities and known limitations

1. Have the database owner verify the live revision/schema against the ORM and approved migration before any demo write. Do not invoke the destructive downgrade.
2. Provide genuine historical mandi data, confirm its grain/units and existing crop/market catalog mapping, and manually review a CSV before invoking the importer. The importer has no schema uniqueness constraint for market-price day keys; simultaneous import jobs can race.
3. Only present forecast output after there are at least 60 observations over at least 90 days for that exact crop-market pair. Otherwise demo the existing price comparison separately and disclose that it uses supplied candidates.
4. Run a controlled live Swagger pass for auth, buyer/farmer workflow, transaction/complaint/notification, catalog and price endpoints after DB owner approval. Verify frontend integration separately; no frontend code was found here.
