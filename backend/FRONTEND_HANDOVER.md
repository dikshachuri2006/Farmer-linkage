# FarmerLinkage backend frontend handover

This document describes the checked-in FastAPI contract and current backend behavior. OpenAPI at `/api/openapi.json` is the runtime source of truth if a response differs from an example here.

## Setup and start

Run these commands in PowerShell from `D:\Farmerlinkage\backend`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` locally with a real PostgreSQL connection and a unique random `SECRET_KEY` of at least 32 characters. Do not send `.env`, database passwords, JWTs, or `.venv` when sharing source. For `ENVIRONMENT=demo` or `production`, set `DEBUG=False`; settings reject the placeholder/short JWT secret and debug mode in these environments. Configure `ALLOWED_ORIGINS` as a JSON array for the frontend origin(s). Environment variable names are `ENVIRONMENT`, `DEBUG`, `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `POSTGRES_SERVER`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, optional `DATABASE_URL`, and `ALLOWED_ORIGINS` (plus optional transport/maps settings shown in `.env.example`).

The repository currently has Alembic revisions `20261024_0001` and `20261024_0002`. After checking the target database backup and connection settings, apply pending migrations with:

```powershell
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Migration commands were documented but were **not run** during this handoff. Do not use `alembic downgrade` as a rollback plan without reviewing the migration: the initial revision's downgrade removes schema objects. Backend base URL for local frontend is `http://127.0.0.1:8000`; OpenAPI/Swagger UI is `http://127.0.0.1:8000/api/docs`, ReDoc is `/api/redoc`, raw schema is `/api/openapi.json`.

## Authentication and roles

Register a FARMER or BUYER with `POST /api/auth/register`, then sign in with `POST /api/auth/login` using email **or** Indian mobile number and password. Send the returned access token on protected calls:

```http
Authorization: Bearer <access_token>
```

Tokens are signed JWTs with expiry. Authenticated requests look up the current user from the user repository and reject missing/inactive users and tokens whose role no longer matches the stored role. `/api/auth/token` accepts OAuth2 form fields (`username`, `password`) for Swagger's Authorize dialog. Public registration cannot create ADMIN. Administrators must be provisioned separately using the existing admin provisioning instructions/tool.

Role summary:

| Role | Main access |
|---|---|
| Public | Register/login; list/read crops, markets and prices; price discovery; health |
| FARMER | Own profile/lots/selling requests; view offers on own lots and accept them; participant transactions/complaints/notifications |
| BUYER | Own profile and verification submission; offers after buyer verification; own requests and accepted/rejected responses; participant transactions/complaints/notifications |
| ADMIN | Farmer/buyer administration, buyer verification decisions, admin complaint resolution and transaction/complaint listings |

Protected routes generally return `401` for invalid/expired/inactive/stale-role credentials and `403` when an authenticated role lacks permission. Ownership-scoped records commonly return `404` to avoid confirming another user's record exists.

## Endpoint inventory

`{schema}` below names the exact Pydantic request/response model where applicable. All paths are under `/api`. Query pagination uses `skip` (default 0) and `limit` (default 50, max 100) unless stated. Read-only crop/market/price routes are public; other access follows the roles shown. Success examples are abbreviated to convey the response shape; consult OpenAPI for every field and enum.

### Health and authentication

| Method and path | Purpose, parameters/body → response | Access; common outcomes |
|---|---|---|
| `GET /` | Health/service metadata → object (`project`, `version`, `status`, `docs`) | Public; `200` |
| `GET /health` | Health check → status object | Public; `200` |
| `POST /auth/register` | `{UserRegisterRequest}` → `{UserResponse}` | Public; `201`, `400` public ADMIN registration, `409` duplicate, `422` invalid |
| `POST /auth/login` | `{UserLoginRequest}` (`username_or_email`, `password`) → `{TokenResponse}` (`access_token`, `token_type`, `expires_in_minutes`, `user`) | Public; `200`, `401` bad credentials, `403` inactive, `503` database unavailable/schema issue |
| `POST /auth/token` | OAuth2 form `username`, `password` → `{OAuth2TokenResponse}` | Public; `200`, `401`, `403` |
| `GET /auth/me` | Current persisted user → `{UserMeResponse}` | Any authenticated role; `200`, `401`, `503` |

### Catalog, historical prices, comparison and forecast

