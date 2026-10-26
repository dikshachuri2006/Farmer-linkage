# Database Schema Proposal & Interface Specification
**SIH Problem Statement SIH26132: Strengthening Market Linkage and Price Discovery of Farmer**

**Author:** Ritesh (Backend Lead)  
**Recipient / Reviewer:** Ankita (Database Lead)  
**Date:** October 2026  
**Status:** PROPOSED FOR ANKITA'S REVIEW & FINAL SCHEMA DESIGN

---

## 1. Overview & Collaboration Boundary

Ankita owns the PostgreSQL database schema and database management. The backend team will **NOT** create, alter, or drop tables directly on the database. 

Instead, this document provides the backend application's expected conceptual models, required fields, foreign key relationships, enums, and query patterns based on SIH26132 requirements.

Please review this proposal, adapt it according to your database normalization and indexing strategy, and provide the final schema (or DDL script). Once confirmed, the backend ORM models will be matched to your schema.

---

## 2. Conceptual Tables & Proposed Fields

### Table 1: `users`
Central authentication and identity table.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL / BIGSERIAL` | `PRIMARY KEY` | Unique user ID |
| `email` | `VARCHAR(255)` | `UNIQUE, NOT NULL` | Email for login & notifications |
| `phone_number` | `VARCHAR(20)` | `UNIQUE, NOT NULL` | Mobile number (used by farmers/buyers) |
| `hashed_password` | `VARCHAR(255)` | `NOT NULL` | Bcrypt password hash |
| `full_name` | `VARCHAR(150)` | `NOT NULL` | User's full name |
| `role` | `VARCHAR(20)` | `NOT NULL` | `'FARMER'`, `'BUYER'`, `'ADMIN'` |
| `is_active` | `BOOLEAN` | `DEFAULT TRUE` | Account active status |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT NOW()` | Registration timestamp |
| `updated_at` | `TIMESTAMPTZ` | `DEFAULT NOW()` | Profile update timestamp |

---

### Table 2: `farmer_profiles`
Farmer-specific identity, location, and operational details.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | `PRIMARY KEY` | Profile ID |
| `user_id` | `INTEGER` | `UNIQUE, NOT NULL, FK -> users(id)` | Linked user account |
| `state` | `VARCHAR(100)` | `NOT NULL` | State (e.g. Maharashtra) |
| `district` | `VARCHAR(100)` | `NOT NULL` | District (e.g. Nashik) |
| `taluka` | `VARCHAR(100)` | `NULLABLE` | Sub-district / Taluka |
| `village` | `VARCHAR(100)` | `NULLABLE` | Village / Town |
| `pincode` | `VARCHAR(10)` | `NOT NULL` | Postal code |
| `land_area_acres` | `NUMERIC(8,2)`| `NULLABLE` | Landholding area |
| `preferred_language`| `VARCHAR(20)` | `DEFAULT 'en'` | Language preference (en/hi/mr) |
| `latitude` | `NUMERIC(10,7)`| `NULLABLE` | Optional geo-coordinates for distance |
| `longitude`| `NUMERIC(10,7)`| `NULLABLE` | Optional geo-coordinates for distance |

---

### Table 3: `buyer_profiles`
Buyer business identity, verification status, and ratings.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | `PRIMARY KEY` | Profile ID |
| `user_id` | `INTEGER` | `UNIQUE, NOT NULL, FK -> users(id)` | Linked user account |
| `business_name` | `VARCHAR(200)` | `NOT NULL` | Trading or business name |
| `business_type` | `VARCHAR(50)` | `NOT NULL` | `'TRADER'`, `'WHOLESALER'`, `'PROCESSOR'`, `'EXPORTER'`, `'RETAILER'` |
| `license_number` | `VARCHAR(100)` | `NULLABLE` | APMC / FSSAI / GSTIN license |
| `state` | `VARCHAR(100)` | `NOT NULL` | Operating state |
| `district` | `VARCHAR(100)` | `NOT NULL` | Operating district |
| `market_address` | `TEXT` | `NOT NULL` | Operating address/mandi premise |
| `latitude` | `NUMERIC(10,7)`| `NULLABLE` | Geo-coordinates for transport calculation |
| `longitude`| `NUMERIC(10,7)`| `NULLABLE` | Geo-coordinates for transport calculation |
| `verification_status`| `VARCHAR(20)` | `DEFAULT 'PENDING'` | `'PENDING'`, `'VERIFIED'`, `'REJECTED'`, `'SUSPENDED'` |
| `verification_notes` | `TEXT` | `NULLABLE` | Admin approval/rejection remarks |
| `rating` | `NUMERIC(3,2)` | `DEFAULT 5.00` | Average reliability rating (1.00 - 5.00) |
| `total_transactions` | `INTEGER` | `DEFAULT 0` | Completed transaction count |

