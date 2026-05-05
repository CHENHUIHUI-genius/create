"""
Poop Tracker - A cute health tracking app
FastAPI backend with SQLite database
星露谷+锈湖混合风格
"""

import os
import sqlite3
import shutil
from datetime import datetime, timedelta, date
from typing import List, Optional
from fastapi import FastAPI, Request, Form, UploadFile, File, Query
from fastapi.responses import HTMLResponse, JSONResponse
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

# 健康评分 (1-10, 10最健康)
# Bristol分型: 1-2便秘, 3-4理想, 5-7腹泻倾向
POOP_HEALTH_SCORE = {
    "sheep": 2,           # 便秘
    "sausage_bumpy": 4,   # 轻度便秘
    "sausage_cracked": 8, # 接近理想
    "banana": 10,         # 理想
    "soft_lumps": 6,      # 偏软
    "mushy": 3,           # 腹泻倾向
    "watery": 1,          # 腹泻
}

# 颜色映射 (用于日历点)
POOP_COLORS = {
    "sheep": "#8b6f47",       # 棕色 - 便秘
    "sausage_bumpy": "#c4a87c", # 浅棕
    "sausage_cracked": "#7cb342", # 浅绿 - 健康
    "banana": "#5c8a4a",      # 绿色 - 最健康
    "soft_lumps": "#f0c040",  # 金色 - 偏软
    "mushy": "#c76b4a",       # 锈红 - 腹泻倾向
    "watery": "#1b7a8a",      # 青色 - 水样
}

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

def get_week_range(dt=None):
    """Get Monday 00:00 and Sunday 23:59 of the current week"""
    if dt is None:
        dt = datetime.now()
    # Monday = 0, Sunday = 6
    monday = dt - timedelta(days=dt.weekday())
    monday_start = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    sunday_end = (monday_start + timedelta(days=6)).replace(hour=23, minute=59, second=59)
    return monday_start, sunday_end

def get_health_level(score):
    """Get health level description based on score"""
    if score >= 8:
        return "非常健康 🎉"
    elif score >= 6:
        return "良好 👍"
    elif score >= 4:
        return "一般 ⚠️"
    else:
        return "需要注意 ❤️‍🩹"

def get_diet_suggestion(records):
    """Simple rule-based diet suggestions based on recent records"""
    if not records:
        return "暂无数据，开始记录后会有饮食建议哦~"
    
    # Count types in recent records (last 7 days)
    type_counts = {}
    for r in records:
        t = r['type']
        type_counts[t] = type_counts.get(t, 0) + 1
    
    total = sum(type_counts.values())
    if total == 0:
        return "暂无数据，开始记录后会有饮食建议哦~"
    
    # Calculate percentages
    constipated_types = ['sheep', 'sausage_bumpy']
    ideal_types = ['sausage_cracked', 'banana']
    diarrhea_types = ['soft_lumps', 'mushy', 'watery']
    
    constipated_pct = sum(type_counts.get(t, 0) for t in constipated_types) / total
    diarrhea_pct = sum(type_counts.get(t, 0) for t in diarrhea_types) / total
    ideal_pct = sum(type_counts.get(t, 0) for t in ideal_types) / total
    
    if constipated_pct > 0.5:
        return "🥦 最近有便秘倾向，建议多喝水、多吃高纤维食物（蔬菜、水果、全谷物），适当运动促进肠道蠕动。"
    elif diarrhea_pct > 0.5:
        return "🍚 最近肠道偏软，建议吃易消化的食物（粥、面条），避免生冷油腻，可以补充益生菌。"
    elif ideal_pct > 0.6:
        return "🌟 肠道状态很好！继续保持均衡饮食，多吃蔬果，保持规律作息。"
    else:
        return "🥗 肠道状态中等，建议保持饮食均衡，多吃蔬菜水果，适量饮水，规律作息。"

