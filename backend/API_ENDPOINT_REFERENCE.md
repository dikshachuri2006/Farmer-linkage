# FarmerLinkage API Endpoint Reference

**Source of truth:** routers in `app/routes`, Pydantic models in `app/schemas`, repositories/services, and `app/main.py`. All paths below use the default `API_V1_STR=/api`; changing that setting changes the prefix. The inventory contains routes actually mounted by `app.main`. There is no frontend source in the inspected file inventory.

## Runtime and status legend

- **No DB** means the route itself does not depend on PostgreSQL: `/`, `/health`, and `/api/price-discovery/compare`.
- **DB required** means the default dependency opens a SQLAlchemy request session and production repositories query/write PostgreSQL. Isolated SQLite or mock test success does not prove the configured live PostgreSQL database works.
- **DB + history** means database-backed historical rows are additionally needed; the prediction endpoint returns 422 until its history requirements are satisfied.
- **Manual DB import** describes the Python CSV importer; it is not an HTTP endpoint and never runs automatically.
- All request-body models are JSON unless marked **form**. Missing/invalid Pydantic path/query/body data normally returns 422. Bearer-protected routes return 401 for missing/invalid/expired credentials and 403 for role/operation denial, where handled by the route dependencies. Endpoints without a route-level generic DB error handler may produce FastAPI's generic 500 on an unhandled repository error; inspect actual route handling before assuming every error path is normalized.
- These routes have not been live-verified as part of this documentation task. Prior user reports of selected working buyer routes are not treated as verification of every endpoint below.

## Health

| Method and path | Purpose; request → response | Auth | Success and established errors | Runtime |
|---|---|---|---|---|
| `GET /` | Service metadata JSON: `project`, `version`, `status`, `docs` → same object. | Public | 200 | No DB |
| `GET /health` | Configuration health JSON: `status`, `environment`, `debug`. It does not probe the database. | Public | 200 | No DB |

## Authentication

| Method and path | Purpose; request → response | Auth | Success and established errors | Runtime |
|---|---|---|---|---|
| `POST /api/auth/register` | JSON `UserRegisterRequest` (`full_name`, `email`, `phone_number`, `password`, `role`) → `UserResponse` (`id`, identity/contact, role, active state, creation time). Publicly supported roles are FARMER and BUYER. | Public | 201; 409 duplicate email/phone; 400 admin role if it reaches route; 422 validation; 503 legacy pending-schema handler | DB required |
| `POST /api/auth/login` | JSON `UserLoginRequest` (`username_or_email`, `password`) → `TokenResponse` (`access_token`, `token_type`, `expires_in_minutes`, `user: UserResponse`). | Public | 200; 401 invalid credentials; 403 inactive account; 503 if user persistence reports pending schema | DB required |
| `POST /api/auth/token` | OAuth2 password form (`username`, `password`) → `OAuth2TokenResponse` (`access_token`, `token_type`). Swagger Authorize uses this route. | Public | 200; 401 invalid credentials; 403 inactive account; 503 pending schema | DB required |
| `GET /api/auth/me` | No body → `UserMeResponse` (same fields as `UserResponse`) for current authenticated account. | Bearer; any active role | 200; 401 invalid/stale token; 404 user not found; 503 auth DB unavailable | DB required |

## Profiles and verification