---

### Table 4: `crops`
Master catalog of agricultural commodities.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | `PRIMARY KEY` | Crop ID |
| `name` | `VARCHAR(100)` | `UNIQUE, NOT NULL` | Crop name (e.g., 'Onion', 'Wheat') |
| `category` | `VARCHAR(50)` | `NOT NULL` | `'CEREAL'`, `'PULSE'`, `'VEGETABLE'`, `'FRUIT'`, `'OILSEED'`, `'SPICE'` |
| `standard_unit` | `VARCHAR(20)` | `DEFAULT 'kg'` | Standard unit of measurement ('kg', 'quintal') |
| `description` | `TEXT` | `NULLABLE` | Description and standard grades |

---

### Table 5: `markets`
Master directory of APMC Mandis and trade hubs.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | `PRIMARY KEY` | Market ID |
| `name` | `VARCHAR(150)` | `NOT NULL` | Mandi / Market name (e.g., 'Lasalgaon APMC') |
| `state` | `VARCHAR(100)` | `NOT NULL` | State |
| `district` | `VARCHAR(100)` | `NOT NULL` | District |
| `latitude` | `NUMERIC(10,7)`| `NULLABLE` | Mandi latitude |
| `longitude`| `NUMERIC(10,7)`| `NULLABLE` | Mandi longitude |

---

