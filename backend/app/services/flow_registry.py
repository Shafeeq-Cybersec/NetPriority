"""
flow_registry.py — in-memory store for classified flow records.

For Phase 1 all data is held in process memory.  A future phase can
swap this for a database by implementing the same interface.

Thread safety
-------------
FastAPI runs async handlers but uses a single-threaded event loop by
default (single worker).  For Phase 1 a plain dict is sufficient.
The registry is instantiated once as a module-level singleton and
injected via FastAPI's dependency-injection mechanism.
"""

from __future__ import annotations

from typing import Optional

from app.models.flow import FlowRecord


class FlowRegistry:
    """In-memory store for FlowRecord objects, keyed by flow_id (UUID str)."""

    def __init__(self) -> None:
        self._store: dict[str, FlowRecord] = {}

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def add(self, record: FlowRecord) -> FlowRecord:
        """Insert a new record.  Raises ValueError if ID already exists."""
        if record.flow_id in self._store:
            raise ValueError(f"Flow '{record.flow_id}' already exists.")
        self._store[record.flow_id] = record
        return record

    def update(self, record: FlowRecord) -> FlowRecord:
        """Replace an existing record.  Raises KeyError if not found."""
        if record.flow_id not in self._store:
            raise KeyError(f"Flow '{record.flow_id}' not found.")
        self._store[record.flow_id] = record
        return record

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get(self, flow_id: str) -> Optional[FlowRecord]:
        """Return the record for flow_id, or None if not found."""
        return self._store.get(flow_id)

    def all(self) -> list[FlowRecord]:
        """Return all records ordered by creation time (oldest first)."""
        return sorted(
            self._store.values(),
            key=lambda r: r.created_at,
        )

    def count(self) -> int:
        return len(self._store)

    # ------------------------------------------------------------------
    # Test helpers
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Remove all records.  Used only in tests."""
        self._store.clear()


# Module-level singleton — imported by the router and tests alike.
flow_registry = FlowRegistry()
