"""Database client for Neon PostgreSQL (psycopg3, sync engine run in threads).

Connections are synchronous and executed via ``asyncio.to_thread`` so the client
works on every asyncio event loop, including Windows' default ProactorEventLoop
which psycopg's async mode cannot use.

One connection is kept per worker thread and reused, so a chat request no longer
pays for a new TLS handshake with Neon on every query. Neon suspends idle
connections, so a dropped connection is detected, discarded and retried once.

The public methods mirror the previous PostgREST-style interface, accepting
filters like ``{"video_id": "eq.123"}`` and ordering like ``"created_at.desc"``.
"""

import asyncio
import json
import logging
import re
import threading
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence, Tuple

import psycopg

from app.config import settings
from app.utils.errors import DatabaseError, DatabaseNotConfigured

logger = logging.getLogger(__name__)

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_FILTER_OPS = {
    "eq": "=",
    "neq": "<>",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
}

# One reusable connection per worker thread.
_local = threading.local()


def _ident(name: str) -> str:
    """Return a validated SQL identifier (prevents identifier injection)."""
    if name == "*":
        return "*"
    if not _IDENT_RE.match(name):
        raise DatabaseError("Invalid database identifier.")
    return name


def _adapt_param(value: Any) -> Any:
    """Convert Python containers into literals psycopg cannot send natively.

    ``jsonb`` columns receive JSON text and ``vector`` columns receive a
    pgvector literal (``[0.1,0.2,...]``). psycopg would otherwise try to send
    these as SQL arrays, which Postgres rejects for jsonb/vector targets.
    """
    if isinstance(value, dict):
        return json.dumps(value)
    if isinstance(value, (list, tuple)):
        if value and all(
            isinstance(item, (int, float)) and not isinstance(item, bool) for item in value
        ):
            return "[" + ",".join(repr(float(item)) for item in value) + "]"
        return json.dumps(list(value))
    return value


def _serialize(value: Any) -> Any:
    """Convert driver-specific types into JSON-friendly values for the schemas."""
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    return value


def _row_dict(columns: Sequence[str], row: Sequence[Any]) -> Dict[str, Any]:
    return {column: _serialize(value) for column, value in zip(columns, row)}


def _split_filter(raw: Any) -> Tuple[str, Any]:
    if isinstance(raw, str) and "." in raw:
        op, _, value = raw.partition(".")
        if op in _FILTER_OPS:
            return _FILTER_OPS[op], value
    return "=", raw


def _drop_connection() -> None:
    """Forget this thread's connection, closing it if it is still usable."""
    conn = getattr(_local, "conn", None)
    _local.conn = None
    if conn is None:
        return
    try:
        conn.close()
    except Exception:  # pragma: no cover - already broken
        pass


