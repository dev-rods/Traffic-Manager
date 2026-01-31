import os
import logging
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional

import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

_pool = None


def _get_connection_pool() -> SimpleConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        _pool = SimpleConnectionPool(
            minconn=1,
            maxconn=5,
            host=os.environ.get("RDS_HOST"),
            port=int(os.environ.get("RDS_PORT", "5432")),
            dbname=os.environ.get("RDS_DATABASE"),
            user=os.environ.get("RDS_USERNAME"),
            password=os.environ.get("RDS_PASSWORD"),
            options="-c search_path=scheduler,public"
        )
    return _pool


class PostgresService:

    def __init__(self):
        self._pool = _get_connection_pool()

    @contextmanager
    def _get_connection(self) -> Generator:
        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            self._pool.putconn(conn)

    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                results = cursor.fetchall()
                return [dict(row) for row in results]

    def execute_write(self, query: str, params: Optional[tuple] = None) -> int:
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                conn.commit()
                return cursor.rowcount

    def execute_write_returning(self, query: str, params: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                conn.commit()
                result = cursor.fetchone()
                return dict(result) if result else None

    def execute_many(self, query: str, params_list: List[tuple]) -> int:
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.executemany(query, params_list)
                conn.commit()
                return cursor.rowcount

    @contextmanager
    def transaction(self) -> Generator:
        with self._get_connection() as conn:
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def health_check(self) -> Dict[str, Any]:
        try:
            results = self.execute_query("SELECT 1 as status, NOW() as server_time")
            return {"status": "healthy", "server_time": str(results[0]["server_time"])}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    def close(self) -> None:
        global _pool
        if _pool and not _pool.closed:
            _pool.closeall()
            _pool = None