| Method and path | Purpose; request → response | Auth | Success and established errors | Runtime |
|---|---|---|---|---|
| `GET /api/farmer/profile` | No body → `FarmerProfileResponse` (profile/user IDs and contacts, state/district, optional taluka/village/land/coordinates, pincode, language, timestamps). | FARMER | 200; 401; 403 wrong role; 404 profile absent | DB required |
| `PUT /api/farmer/profile` | JSON `FarmerProfileUpdate` (optional state, district, taluka, village, pincode, land area, language, coordinates); also creates a missing profile only when required creation fields are supplied → `FarmerProfileResponse`. | FARMER, own profile | 200; 401/403; 404 user/profile unavailable; 422 invalid or insufficient create fields | DB required |
| `GET /api/buyer/profile` | No body → `BuyerProfileResponse` (profile/user IDs and contacts, business fields, verification state/notes, rating, count, coordinates, timestamps). | BUYER | 200; 401; 403 wrong role; 404 profile absent | DB required |
| `PUT /api/buyer/profile` | JSON `BuyerProfileUpdate` (optional business name/type, license, location/address, coordinates); upserts the authenticated buyer profile when valid → `BuyerProfileResponse`. | BUYER, own profile | 200; 401/403; 422 insufficient fields when creating or invalid input | DB required |
| `POST /api/buyer/verification` | JSON `BuyerVerificationRequest` (`license_number`, `business_name`, `business_type`, `market_address`, optional `documents_url`, `verification_notes`) → `BuyerProfileResponse`; submission puts status back to PENDING. | BUYER, own profile | 200; 401/403; 404 buyer profile absent; 422 validation; 500 database error; legacy 503 pending schema | DB required |

## Admin operations

`buyer_id` in these admin paths is the **buyer profile row ID**, not the authenticated user's ID. `farmer_id` in farmer detail is likewise the **farmer profile row ID**.

| Method and path | Purpose; request → response | Auth | Success and established errors | Runtime |
|---|---|---|---|---|
| `GET /api/admin/farmers` | Query `skip=0`, `limit=50` (1–100), optional `state`, `district` → `List[FarmerProfileResponse]`. | ADMIN | 200; 401/403; 500 DB error; legacy 503 pending schema | DB required |
| `GET /api/admin/farmers/{farmer_id}` | Positive path profile ID → `FarmerProfileResponse`. | ADMIN | 200; 401/403; 404; 500 DB error; legacy 503 | DB required |
| `GET /api/admin/buyers` | Query optional `status` (`PENDING`, `VERIFIED`, `REJECTED`, `SUSPENDED`), `skip=0`, `limit=50` (1–100) → `List[BuyerProfileResponse]`. | ADMIN | 200; 401/403; 500 DB error; legacy 503 | DB required |
| `GET /api/admin/buyers/pending` | Query `skip=0`, `limit=50` → list of pending `BuyerProfileResponse`. | ADMIN | 200; 401/403; 500 DB error; legacy 503 | DB required |
| `PUT /api/admin/buyers/{buyer_id}/approve` | Optional JSON `AdminBuyerActionRequest` (`notes`) → `BuyerProfileResponse`; marks buyer verified. | ADMIN | 200; 401/403; 404; 500 DB error; legacy 503 | DB required |
| `PUT /api/admin/buyers/{buyer_id}/reject` | Optional JSON `AdminBuyerActionRequest` (`notes`) → `BuyerProfileResponse`; marks verification rejected. | ADMIN | 200; 401/403; 404; 500 DB error; legacy 503 | DB required |
| `PUT /api/admin/buyers/{buyer_id}/suspend` | Optional JSON `AdminBuyerActionRequest` (`notes`) → `BuyerProfileResponse`; suspension also deactivates the user account. | ADMIN | 200; 401/403; 404; 500 DB error; legacy 503 | DB required |
| `GET /api/admin/transactions` | Query optional `trans_status`, `pay_status`, `skip=0`, `limit=50` (1–100) → `TransactionListResponse`. | ADMIN | 200; 401/403; 422 invalid enum/query; legacy 503 | DB required |
| `GET /api/admin/complaints` | Query optional `status`, `issue_type`, `skip=0`, `limit=50` (1–100) → `ComplaintListResponse`. | ADMIN | 200; 401/403; 422 invalid query; legacy 503 | DB required |
| `PUT /api/admin/complaints/{complaint_id}/status` | JSON `ComplaintUpdateAdmin` (optional status, admin notes, resolution summary) → `ComplaintResponse`; sends in-app notification to complainant. | ADMIN | 200; 401/403; 404; 409 workflow conflict; legacy 503 | DB required |