| Method and path | Parameters/body → response | Access; common outcomes |
|---|---|---|
| `POST /crops` | `{CropCreate}` → `{CropResponse}` | ADMIN; `201`, `409`, `422`, `500` |
| `GET /crops` | `search`, `category`, `skip`, `limit` → `{CropListResponse}` | Public; `200`, `422`, DB errors |
| `GET /crops/{crop_id}` | Crop ID → `{CropResponse}` | Public; `200`, `404` |
| `GET /markets` | `search`, `state`, `district`, `skip`, `limit` → `{MarketListResponse}` | Public; `200`, `500` |
| `GET /markets/{market_id}` | Market ID → `{MarketResponse}` | Public; `200`, `404`, `500` |
| `GET /market-prices` | Optional `crop_id`, `market_id`, `start_date`, `end_date`, `variety`, `grade`; `sort_by`, `sort_order`, `skip`, `limit` → `{PriceRecordListResponse}` | Public; `200`, `400` reversed dates/invalid sort, `500` |
| `GET /market-prices/latest` | Required `crop_id`, optional `market_id`, `variety`, `grade` → `{PriceRecordResponse}` | Public; `200`, `404`, `500` |
| `GET /market-prices/{price_id}` | Price record ID → `{PriceRecordResponse}` | Public; `200`, `404`, `500` |
| `POST /price-discovery/compare` | `{PriceComparisonRequest}` → `{PriceComparisonResponse}` | Public; `200`, `400` invalid comparison, `500` generic failure. This compares values supplied in the request; it is not the forecast endpoint. |
| `GET /price-predictions` | Required `crop_id`, `market_id`; `horizon_days` 1–30 (default 7); optional `variety`, `grade` → `{PricePredictionResponse}` | Public; `200`, `404` catalog ID missing, `422` insufficient/ambiguous/inconsistent history, `500` DB/model error |

Price filters use ISO dates `YYYY-MM-DD`. Money fields are decimal-like numeric values; imported modal/min/max prices retain the declared `price_unit`. Arrival quantity and `arrival_unit` are not inferred or converted. The importer requires exact crop and market/state/district catalog matches; it does not merge market spellings. Variety and grade are separate series dimensions.

Forecast is a simple chronological linear trend. It requires at least 60 observations spanning 90 days per crop/market/variety/grade series. The newest chronological 20% is held out for MAE/MAPE evaluation; the final prediction refits on available history. It does not invent observations. No model artifact is persisted; the endpoint computes from database history on each request. Metrics are diagnostics, not accuracy guarantees.

### Farmer and buyer workflows

| Method and path | Parameters/body → response | Access; common outcomes |
|---|---|---|
| `GET /farmer/profile` | Current farmer → `{FarmerProfileResponse}` | FARMER; `200`, `404` |
| `PUT /farmer/profile` | `{FarmerProfileUpdate}` → `{FarmerProfileResponse}` | FARMER; `200`, `404`, `422` |
| `POST /farmer/lots` | `{FarmerLotCreate}` → `{FarmerLotResponse}` | FARMER; `201`, `404` crop, `422` |
| `GET /farmer/lots` | `skip`, `limit` → `{FarmerLotListResponse}` | FARMER; `200` |
| `GET /farmer/lots/{lot_id}` | Own lot → `{FarmerLotResponse}` | FARMER owner; `200`, `404` |
| `PUT /farmer/lots/{lot_id}` | `{FarmerLotUpdate}` → `{FarmerLotResponse}` | FARMER owner; `200`, `404`, `409` workflow-managed status |
| `DELETE /farmer/lots/{lot_id}` | Withdraw own lot → `{FarmerLotResponse}` | FARMER owner; `200`, `404`, `409` committed/sold |
| `GET /farmer/lots/{lot_id}/offers` | Active/unexpired lot offers → array of `{BuyerOfferResponse}` | FARMER owner; `200`, `404` |
| `POST /farmer/offers/{offer_id}/accept` | Accept offer → `{OfferAcceptanceResponse}` containing `offer` and `selling_request` | FARMER owning lot; `200`, `404`, `409`, `401/403`, `503` |
| `POST /farmer/selling-requests` | `{SellingRequestCreate}` → `{SellingRequestResponse}` | FARMER; `201`, `404` buyer/lot, `409` invalid state/unit, `422` invalid body |
| `GET /farmer/selling-requests` | `skip`, `limit` → `{SellingRequestListResponse}` | FARMER; `200` |
| `POST /farmer/selling-requests/{request_id}/action` | `{SellingRequestActionRequest}` (`ACCEPT`, `REJECT`, `COUNTER`, `CANCEL`) → `{SellingRequestResponse}` | FARMER participant; `200`, `404`, `409`, `422` |
| `GET /buyer/profile` | Current buyer → `{BuyerProfileResponse}` | BUYER; `200`, `404` |
| `PUT /buyer/profile` | `{BuyerProfileUpdate}` → `{BuyerProfileResponse}` | BUYER owner; `200`, `404`, `422` |
| `POST /buyer/verification` | `{BuyerVerificationRequest}` → `{BuyerProfileResponse}` | BUYER owner; `200`, `404`, `409`, `422` |
| `POST /buyer/offers` | `{BuyerOfferCreate}` → `{BuyerOfferResponse}` | Verified BUYER; `201`, `404` lot, `409` unavailable/invalid units, `403` unverified |
| `GET /buyer/offers` | `skip`, `limit` → `{BuyerOfferListResponse}` | BUYER's offers; `200` |
| `GET /buyer/offers/{offer_id}` | Own offer → `{BuyerOfferResponse}` | BUYER owner; `200`, `404` |
| `DELETE /buyer/offers/{offer_id}` | Withdraw own offer → `{BuyerOfferResponse}` | BUYER owner; `200`, `404`, `409` accepted offer |
| `GET /buyer/requests` | `skip`, `limit` → `{SellingRequestListResponse}` | BUYER's requests; `200` |
| `GET /buyer/requests/{request_id}` | Own request → `{SellingRequestResponse}` | BUYER participant; `200`, `404` |
| `POST /buyer/requests/{request_id}/accept` | Accept request → `{SellingRequestResponse}` | BUYER participant; `200`, `404`, `409` invalid transition |
| `POST /buyer/requests/{request_id}/reject` | Optional `notes` query → `{SellingRequestResponse}` | BUYER participant; `200`, `404`, `409` |

