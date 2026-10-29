"""Reading-queue storage and queries."""
import datetime
import os
import sqlite3

STATUSES = ("to-read", "reading", "read", "skipped")

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    url TEXT,
    doi TEXT UNIQUE,
    priority INTEGER NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    status TEXT NOT NULL DEFAULT 'to-read',
    added TEXT NOT NULL,
    started TEXT,
    finished TEXT,
    pages INTEGER,
    rating INTEGER CHECK (rating IS NULL OR rating BETWEEN 1 AND 5),
    notes TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS tags (
    paper_id INTEGER REFERENCES papers(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    PRIMARY KEY (paper_id, tag)
);
"""


def default_db():
    return os.environ.get("READING_QUEUE_DB", os.path.join(os.path.expanduser("~"), ".reading_queue.sqlite"))


class ReadingQueue:
    """Manage papers to read. `today` can be injected for deterministic tests."""

    def __init__(self, path=None, today=None):
        self.db = sqlite3.connect(path or default_db())
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA)
        self._today = today

    def today(self):
        return (self._today or datetime.date.today()).isoformat()

    def close(self):
        self.db.close()

    def add(self, title, url=None, doi=None, priority=3, tags=(), pages=None):
        """Add a paper; returns its id. Raises ValueError if the DOI is already queued."""
        try:
            with self.db:
                cur = self.db.execute(
                    "INSERT INTO papers (title, url, doi, priority, added, pages) VALUES (?, ?, ?, ?, ?, ?)",
                    (title, url, doi.lower() if doi else None, priority, self.today(), pages))
                for t in tags:
                    self.db.execute("INSERT OR IGNORE INTO tags VALUES (?, ?)", (cur.lastrowid, t.lower()))
        except sqlite3.IntegrityError as exc:
            raise ValueError(str(exc)) from exc
        return cur.lastrowid

    def get(self, pid):
        row = self.db.execute("SELECT * FROM papers WHERE id = ?", (pid,)).fetchone()
        if row is None:
            raise KeyError(pid)
        d = dict(row)
        d["tags"] = [r[0] for r in self.db.execute("SELECT tag FROM tags WHERE paper_id = ? ORDER BY tag", (pid,))]
        return d

    def set_status(self, pid, status, rating=None):
        if status not in STATUSES:
            raise ValueError("status must be one of %s" % ", ".join(STATUSES))
        self.get(pid)
        with self.db:
            self.db.execute("UPDATE papers SET status = ? WHERE id = ?", (status, pid))
            if status == "reading":
                self.db.execute("UPDATE papers SET started = COALESCE(started, ?) WHERE id = ?", (self.today(), pid))
            if status == "read":
                self.db.execute("UPDATE papers SET finished = ?, started = COALESCE(started, ?) WHERE id = ?",
                                (self.today(), self.today(), pid))
            if rating is not None:
                self.db.execute("UPDATE papers SET rating = ? WHERE id = ?", (rating, pid))

    def note(self, pid, text):
        self.get(pid)
        with self.db:
            self.db.execute("UPDATE papers SET notes = TRIM(notes || char(10) || ?, char(10) || ' ') WHERE id = ?", (text, pid))

    def tag(self, pid, *tags):
        with self.db:
            for t in tags:
                self.db.execute("INSERT OR IGNORE INTO tags VALUES (?, ?)", (pid, t.lower()))

    def remove(self, pid):
        with self.db:
            self.db.execute("DELETE FROM papers WHERE id = ?", (pid,))

    def list(self, status=None, tag=None, search=None):
        """List papers ordered by status then priority (1 = highest) then age."""
        sql = "SELECT DISTINCT p.* FROM papers p LEFT JOIN tags t ON t.paper_id = p.id WHERE 1=1"
        args = []
        if status:
            sql += " AND p.status = ?"
            args.append(status)
        if tag:
            sql += " AND t.tag = ?"
            args.append(tag.lower())
        if search:
            sql += " AND (p.title LIKE ? OR p.notes LIKE ?)"
            args += ["%" + search + "%"] * 2
        sql += (" ORDER BY CASE p.status WHEN 'reading' THEN 0 WHEN 'to-read' THEN 1 WHEN 'read' THEN 2 ELSE 3 END,"
                " p.priority, p.added, p.id")
        return [dict(r) for r in self.db.execute(sql, args)]

    def next(self):
        """The paper to read next: one already in progress, else the top-priority unread paper."""
        rows = self.list("reading") or self.list("to-read")
        return rows[0] if rows else None

    def stats(self, days=30):
        """Counts per status, papers finished in the last `days`, mean days from added to finished."""
        counts = {s: 0 for s in STATUSES}
        for s, n in self.db.execute("SELECT status, COUNT(*) FROM papers GROUP BY status"):
            counts[s] = n
        since = (datetime.date.fromisoformat(self.today()) - datetime.timedelta(days=days)).isoformat()
        recent = self.db.execute("SELECT COUNT(*) FROM papers WHERE finished >= ?", (since,)).fetchone()[0]
        lag = self.db.execute("SELECT AVG(julianday(finished) - julianday(added)) FROM papers "
                              "WHERE finished IS NOT NULL").fetchone()[0]
        top_tags = self.db.execute("SELECT tag, COUNT(*) n FROM tags GROUP BY tag ORDER BY n DESC, tag LIMIT 5").fetchall()
        return {"counts": counts, "finished_recently": recent, "days": days,
                "mean_days_to_finish": round(lag, 1) if lag is not None else None,
                "top_tags": [(t, n) for t, n in top_tags]}