## Crop and market catalog

| Method and path | Purpose; request → response | Auth | Success and established errors | Runtime |
|---|---|---|---|---|
| `POST /api/crops` | JSON `CropCreate` (`name`, `category`, `standard_unit`, optional description) → `CropResponse`. | ADMIN | 201; 401/403; 409 duplicate crop name; 422 invalid input; 500 DB error | DB required |
| `GET /api/crops` | Query optional `search`, `category`; `skip=0`, `limit=50` (1–100) → `CropListResponse` (`total`, `items`, `skip`, `limit`). | Public | 200; 422 invalid query; 500 DB error; legacy 503 pending schema | DB required |
| `GET /api/crops/{crop_id}` | Positive ID → `CropResponse` (`id`, `name`, `category`, `standard_unit`, description, creation time). | Public | 200; 404 missing; 422 invalid ID; 500 DB error | DB required |
| `GET /api/markets` | Query optional `search`, `state`, `district`; `skip=0`, `limit=50` (1–100) → `MarketListResponse`. | Public | 200; 422 invalid query; 500 DB error | DB required |
| `GET /api/markets/{market_id}` | Positive ID → `MarketResponse` (`id`, name, state, district, optional code and coordinates). | Public | 200; 404 missing; 422 invalid ID; 500 DB error | DB required |

## Market prices and forecast

| Method and path | Purpose; request → response | Auth | Success and established errors | Runtime |
|---|---|---|---|---|
| `GET /api/market-prices` | Query optional `crop_id`, `market_id`, `start_date`, `end_date`; `sort_by` in `price_date`, `modal_price`, `min_price`, `max_price`, `arrival_quantity`; `sort_order=desc` or `asc`; `skip=0`, `limit=50` (1–100) → `PriceRecordListResponse` containing `PriceRecordResponse` items. | Public | 200 (including empty result); 400 reversed date range/invalid sort; 422 invalid query; generic 500 DB error | DB required |
| `GET /api/market-prices/latest` | Required `crop_id`, optional `market_id` → latest `PriceRecordResponse`. | Public | 200; 404 no matching prices; 422 invalid query; generic 500 DB error | DB required; no history gives 404 |
| `GET /api/market-prices/{price_id}` | Positive price ID → `PriceRecordResponse` (record IDs/names/location, date, min/max/modal, optional arrivals, explicit units/source). | Public | 200; 404 missing; 422 invalid ID; generic 500 DB error | DB required |
| `GET /api/price-predictions` | Required `crop_id`, `market_id`; optional `horizon_days=7` (1–30) → `PricePredictionResponse` (`predicted_modal_price`, unit, model, as-of date, train/evaluation counts, MAE and optional MAPE). | Public | 200 only if adequate consistent-unit price history; 404 crop/market absent; 422 invalid horizon, no/insufficient history, inconsistent units; generic 500 SQLAlchemy error | DB + history |

Prediction uses current DB rows and does chronological 80/20 holdout evaluation before refitting on all data for the forecast. It requires at least 60 rows spanning at least 90 days for the selected crop-market. No trained artifact or genuine historical data was found in the project inventory; successful forecast response and meaningful metrics remain unverified. The price APIs are public by current route design.

### Manual CSV ingestion (not an endpoint)

`app.services.price_importer.import_market_prices_csv(db, file, *, source, price_unit=None, arrival_unit=None)` is called explicitly by trusted code/operators. Required CSV headers are `Commodity` (or `Crop`), `Market` (or `Mandi`), `State`, `District`, `Arrival_Date` (or `Price_Date`/`Date`), `Min_Price` (or `Minimum_Price`), `Max_Price` (or `Maximum_Price`), and `Modal_Price`. `Price_Unit` is optional as a column only if `price_unit=` is supplied. `Arrival_Quantity`, `Arrival_Unit`, and `Source` are optional. Dates accepted: ISO `YYYY-MM-DD`, `DD/MM/YYYY`, `DD-MM-YYYY`; units accepted: `INR/kg`, `INR/Quintal`, `INR/tonne`. Crop/market must already exist. It is atomic and duplicate-aware for sequential use, but the current database schema has no unique natural key to serialize concurrent imports. No import was run for this handoff.

