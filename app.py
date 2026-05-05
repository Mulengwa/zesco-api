from flask import Flask, request, jsonify
import sqlite3
from datetime import datetime
from rapidfuzz import process

app = Flask(__name__)
DB = 'zesco.db'

# ============================================
# API KEY SYSTEM - PAID TIER
# ============================================
API_KEYS = {
    "free_demo_123": {"tier": "free", "calls_made": 0, "limit": 100},
    "starter_customer1": {"tier": "starter", "calls_made": 0, "limit": 10000},
    "starter_customer2": {"tier": "starter", "calls_made": 0, "limit": 10000}
}

# ============================================
# DATABASE HELPER
# ============================================
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
    conn = get_db()
    areas = [row['name'] for row in conn.execute('SELECT name FROM areas')]
    conn.close()
    return jsonify({"areas": areas, "zone": "Eastern", "data_date": "2025-11-27"})

@app.route('/v1/schedule')
def schedule():
    """FREE ENDPOINT - Real DB data via area name"""
    area_query = request.args.get('area')
    if not area_query:
        return jsonify({"error": "Missing?area= parameter", "try": "/v1/schedule?area=Lusaka"}), 400
    
    conn = get_db()
    areas = [row['name'] for row in conn.execute('SELECT name FROM areas')]
    match = process.extractOne(area_query, areas, score_cutoff=70)
    if not match:
        conn.close()
        return jsonify({"error": f"Area '{area_query}' not found", "try": "/v1/areas"}), 404
    
    area = match[0]
    
    row = conn.execute('''
        SELECT a.group_name, s.date, s.slot1_start,
        s.slot1_end, s.slot2_start, s.slot2_end, s.source
        FROM areas a JOIN schedules s ON a.group_name = s.group_name
        WHERE a.name =? ORDER BY s.date DESC LIMIT 1
    ''', (area,)).fetchone()
    conn.close()
    
    if not row:
        return jsonify({"error": "No schedule data for this area"}), 404
    
    slots = []
    for start, end in [(row['slot1_start'], row['slot1_end']), (row['slot2_start'], row['slot2_end'])]:
        if start and end:
            slots.append({"start": start, "end": end})
    
    return jsonify({
        "area": area,
        "group": row['group_name'],
        "status": "last_known_schedule",
        "data_date": row['date'],
        "source": row['source'],
        "cuts": slots,
        "note": "Loadshedding significantly reduced in 2026. No current schedule published by ZESCO.",
        "confidence": "low"
    })

@app.route('/v1/schedule-key')
def get_schedule_key():
    """PAID ENDPOINT - API key required, rate limited"""
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
        "note": "Demo data for paid tier. For real DB data use /v1/schedule?area=Lusaka"
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
            "free": {
                "price": 0, 
                "requests_per_day": 100,
                "note": "Via /v1/schedule-key with free_demo_123"
            },
            "starter": {
                "price": 49, 
                "requests_per_month": 10000,
                "support": "WhatsApp priority"
            }
        },
        "launch_offer": "Live ZESCO data ships Fri 9th May. Buy now, get grandfathered at $49."
    })

@app.route('/')
def home():
    return {
        "service": "GridAlert ZESCO API",
        "docs": "/health for status, /pricing for plans, /v1/areas for area list",
        "status": "live",
        "version": "2.0"
    }, 200

# ============================================
# START SERVER
# ============================================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)