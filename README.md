# FarmerLinkage

> **Connecting Farmers Directly with Buyers**
> Digital Agricultural Marketplace for SIH26132: Strengthening Market Linkage and Price Discovery of Farmers.

FarmerLinkage is a production-grade, multi-page agricultural web application designed to empower farmers with transparent price discovery, direct connections to commercial buyers, and formal electronic settlement records.

---

## 1. Project Architecture & File Structure

```text
FarmerLinkage/
│
├── index.html                   # Homepage (Hero, image cards, about, how-it-works, prices intro, CTA)
├── login.html                   # Dedicated sign-in page with role-based routing
├── register.html                # Role-based registration (Farmer or Commercial Buyer)
├── about.html                   # Mission, agricultural challenges, and benefits
├── contact.html                 # Inquiries, platform notices, and ticket redirection
├── marketplace.html             # Farmgate produce listings discovery and multi-parameter filtering
├── market-prices.html           # Official APMC mandi arrival prices and modal rates
├── price-discovery.html         # Interactive net-realization calculator across mandis & buyer bids
├── listing-details.html         # Detailed produce lot specifications and buyer offer submission
├── not-found.html               # 404 error page
│
├── farmer.html                  # Farmer dashboard (overview metrics, recent lots & offers)
├── farmer-profile.html          # Farmer landholding and farmgate location profile
├── farmer-produce.html          # Producer lot management (active listings, details, withdraw)
├── add-produce.html             # New produce lot posting form
├── farmer-offers.html           # Review received commercial buyer offers & accept action
│
├── buyer.html                   # Buyer procurement dashboard (metrics, activity)
├── buyer-profile.html           # Buyer commercial entity profile & verification request
├── buyer-offers.html           # Submitted purchase offers and status tracking
│
├── transactions.html            # Trade settlement ledger & ReportLab PDF receipt download
│
├── admin.html                   # Administrator dashboard
├── admin-users.html             # User directory (farmers and commercial buyers)
├── admin-verification.html      # Buyer verification approval and rejection management
├── admin-markets.html           # APMC mandi registry
├── admin-reports.html           # Real-time analytical data exports (JSON/CSV)
│
├── css/
│   ├── styles.css               # Design system tokens, variables, typography, and layout
│   ├── components.css           # Buttons, cards, forms, tables, badges, toasts, and modals
│   ├── public.css               # Strict public navbar, hero, cards, and footer
│   ├── auth.css                 # Clean card styling for login and registration
│   ├── marketplace.css          # Listing cards, detail views, and realization output
│   └── dashboard.css            # Responsive sidebar, top header, and stat cards
│
├── js/
│   ├── config.js                # Centralized API base URL and role configuration
│   ├── api.js                   # Unified Fetch API client with Bearer auth and blob downloads
│   ├── utils.js                 # XSS-safe escaping, INR currency formatting, and toasts
│   ├── auth.js                  # Token storage, session manager, and route guards
│   ├── navigation.js            # Strict navbar, footer, and role-based dashboard navigation
│   ├── i18n.js                  # Multilingual translation engine (English, Marathi, Hindi)
│   ├── homepage.js              # Homepage dynamic logic
│   ├── marketplace.js           # Produce discovery and buyer offer modal
│   ├── market-prices.js         # APMC mandi price browser
│   ├── price-discovery.js       # Live net-realization algorithm client
│   ├── farmer.js                # Farmer portal logic
│   ├── buyer.js                 # Buyer procurement logic
│   ├── transactions.js          # Trade settlement and PDF receipt downloads
│   └── admin.js                 # Administrative controls and data exports
│
├── assets/
│   ├── images/
│   │   ├── hero_farmer_field.jpg
│   │   ├── fresh_vegetables.jpg
│   │   ├── grains_cereals.jpg
│   │   └── farmers_farming.jpg
│   └── logo/
│       └── logo.svg             # Vector logo
│
└── backend/                     # FastAPI backend application
```

---

## 2. Prerequisites & Installation

- **Frontend**: Any modern web browser (Chrome, Edge, Firefox, Safari) and a static file server (Python `http.server` or Node `serve` / `npx http-server`).
- **Backend**: Python 3.10+ (tested on Python 3.13) with dependencies in `backend/requirements.txt`.
- **Database**: PostgreSQL (for persistent user accounts and mandi datasets).

