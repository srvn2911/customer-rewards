import os
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

load_dotenv()
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///loyalty.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)
CORS(app, resources={r"/api/*": {"origins": os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")}})

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    phone = db.Column(db.String(30), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class RewardRule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    points_per_unit = db.Column(db.Float, nullable=False, default=0.01) # 1 point per ₹100
    points_per_redemption = db.Column(db.Integer, nullable=False, default=100)
    redemption_value = db.Column(db.Float, nullable=False, default=10.0) # ₹10 per 100 points

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=False)
    kind = db.Column(db.String(20), nullable=False) # EARN, REDEEM, EXPIRE
    points = db.Column(db.Integer, nullable=False) # earn positive, redeem/expire negative
    amount = db.Column(db.Float, nullable=False, default=0.0)
    description = db.Column(db.String(240), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_on = db.Column(db.Date, nullable=True)
    customer = db.relationship("Customer", backref=db.backref("transactions", lazy=True))

def current_rule():
    rule = RewardRule.query.first()
    if not rule:
        rule = RewardRule()
        db.session.add(rule)
        db.session.commit()
    return rule

def balance(customer_id):
    total = db.session.query(func.coalesce(func.sum(Transaction.points), 0)).filter_by(customer_id=customer_id).scalar()
    return int(total or 0)

def tx_json(t):
    return {
        "id": t.id, "customer_id": t.customer_id, "customer_name": t.customer.name,
        "kind": t.kind, "points": t.points, "amount": t.amount,
        "description": t.description, "created_at": t.created_at.isoformat(timespec="minutes"),
        "expires_on": t.expires_on.isoformat() if t.expires_on else None
    }

def customer_json(c):
    return {"id": c.id, "name": c.name, "email": c.email, "phone": c.phone,
            "created_at": c.created_at.isoformat(timespec="minutes"), "points_balance": balance(c.id)}

def error(message, code=400):
    return jsonify({"error": message}), code

@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "Customer Loyalty & Rewards Manager"})

@app.get("/api/dashboard")
def dashboard():
    customers = Customer.query.count()
    earned = db.session.query(func.coalesce(func.sum(Transaction.points), 0)).filter_by(kind="EARN").scalar() or 0
    redeemed = db.session.query(func.coalesce(func.sum(-Transaction.points), 0)).filter_by(kind="REDEEM").scalar() or 0
    expired = db.session.query(func.coalesce(func.sum(-Transaction.points), 0)).filter_by(kind="EXPIRE").scalar() or 0
    outstanding = sum(balance(c.id) for c in Customer.query.all())
    rule = current_rule()
    recent = Transaction.query.order_by(Transaction.created_at.desc()).limit(8).all()
    return jsonify({
        "customers": customers, "points_earned": int(earned), "points_redeemed": int(redeemed),
        "points_expired": int(expired), "outstanding_points": outstanding,
        "estimated_liability": round(outstanding * rule.redemption_value / rule.points_per_redemption, 2),
        "recent_transactions": [tx_json(t) for t in recent]
    })

@app.route("/api/customers", methods=["GET", "POST"])
def customers():
    if request.method == "GET":
        q = request.args.get("q", "").strip()
        query = Customer.query
        if q:
            query = query.filter(db.or_(Customer.name.ilike(f"%{q}%"), Customer.email.ilike(f"%{q}%"), Customer.phone.ilike(f"%{q}%")))
        return jsonify([customer_json(c) for c in query.order_by(Customer.name).all()])
    data = request.get_json(silent=True) or {}
    name, email = data.get("name", "").strip(), data.get("email", "").strip().lower()
    if not name or not email:
        return error("Customer name and email are required.")
    if Customer.query.filter_by(email=email).first():
        return error("A customer with this email already exists.")
    c = Customer(name=name, email=email, phone=data.get("phone", "").strip())
    db.session.add(c)
    db.session.commit()
    return jsonify(customer_json(c)), 201

@app.get("/api/customers/<int:customer_id>")
def customer_detail(customer_id):
    c = db.session.get(Customer, customer_id)
    if not c: return error("Customer not found.", 404)
    history = Transaction.query.filter_by(customer_id=c.id).order_by(Transaction.created_at.desc()).all()
    return jsonify({"customer": customer_json(c), "transactions": [tx_json(t) for t in history]})

@app.route("/api/rules", methods=["GET", "PUT"])
def rules():
    rule = current_rule()
    if request.method == "GET":
        return jsonify({"points_per_unit": rule.points_per_unit,
                        "points_per_redemption": rule.points_per_redemption,
                        "redemption_value": rule.redemption_value})
    data = request.get_json(silent=True) or {}
    try:
        ppu = float(data.get("points_per_unit", rule.points_per_unit))
        ppr = int(data.get("points_per_redemption", rule.points_per_redemption))
        value = float(data.get("redemption_value", rule.redemption_value))
        if ppu <= 0 or ppr <= 0 or value <= 0: raise ValueError()
    except (ValueError, TypeError):
        return error("All reward rule values must be positive numbers.")
    rule.points_per_unit, rule.points_per_redemption, rule.redemption_value = ppu, ppr, value
    db.session.commit()
    return jsonify({"points_per_unit": ppu, "points_per_redemption": ppr, "redemption_value": value})

@app.route("/api/transactions", methods=["GET", "POST"])
def transactions():
    if request.method == "GET":
        rows = Transaction.query.order_by(Transaction.created_at.desc()).limit(250).all()
        return jsonify([tx_json(t) for t in rows])
    data = request.get_json(silent=True) or {}
    try:
        customer_id = int(data.get("customer_id"))
        amount = float(data.get("amount", 0))
        if amount <= 0: raise ValueError()
    except (ValueError, TypeError):
        return error("Select a customer and enter a valid purchase amount.")
    c = db.session.get(Customer, customer_id)
    if not c: return error("Customer not found.", 404)
    rule = current_rule()
    points = int(amount * rule.points_per_unit)
    if points < 1: return error("This purchase is too small to earn a point with the current rule.")
    expires = None
    expiry_days = data.get("expiry_days", 365)
    try: expires = date.today().fromordinal(date.today().toordinal() + max(1, int(expiry_days)))
    except (ValueError, TypeError): expires = None
    t = Transaction(customer_id=c.id, kind="EARN", points=points, amount=amount,
                    description=data.get("description", "Purchase points"), expires_on=expires)
    db.session.add(t); db.session.commit()
    return jsonify({"transaction": tx_json(t), "new_balance": balance(c.id)}), 201

@app.post("/api/redeem")
def redeem():
    data = request.get_json(silent=True) or {}
    try:
        customer_id = int(data.get("customer_id"))
        points = int(data.get("points"))
        if points <= 0: raise ValueError()
    except (ValueError, TypeError):
        return error("Select a customer and enter a valid number of points.")
    c = db.session.get(Customer, customer_id)
    if not c: return error("Customer not found.", 404)
    available = balance(c.id)
    if points > available: return error(f"Not enough points. Available balance: {available}.")
    rule = current_rule()
    if points % rule.points_per_redemption != 0:
        return error(f"Points must be redeemed in multiples of {rule.points_per_redemption}.")
    value = (points // rule.points_per_redemption) * rule.redemption_value
    t = Transaction(customer_id=c.id, kind="REDEEM", points=-points, amount=value,
                    description=f"Redeemed {points} points for ₹{value:.2f} discount")
    db.session.add(t); db.session.commit()
    return jsonify({"transaction": tx_json(t), "discount_value": value, "new_balance": balance(c.id)}), 201

@app.post("/api/expire")
def expire():
    data = request.get_json(silent=True) or {}
    try: cutoff = date.fromisoformat(data.get("cutoff_date", date.today().isoformat()))
    except ValueError: return error("Use a valid cutoff date.")
    expired_count = 0
    # Expire only remaining points from earning entries whose expiry date has passed.
    for earning in Transaction.query.filter_by(kind="EARN").filter(Transaction.expires_on <= cutoff).all():
        already_used = -sum(t.points for t in Transaction.query.filter(
            Transaction.customer_id == earning.customer_id,
            Transaction.id > earning.id,
            Transaction.kind.in_(["REDEEM", "EXPIRE"])
        ).all())
        remaining = max(0, earning.points - already_used)
        if remaining:
            db.session.add(Transaction(customer_id=earning.customer_id, kind="EXPIRE",
                points=-remaining, amount=0, description=f"Expired points from earning entry #{earning.id}"))
            expired_count += remaining
    db.session.commit()
    return jsonify({"expired_points": expired_count, "message": f"{expired_count} points expired."})

with app.app_context():
    db.create_all()
    current_rule()

if __name__ == "__main__":
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=5000, debug=True)
