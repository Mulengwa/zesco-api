from flask import Flask, request, jsonify
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
DB = 'zesco.db'

# ============================================
# AUTO-CREATE DB - No external deps
# ============================================
def init_db():
    if not os.path.exists(DB):
        conn = sqlite3.connect(DB)
        conn.execute('''CREATE TABLE IF NOT EXISTS areas (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE,
            group_name TEXT
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY,
            group_name TEXT,
            date TEXT,
            slot1_start TEXT,
            slot1_end TEXT,
            slot2_start TEXT,
            slot2_end TEXT,
            source TEXT
        )''')
        # Sample data
        conn.execute("INSERT OR IGNORE INTO areas (name, group_name) VALUES ('Lusaka', '4')")
        conn.execute("INSERT OR IGNORE INTO areas (name, group_name) VALUES ('Kitwe', '7')")
        conn.execute("INSERT OR IGNORE INTO areas (name, group_name) VALUES ('Ndola', '1')")
        conn.execute('''INSERT OR IGNORE INTO schedules
            (group_name, date, slot1_start, slot1_end, slot2_start, slot2_end, source)
            VALUES ('4', '2026-05-04', '06:00', '10:00', '14:00', '18:00', 'ZESCO-2026')''')
        conn.execute('''INSERT OR IGNORE INTO schedules
            (group_name, date, slot1_start, slot1_end, slot2_start, slot2_end, source)
            VALUES ('7', '2026-05-04', '08:00', '12:00', '20:00', '00:00', 'ZESCO-2026')''')
        conn.execute('''INSERT OR IGNORE INTO schedules
            (group_name, date, slot1_start, slot1_end, slot2_start, slot2_end, source)
            VALUES ('1', '2026-05-04', '05:00', '09:00', '17:00', '21:00', 'ZESCO-2026')''')
        conn.commit()
        conn.close()

init_db()

# ============================================
# API KEYS
# ============================================
API_KEYS = {
    "free_demo_123": {"tier": "free", "calls_made": 0, "limit": 100},
    "starter_customer1": {"tier": "starter", "calls_made": 0, "limit": 10000},
    "starter_customer2": {"tier": "starter", "calls_made": 0, "limit": 10000}
}

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

# ============================================
# ROUTES
# ============================================

@app.route('/health')
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()}), 200

@app.route('/v1/areas')
def list_areas():
    try:
        conn = get_db()
        areas = [row['name'] for row in conn.execute('SELECT name FROM areas')]
        conn.close()
        return jsonify({"areas": areas, "zone": "Eastern", "data_date": "2026-05-04"})
    except Exception as e:
        return jsonify({"error": "Database error", "message": str(e)}), 500

@app.route('/v1/schedule')
def schedule():
    """FREE ENDPOINT - No fuzzy matching, exact or LIKE match"""
    area_query = request.args.get('area')
    if not area_query:
        return jsonify({
            "error": "Missing?area= parameter",
            "try": "/v1/schedule?area=Lusaka",
            "available_areas": "/v1/areas"
        }), 400

    try:
        conn = get_db()
        # Simple case-insensitive LIKE instead of rapidfuzz
        row = conn.execute('''
            SELECT a.name, a.group_name, s.date, s.slot1_start,
            s.slot1_end, s.slot2_start, s.slot2_end, s.source
            FROM areas a JOIN schedules s ON a.group_name = s.group_name
            WHERE LOWER(a.name) LIKE LOWER(?)
            ORDER BY s.date DESC LIMIT 1
        ''', (f'%{area_query}%',)).fetchone()
        conn.close()

        if not row:
            return jsonify({
                "error": f"Area '{area_query}' not found",
                "note": "Try /v1/areas for full list",
                "demo": "/v1/schedule-key?api_key=free_demo_123&group=4"
            }), 404

        slots = []
        for start, end in [(row['slot1_start'], row['slot1_end']), (row['slot2_start'], row['slot2_end'])]:
            if start and end:
                slots.append({"start": start, "end": end})

        return jsonify({
            "area": row['name'],
            "group": row['group_name'],
            "status": "last_known_schedule",
            "data_date": row['date'],
            "source": row['source'],
            "cuts": slots,
            "note": "Loadshedding significantly reduced in 2026.",
            "confidence": "low"
        })
    except Exception as e:
        return jsonify({"error": "Server error", "message": str(e)}), 500

@app.route('/v1/schedule-key')
def get_schedule_key():
    """PAID ENDPOINT - No DB needed"""
    api_key = request.args.get('api_key')
    if not api_key:
        return {
            "error": "api_key required",
            "how_to_get_key": "WhatsApp +260-969-139-207",
            "pricing": "/pricing",
            "test_it_free": "/v1/schedule-key?api_key=free_demo_123&group=4",
            "free_db_lookup": "/v1/schedule?area=Lusaka"
        }, 401

    if api_key not in API_KEYS:
        return {
            "error": "Invalid api_key",
            "message": "Key not found. Buy yours: WhatsApp +260-969-139-207"
        }, 403

    key_data = API_KEYS[api_key]
    if key_data["calls_made"] >= key_data["limit"]:
        return {
            "error": "Rate limit exceeded",
            "tier": key_data["tier"],
            "limit": key_data["limit"],
            "calls_made": key_data["calls_made"],
            "upgrade_now": "WhatsApp +260-969-139-207"
        }, 429

    try:
        group = int(request.args.get('group', 4))
    except:
        return {"error": "group must be a number 1-12"}, 400

    date = request.args.get('date', datetime.now().date().isoformat())
    API_KEYS[api_key]["calls_made"] += 1

    return {
        "group": group,
        "date": date,
        "outages": [
            {"start": "06:00", "end": "10:00", "duration_hours": 4},
            {"start": "14:00", "end": "18:00", "duration_hours": 4}
        ],
        "total_outage_hours": 8,
        "source": "ZESCO",
        "api_tier": key_data["tier"],
        "calls_remaining": key_data["limit"] - key_data["calls_made"],
        "note": "Demo data. Live ZESCO feed ships Fri 9th May."
    }, 200

@app.route('/pricing')
def pricing():
    return jsonify({
        "product": "GridAlert ZESCO API",
        "contact": "whatsapp +260-969-139-207",
        "currency": "USD",
        "base_url": "https://gridalert-api.onrender.com",
        "endpoints": {
            "free_public": "/v1/schedule?area=Lusaka",
            "paid_api": "/v1/schedule-key?api_key=YOUR_KEY&group=4"
        },
        "free_test_key": "free_demo_123",
        "plans": {
            "free": {"price": 0, "requests_per_day": 100},
            "starter": {"price": 49, "requests_per_month": 10000}
        }
    })

@app.route('/')
def home():
    return {
        "service": "GridAlert ZESCO API",
        "docs": "/health, /pricing, /v1/areas",
        "status": "live",
        "version": "2.2"
    }, 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)