class NeonClient:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    # ------------------------------------------------------------ low level
    def _connection(self) -> "psycopg.Connection":
        conn = getattr(_local, "conn", None)
        if conn is not None:
            if not conn.closed:
                return conn
            _drop_connection()
        conn = psycopg.connect(self._dsn, autocommit=True)
        _local.conn = conn
        return conn

    def _run_sync(self, sql: str, params: Sequence[Any], fetch: Optional[str]):
        for attempt in range(2):
            try:
                conn = self._connection()
                with conn.cursor() as cur:
                    cur.execute(sql, list(params))
                    if cur.description is None:
                        return None
                    cols = [c.name for c in cur.description]
                    if fetch == "one":
                        row = cur.fetchone()
                        return _row_dict(cols, row) if row is not None else None
                    return [_row_dict(cols, row) for row in cur.fetchall()]
            except psycopg.OperationalError as exc:
                # Neon may have suspended the idle connection: reconnect once.
                _drop_connection()
                if attempt == 0:
                    logger.warning("Reconnecting to the database: %s", exc)
                    continue
                logger.error("Database connection error: %s", exc)
                raise DatabaseError(
                    "The database connection dropped. Please retry."
                ) from exc
            except psycopg.Error as exc:
                logger.error("Database error: %s", exc)
                raise DatabaseError("The database rejected the request. Please retry.") from exc
        raise DatabaseError("The database rejected the request. Please retry.")

    async def _run(self, sql: str, params: Sequence[Any] = (), fetch: Optional[str] = None):
        adapted = [_adapt_param(param) for param in params]
        return await asyncio.to_thread(self._run_sync, sql, adapted, fetch)

    def ping(self) -> None:
        """Open (and keep) this thread's connection. Used for warm-up."""
        self._run_sync("SELECT 1", [], "one")

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _where(filters: Optional[Dict[str, Any]]) -> Tuple[str, List[Any]]:
        if not filters:
            return "", []
        clauses: List[str] = []
        params: List[Any] = []
        for column, raw in filters.items():
            op, value = _split_filter(raw)
            clauses.append(f"{_ident(column)} {op} %s")
            params.append(value)
        return " WHERE " + " AND ".join(clauses), params

    @staticmethod
    def _order(order: Optional[str]) -> str:
        if not order:
            return ""
        parts: List[str] = []
        for token in order.split(","):
            token = token.strip()
            if not token:
                continue
            column, _, direction = token.partition(".")
            direction = direction.upper() if direction.lower() in {"asc", "desc"} else "ASC"
            parts.append(f"{_ident(column)} {direction}")
        return " ORDER BY " + ", ".join(parts) if parts else ""

    # ------------------------------------------------------------ public API
    async def select_one(self, table: str, filters: Dict[str, Any]) -> Optional[dict]:
        where, params = self._where(filters)
        sql = f"SELECT * FROM {_ident(table)}{where} LIMIT 1"
        return await self._run(sql, params, fetch="one")

    async def select(
        self,
        table: str,
        *,
        columns: str = "*",
        filters: Optional[Dict[str, Any]] = None,
        order: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        if columns == "*":
            col_sql = "*"
        else:
            col_sql = ", ".join(_ident(c.strip()) for c in columns.split(","))
        where, params = self._where(filters)
        sql = f"SELECT {col_sql} FROM {_ident(table)}{where}{self._order(order)}"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        if offset is not None:
            sql += f" OFFSET {int(offset)}"
        return await self._run(sql, params, fetch="all") or []

    async def insert(
        self, table: str, payload: Any, *, return_representation: bool = False
    ):
        rows = payload if isinstance(payload, list) else [payload]
        if not rows:
            return [] if return_representation else None
        columns = list(rows[0].keys())
        for column in columns:
            _ident(column)
        col_sql = ", ".join(columns)
        row_ph = "(" + ", ".join(["%s"] * len(columns)) + ")"
        placeholders = ", ".join([row_ph] * len(rows))
        params = [row[column] for row in rows for column in columns]
        sql = f"INSERT INTO {_ident(table)} ({col_sql}) VALUES {placeholders}"
        if return_representation:
            sql += " RETURNING *"
            return await self._run(sql, params, fetch="all")
        await self._run(sql, params, fetch=None)
        return None

    async def upsert(self, table: str, payload: Dict[str, Any], conflict_column: str):
        columns = list(payload.keys())
        for column in columns:
            _ident(column)
        col_sql = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))
        updates = ", ".join(
            f"{column} = EXCLUDED.{column}" for column in columns if column != conflict_column
        )
        sql = (
            f"INSERT INTO {_ident(table)} ({col_sql}) VALUES ({placeholders}) "
            f"ON CONFLICT ({_ident(conflict_column)}) DO UPDATE SET {updates} RETURNING *"
        )
        return await self._run(sql, [payload[column] for column in columns], fetch="all") or []

    async def update(self, table: str, filters: Dict[str, Any], payload: Dict[str, Any]) -> None:
        set_sql = ", ".join(f"{_ident(column)} = %s" for column in payload)
        where, where_params = self._where(filters)
        sql = f"UPDATE {_ident(table)} SET {set_sql}{where}"
        await self._run(sql, list(payload.values()) + where_params, fetch=None)

    async def delete(self, table: str, filters: Dict[str, Any]) -> None:
        where, params = self._where(filters)
        sql = f"DELETE FROM {_ident(table)}{where}"
        await self._run(sql, params, fetch=None)

    async def fetch_all(self, sql: str, params: Optional[Sequence[Any]] = None) -> List[dict]:
        return await self._run(sql, list(params or []), fetch="all") or []

    async def fetch_one(self, sql: str, params: Optional[Sequence[Any]] = None) -> Optional[dict]:
        return await self._run(sql, list(params or []), fetch="one")

    async def close(self) -> None:
        await asyncio.to_thread(_drop_connection)


_client: Optional[NeonClient] = None


def get_db() -> NeonClient:
    """Return the shared Neon client, creating it on first use."""
    global _client
    if _client is None:
        if not settings.neon_dsn:
            raise DatabaseNotConfigured()
        _client = NeonClient(settings.neon_dsn)
    return _client


async def close_db() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
