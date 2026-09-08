import aiosqlite
from datetime import datetime

from .config import config

DB = config.db_path


async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.executescript('''
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
        CREATE TABLE IF NOT EXISTS bookings(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, username TEXT, name TEXT NOT NULL,
          phone TEXT, service TEXT NOT NULL, detail TEXT, duration INTEGER NOT NULL,
          start_at TEXT NOT NULL, end_at TEXT NOT NULL, comment TEXT, reference_file_id TEXT,
          status TEXT NOT NULL DEFAULT 'confirmed', reminder_sent INTEGER DEFAULT 0,
          confirmed_day_before INTEGER DEFAULT 0, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_bookings_start ON bookings(start_at,status);
        ''')
        await db.commit()


async def setting_get(key):
    async with aiosqlite.connect(DB) as db:
        async with db.execute('SELECT value FROM settings WHERE key=?',(key,)) as c:
            r=await c.fetchone(); return r[0] if r else None


async def setting_set(key,value):
    async with aiosqlite.connect(DB) as db:
        await db.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,str(value))); await db.commit()


async def overlaps(start,end,exclude_id=None):
    q="SELECT 1 FROM bookings WHERE status='confirmed' AND start_at < ? AND end_at > ?"; args=[end.isoformat(),start.isoformat()]
    if exclude_id: q+=' AND id != ?'; args.append(exclude_id)
    async with aiosqlite.connect(DB) as db:
        async with db.execute(q,args) as c: return await c.fetchone() is not None


async def create_booking(data):
    async with aiosqlite.connect(DB) as db:
        cur=await db.execute('''INSERT INTO bookings(user_id,username,name,phone,service,detail,duration,start_at,end_at,comment,reference_file_id,status,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(data['user_id'],data.get('username'),data['name'],data.get('phone'),data['service'],data.get('detail'),data['duration'],data['start_at'].isoformat(),data['end_at'].isoformat(),data.get('comment'),data.get('reference_file_id'),'confirmed',datetime.now().isoformat()))
        await db.commit(); return cur.lastrowid


async def get_booking(bid):
    async with aiosqlite.connect(DB) as db:
        db.row_factory=aiosqlite.Row
        async with db.execute('SELECT * FROM bookings WHERE id=?',(bid,)) as c: return await c.fetchone()


async def user_active(uid):
    async with aiosqlite.connect(DB) as db:
        db.row_factory=aiosqlite.Row
        async with db.execute("SELECT * FROM bookings WHERE user_id=? AND status='confirmed' AND start_at>=? ORDER BY start_at LIMIT 1",(uid,datetime.now().isoformat())) as c: return await c.fetchone()


async def list_range(start,end):
    async with aiosqlite.connect(DB) as db:
        db.row_factory=aiosqlite.Row
        async with db.execute("SELECT * FROM bookings WHERE status='confirmed' AND start_at>=? AND start_at<? ORDER BY start_at",(start.isoformat(),end.isoformat())) as c: return await c.fetchall()


async def cancel(bid):
    async with aiosqlite.connect(DB) as db: await db.execute("UPDATE bookings SET status='cancelled' WHERE id=?",(bid,)); await db.commit()


async def move(bid,start,end):
    async with aiosqlite.connect(DB) as db: await db.execute('UPDATE bookings SET start_at=?,end_at=?,confirmed_day_before=0,reminder_sent=0 WHERE id=?',(start.isoformat(),end.isoformat(),bid)); await db.commit()


async def mark_confirmed(bid):
    async with aiosqlite.connect(DB) as db: await db.execute('UPDATE bookings SET confirmed_day_before=1 WHERE id=?',(bid,)); await db.commit()


async def reminders_due(day_start,day_end):
    async with aiosqlite.connect(DB) as db:
        db.row_factory=aiosqlite.Row
        async with db.execute("SELECT * FROM bookings WHERE status='confirmed' AND reminder_sent=0 AND start_at>=? AND start_at<?",(day_start.isoformat(),day_end.isoformat())) as c:return await c.fetchall()


async def mark_reminder(bid):
    async with aiosqlite.connect(DB) as db: await db.execute('UPDATE bookings SET reminder_sent=1 WHERE id=?',(bid,)); await db.commit()
