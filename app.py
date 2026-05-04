from flask import Flask, request, jsonify
import sqlite3
from datetime import datetime
from rapidfuzz import process

app = Flask(__name__)
DB = 'zesco.db'

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/v1/areas')
def list_areas():
    conn = get_db()
    areas = [row['name'] for row in conn.execute('SELECT name FROM areas')]
    conn.close()
    return jsonify({"areas": areas, "zone": "Eastern", "data_date": "2025-11-27"})

@app.route('/v1/schedule')
def schedule():
    area_query = request.args.get('area')
    if not area_query:
        return jsonify({"error":"Missing?area= parameter"}), 400
    
    conn = get_db()
    areas = [row['name'] for row in conn.execute('SELECT name FROM areas')]
    match = process.extractOne(area_query, areas, score_cutoff=70)
    if not match:
        conn.close()
        return jsonify({"error":f"Area '{area_query}' not found","try":"/v1/areas"}), 404
    
    area = match[0]
    
    row = conn.execute('''
        SELECT a.group_name, s.date, s.slot1_start, s.slot1_end, s.slot2_start, s.slot2_end, s.source
        FROM areas a JOIN schedules s ON a.group_name = s.group_name 
        WHERE a.name =? ORDER BY s.date DESC LIMIT 1
    ''', (area,)).fetchone()
    conn.close()
    
    if not row:
        return jsonify({"error":"No schedule data"}), 404
    
    slots = []
    for start, end in [(row['slot1_start'], row['slot1_end']), (row['slot2_start'], row['slot2_end'])]:
        if start and end:
            slots.append({"start":start, "end":end})
    
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

@app.route('/health')
def health():
    return {"status": "ok", "service": "GridAlert API", "version": "0.1"}, 200

@app.route('/pricing')
def pricing():
    return {
        "currency": "USD",
        "plans": {
            "free": {"price": 0, "requests_per_day": 100},
            "starter": {"price": 49, "requests_per_month": 10000}
        },
        "contact": "whatsapp +260-969-139-207"
    }, 200

@app.route('/')
def home():
    return {
        "service": "GridAlert ZESCO API",
        "docs": "/health for status, /pricing for plans",
        "status": "live"
    }, 200

if __name__ == '__main__':
    exec(open('init_db.py').read())
    app.run(host='0.0.0.0', port=5000)

# For Render production
if __name__ != '__main__':
    exec(open('init_db.py').read())