---

## 3. How to Run Locally

### 3.1 Start Frontend Server

From the project root (`c:\Users\DIKSHA CHURI\OneDrive\Desktop\Farmer linkage`):

```powershell
python -m http.server 3000
```

Open your browser to: **`http://localhost:3000/index.html`**

### 3.2 Start FastAPI Backend

From the `backend` directory:

```powershell
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

- **API Base URL**: `http://127.0.0.1:8000/api`
- **Swagger Documentation**: `http://127.0.0.1:8000/api/docs`
- **ReDoc**: `http://127.0.0.1:8000/api/redoc`

---

## 4. API Configuration & Centralized Client

The frontend communicates with the backend via `js/config.js`:

```javascript
const CONFIG = {
  API_BASE_URL: window.API_BASE_URL || 'http://127.0.0.1:8000/api',
  ...
};
```

To configure a production or staging backend without modifying code, set `window.API_BASE_URL` prior to script execution or update `CONFIG.API_BASE_URL` in `js/config.js`.

---

## 5. Authentication & Authorization

Authentication is built around JSON Web Tokens (JWT) issued by `POST /api/auth/login`:
- Tokens are stored in browser `localStorage` as `farmerlinkage_token`.
- User profiles are sanitized and stored as `farmerlinkage_user`.
- Passwords are **never** stored in browser storage.
- Protected API calls attach `Authorization: Bearer <token>`.
- Client-side route guards enforce role access:
  - `FARMER` &rarr; `farmer.html`
  - `BUYER` &rarr; `buyer.html`
  - `ADMIN` &rarr; `admin.html`
- Expired or invalid tokens automatically clear the session and prompt for re-authentication.

---

## 6. Page-to-API Capability Matrix

| Page | Primary Backend Endpoints Used | Status |
|---|---|---|
| `index.html` | `GET /api/market-prices` (preview) | Connected |
| `login.html` | `POST /api/auth/login`, `GET /api/auth/me` | Connected |
| `register.html` | `POST /api/auth/register` | Connected |
| `marketplace.html` | `GET /api/marketplace/lots`, `GET /api/crops` | Connected |
| `listing-details.html`| `GET /api/marketplace/lots`, `POST /api/buyer/offers` | Connected |
| `market-prices.html` | `GET /api/market-prices`, `GET /api/crops`, `GET /api/markets` | Connected |
| `price-discovery.html`| `POST /api/price-discovery/compare` | Connected & Live Tested |
| `farmer.html` | `GET /api/farmer/lots`, `GET /api/transactions` | Connected |
| `farmer-profile.html` | `GET /api/farmer/profile`, `PUT /api/farmer/profile` | Connected |
| `farmer-produce.html` | `GET /api/farmer/lots`, `DELETE /api/farmer/lots/{id}` | Connected |
| `add-produce.html` | `POST /api/farmer/lots`, `GET /api/crops`, `GET /api/farmer/profile` | Connected |
| `farmer-offers.html` | `GET /api/farmer/lots/{id}/offers`, `POST /api/farmer/offers/{id}/accept` | Connected |
| `buyer.html` | `GET /api/buyer/offers`, `GET /api/transactions` | Connected |
| `buyer-profile.html` | `GET /api/buyer/profile`, `PUT /api/buyer/profile`, `POST /api/buyer/verification` | Connected |
| `buyer-offers.html` | `GET /api/buyer/offers`, `DELETE /api/buyer/offers/{id}` | Connected |
| `transactions.html` | `GET /api/transactions`, `PUT /api/transactions/{id}/status`, `GET /api/transactions/{id}/receipt` | Connected & PDF Enabled |
| `admin.html` | `GET /api/admin/farmers`, `GET /api/admin/buyers`, `GET /api/admin/buyers/pending` | Connected |
| `admin-users.html` | `GET /api/admin/farmers`, `GET /api/admin/buyers` | Connected |
| `admin-verification.html`| `GET /api/admin/buyers/pending`, `PUT /api/admin/buyers/{id}/approve`, `PUT /api/admin/buyers/{id}/reject` | Connected |
| `admin-markets.html` | `GET /api/markets` | Connected |
| `admin-reports.html` | `GET /api/admin/transactions`, `GET /api/admin/farmers`, `GET /api/admin/buyers` | Connected |
| `contact.html` | N/A (documented backend notice) | Informational |

