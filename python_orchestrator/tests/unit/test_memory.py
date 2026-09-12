"""Tests for WebCMD memory system."""
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4

from webcmd.config import WebCMDConfig
from webcmd.memory.confidence import ConfidenceEvaluator
from webcmd.memory.engine import MemoryEngine
from webcmd.memory.store import MemoryStore
from webcmd.state.enums import MemoryType
from webcmd.storage.database import DatabaseManager


@pytest.fixture
async def db(tmp_path: Path):
    config = WebCMDConfig(home_dir=tmp_path / ".webcmd")
    config.ensure_dirs()
    db = DatabaseManager(config.get_db_path())
    await db.initialize()
    yield db
    await db.close()


class TestConfidenceEvaluator:
    def test_fresh_high_success(self):
        e = ConfidenceEvaluator()
        c = e.compute_confidence(
            success_count=10, failure_count=0,
            last_verified=datetime.now(timezone.utc),
        )
        assert c > 0.7
    
    def test_stale_degrades(self):
        e = ConfidenceEvaluator()
        old = datetime.now(timezone.utc) - timedelta(days=60)
        c = e.compute_confidence(
            success_count=10, failure_count=0,
            last_verified=old,
        )
        assert c < 0.7
    
    def test_no_data_neutral(self):
        e = ConfidenceEvaluator()
        c = e.compute_confidence()
        assert 0.2 < c < 0.6
    
    def test_trust_thresholds(self):
        e = ConfidenceEvaluator()
        assert e.should_trust_directly(0.9)
        assert e.should_use_as_hint(0.5)
        assert e.should_explore(0.2)


class TestMemoryStore:
    async def test_store_and_query(self, db):
        store = MemoryStore(db)
        pid = uuid4()
        mid = await store.store(
            project_id=pid,
            memory_type=MemoryType.SITE,
            scope_type="site",
            scope_key="example.com",
            content={"url": "https://example.com"},
        )
        results = await store.query(pid, scope_key="example.com")
        assert len(results) >= 1
    
    async def test_record_success(self, db):
        store = MemoryStore(db)
        pid = uuid4()
        mid = await store.store(
            project_id=pid,
            memory_type=MemoryType.INTERACTION,
            scope_type="page",
            scope_key="test",
            content={},
        )
        await store.record_success(mid)
        results = await store.query(pid, scope_key="test")
        assert results[0]["success_count"] == 1
    
    async def test_invalidate(self, db):
        store = MemoryStore(db)
        pid = uuid4()
        mid = await store.store(
            project_id=pid,
            memory_type=MemoryType.SITE,
            scope_type="site",
            scope_key="old.com",
            content={},
            confidence=0.8,
        )
        await store.invalidate(mid, "site changed")
        results = await store.query(pid, scope_key="old.com")
        assert len(results) == 0  # Invalidated items filtered by default


class TestMemoryEngine:
    async def test_remember_and_recall(self, db):
        engine = MemoryEngine(db)
        pid = uuid4()
        await engine.remember_site(pid, "github.com", {"last_url": "https://github.com"})
        result = await engine.recall(pid, domain="github.com")
        assert result.found
