from __future__ import annotations

import re
import sqlite3
from pathlib import Path


def _db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS files(
            path TEXT PRIMARY KEY,
            mtime_ns INTEGER NOT NULL,
            size INTEGER NOT NULL
        )"""
    )
    conn.execute(
        """CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(
            path UNINDEXED,
            heading,
            body,
            chunk_no UNINDEXED,
            tokenize='unicode61'
        )"""
    )
    return conn


def split_chunks(text: str, max_chars: int = 1800) -> list[tuple[str, str, int]]:
    heading = ""
    buffer: list[str] = []
    chunks: list[tuple[str, str, int]] = []
    chunk_no = 0

    def flush() -> None:
        nonlocal chunk_no
        if not buffer:
            return
        body = "\n".join(buffer).strip()
        buffer.clear()
        if not body:
            return
        for start in range(0, len(body), max_chars):
            piece = body[start : start + max_chars].strip()
            if piece:
                chunks.append((heading, piece, chunk_no))
                chunk_no += 1

    for line in text.splitlines():
        if re.match(r"^#{1,6}\s+", line):
            flush()
            heading = re.sub(r"^#{1,6}\s+", "", line).strip()
        else:
            buffer.append(line)
            if sum(len(item) + 1 for item in buffer) >= max_chars:
                flush()
    flush()
    return chunks


def refresh(markdown_dir: Path, index_path: Path) -> int:
    markdown_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in markdown_dir.rglob("*.md") if p.is_file())
    current = {str(path) for path in files}
    changed = 0

    with _db(index_path) as conn:
        known = {
            row[0]: (row[1], row[2])
            for row in conn.execute("SELECT path,mtime_ns,size FROM files")
        }

        for stale in set(known) - current:
            conn.execute("DELETE FROM chunks WHERE path=?", (stale,))
            conn.execute("DELETE FROM files WHERE path=?", (stale,))
            changed += 1

        for path in files:
            stat = path.stat()
            signature = (stat.st_mtime_ns, stat.st_size)
            if known.get(str(path)) == signature:
                continue
            conn.execute("DELETE FROM chunks WHERE path=?", (str(path),))
            for heading, body, number in split_chunks(path.read_text(errors="replace")):
                conn.execute(
                    "INSERT INTO chunks(path,heading,body,chunk_no) VALUES(?,?,?,?)",
                    (str(path), heading, body, number),
                )
            conn.execute(
                """INSERT INTO files(path,mtime_ns,size) VALUES(?,?,?)
                ON CONFLICT(path) DO UPDATE SET
                    mtime_ns=excluded.mtime_ns,
                    size=excluded.size""",
                (str(path), stat.st_mtime_ns, stat.st_size),
            )
            changed += 1
        conn.commit()
    return changed

def _terms(query: str) -> list[str]:
    seen = set()
    output = []
    for value in re.findall(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,}", query.lower()):
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output[:20]


def search(index_path: Path, query: str, limit: int = 5) -> list[dict]:
    terms = _terms(query)
    if not terms or not index_path.exists():
        return []

    match = " OR ".join(f'"{term}"' for term in terms)
    with _db(index_path) as conn:
        rows = conn.execute(
            """SELECT path,heading,body,bm25(chunks) AS rank
            FROM chunks
            WHERE chunks MATCH ?
            ORDER BY rank
            LIMIT ?""",
            (match, limit),
        ).fetchall()

    return [
        {
            "path": row[0],
            "heading": row[1],
            "text": row[2],
            "rank": row[3],
        }
        for row in rows
    ]