---

## 7. Multilingual Support (i18n)

FarmerLinkage features a built-in multilingual engine (`js/i18n.js`):
- **Supported Languages**: English (`en`), Marathi (`mr`), Hindi (`hi`).
- **Default**: English.
- **Dynamic Translation**: Changing the language selector immediately updates visible elements with `data-i18n` attributes across public pages, forms, and dashboard navigation without page reloads.
- User language preference is persisted in `localStorage`.

---

## 8. Database Architecture & National AGMARKNET Integration

The application connects to a verified PostgreSQL database containing official Government of India AGMARKNET agricultural market datasets:

| Table | Record Count | Description |
|---|---|---|
| `crops` | **238** | Normalized agricultural commodities across Cereals, Pulses, Vegetables, Fruits, Oilseeds, and Spices |
| `markets` | **1,533** | Regulated APMC mandis covering 27 States and Union Territories with state/district normalization |
| `market_prices` | **15,082** | Official daily arrivals with Min, Max, and Modal prices in ₹/Quintal, reporting date 2026-10-24 |
| `users` | **38** | Platform users across Farmer, Commercial Buyer, and System Administrator roles |
| `farmer_lots` | **21** | Active producer lots available for discovery and direct purchase offers |
| `buyer_offers` | **9** | Formal commercial purchase bids with quantity, delivery, and pickup specifications |
| `selling_requests` | **6** | Price discovery trade proposals linking farmers with buyer bids |
| `transactions` | **5** | Formal trade settlement ledger with settlement receipts |
| `notifications` | **25** | System alert triggers for bids, status updates, and verification |

### 8.1 Safe Data Population Script
The full Agmarknet dataset can be re-synchronized or verified at any time using:
```powershell
cd backend
python -m app.scripts.populate_agmarknet_full
```
This script runs in an atomic transaction, maps foreign keys safely, skips duplicates, and preserves all user accounts and transaction history.

---

## 9. Verification & Automated Test Suite

### 9.1 Backend Test Suite (Pytest)
The FastAPI backend test suite contains **215 automated unit, validation, and integration tests**:

```powershell
cd backend
python -m pytest
# Result: 215 passed in 26.60s (100% PASS)
```

Test coverage includes:
- `tests/test_auth.py` (13 tests): JWT generation, Argon2/Bcrypt password hashing, token expiration, role claims.
- `tests/test_crops_markets_prices.py` (46 tests): Filter logic, pagination, mandi arrivals, price sorting.
- `tests/test_price_discovery_validation.py` (7 tests): Mathematical net realization proof, ₹/Quintal to ₹/kg conversions, transportation cost models, nominal vs net optimization, negative/zero input validation.
- `tests/test_selling_workflow.py` (53 tests): Farmer lot creation, buyer offer negotiation, acceptance, and transaction settlement.
- `tests/test_profiles.py` (30 tests): Farmer landholdings, buyer business verification, KYC validations.
- `tests/test_provision_admin.py` (8 tests): Admin RBAC security and role barriers.
- `tests/test_security.py` (4 tests): SQL injection prevention, parameter tampering, unauthorized access guards.

### 9.2 Frontend Validation (Node.js Syntax Compiler)
All 14 frontend JavaScript modules compile with 0 syntax errors:
```powershell
cd frontend
node -c js\config.js js\api.js js\utils.js js\auth.js js\navigation.js js\i18n.js js\homepage.js js\marketplace.js js\market-prices.js js\price-discovery.js js\farmer.js js\buyer.js js\transactions.js js\admin.js
# Result: Clean exit code 0
```

---

## 10. Genuine Application Screenshots

Captured genuine browser screenshots are saved in `docs/screenshots/`:

