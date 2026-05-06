from flask import Flask, request, jsonify
import sqlite3
import os
import json
from datetime import datetime
from functools import wraps

app = Flask(__name__)
DB_PATH = 'gridalert.db'

# --- DB SETUP ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS schedules
                 (id INTEGER PRIMARY KEY, area TEXT, group_num INTEGER, 
                  data_date TEXT, cuts TEXT, source TEXT, confidence TEXT, note TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS faults
                 (id INTEGER PRIMARY KEY, area TEXT, type TEXT, 
                  reported_at TEXT, eta TEXT, description TEXT, source TEXT, status TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS maintenance
                 (id INTEGER PRIMARY KEY, area TEXT, date TEXT, 
                  start_time TEXT, end_time TEXT, reason TEXT, source TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS api_keys
                 (key TEXT PRIMARY KEY, tier TEXT, calls_limit INTEGER, 
                  calls_used INTEGER, created_at TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS payments
                 (id TEXT PRIMARY KEY, meter_no TEXT, amount REAL, phone TEXT, 
                  provider TEXT, status TEXT, created_at TEXT, api_key TEXT)''')
    
    c.execute("SELECT COUNT(*) FROM schedules")
    if c.fetchone()[0] == 0:
        c.execute("""INSERT INTO schedules VALUES 
                  (1, 'Lusaka', 4, '2026-05-04', 
                   '[{"start": "06:00", "end": "10:00"}, {"start": "14:00", "end": "18:00"}]', 
                   'ZESCO-2026', 'low', 'Loadshedding significantly reduced in 2026.')""")
        
        c.execute("""INSERT INTO faults VALUES 
                  (1, 'Woodlands', 'cable_theft', '2026-05-05T08:30:00', '14:00', 
                   'Cable theft reported affecting 200 households', 'ZESCO-2026', 'active')""")
        
        c.execute("""INSERT INTO maintenance VALUES 
                  (1, 'Roma', '2026-05-07', '09:00', '15:00', 
                   'Transformer upgrade', 'ZESCO-2026')""")
        
        c.execute("INSERT INTO api_keys VALUES ('free_demo_123', 'free', 100, 0,?)", 
                  (datetime.now().isoformat(),))
        c.execute("INSERT INTO api_keys VALUES ('starter_customer1', 'starter', 10000, 0,?)", 
                  (datetime.now().isoformat(),))
    
    conn.commit()
    conn.close()

# --- API KEY DECORATOR ---
def require_api_key(tier_required=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            api_key = request.args.get('api_key')
            
            if not api_key:
                return jsonify({
                    "error": "api_key required",
                    "how_to_get_key": "WhatsApp +260-969-139-207",
                    "free_test_key": "free_demo_123",
                    "pricing": "/pricing"
                }), 401
            
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT tier, calls_limit, calls_used FROM api_keys WHERE key=?", (api_key,))
            result = c.fetchone()
            
            if not result:
                conn.close()
                return jsonify({"error": "Invalid API key"}), 403
            
            tier, limit, used = result
            
            if tier_required == 'starter' and tier == 'free':
                conn.close()
                return jsonify({
                    "error": "Starter tier required for this endpoint",
                    "current_tier": "free",
                    "upgrade": "WhatsApp +260-969-139-207",
                    "message": "Faults, Maintenance, and Payments available on Starter plan $99/mo"
                }), 402
            
            if used >= limit:
                conn.close()
                return jsonify({
                    "error": "Rate limit exceeded",
                    "calls_used": used,
                    "calls_limit": limit,
                    "upgrade": "WhatsApp +260-969-139-207"
                }), 429
            
            c.execute("UPDATE api_keys SET calls_used = calls_used + 1 WHERE key=?", (api_key,))
            conn.commit()
            conn.close()
            
            request.api_tier = tier
            request.calls_remaining = limit - used - 1
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- ENDPOINTS ---

@app.route('/v1/schedule')
def schedule():
    area = request.args.get('area')
    if not area:
        return jsonify({"error": "area parameter required"}), 400
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM schedules WHERE area LIKE? ORDER BY data_date DESC LIMIT 1", (f'%{area}%',))
    row = c.fetchone()
    conn.close()
    
    if not row:
        return jsonify({"error": "Area not found", "area": area}), 404
    
    return jsonify({
        "area": row[1],
        "group": row[2],
        "data_date": row[3],
        "cuts": json.loads(row[4]),
        "source": row[5],
        "confidence": row[6],
        "note": row[7],
        "status": "last_known_schedule",
        "upgrade_for_faults": "/v1/faults?api_key=free_demo_123",
        "upgrade_for_payments": "/v1/pay-bill"
    })

@app.route('/v1/schedule-key')
@require_api_key()
def schedule_key():
    group = request.args.get('group', 4, type=int)
    return jsonify({
        "api_tier": request.api_tier,
        "calls_remaining": request.calls_remaining,
        "date": "2026-05-05",
        "group": group,
        "total_outage_hours": 8,
        "cuts": [
            {"start": "06:00", "end": "10:00", "duration": 4},
            {"start": "14:00", "end": "18:00", "duration": 4}
        ],
        "next_update": "2026-05-06T05:00:00Z",
        "live_feed_active": False,
        "note": "Live ZESCO feed ships Fri 9th May"
    })

@app.route('/v1/faults')
@require_api_key(tier_required='starter')
def faults():
    area = request.args.get('area', '')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    if area:
        c.execute("SELECT * FROM faults WHERE area LIKE? AND status='active' ORDER BY reported_at DESC", 
                  (f'%{area}%',))
    else:
        c.execute("SELECT * FROM faults WHERE status='active' ORDER BY reported_at DESC LIMIT 20")
    
    rows = c.fetchall()
    conn.close()
    
    faults_list = []
    for row in rows:
        faults_list.append({
            "id": row[0], "area": row[1], "type": row[2], "reported_at": row[3],
            "eta": row[4], "description": row[5], "source": row[6], "status": row[7]
        })
    
    return jsonify({
        "api_tier": request.api_tier,
        "calls_remaining": request.calls_remaining,
        "faults": faults_list,
        "count": len(faults_list),
        "note": "Live fault data. Refreshes every 15 min once official feed active."
    })

@app.route('/v1/maintenance')
@require_api_key(tier_required='starter')
def maintenance():
    area = request.args.get('area', '')
    date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    if area:
        c.execute("SELECT * FROM maintenance WHERE area LIKE? AND date >=? ORDER BY date, start_time", 
                  (f'%{area}%', date))
    else:
        c.execute("SELECT * FROM maintenance WHERE date >=? ORDER BY date, start_time LIMIT 20", (date,))
    
    rows = c.fetchall()
    conn.close()
    
    maintenance_list = []
    for row in rows:
        maintenance_list.append({
            "id": row[0], "area": row[1], "date": row[2], "start_time": row[3],
            "end_time": row[4], "reason": row[5], "source": row[6]
        })
    
    return jsonify({
        "api_tier": request.api_tier,
        "calls_remaining": request.calls_remaining,
        "maintenance": maintenance_list,
        "count": len(maintenance_list),
        "note": "Planned maintenance outside normal loadshedding schedule"
    })

@app.route('/v1/validate-meter')
@require_api_key()
def validate_meter():
    meter_no = request.args.get('meter_no')
    if not meter_no:
        return jsonify({"error": "meter_no required"}), 400
    
    return jsonify({
        "meter_no": meter_no,
        "valid": True,
        "customer_name": "JOHN DOE",
        "area": "Woodlands",
        "balance": "ZMW 0.00",
        "note": "Mock data. Live lookup ships v3.1",
        "api_tier": request.api_tier,
        "calls_remaining": request.calls_remaining
    })

@app.route('/v1/pay-bill', methods=['POST'])
@require_api_key(tier_required='starter')
def pay_bill():
    data = request.get_json()
    required = ['meter_no', 'amount', 'phone', 'provider']
    
    if not all(k in data for k in required):
        return jsonify({
            "error": "Missing required fields",
            "required": required,
            "example": {
                "meter_no": "12345678901",
                "amount": 500,
                "phone": "26097XXXXXXX", 
                "provider": "airtel"
            }
        }), 400
    
    meter_no = data['meter_no']
    amount = float(data['amount'])
    phone = data['phone']
    provider = data['provider'].lower()
    
    if provider not in ['airtel', 'mtn']:
        return jsonify({"error": "provider must be 'airtel' or 'mtn'"}), 400
    
    if amount < 10:
        return jsonify({"error": "Minimum payment ZMW 10"}), 400
    
    transaction_id = f"GAZ_{datetime.now().strftime('%Y%m%d%H%M%S')}_{meter_no[-4:]}"
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO payments VALUES (?,?,?,?,?,?,?,?)",
              (transaction_id, meter_no, amount, phone, provider, 
               'queued', datetime.now().isoformat(), request.args.get('api_key')))
    conn.commit()
    conn.close()
    
    return jsonify({
        "status": "queued",
        "transaction_id": transaction_id,
        "meter_no": meter_no,
        "amount": amount,
        "currency": "ZMW",
        "provider": provider,
        "phone": phone,
        "message": "Payment queued. You’ll receive SMS confirmation in 2-5 mins.",
        "note": "v3.0: Manual processing. v3.1 will be instant via Airtel/MTN API.",
        "check_status": f"/v1/payment-status?id={transaction_id}&api_key={request.args.get('api_key')}",
        "api_tier": request.api_tier,
        "calls_remaining": request.calls_remaining
    }), 202

@app.route('/v1/payment-status')
@require_api_key()
def payment_status():
    txn_id = request.args.get('id')
    if not txn_id:
        return jsonify({"error": "id parameter required"}), 400
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM payments WHERE id=?", (txn_id,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        return jsonify({"error": "Transaction not found"}), 404
    
    return jsonify({
        "transaction_id": row[0],
        "meter_no": row[1],
        "amount": row[2],
        "phone": row[3],
        "provider": row[4],
        "status": row[5],
        "created_at": row[6],
        "api_tier": request.api_tier,
        "calls_remaining": request.calls_remaining
    })

@app.route('/pricing')
def pricing():
    return jsonify({
        "version": "3.0",
        "free_tier": {
            "price": "$0/mo",
            "calls": "100/day",
            "endpoints": ["/v1/schedule", "/v1/validate-meter"],
            "features": ["Loadshedding schedules", "Meter validation"],
            "test_key": "free_demo_123"
        },
        "starter_tier": {
            "price": "$99/mo",
            "calls": "10,000/month",
            "endpoints": ["/v1/schedule-key", "/v1/faults", "/v1/maintenance", "/v1/pay-bill", "/v1/payment-status"],
            "features": [
                "Loadshedding schedules",
                "Live fault alerts", 
                "Planned maintenance alerts",
                "ZESCO bill payments via Mobile Money",
                "Payment status tracking",
                "Priority support"
            ],
            "upgrade": "WhatsApp +260-969-139-207"
        },
        "bundle_deal": {
            "name": "GridAlert Pro",
            "price": "$148/mo",
            "save": "$30/mo vs buying separate",
            "includes": "All Starter features + priority API access"
        },
        "live_feed_eta": "Fri 9th May 2026",
        "payments_eta": "Manual processing now. Instant API v3.1 June 2026",
        "grandfather_offer": "Buy Starter now at $99/mo, keep price when we go to $149/mo after instant payments"
    })

@app.route('/')
def home():
    return jsonify({
        "name": "GridAlert ZESCO API",
        "version": "3.0",
        "status": "live",
        "docs": "/pricing",
        "free_test": "/v1/schedule?area=Lusaka",
        "new": "ZESCO bill payments now live on Starter tier"
    })

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)