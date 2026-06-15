import sqlite3
import os

db_path = "sportsmd.db"
if not os.path.exists(db_path):
    print("Database not found!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get columns info
cursor.execute("PRAGMA table_info(analyses)")
cols = [c[1] for c in cursor.fetchall()]

cursor.execute("SELECT * FROM analyses WHERE pose_model = 'rtm' ORDER BY created_at DESC LIMIT 5")
rows = cursor.fetchall()

print(f"Total analyses using rtm: {len(rows)}")
for row in rows:
    analysis = dict(zip(cols, row))
    print(f"ID: {analysis['id']}, Athlete ID: {analysis['athlete_id']}, Status: {analysis['status']}, Side Video: {analysis['side_video_path']}, Front Video: {analysis['front_video_path']}, Created At: {analysis['created_at']}")

conn.close()