def format_duration(seconds):
    """Convert seconds to readable format"""
    if not seconds:
        return ""
    minutes = seconds // 60
    secs = seconds % 60
    if minutes > 0:
        return f"{minutes}分{secs}秒"
    return f"{secs}秒"

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
        record['duration_text'] = format_duration(record.get('duration'))
    
    # Get statistics
    cursor.execute("SELECT COUNT(*) as total FROM records")
    total = cursor.fetchone()["total"]
    
    cursor.execute("SELECT type, COUNT(*) as count FROM records GROUP BY type")
    type_counts = {row["type"]: row["count"] for row in cursor.fetchall()}
    
    # Get average duration
    cursor.execute("SELECT AVG(duration) as avg_duration FROM records WHERE duration > 0")
    avg_duration = cursor.fetchone()["avg_duration"]
    avg_duration_text = format_duration(int(avg_duration)) if avg_duration else "-"
    
    # === Weekly Summary ===
    week_start, week_end = get_week_range()
    week_start_str = week_start.strftime("%Y-%m-%d %H:%M:%S")
    week_end_str = week_end.strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute(
        "SELECT * FROM records WHERE datetime >= ? AND datetime <= ? ORDER BY datetime",
        (week_start_str, week_end_str)
    )
    week_records = [dict(row) for row in cursor.fetchall()]
    
    week_total_duration = sum(r.get('duration', 0) for r in week_records)
    week_poop_count = len(week_records)
    
    # Calculate average health score for the week
    if week_records:
        week_health_scores = [POOP_HEALTH_SCORE.get(r['type'], 5) for r in week_records]
        week_avg_health = sum(week_health_scores) / len(week_health_scores)
        week_health_level = get_health_level(week_avg_health)
    else:
        week_avg_health = 0
        week_health_level = "暂无数据"
    
    week_summary = {
        'start_date': week_start.strftime("%m/%d"),
        'end_date': week_end.strftime("%m/%d"),
        'poop_count': week_poop_count,
        'total_duration': format_duration(week_total_duration),
        'total_duration_seconds': week_total_duration,
        'avg_health': round(week_avg_health, 1),
        'health_level': week_health_level,
    }
    
    # === Diet Suggestion ===
    # Get last 7 days of records for diet analysis
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "SELECT * FROM records WHERE datetime >= ? ORDER BY datetime DESC",
        (seven_days_ago,)
    )
    recent_records = [dict(row) for row in cursor.fetchall()]
    diet_suggestion = get_diet_suggestion(recent_records)
    
    conn.close()
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "records": records,
        "total": total,
        "type_counts": type_counts,
        "poop_types": POOP_TYPES,
        "avg_duration": avg_duration_text,
        "week_summary": week_summary,
        "diet_suggestion": diet_suggestion,
        "poop_health_scores": POOP_HEALTH_SCORE,
        "poop_colors": POOP_COLORS,
    })

@app.get("/calendar-data")
async def calendar_data(year: int = Query(None), month: int = Query(None)):
    """Get calendar data for a specific month"""
    now = datetime.now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month
    
    # Calculate month range
    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year
    
    month_start = f"{year:04d}-{month:02d}-01 00:00:00"
    month_end = f"{next_year:04d}-{next_month:02d}-01 00:00:00"
    
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT * FROM records WHERE datetime >= ? AND datetime < ? ORDER BY datetime",
        (month_start, month_end)
    )
    records = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    # Group records by day
    days_data = {}
    for r in records:
        try:
            dt = datetime.strptime(r['datetime'], "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        day = dt.day
        if day not in days_data:
            days_data[day] = []
        days_data[day].append({
            'type': r['type'],
            'duration': r.get('duration', 0),
            'color': POOP_COLORS.get(r['type'], '#888888'),
            'health_score': POOP_HEALTH_SCORE.get(r['type'], 5),
        })
    
    # Calculate max duration for scaling
    all_durations = [r['duration'] for day_records in days_data.values() for r in day_records]
    max_duration = max(all_durations) if all_durations else 1
    
    return JSONResponse({
        'year': year,
        'month': month,
        'days': days_data,
        'max_duration': max_duration,
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

@app.post("/upload-avatar", response_class=HTMLResponse)
async def upload_avatar(request: Request, avatar: UploadFile = File(...)):
    """Upload avatar image"""
    # Ensure uploads directory exists
    os.makedirs("static/uploads", exist_ok=True)
    
    # Save with consistent filename
    file_ext = os.path.splitext(avatar.filename)[1] if avatar.filename else ".png"
    file_path = f"static/uploads/avatar{file_ext}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(avatar.file, buffer)
    
    # Redirect back to home
    return await home(request)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)