**Offer-to-transaction sequence:** a verified buyer creates an offer for an available farmer lot; the owning farmer views it and calls `/farmer/offers/{offer_id}/accept`. The backend atomically marks the offer accepted, commits the lot, and creates an ACCEPTED selling request linked by `buyer_offer_id`. A participant then creates the digital transaction using `POST /transactions` with that selling request ID. One offer can create only one linked request; one selling request can create only one transaction.

### Transactions, disputes, notifications and administration

| Method and path | Parameters/body → response | Access; common outcomes |
|---|---|---|
| `POST /transactions` | `{TransactionCreate}` → `{TransactionResponse}` | Authenticated participant/admin; `201`, `400` request not accepted, `403`, `404`, `409` duplicate, `503` |
| `GET /transactions` | `skip`, `limit` → `{TransactionListResponse}` | Authenticated user's transactions; `200` |
| `GET /transactions/{transaction_id}` | Transaction → `{TransactionResponse}` | Participant/admin; `200`, `403`, `404` |
| `PUT /transactions/{transaction_id}/status` | `{TransactionStatusUpdate}` → `{TransactionResponse}` | Participant/admin with role-specific transitions; `200`, `403`, `404`, `409` |
| `POST /complaints` | `{ComplaintCreate}` → `{ComplaintResponse}` | Authenticated user; `201`, `403` nonparticipant, `404` invalid reference, `409`, `422` |
| `GET /complaints` | `skip`, `limit` → `{ComplaintListResponse}` | Authenticated complainant's own tickets; `200` |
| `GET /complaints/{complaint_id}` | Complaint → `{ComplaintResponse}` | Complainant/respondent/admin; `200`, `403`, `404` |
| `GET /notifications` | `unread_only`, `skip`, `limit` → `{NotificationListResponse}` | Any authenticated user, own inbox; `200` |
| `PUT /notifications/{notification_id}/read` | Mark own notification read → `{NotificationResponse}` | Authenticated owner; `200`, `404` |
| `PUT /notifications/mark-all-read` | No body → `{status,message,marked_count}` | Authenticated user's inbox; `200` |
| `GET /admin/farmers` | Farmer profiles → array of `{FarmerProfileResponse}` | ADMIN; `200`, `403` |
| `GET /admin/farmers/{farmer_id}` | Farmer profile → `{FarmerProfileResponse}` | ADMIN; `200`, `404`, `403` |
| `GET /admin/buyers` | Buyer profiles → array of `{BuyerProfileResponse}` | ADMIN; `200`, `403` |
| `GET /admin/buyers/pending` | Pending verification profiles → array of `{BuyerProfileResponse}` | ADMIN; `200`, `403` |
| `PUT /admin/buyers/{buyer_id}/approve` | Optional `{AdminBuyerActionRequest}` → `{BuyerProfileResponse}` | ADMIN; `200`, `404`, `409`, `403` |
| `PUT /admin/buyers/{buyer_id}/reject` | Optional `{AdminBuyerActionRequest}` → `{BuyerProfileResponse}` | ADMIN; `200`, `404`, `409`, `403` |
| `PUT /admin/buyers/{buyer_id}/suspend` | Optional `{AdminBuyerActionRequest}` → `{BuyerProfileResponse}` | ADMIN; `200`, `404`, `409`, `403` |
| `GET /admin/transactions` | `skip`, `limit` → `{TransactionListResponse}` | ADMIN; `200`, `403` |
| `GET /admin/complaints` | `skip`, `limit` → `{ComplaintListResponse}` | ADMIN; `200`, `403` |
| `PUT /admin/complaints/{complaint_id}/status` | `{ComplaintUpdateAdmin}` → `{ComplaintResponse}` | ADMIN; `200`, `404`, `409`, `403` |

