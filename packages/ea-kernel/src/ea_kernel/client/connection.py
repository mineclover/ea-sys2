"""TypeDB client connection for ea-kernel.

Follows ea-typed patterns: lazy driver, context-managed transactions,
auto-commit for schema/write.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from typedb.driver import TypeDB, Credentials, DriverOptions, TransactionType


class KernelDBClient:
    """TypeDB client for the kernel metamodel."""

    DEFAULT_ADDRESS = "localhost:1729"
    DEFAULT_DATABASE = "ea_kernel"

    def __init__(
        self,
        address: str = DEFAULT_ADDRESS,
        database: str = DEFAULT_DATABASE,
        username: str = "admin",
        password: str = "password",
        use_tls: bool = False,
    ):
        self._address = address
        self._database = database
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._driver = None

    @property
    def driver(self):
        if self._driver is None:
            credentials = Credentials(self._username, self._password)
            options = DriverOptions(is_tls_enabled=self._use_tls)
            self._driver = TypeDB.driver(self._address, credentials, options)
        return self._driver

    @property
    def database(self) -> str:
        return self._database

    @database.setter
    def database(self, value: str) -> None:
        self._database = value

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    # ─── Database lifecycle ────────────────────────────────────────────

    def ensure_database(self, name: str | None = None) -> None:
        db_name = name or self._database
        if not self.driver.databases.contains(db_name):
            self.driver.databases.create(db_name)
        if name:
            self._database = name

    def drop_database(self, name: str | None = None) -> None:
        db_name = name or self._database
        if self.driver.databases.contains(db_name):
            self.driver.databases.get(db_name).delete()

    def reset_database(self, name: str | None = None) -> None:
        self.drop_database(name)
        self.ensure_database(name)

    # ─── Transactions ──────────────────────────────────────────────────

    @contextmanager
    def schema_transaction(self) -> Iterator:
        tx = self.driver.transaction(self._database, TransactionType.SCHEMA)
        try:
            yield tx
            tx.commit()
        finally:
            tx.close()

    @contextmanager
    def write_transaction(self) -> Iterator:
        tx = self.driver.transaction(self._database, TransactionType.WRITE)
        try:
            yield tx
            tx.commit()
        finally:
            tx.close()

    @contextmanager
    def read_transaction(self) -> Iterator:
        tx = self.driver.transaction(self._database, TransactionType.READ)
        try:
            yield tx
        finally:
            tx.close()

    # ─── Query helpers ─────────────────────────────────────────────────

    def execute_schema(self, query: str) -> None:
        with self.schema_transaction() as tx:
            tx.query(query).resolve()

    def execute_write(self, query: str) -> list[Any]:
        with self.write_transaction() as tx:
            result = tx.query(query).resolve()
            return list(result) if result else []

    def execute_read(self, query: str) -> list[Any]:
        with self.read_transaction() as tx:
            result = tx.query(query).resolve()
            return list(result) if result else []
