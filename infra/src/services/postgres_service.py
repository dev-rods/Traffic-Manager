"""
PostgreSQL Service for database operations.
Provides connection pooling and common database operations for Lambda functions.
"""
import os
from typing import Dict, List, Any, Optional, Generator
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool, extras


# Module-level connection pool (reused across Lambda invocations)
_connection_pool: Optional[pool.SimpleConnectionPool] = None


def _get_connection_pool() -> pool.SimpleConnectionPool:
    """
    Get or create the connection pool.
    The pool is created once and reused across Lambda invocations.
    """
    global _connection_pool

    if _connection_pool is None or _connection_pool.closed:
        _connection_pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=5,
            host=os.environ.get('RDS_HOST'),
            port=int(os.environ.get('RDS_PORT', 5432)),
            database=os.environ.get('RDS_DATABASE', 'trafficmanager'),
            user=os.environ.get('RDS_USERNAME'),
            password=os.environ.get('RDS_PASSWORD'),
            sslmode='require',
            connect_timeout=10
        )

    return _connection_pool


class PostgresService:
    """Service for PostgreSQL database operations."""

    def __init__(self):
        """Initialize the PostgreSQL service."""
        self._pool = _get_connection_pool()

    @contextmanager
    def _get_connection(self) -> Generator:
        """
        Context manager for getting a connection from the pool.
        Automatically returns the connection to the pool when done.
        """
        conn = None
        try:
            conn = self._pool.getconn()
            yield conn
        finally:
            if conn:
                self._pool.putconn(conn)

    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return results as a list of dictionaries.

        Args:
            query: SQL SELECT query
            params: Optional tuple of query parameters

        Returns:
            List of dictionaries with column names as keys
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cursor:
                cursor.execute(query, params)
                results = cursor.fetchall()
                return [dict(row) for row in results]

    def execute_write(self, query: str, params: Optional[tuple] = None) -> int:
        """
        Execute an INSERT, UPDATE, or DELETE query.

        Args:
            query: SQL write query
            params: Optional tuple of query parameters

        Returns:
            Number of affected rows
        """
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                conn.commit()
                return cursor.rowcount

    def execute_many(self, query: str, params_list: List[tuple]) -> int:
        """
        Execute a query multiple times with different parameters (batch operation).

        Args:
            query: SQL query with placeholders
            params_list: List of parameter tuples

        Returns:
            Total number of affected rows
        """
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.executemany(query, params_list)
                conn.commit()
                return cursor.rowcount

    def create_table(self, table_name: str, columns: Dict[str, str]) -> bool:
        """
        Create a table with the specified columns.

        Args:
            table_name: Name of the table to create
            columns: Dictionary mapping column names to their SQL definitions
                     Example: {"id": "SERIAL PRIMARY KEY", "name": "VARCHAR(255)"}

        Returns:
            True if successful
        """
        column_defs = ", ".join(f"{col} {definition}" for col, definition in columns.items())
        query = f"CREATE TABLE IF NOT EXISTS {table_name} ({column_defs})"

        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                conn.commit()
                return True

    def drop_table(self, table_name: str) -> bool:
        """
        Drop a table if it exists.

        Args:
            table_name: Name of the table to drop

        Returns:
            True if successful
        """
        query = f"DROP TABLE IF EXISTS {table_name}"

        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                conn.commit()
                return True

    def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists in the database.

        Args:
            table_name: Name of the table to check

        Returns:
            True if the table exists, False otherwise
        """
        query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = %s
            )
        """
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (table_name,))
                result = cursor.fetchone()
                return result[0] if result else False

    @contextmanager
    def transaction(self) -> Generator:
        """
        Context manager for database transactions.
        Commits on success, rolls back on exception.

        Usage:
            with service.transaction() as cursor:
                cursor.execute("INSERT INTO ...")
                cursor.execute("UPDATE ...")
        """
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            try:
                yield cursor
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cursor.close()

    def health_check(self) -> Dict[str, Any]:
        """
        Check database connectivity and return status information.

        Returns:
            Dictionary with health status and database info
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT version(), current_database(), current_user")
                    result = cursor.fetchone()
                    return {
                        "status": "healthy",
                        "version": result[0],
                        "database": result[1],
                        "user": result[2]
                    }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    def close(self) -> None:
        """
        Close all connections in the pool.
        Note: Usually not needed in Lambda as connections are reused.
        """
        global _connection_pool
        if _connection_pool:
            _connection_pool.closeall()
            _connection_pool = None
