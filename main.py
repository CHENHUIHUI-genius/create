"""
Daily Health Tracker - Bowel Movement Tracking App
FastAPI backend with SQLite database
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
app = FastAPI(title="Daily Health Tracker")

# Setup templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Database setup
DB_NAME = "health_tracker.db"

def init_db():
    """Initialize SQLite database with required table"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            datetime TEXT NOT NULL,
            type TEXT NOT NULL,
            notes TEXT
        )
    """)
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()

# Pydantic model for record
class Record(BaseModel):
    id: int
    datetime: str
    type: str
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
    
    # Get statistics
    cursor.execute("SELECT COUNT(*) as total FROM records")
    total = cursor.fetchone()["total"]
    
    cursor.execute("SELECT type, COUNT(*) as count FROM records GROUP BY type")
    type_counts = {row["type"]: row["count"] for row in cursor.fetchall()}
    
    conn.close()
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "records": records,
        "total": total,
        "type_counts": type_counts
    })

@app.post("/add", response_class=HTMLResponse)
async def add_record(
    request: Request,
    datetime: str = Form(...),
    type: str = Form(...),
    notes: str = Form("")
):
    """Add a new record"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Parse datetime and format it nicely
    dt = datetime.fromisoformat(datetime.replace('T', ' '))
    formatted_datetime = dt.strftime("%Y-%m-%d %H:%M")
    
    cursor.execute(
        "INSERT INTO records (datetime, type, notes) VALUES (?, ?, ?)",
        (formatted_datetime, type, notes if notes else None)
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