## Price discovery

| Method and path | Purpose; request → response | Auth | Success and established errors | Runtime |
|---|---|---|---|---|
| `POST /api/price-discovery/compare` | JSON `PriceComparisonRequest` (`crop_name`, positive `sale_quantity`, quantity unit, optional farmer location/coordinates, candidate options); each `MarketOptionInput` can include price/unit, location/distance, supplied transport, rate override and charges → `PriceComparisonResponse` with ranked realization options, estimated deductions and best option. | Public | 200; 422 validation/calculation error; generic 500 internal calculation/transport failure | No DB; uses request-supplied candidate values, not historic-price records |

## Farmer lots and selling requests

| Method and path | Purpose; request → response | Auth | Success and established errors | Runtime |
|---|---|---|---|---|
| `POST /api/farmer/lots` | JSON `FarmerLotCreate` (crop ID/name, quantity/unit, quality, expected price/unit, harvest date, location) → `FarmerLotResponse`. | FARMER; own account | 201; 401/403; 404 crop missing; 409 lot workflow conflict; 422 invalid input | DB required |
| `GET /api/farmer/lots` | Query `skip=0`, `limit=50` (1–100) → `FarmerLotListResponse`, scoped to current farmer. | FARMER; own account | 200; 401/403; 422; generic DB failure handler in route/repository | DB required |
| `GET /api/farmer/lots/{lot_id}` | Positive ID → `FarmerLotResponse`, scoped to owner. | FARMER; own account | 200; 401/403; 404 not found/not owned; 422 invalid ID; generic DB error | DB required |
| `PUT /api/farmer/lots/{lot_id}` | JSON `FarmerLotUpdate` (optional quantity, grade, price, location, status) → `FarmerLotResponse`. Status COMMITTED/SOLD is workflow-managed. | FARMER; owner | 200; 401/403; 404; 409 committed/sold/invalid transition; 422; generic DB failure | DB required |
| `DELETE /api/farmer/lots/{lot_id}` | Soft-withdraw/deactivate lot → `FarmerLotResponse`. | FARMER; owner | 200; 401/403; 404; 409 committed/sold; 422; generic DB failure | DB required |
| `GET /api/farmer/lots/{lot_id}/offers` | Lists current active/unexpired offers on farmer-owned lot → `List[BuyerOfferResponse]`. | FARMER; owns lot | 200; 401/403; 404 lot absent/not owned; DB required | DB required |
| `POST /api/farmer/selling-requests` | JSON `SellingRequestCreate` (`lot_id`, target `buyer_id` as users.id, proposed price/unit, quantity/unit, estimated costs, optional message) → `SellingRequestResponse`. | FARMER; own lot | 201; 401/403; 400 quantity exceeds lot; 404 lot/buyer missing; 409 unavailable/workflow conflict; 422 invalid input | DB required |
| `GET /api/farmer/selling-requests` | Query `skip=0`, `limit=50` (1–100) → `SellingRequestListResponse`, scoped to farmer. | FARMER | 200; 401/403; 422; 503 legacy pending schema | DB required |
| `POST /api/farmer/selling-requests/{request_id}/action` | JSON `SellingRequestActionRequest` (`action`: ACCEPT/REJECT/COUNTER/CANCEL; optional counter price/quantity and reason) → `SellingRequestResponse`. Farmer-side actions follow service transition rules. | FARMER; request owner | 200; 401/403; 404; 409 invalid transition; 422 body/path | DB required |

## Buyer offers and requests