### Table 6: `market_prices`
Historical and daily mandi arrivals and price records (supplied by Diya's dataset).
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `BIGSERIAL` | `PRIMARY KEY` | Price record ID |
| `crop_id` | `INTEGER` | `NOT NULL, FK -> crops(id)` | Crop foreign key |
| `market_id` | `INTEGER` | `NOT NULL, FK -> markets(id)` | Market foreign key |
| `price_date` | `DATE` | `NOT NULL` | Trading date |
| `min_price` | `NUMERIC(10,2)`| `NOT NULL` | Minimum price (₹ per quintal/kg) |
| `max_price` | `NUMERIC(10,2)`| `NOT NULL` | Maximum price (₹ per quintal/kg) |
| `modal_price` | `NUMERIC(10,2)`| `NOT NULL` | Modal / Prevailing price |
| `arrival_quantity`| `NUMERIC(12,2)`| `DEFAULT 0.00` | Daily arrival volume |
| `price_unit` | `VARCHAR(20)` | `DEFAULT 'quintal'` | Unit ('quintal' or 'kg') |
| `source` | `VARCHAR(100)` | `DEFAULT 'Agmarknet'` | Dataset source (from Diya) |

---

### Table 7: `farmer_lots`
Farmer's harvest lots listed for sale or price comparison.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | `PRIMARY KEY` | Lot ID |
| `farmer_id` | `INTEGER` | `NOT NULL, FK -> farmer_profiles(id)` | Farmer profile reference |
| `crop_id` | `INTEGER` | `NOT NULL, FK -> crops(id)` | Crop reference |
| `quantity` | `NUMERIC(12,2)`| `NOT NULL` | Available quantity |
| `unit` | `VARCHAR(20)` | `DEFAULT 'kg'` | Unit ('kg', 'quintal') |
| `quality_grade` | `VARCHAR(20)` | `NOT NULL` | `'GRADE_A'`, `'GRADE_B'`, `'GRADE_C'`, `'FAIR_AVERAGE'` |
| `expected_price_per_unit`| `NUMERIC(10,2)`| `NOT NULL` | Farmer's expected price |
| `harvest_date` | `DATE` | `NULLABLE` | Harvesting date |
| `location_district` | `VARCHAR(100)` | `NOT NULL` | Location district |
| `location_state` | `VARCHAR(100)` | `NOT NULL` | Location state |
| `status` | `VARCHAR(20)` | `DEFAULT 'AVAILABLE'` | `'AVAILABLE'`, `'NEGOTIATING'`, `'SOLD'`, `'WITHDRAWN'` |

---

### Table 8: `buyer_offers`
Buyer bids and standing offers for crop purchase.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | `PRIMARY KEY` | Offer ID |
| `buyer_id` | `INTEGER` | `NOT NULL, FK -> buyer_profiles(id)` | Buyer profile reference |
| `crop_id` | `INTEGER` | `NOT NULL, FK -> crops(id)` | Crop reference |
| `lot_id` | `INTEGER` | `NULLABLE, FK -> farmer_lots(id)` | Optional specific lot |
| `offered_price_per_unit`| `NUMERIC(10,2)`| `NOT NULL` | Offerd price per unit |
| `min_quantity` | `NUMERIC(12,2)`| `DEFAULT 1.0` | Minimum purchase quantity |
| `max_quantity` | `NUMERIC(12,2)`| `NULLABLE` | Maximum purchase quantity |
| `pickup_included` | `BOOLEAN` | `DEFAULT FALSE` | Whether buyer arranges transport |
| `delivery_location` | `VARCHAR(255)` | `NOT NULL` | Destination market / warehouse |
| `is_active` | `BOOLEAN` | `DEFAULT TRUE` | Active status |

---

### Table 9: `selling_requests`
Trade negotiation initiated by farmer towards a verified buyer.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | `PRIMARY KEY` | Selling request ID |
| `request_code` | `VARCHAR(50)` | `UNIQUE, NOT NULL` | Human-readable code (e.g., `REQ-2026-0001`) |
| `farmer_id` | `INTEGER` | `NOT NULL, FK -> farmer_profiles(id)` | Requesting farmer |
| `buyer_id` | `INTEGER` | `NOT NULL, FK -> buyer_profiles(id)` | Target buyer |
| `lot_id` | `INTEGER` | `NOT NULL, FK -> farmer_lots(id)` | Linked harvest lot |
| `quantity` | `NUMERIC(12,2)`| `NOT NULL` | Quantity to sell |
| `proposed_price` | `NUMERIC(10,2)`| `NOT NULL` | Proposed selling price |
| `estimated_transport_cost`| `NUMERIC(10,2)`| `DEFAULT 0.00` | Transport cost calculated by engine |
| `estimated_other_charges`| `NUMERIC(10,2)`| `DEFAULT 0.00` | Mandi fee, handling, packaging |
| `estimated_net_realization`| `NUMERIC(12,2)`| `NOT NULL` | `(quantity * price) - transport - charges` |
| `status` | `VARCHAR(20)` | `DEFAULT 'PENDING'` | `'PENDING'`, `'ACCEPTED'`, `'REJECTED'`, `'CANCELLED'`, `'COMPLETED'` |
| `rejection_reason` | `TEXT` | `NULLABLE` | Reason if rejected by buyer |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT NOW()` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | `DEFAULT NOW()` | Update timestamp |

---

### Table 10: `transactions`
Digital trade and settlement record generated when a selling request is accepted.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | `PRIMARY KEY` | Record ID |
| `transaction_id` | `VARCHAR(60)` | `UNIQUE, NOT NULL` | Unique ID (e.g. `TXN-20261017-XXXX`) |
| `selling_request_id` | `INTEGER` | `UNIQUE, NOT NULL, FK -> selling_requests(id)` | Linked selling request |
| `farmer_id` | `INTEGER` | `NOT NULL, FK -> farmer_profiles(id)` | Farmer |
| `buyer_id` | `INTEGER` | `NOT NULL, FK -> buyer_profiles(id)` | Buyer |
| `crop_id` | `INTEGER` | `NOT NULL, FK -> crops(id)` | Commodity |
| `quantity` | `NUMERIC(12,2)`| `NOT NULL` | Settled quantity |
| `agreed_price` | `NUMERIC(10,2)`| `NOT NULL` | Agreed price per unit |
| `gross_amount` | `NUMERIC(14,2)`| `NOT NULL` | `quantity * agreed_price` |
| `transport_cost` | `NUMERIC(10,2)`| `DEFAULT 0.00` | Transport deduction |
| `other_charges` | `NUMERIC(10,2)`| `DEFAULT 0.00` | Mandi cess / handling deductions |
| `net_amount` | `NUMERIC(14,2)`| `NOT NULL` | Final realization received by farmer |
| `payment_status` | `VARCHAR(20)` | `DEFAULT 'PENDING'` | `'PENDING'`, `'PAID'`, `'ESCROW_HELD'`, `'DISPUTED'` |
| `transaction_status`| `VARCHAR(20)` | `DEFAULT 'CONFIRMED'`| `'CONFIRMED'`, `'IN_TRANSIT'`, `'DELIVERED'`, `'COMPLETED'`, `'CANCELLED'` |
| `payment_method` | `VARCHAR(50)` | `NULLABLE` | `'UPI'`, `'BANK_TRANSFER'`, `'CASH_AT_MANDI'` |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT NOW()` | Timestamp |

---

### Table 11: `complaints`
Farmer or buyer dispute filing and admin resolution tracking.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | `PRIMARY KEY` | Complaint ID |
| `ticket_number` | `VARCHAR(50)` | `UNIQUE, NOT NULL` | e.g. `TKT-2026-0001` |
| `complainant_user_id`| `INTEGER` | `NOT NULL, FK -> users(id)` | User filing complaint |
| `transaction_id` | `INTEGER` | `NULLABLE, FK -> transactions(id)` | Optional linked transaction |
| `against_user_id` | `INTEGER` | `NULLABLE, FK -> users(id)` | User accused in dispute |
| `issue_type` | `VARCHAR(30)` | `NOT NULL` | `'PAYMENT_ISSUE'`, `'WRONG_QUANTITY'`, `'BUYER_NO_SHOW'`, `'PRICE_DISPUTE'`, `'FRAUD'`, `'OTHER'` |
| `title` | `VARCHAR(200)` | `NOT NULL` | Summary |
| `description` | `TEXT` | `NOT NULL` | Detailed complaint statement |
| `status` | `VARCHAR(20)` | `DEFAULT 'OPEN'` | `'OPEN'`, `'UNDER_REVIEW'`, `'RESOLVED'`, `'DISMISSED'` |
| `admin_notes` | `TEXT` | `NULLABLE` | Admin investigation notes |
| `resolution_summary`| `TEXT` | `NULLABLE` | Official resolution |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT NOW()` | Filing timestamp |
| `resolved_at` | `TIMESTAMPTZ` | `NULLABLE` | Resolution timestamp |

---

### Table 12: `price_predictions`
Decision-support trend projections produced by our AI/ML pipeline.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | `PRIMARY KEY` | Prediction ID |
| `crop_id` | `INTEGER` | `NOT NULL, FK -> crops(id)` | Target crop |
| `market_id` | `INTEGER` | `NOT NULL, FK -> markets(id)` | Target market |
| `current_price` | `NUMERIC(10,2)`| `NOT NULL` | Current modal price |
| `predicted_price`| `NUMERIC(10,2)`| `NOT NULL` | Estimated future price |
| `trend` | `VARCHAR(20)` | `NOT NULL` | `'INCREASING'`, `'DECREASING'`, `'STABLE'` |
| `confidence` | `NUMERIC(4,3)` | `NOT NULL` | Confidence score (0.000 to 1.000) |
| `horizon_days` | `INTEGER` | `DEFAULT 7` | Forecast window (e.g. 7 days) |
| `generated_at` | `TIMESTAMPTZ` | `DEFAULT NOW()` | Prediction generation timestamp |

---

### Table 13: `notifications`
System alerts for users regarding verification, trades, and status changes.
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `SERIAL` | `PRIMARY KEY` | Notification ID |
| `user_id` | `INTEGER` | `NOT NULL, FK -> users(id)` | Target recipient |
| `notification_type` | `VARCHAR(40)` | `NOT NULL` | `'BUYER_VERIFICATION'`, `'NEW_REQUEST'`, `'REQUEST_ACCEPTED'`, `'REQUEST_REJECTED'`, `'TRANSACTION_CREATED'`, `'TRANSACTION_COMPLETED'`, `'COMPLAINT_UPDATE'`, `'PRICE_UPDATE'` |
| `title` | `VARCHAR(200)` | `NOT NULL` | Short title |
| `message` | `TEXT` | `NOT NULL` | Notification message body |
| `is_read` | `BOOLEAN` | `DEFAULT FALSE` | Read status |
| `reference_id` | `VARCHAR(60)` | `NULLABLE` | Linked ID (e.g. `transaction_id`, `request_id`) |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT NOW()` | Timestamp |

---

## 3. Recommended Performance Indices
For Ankita's database indexing plan:
1. `CREATE INDEX idx_market_prices_crop_market_date ON market_prices (crop_id, market_id, price_date DESC);`
2. `CREATE INDEX idx_buyer_profiles_verification ON buyer_profiles (verification_status) WHERE verification_status = 'VERIFIED';`
3. `CREATE INDEX idx_farmer_lots_crop_status ON farmer_lots (crop_id, status);`
4. `CREATE INDEX idx_selling_requests_status ON selling_requests (farmer_id, buyer_id, status);`
5. `CREATE INDEX idx_transactions_created ON transactions (created_at DESC);`
6. `CREATE INDEX idx_notifications_user_read ON notifications (user_id, is_read, created_at DESC);`

---

## 4. Questions & Alignment with Ankita
1. Would you prefer integer surrogate primary keys (`SERIAL`) or UUIDs (`UUID`) for sensitive business records like `transactions`? (The proposal uses `SERIAL` with a human-readable `transaction_id` like `TXN-20261017-001`).
2. Do you have existing DDL scripts, or would you like us to generate a draft PostgreSQL migration script for you to adapt?
3. Should market prices store rates normalized in **₹/quintal** or **₹/kg**? (Backend price discovery engine normalizes everything to ₹/kg for accurate comparison with buyer offers).