| Page / Component | Screenshot File | Description |
|---|---|---|
| **Login** | `docs/screenshots/01_login_page.png` | Dedicated sign-in with role badge preview and session persistence |
| **Registration** | `docs/screenshots/02_registration_page.png` | Role-based onboarding for Farmers and Commercial Buyers |
| **Market Prices** | `docs/screenshots/03_market_prices_page.png` | National AGMARKNET mandi catalog with State filters and 50/page pagination |
| **Price Discovery** | `docs/screenshots/04_price_discovery_results.png` | Net realization calculation comparing Lasalgaon vs Vashi APMC |
| **Farmer Dashboard** | `docs/screenshots/05_farmer_dashboard.png` | Producer overview metrics, active produce lots, and incoming buyer bids |
| **Produce Lots** | `docs/screenshots/06_farmer_produce_lots.png` | Farmer produce inventory management and lot creation form |
| **Buyer Dashboard** | `docs/screenshots/07_buyer_dashboard.png` | Commercial procurement metrics, active bids, and market linkage |
| **Admin Console** | `docs/screenshots/08_admin_console.png` | Administrator user directory, verification queue, and mandi registry |

---

## 11. College Demonstration & Viva Guide

### 11.1 Demo Accounts

| Role | Email | Password | Intended Workflow |
|---|---|---|---|
| **Farmer** | `demo_farmer@farmerlinkage.org` | `FarmerDemo123!` | Post produce lots, view bids, accept trade offers |
| **Buyer** | `demo_buyer@farmerlinkage.org` | `BuyerDemo123!` | Explore marketplace, submit purchase offers, request verification |
| **Admin** | `demo_admin@farmerlinkage.org` | `AdminDemo123!` | Review buyer KYC, oversee user directory, inspect APMC mandis |

### 11.2 Demonstration Walkthrough (5-Minute Viva Script)

1. **Homepage & Multilingual Support (`http://localhost:3000/index.html`)**:
   - Showcase modern agricultural hero banner and purpose-driven design.
   - Switch language to **Marathi** and **Hindi** via the top navbar dropdown to show full localization without page reloads.
2. **National Mandi Prices (`http://localhost:3000/market-prices.html`)**:
   - Filter by State (e.g. `Maharashtra`) and Commodity (e.g. `Onion`).
   - Point out the official AGMARKNET source badge, reporting date (`2026-10-24`), and multi-page pagination.
3. **Price Discovery Engine (`http://localhost:3000/price-discovery.html`)**:
   - Select `Onion`, Quantity `50 quintal` (5,000 kg), Farmgate `Nashik`.
   - Run comparison between candidate markets:
     - **Lasalgaon APMC (Nashik)**: Offered rate ₹1,450/qtl &rarr; Gross: ₹72,500.00; Freight (45 km): ₹11,400.00; Mandi cess & charges (1.05% + ₹50): ₹811.25; Total deductions: ₹12,211.25 &rarr; **Net Realization: ₹60,288.75** (₹12.06/kg).
     - **Vashi APMC (Navi Mumbai)**: Offered rate ₹1,680/qtl &rarr; Gross: ₹84,000.00; Freight (180 km): ₹45,150.00; Mandi cess & charges (1.20% + ₹50): ₹1,058.00; Total deductions: ₹46,208.00 &rarr; **Net Realization: ₹37,792.00** (₹7.56/kg).
   - **Key Viva Takeaway**: The algorithm proves that Lasalgaon yields **₹22,496.75 higher net profit** to the farmer despite Vashi offering a ₹230/qtl higher gross nominal rate, demonstrating the critical impact of distance and transport costs.
4. **Marketplace & Direct Trade (`http://localhost:3000/marketplace.html`)**:
   - Show available farmer lots directly connecting producers to commercial buyers.
5. **Farmer Portal (`http://localhost:3000/farmer.html`)**:
   - Sign in as `demo_farmer@farmerlinkage.org`. View produce lots, incoming bids, and completed transactions.
6. **Trade Settlements & PDF Receipts (`http://localhost:3000/transactions.html`)**:
   - Click "Download Receipt" on any completed transaction to generate an official electronic trade receipt.

---

## 12. Known Boundaries & Limitations

1. **Real-time Live Prices**: Prices reflect official daily AGMARKNET reporting (`2026-10-24`). The application does not fabricate simulated intraday price ticks.
2. **Contact Us Endpoint**: No general public ticketing endpoint is exposed on the public API; trade inquiries are directed to the authenticated user dashboard.
3. **Price Predictions**: Predictive trend forecasting requires 60+ historical daily data points per crop-market pair for statistical validity.
