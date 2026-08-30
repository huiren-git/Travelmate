"""Seed the isolated benchmark database with a known, non-user reference itinerary."""
import hashlib
import json
import os
import sqlite3
from pathlib import Path

database_dir = Path(os.getenv("DATABASE_DIR", "./data"))
database_dir.mkdir(parents=True, exist_ok=True)
db = sqlite3.connect(database_dir / "reference.db")
db.execute("""CREATE TABLE IF NOT EXISTS reference_trips (
 id INTEGER PRIMARY KEY AUTOINCREMENT, source_trace_id TEXT, destination TEXT NOT NULL,
 duration INTEGER NOT NULL, sequence TEXT NOT NULL, sequence_hash TEXT NOT NULL,
 rhythm TEXT, budget TEXT, travelers INTEGER, tags TEXT, experience_tips TEXT, score INTEGER,
 usage_count INTEGER NOT NULL DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(destination, duration, sequence_hash))""")
sequence = ["拙政园", "平江路", "苏州博物馆", "虎丘", "山塘街", "留园"]
sequence_json = json.dumps(sequence, ensure_ascii=False, separators=(",", ":"))
db.execute("""INSERT OR IGNORE INTO reference_trips
 (id, source_trace_id, destination, duration, sequence, sequence_hash, rhythm, budget, travelers, tags, experience_tips, score)
 VALUES (1, 'benchmark-fixture', '苏州', 3, ?, ?, ?, ?, 2, ?, '仅用于基准测试的匿名参考行程', 90)""",
 (sequence_json, hashlib.sha256(sequence_json.encode()).hexdigest(), json.dumps(["2小时"] * 6, ensure_ascii=False),
  json.dumps({"level": "mid"}, ensure_ascii=False), json.dumps(["园林", "轻松"], ensure_ascii=False)))
db.commit(); db.close()
print(database_dir / "reference.db")
