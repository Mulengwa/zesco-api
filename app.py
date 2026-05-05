from flask import Flask, request, jsonify
import sqlite3
import os
from datetime import datetime
from rapidfuzz import process

app = Flask(__name__)
DB = 'zesco.db'

# ============================================
# AUTO-CREATE DB - Fixes 500 errors on Render
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
        # Sample data so endpoints work immediately
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

# Create DB on startup
init_db()

# ============================================
# API KEY SYSTEM
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
    try:
        conn = get_db()
        areas = [row['name'] for row in conn.execute('SELECT name FROM areas')]
        conn.close()
        return jsonify({"areas": areas, "zone": "Eastern", "data_date": "2026-05-04"})
    except Exception as e:
        return jsonify({"error": "Database error", "message": str(e)}), 500

@app.route('/v1/schedule')
def schedule():
    """FREE ENDPOINT - Real DB data via area name"""
    area_query = request.args.get('area')
    if not area_query:
        return jsonify({
            "error": "Missing?area= parameter",
            "try": "/v1/schedule?area=Lusaka",
            "available_areas": "/v1/areas"
        }), 400

    try:
        conn = get_db()
        areas = [row['name'] for row in conn.execute('SELECT name FROM areas')]

        if not areas:
            conn.close()
            return jsonify({
                "error": "Database initializing",
                "note": "Use /v1/schedule-key?api_key=free_demo_123&group=4 for demo data",
                "upgrade": "WhatsApp +260-969-139-207"
            }), 503

        match = process.extractOne(area_query, areas, score_cutoff=70)
        if not match:
            conn.close()
            return jsonify({
                "error": f"Area '{area_query}' not found",
                "available": areas,
                "try": "/v1/areas"
            }), 404

        area = match[0]

        row = conn.execute('''
            SELECT a.group_name, s.date, s.slot1_start,
            s.slot1_end, s.slot2_start, s.slot2_end, s.source
            FROM areas a JOIN schedules s ON a.group_name = s.group_name
            WHERE a.name =? ORDER BY s.date DESC LIMIT 1
        ''', (area,)).fetchone()
        conn.close()

        if not row:
            return jsonify({
                "error": "No schedule data for this area",
                "area": area,
                "note": "Loadshedding significantly reduced in 2026. Try /v1/schedule-key for demo"
            }), 404

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
    except Exception as e:
        return jsonify({"error": "Server error", "message": str(e)}), 500

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

    # Dummy data for now - replace with real DB lookup after first sale
    dummy_schedules = {