| Method and path | Purpose; request → response | Auth | Success and established errors | Runtime |
|---|---|---|---|---|
| `GET /api/buyer/profile` | No body → current buyer's `BuyerProfileResponse`. | BUYER; own profile | 200; 401/403; 404 profile missing; legacy 503 | DB required |
| `PUT /api/buyer/profile` | JSON `BuyerProfileUpdate` → create/update own `BuyerProfileResponse`. | BUYER; own profile | 200; 401/403; 422 create fields/input; legacy 503 | DB required |
| `POST /api/buyer/verification` | JSON `BuyerVerificationRequest` → profile in PENDING status. | BUYER; own profile | 200; 401/403; 404 profile missing; 422; 500/503 DB paths | DB required |
| `POST /api/buyer/offers` | JSON `BuyerOfferCreate` (`lot_id`, price/unit, requested quantity/unit, pickup flag, delivery location, optional expiry/terms) → `BuyerOfferResponse` (includes derived buyer/crop names and total value). | BUYER; verified buyer; creates as current user | 201; 401/403 unverified/wrong role; 400 quantity exceeds lot; 404 unavailable lot; 409 workflow conflict; 422; legacy 503 | DB required |
| `GET /api/buyer/offers` | Query `skip=0`, `limit=50` (1–100) → `BuyerOfferListResponse`, scoped to buyer. | BUYER | 200; 401/403; 422; legacy 503 | DB required |
| `GET /api/buyer/offers/{offer_id}` | Positive ID → own `BuyerOfferResponse`; other buyer's record is masked as 404. | BUYER; owner | 200; 401/403; 404 absent/not owned; 422; legacy 503 | DB required |
| `DELETE /api/buyer/offers/{offer_id}` | Withdraw offer → `BuyerOfferResponse`. | BUYER; owner | 200; 401/403; 404 absent/not owned; 409 already accepted; legacy 503 | DB required |
| `GET /api/buyer/requests` | Query `skip=0`, `limit=50` (1–100) → `SellingRequestListResponse`, scoped to buyer. | BUYER | 200; 401/403; 422; legacy 503 | DB required |
| `GET /api/buyer/requests/{request_id}` | Positive ID → buyer-owned `SellingRequestResponse`. | BUYER; recipient | 200; 401/403; 404 absent/not addressed to buyer; 422; legacy 503 | DB required |
| `POST /api/buyer/requests/{request_id}/accept` | No body → accepted `SellingRequestResponse`; service also commits/locks lot according to workflow. | BUYER; recipient | 200; 401/403; 404; 409 invalid state/concurrent conflict; 422 path; legacy 503 | DB required |
| `POST /api/buyer/requests/{request_id}/reject` | Optional `notes` query parameter → rejected `SellingRequestResponse`. | BUYER; recipient | 200; 401/403; 404; 409 invalid state; 422; legacy 503 | DB required |

## Transactions

| Method and path | Purpose; request → response | Auth | Success and established errors | Runtime |
|---|---|---|---|---|
| `POST /api/transactions` | JSON `TransactionCreate` (`selling_request_id`, optional payment method and notes) → `TransactionResponse`; request must be ACCEPTED; emits notifications. | Bearer FARMER/BUYER participant or ADMIN | 201; 401; 403 nonparticipant; 404 missing request; 400 request not accepted; 409 duplicate/workflow; 422 invalid body; legacy 503 | DB required |
| `GET /api/transactions` | Query `skip=0`, `limit=50` (1–100) → `TransactionListResponse`, scoped to authenticated user/role. | Bearer FARMER or BUYER; admin has separate list | 200; 401; 422; legacy 503 | DB required |
| `GET /api/transactions/{transaction_id}` | Positive ID → `TransactionResponse`. | Bearer participant or ADMIN | 200; 401; 403 nonparticipant; 404 missing; 422; legacy 503 | DB required |
| `PUT /api/transactions/{transaction_id}/status` | JSON `TransactionStatusUpdate` (optional transaction/payment status, notes) → updated `TransactionResponse`; valid transitions and role-specific rights are enforced. Farmers may mark IN_TRANSIT, buyers may mark DELIVERED/COMPLETED and initiate/hold escrow payment; admins may administer statuses subject to workflow. | Bearer participant or ADMIN | 200; 401; 403 unauthorized status action; 404; 409 invalid transition; 422; legacy 503 | DB required |

