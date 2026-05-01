import sqlite3
from datetime import datetime

conn = sqlite3.connect('zesco.db')
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS areas (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    group_name TEXT,
    district TEXT,
    zone TEXT
)''')

c.execute('''CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY,
    group_name TEXT,
    date TEXT,
    slot1_start TEXT,
    slot1_end TEXT,
    slot2_start TEXT,
    slot2_end TEXT,
    source TEXT
)''')

c.execute('''CREATE TABLE IF NOT EXISTS webhooks (
    id INTEGER PRIMARY KEY,
    agent_url TEXT,
    area TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)''')

areas_data = [
    ('Chipata Town', 'Group A', 'Chipata', 'Eastern'),
    ('Moth', 'Group B', 'Chipata', 'Eastern'),
    ('Hillside', 'Group C', 'Chipata', 'Eastern'),
    ('Nabvutika', 'Group D', 'Chipata', 'Eastern'),
]

schedules_data = [
    ('Group A', '2025-11-27', '01:00', '19:00', None, None, '2025_schedule'),
    ('Group B', '2025-11-27', '12:00', '23:59', '00:00', '05:00', '2025_schedule'),
    ('Group C', '2025-11-27', '19:00', '23:59', '00:00', '12:00', '2025_schedule'),
    ('Group D', '2025-11-27', '22:00', '12:00', None, None, '2025_schedule'),
]

c.executemany('INSERT OR IGNORE INTO areas (name,group_name,district,zone) VALUES (?,?,?,?)', areas_data)
c.executemany('INSERT OR IGNORE INTO schedules (group_name,date,slot1_start,slot1_end,slot2_start,slot2_end,source) VALUES (?,?,?,?,?,?,?)', schedules_data)

conn.commit()
conn.close()
print("DB ready with 2025 Eastern Zone schedules")