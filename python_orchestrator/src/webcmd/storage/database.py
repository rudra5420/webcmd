import aiosqlite
from contextlib import asynccontextmanager
from typing import AsyncGenerator

class DatabaseManager:
    """SQLite Database Manager."""
    def __init__(self, db_path: str):
        self.db_path = db_path

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Provide a transactional scope around a series of operations."""
        conn = await aiosqlite.connect(self.db_path)
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            await conn.close()

    async def close(self) -> None:
        """Close method for explicit resource cleanup."""
        pass

    async def initialize(self) -> None:
        """Initialize all tables based on domain models."""
        ddl = '''
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS intents (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            intent_id TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS workflows (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS workflow_versions (
            id TEXT PRIMARY KEY,
            workflow_id TEXT REFERENCES workflows(id),
            version INTEGER NOT NULL,
            definition TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS executions (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            task_id TEXT,
            workflow_version_id TEXT,
            status TEXT NOT NULL,
            human_verification TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS steps (
            id TEXT PRIMARY KEY,
            execution_id TEXT REFERENCES executions(id),
            name TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS workers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            metadata TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS worker_runs (
            id TEXT PRIMARY KEY,
            worker_id TEXT REFERENCES workers(id),
            execution_id TEXT REFERENCES executions(id),
            started_at TEXT NOT NULL,
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS observations (
            id TEXT PRIMARY KEY,
            step_id TEXT REFERENCES steps(id),
            content TEXT NOT NULL,
            captured_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS assertions (
            id TEXT PRIMARY KEY,
            step_id TEXT REFERENCES steps(id),
            evaluation TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS checkpoints (
            id TEXT PRIMARY KEY,
            execution_id TEXT REFERENCES executions(id),
            data TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS handoffs (
            id TEXT PRIMARY KEY,
            execution_id TEXT REFERENCES executions(id),
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS recovery_attempts (
            id TEXT PRIMARY KEY,
            execution_id TEXT REFERENCES executions(id),
            strategy TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS artifacts (
            id TEXT PRIMARY KEY,
            execution_id TEXT REFERENCES executions(id),
            path TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS memory_items (
            memory_id TEXT PRIMARY KEY,
            project_id TEXT,
            scope_type TEXT NOT NULL,
            scope_key TEXT NOT NULL,
            memory_type TEXT NOT NULL,
            content TEXT NOT NULL,
            provenance TEXT,
            confidence REAL NOT NULL,
            freshness_score REAL NOT NULL,
            last_verified_at TEXT,
            success_count INTEGER DEFAULT 0,
            failure_count INTEGER DEFAULT 0,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS site_profiles (
            site_id TEXT PRIMARY KEY,
            project_id TEXT,
            domain TEXT NOT NULL,
            last_visit_at TEXT,
            last_success_at TEXT,
            known_entrypoints TEXT,
            authentication_reference TEXT,
            environment_fingerprint TEXT,
            profile_version INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS policies (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            rules TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS approvals (
            id TEXT PRIMARY KEY,
            execution_id TEXT REFERENCES executions(id),
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audit_events (
            id TEXT PRIMARY KEY,
            action TEXT NOT NULL,
            actor TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS domain_events (
            event_id TEXT PRIMARY KEY,
            execution_id TEXT REFERENCES executions(id),
            event_type TEXT NOT NULL,
            sequence_number INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            payload TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_domain_events_exec_seq ON domain_events (execution_id, sequence_number);
        CREATE INDEX IF NOT EXISTS idx_steps_execution ON steps (execution_id);
        CREATE INDEX IF NOT EXISTS idx_observations_step ON observations (step_id);
        '''
        async with self.get_connection() as conn:
            await conn.executescript(ddl)
            try:
                await conn.execute("ALTER TABLE executions ADD COLUMN human_verification TEXT")
            except Exception:
                pass
            try:
                await conn.execute("ALTER TABLE executions ADD COLUMN result TEXT")
            except Exception:
                pass
            await conn.commit()
