"""
Poop Tracker - A cute health tracking app
FastAPI backend with SQLite database
星露谷+锈湖混合风格
"""

import sqlite3
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Initialize FastAPI
app = FastAPI(title="Poop Tracker")

# Setup templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Database setup
DB_NAME = "health_tracker.db"

# 大便类型 - Bristol分类法
POOP_TYPES = [
    ("sheep", "羊粪蛋型"),
    ("sausage_bumpy", "香肠状表面凹凸不平"),
    ("sausage_cracked", "香肠状表面有裂痕"),
    ("banana", "香蕉型"),
    ("soft_lumps", "软团状"),
    ("mushy", "糊状"),
    ("watery", "水样"),
]

def init_db():
    """Initialize SQLite database with required table"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # 创建表（如果不存在）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            datetime TEXT NOT NULL,
            type TEXT NOT NULL,
            duration INTEGER DEFAULT 0,
            notes TEXT
        )
    """)
    # 迁移：为旧数据库添加duration列（如果不存在）
    try:
        cursor.execute("ALTER TABLE records ADD COLUMN duration INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # 列已存在
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()

# Pydantic model for record
class Record(BaseModel):
    id: int
    datetime: str
    type: str
    duration: int = 0
    notes: Optional[str] = None

# Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Main page showing records and statistics"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all records sorted by datetime (newest first)
    cursor.execute("SELECT * FROM records ORDER BY datetime DESC")
    records = [dict(row) for row in cursor.fetchall()]
    
    # Convert duration from seconds to readable format
    for record in records:
        if record.get('duration'):
            minutes = record['duration'] // 60
            seconds = record['duration'] % 60
            if minutes > 0:
                record['duration_text'] = f"{minutes}分{seconds}秒"
            else:
                record['duration_text'] = f"{seconds}秒"
        else:
            record['duration_text'] = ""
    
    # Get statistics
    cursor.execute("SELECT COUNT(*) as total FROM records")
    total = cursor.fetchone()["total"]
    
    cursor.execute("SELECT type, COUNT(*) as count FROM records GROUP BY type")
    type_counts = {row["type"]: row["count"] for row in cursor.fetchall()}
    
    # Get average duration
    cursor.execute("SELECT AVG(duration) as avg_duration FROM records WHERE duration > 0")
    avg_duration = cursor.fetchone()["avg_duration"]
    if avg_duration:
        avg_minutes = int(avg_duration) // 60
        avg_seconds = int(avg_duration) % 60
        avg_duration_text = f"{avg_minutes}分{avg_seconds}秒" if avg_minutes > 0 else f"{avg_seconds}秒"
    else:
        avg_duration_text = "-"
    
    conn.close()
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "records": records,
        "total": total,
        "type_counts": type_counts,
        "poop_types": POOP_TYPES,
        "avg_duration": avg_duration_text
    })

@app.post("/add", response_class=HTMLResponse)
async def add_record(
    request: Request,
    record_datetime: str = Form(alias="datetime"),
    type: str = Form(...),
    duration_minutes: int = Form(0),
    duration_seconds: int = Form(0),
    notes: str = Form("")
):
    """Add a new record"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Parse datetime and format it nicely
    dt = datetime.fromisoformat(record_datetime.replace('T', ' '))
    formatted_datetime = dt.strftime("%Y-%m-%d %H:%M")
    
    # Calculate total duration in seconds
    total_duration = duration_minutes * 60 + duration_seconds
    
    cursor.execute(
        "INSERT INTO records (datetime, type, duration, notes) VALUES (?, ?, ?, ?)",
        (formatted_datetime, type, total_duration, notes if notes else None)
    )
    conn.commit()
    conn.close()
    
    # Redirect to home page
    return await home(request)

@app.post("/delete/{record_id}", response_class=HTMLResponse)
async def delete_record(request: Request, record_id: int):
    """Delete a record"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM records WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()
    
    # Redirect to home page
    return await home(request)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)