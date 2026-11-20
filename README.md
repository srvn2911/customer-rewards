# Customer Loyalty & Rewards Manager

A full-stack college project for retailers to manage customer accounts, loyalty points, reward rules, redemption, expiry, and activity summaries.

## Stack
- Frontend: React + Vite
- Backend: Python Flask + Flask-SQLAlchemy
- Database: SQLite (created automatically)

## Roles represented
Customer, Cashier, Marketing Officer, Loyalty Administrator.
This academic demo includes a role selector in the UI. It is not production authentication.

## Features
- Dashboard: customer count, points issued/redeemed/expired, outstanding liability
- Customer account creation and search
- Internal points ledger: every earn, redeem, and expiry is recorded
- Configurable earn rule (points per currency unit)
- Configurable redemption rule (points required and cash value)
- Redemption validation against available points
- Manual points earning for purchases
- Customer activity and transaction history
- Expire points using a selected cutoff date
- SQLite persistence

## Requirements
- Python 3.10+
- Node.js 18+
- npm

## Run on Windows 11 (PowerShell)

### 1. Backend
Open PowerShell:
```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
py app.py
```
Backend runs at http://127.0.0.1:5000

If PowerShell blocks activation, use:
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```
Or use Command Prompt:
```cmd
.venv\Scripts\activate.bat
```

### 2. Frontend
Open a second terminal:
```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```
Frontend runs at http://localhost:5173

## Default reward rules
- Earn: 1 point for every ₹100 spent
- Redeem: 100 points = ₹10 discount
You can change these in the **Reward Rules** section.

## Main API endpoints
- `GET /api/dashboard`
- `GET, POST /api/customers`
- `GET /api/customers/<id>`
- `GET, POST /api/transactions`
- `POST /api/redeem`
- `GET, PUT /api/rules`
- `POST /api/expire`

## Important project note
The points ledger is append-only through the application: earning, redemption, and expiry each create a transaction record. Available points are calculated from ledger entries, rather than being silently overwritten.

This is a classroom/demo application. Before real business use, add secure login and role-based permissions, input rate limits, audit controls, backups, HTTPS, and privacy/legal review.
