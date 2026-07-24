"""SQLite persistence for spam report summaries."""

import sqlite3
from dataclasses import dataclass
from time import time

from pyspamcop.domain import Summary


@dataclass(frozen=True)
class LookupTable:
    """A single-column reference table used for de-duplicated lookups (name/email -> id)."""

    name: str
    column: str


_LOOKUP_TABLES = (
    LookupTable("email_content_type", "name"),
    LookupTable("spam_age_unit", "name"),
    LookupTable("email_charset", "name"),
    LookupTable("mailer", "name"),
    LookupTable("receiver", "email"),
)

_LOOKUP_COLUMN = {table.name: table.column for table in _LOOKUP_TABLES}

_LOOKUP_TABLES_DDL = "\n".join(
    f"""
CREATE TABLE IF NOT EXISTS {table.name} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    {table.column} TEXT NOT NULL UNIQUE
);
"""
    for table in _LOOKUP_TABLES
)

_SCHEMA = (
    _LOOKUP_TABLES_DDL
    + """
CREATE TABLE IF NOT EXISTS summary (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    tracking_id      TEXT NOT NULL UNIQUE,
    created          INTEGER NOT NULL,
    charset_id       INTEGER REFERENCES email_charset(id),
    content_type_id  INTEGER REFERENCES email_content_type(id),
    age              INTEGER,
    age_unit_id      INTEGER REFERENCES spam_age_unit(id),
    mailer_id        INTEGER REFERENCES mailer(id)
);
CREATE TABLE IF NOT EXISTS summary_receiver (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    summary_id  INTEGER NOT NULL REFERENCES summary(id),
    receiver_id INTEGER NOT NULL REFERENCES receiver(id),
    report_id   TEXT UNIQUE
);
"""
)


def _upsert_lookup(conn: sqlite3.Connection, table: str, value: str) -> int:
    column = _LOOKUP_COLUMN[table]
    conn.execute(f"INSERT OR IGNORE INTO {table} ({column}) VALUES (?)", (value,))
    row = conn.execute(f"SELECT id FROM {table} WHERE {column} = ?", (value,)).fetchone()
    return row[0]


class Recorder:
    """Persists SPAM report summaries to a local SQLite database."""

    def __init__(self, db_path: str, created: int | None = None) -> None:
        self._db_path = db_path
        self._created = created if created is not None else int(time())
        self._conn: sqlite3.Connection | None = None

    def init(self) -> bool:
        self._conn = sqlite3.connect(self._db_path)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        return True

    def save(self, summary: Summary) -> bool:
        if self._conn is None:
            raise RuntimeError("Recorder.init() must be called before save()")

        conn = self._conn

        charset_id = (
            _upsert_lookup(conn, "email_charset", summary.header.charset)
            if summary.header and summary.header.charset
            else None
        )
        content_type_id = (
            _upsert_lookup(conn, "email_content_type", summary.header.content_type)
            if summary.header and summary.header.content_type
            else None
        )
        mailer_id = (
            _upsert_lookup(conn, "mailer", summary.header.mailer) if summary.header and summary.header.mailer else None
        )
        age_unit_id = _upsert_lookup(conn, "spam_age_unit", summary.age.unit) if summary.age else None
        age = summary.age.amount if summary.age else None

        conn.execute(
            """
            INSERT OR IGNORE INTO summary
                (tracking_id, created, charset_id, content_type_id, age, age_unit_id, mailer_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (summary.tracking_id, self._created, charset_id, content_type_id, age, age_unit_id, mailer_id),
        )
        summary_id = conn.execute("SELECT id FROM summary WHERE tracking_id = ?", (summary.tracking_id,)).fetchone()[0]

        for receiver in summary.receivers:
            receiver_id = _upsert_lookup(conn, "receiver", receiver.address)
            report_id = receiver.report_id
            conn.execute(
                """
                INSERT OR IGNORE INTO summary_receiver (summary_id, receiver_id, report_id)
                VALUES (?, ?, ?)
                """,
                (summary_id, receiver_id, report_id),
            )

        conn.commit()
        return True
