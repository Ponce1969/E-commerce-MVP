import asyncio
import contextlib
from collections.abc import Generator

import pytest
from src.infrastructure.db.session import engine


@pytest.fixture(scope="session", autouse=True)
def cleanup_db_engine() -> Generator[None, None, None]:
    yield
    with contextlib.suppress(Exception):
        # Avoid hanging if engine was never connected or PostgreSQL is not reachable
        checked_in = getattr(engine.pool, "checkedin", lambda: 0)()
        checked_out = getattr(engine.pool, "checkedout", lambda: 0)()
        if checked_in > 0 or checked_out > 0:
            asyncio.run(asyncio.wait_for(engine.dispose(), timeout=2.0))