## Schemas and response examples

OpenAPI includes all properties, required fields, bounds, enums, and OAuth2 security metadata. Example common responses:

```json
{"access_token":"<JWT>","token_type":"bearer","expires_in_minutes":1440,"user":{"id":42,"full_name":"Example","email":"person@example.test","phone_number":"9876543210","role":"BUYER","is_active":true,"created_at":"2026-01-01T00:00:00Z"}}
```

```json
{"total":1,"items":[{"id":1,"crop_id":1,"crop_name":"Onion","market_id":1,"market_name":"Example APMC","price_date":"2026-05-30","min_price":1000,"max_price":1600,"modal_price":1300,"price_unit":"INR/Quintal","variety":"Red","grade":"Local","arrival_quantity":12,"arrival_unit":"Metric Tonnes","source":"source-label"}],"skip":0,"limit":50}
```

Errors use FastAPI's `{"detail":"..."}` shape (validation errors may be arrays of field errors). Common codes are `401`, `403`, `404`, `409`, `422`, and `500/503` as listed above. Price discovery returns its result schema with ranked options and calculation breakdown; inspect the OpenAPI component `PriceComparisonResponse` before binding a UI.

## Price import and current historical data status

The importer is explicit and never runs at server startup. Its required columns map to crop/commodity, market, state, district, date, min price, max price, modal price; optional dimensions include variety, grade, arrival quantity/unit, source, and price unit. The price unit is mandatory in the CSV or CLI argument. It matches existing crop and market catalog records exactly (case-insensitive names plus state and district), stages and validates all rows, skips identical duplicates, rejects conflicts, and commits atomically only with `--apply`.

Dry-run example (requires catalog rows in the configured DB, but rolls back imported prices):

```powershell
python -m app.scripts.import_market_prices --file "C:\data\historical_prices.csv" --source "source name and retrieval date" --price-unit INR/Quintal --arrival-unit "Metric Tonnes"
```

To persist a reviewed import, add `--apply`; review the printed counts and the source file/catalog mapping first. Never run this against the demo database until the team has confirmed provenance, market names, varieties, date format and units.

Two locally supplied Lasalgaon onion CSVs were inspected during implementation. The older file has 1,252 dates (2021-01-01 through 2025-10-24), but has **no declared price unit**, so it was not imported or used for forecasts. The newer file has 599 rows (2025-10-27 through 2026-05-30), includes `price_unit=Rs./Quintal`, and records three separate market names (Lasalgaon Apmc, Lasalgaon(Niphad) Apmc, Lasalgaon(Vinchur) Apmc), as well as Other/Red/Unhali variety groups and Local grade. It was validated in an in-memory SQLite dry run only (599 inserted in the temporary transaction, then discarded); PostgreSQL was not modified. Source provenance has not been independently authenticated. Forecast endpoint performance should therefore be demonstrated only after a reviewer confirms and imports the intended dataset.

The baseline was also evaluated against the newer local file using chronological 80/20 holdouts. Example MAEs were Lasalgaon APMC/Other **₹72.49 per quintal** (17 holdout observations), Lasalgaon APMC/Red **₹282.74 per quintal** (20), Niphad APMC/Red **₹87.23 per quintal** (18), and Vinchur APMC/Red **₹344.91 per quintal** (20). Red-series MAPE ranged from about 10.56% in Niphad to 40.43% in Vinchur; Lasalgaon APMC/Other MAPE was 6.92%. Unhali series were below the minimum-history threshold. This variation shows the baseline is a demonstration, not a reliability claim; do not present it as accurate.

## Verification and known blockers

- Unit and isolated SQLite tests exercise routes, repository workflows, importer validation, and forecasting; they do not prove the configured PostgreSQL schema is migrated or reachable.
- During this implementation, no migration was applied, no live database connection was made, and no frontend integration request was made.
- Apply revision `20261024_0002` before using the new `market_prices.variety`/`grade` dimensions and `selling_requests.buyer_offer_id` association on an existing database.
- Two-row variant date duplicates are supported only when variety/grade differ; exact duplicates are de-duplicated or skipped. The older CSV's missing unit remains a manual provenance question.
- Forecast coverage is per crop/market/variety/grade. Series below 60 records or 90 days return `422`. Even a qualifying series may have poor error metrics; display the metric and as-of date rather than implying certainty.
- Backend CORS, PostgreSQL connectivity, migration application, Swagger requests against live data, and frontend rendering remain to be verified in the demo environment.