## Complaints and notifications

| Method and path | Purpose; request → response | Auth | Success and established errors | Runtime |
|---|---|---|---|---|
| `POST /api/complaints` | JSON `ComplaintCreate` (optional transaction/respondent IDs, issue type, title, description) → `ComplaintResponse`; linked transaction must exist and caller must be participant unless ADMIN; notifies respondent when set. | Bearer any role; transaction participant/admin when linked | 201; 401; 403 nonparticipant; 404 missing transaction/reference; 409 workflow; 422 invalid input; legacy 503 | DB required |
| `GET /api/complaints` | Query `skip=0`, `limit=50` (1–100) → `ComplaintListResponse` scoped to complainant. | Bearer any role | 200; 401; 422; legacy 503 | DB required |
| `GET /api/complaints/{complaint_id}` | Positive ID → `ComplaintResponse`; visible to complainant, respondent, ADMIN. | Bearer any role, then party/admin check | 200; 401; 403 nonparty; 404 missing; 422; legacy 503 | DB required |
| `GET /api/notifications` | Query `unread_only=false`, `skip=0`, `limit=50` (1–100) → `NotificationListResponse` (`total`, `unread_count`, items, pagination), scoped to recipient. | Bearer any active role | 200; 401; 422; legacy 503 | DB required |
| `PUT /api/notifications/{notification_id}/read` | Positive ID → own `NotificationResponse` marked read. | Bearer; recipient only | 200; 401; 404 missing/not owned; 422; legacy 503 | DB required |
| `PUT /api/notifications/mark-all-read` | No body → `{status, message, marked_count}` for current user's unread notifications. | Bearer; own inbox | 200; 401; legacy 503 | DB required |

Notification creation is an internal repository/service operation invoked by workflows; `NotificationCreate` exists as a schema, but no public create route is mounted.

## Schema references

Pydantic models are defined in `app/schemas`: `UserRegisterRequest`, `UserLoginRequest`, `UserResponse`, `TokenResponse`, `OAuth2TokenResponse`, `UserMeResponse`; `FarmerProfileCreate/Update/Response`; `BuyerProfileCreate/Update/VerificationRequest/AdminBuyerActionRequest/ProfileResponse`; `CropCreate/Response/ListResponse`; `MarketResponse/ListResponse`; `PriceRecordResponse/ListResponse`; `PricePredictionResponse`; `PriceComparisonRequest/Response`, `MarketOptionInput`, `MarketRealizationOption`; `FarmerLotCreate/Update/Response/ListResponse`; `BuyerOfferCreate/Update/Response/ListResponse`; `SellingRequestCreate/ActionRequest/Response/ListResponse`; `TransactionCreate/StatusUpdate/Response/ListResponse`; `ComplaintCreate/UpdateAdmin/Response/ListResponse`; and `NotificationCreate/Response/ListResponse`. Consult those schemas for exact field validation and enum literals; the endpoint tables identify which models are consumed or returned.

## Demo readiness boundaries

The repository includes no genuine historical mandi dataset or trained model artifact. For price reads, the catalog and `market_prices` tables must exist and contain reviewed source rows. The prediction route additionally needs at least 60 observations over at least 90 calendar days for a single crop-market and a consistent price unit. The CSV importer must be explicitly invoked after matching crop/market records exist; it does not create catalog data, seed sample rows, or run at application startup. All PostgreSQL-backed endpoints and frontend integration require separate live verification; automated SQLite tests do not establish either.
