from collections.abc import AsyncGenerator

import pytest

from src.infrastructure.db.session import engine


@pytest.fixture(autouse=True)
async def cleanup_db_engine() -> AsyncGenerator[None, None]:
    yield
    await engine.dispose()
