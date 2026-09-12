from typing import Any, List, Optional
from uuid import UUID
from .database import DatabaseManager
from .models import Execution, Task, Workflow

class BaseRepository:
    """Base repository with common patterns."""
    def __init__(self, db: DatabaseManager):
        self.db = db

class ExecutionRepository(BaseRepository):
    """Repository for Executions."""
    async def create(
        self,
        execution: Any,
        project_id: Optional[UUID] = None,
        workflow_version_id: Optional[UUID] = None,
        status: Optional[str] = None,
    ) -> None:
        hv_str = None
        if hasattr(execution, "id"):
            eid = execution.id
            pid = getattr(execution, "project_id", None) or project_id
            tid = getattr(execution, "task_id", None)
            wid = getattr(execution, "workflow_version_id", None) or workflow_version_id
            st = str(getattr(execution, "status", status or "pending"))
            if getattr(execution, "human_verification", None):
                hv_str = execution.human_verification.model_dump_json()
        else:
            eid = execution
            pid = project_id
            tid = None
            wid = workflow_version_id
            st = status or "pending"

        query = 'INSERT INTO executions (id, project_id, task_id, workflow_version_id, status, human_verification, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, datetime("now"), datetime("now"))'
        async with self.db.get_connection() as conn:
            await conn.execute(query, (str(eid), str(pid) if pid else None, str(tid) if tid else None, str(wid) if wid else None, st, hv_str))
            await conn.commit()

    @staticmethod
    def _parse_row(cols: list[str], row: tuple) -> Execution:
        import json
        data = dict(zip(cols, row))
        if data.get("human_verification") and isinstance(data["human_verification"], str):
            try:
                data["human_verification"] = json.loads(data["human_verification"])
            except Exception:
                pass
        if data.get("result") and isinstance(data["result"], str):
            try:
                data["result"] = json.loads(data["result"])
            except Exception:
                pass
        return Execution.model_validate(data)

    async def get(self, execution_id: UUID) -> Optional[Execution]:
        query = 'SELECT * FROM executions WHERE id = ?'
        async with self.db.get_connection() as conn:
            async with conn.execute(query, (str(execution_id),)) as cursor:
                row = await cursor.fetchone()
                if row:
                    cols = [col[0] for col in cursor.description]
                    return self._parse_row(cols, row)
                return None

    async def update_status(self, execution_id: UUID, status: Any) -> None:
        query = 'UPDATE executions SET status = ?, updated_at = datetime("now") WHERE id = ?'
        async with self.db.get_connection() as conn:
            await conn.execute(query, (str(status), str(execution_id)))
            await conn.commit()

    async def update_human_verification(
        self,
        execution_id: UUID,
        status: Any,
        human_verification: Any,
        result: Any = None,
    ) -> None:
        import json
        hv_json = None
        if human_verification:
            if hasattr(human_verification, "model_dump_json"):
                hv_json = human_verification.model_dump_json()
            elif isinstance(human_verification, dict):
                hv_json = json.dumps(human_verification)
        res_json = json.dumps(result) if result is not None else None
        async with self.db.get_connection() as conn:
            if res_json is not None:
                try:
                    await conn.execute(
                        'UPDATE executions SET status = ?, human_verification = ?, result = ?, updated_at = datetime("now") WHERE id = ?',
                        (str(status), hv_json, res_json, str(execution_id))
                    )
                    await conn.commit()
                    return
                except Exception:
                    pass
            query = 'UPDATE executions SET status = ?, human_verification = ?, updated_at = datetime("now") WHERE id = ?'
            await conn.execute(query, (str(status), hv_json, str(execution_id)))
            await conn.commit()

    async def list_all(self) -> List[Execution]:
        query = 'SELECT * FROM executions ORDER BY created_at DESC'
        async with self.db.get_connection() as conn:
            async with conn.execute(query) as cursor:
                rows = await cursor.fetchall()
                cols = [col[0] for col in cursor.description]
                return [self._parse_row(cols, row) for row in rows]

    async def list_by_project(self, project_id: UUID) -> List[Execution]:
        query = 'SELECT * FROM executions WHERE project_id = ? ORDER BY created_at DESC'
        async with self.db.get_connection() as conn:
            async with conn.execute(query, (str(project_id),)) as cursor:
                rows = await cursor.fetchall()
                cols = [col[0] for col in cursor.description]
                return [self._parse_row(cols, row) for row in rows]

class TaskRepository(BaseRepository):
    """Repository for Tasks."""
    async def create(
        self,
        task: Any,
        intent_id: Optional[UUID] = None,
        status: Optional[str] = None,
    ) -> None:
        if hasattr(task, "id"):
            tid = task.id
            iid = getattr(task, "intent_id", None) or getattr(task, "intent_spec_id", None) or intent_id
            st = str(getattr(task, "status", status or "pending"))
        else:
            tid = task
            iid = intent_id
            st = status or "pending"

        query = 'INSERT INTO tasks (id, intent_id, status, created_at, updated_at) VALUES (?, ?, ?, datetime("now"), datetime("now"))'
        async with self.db.get_connection() as conn:
            await conn.execute(query, (str(tid), str(iid) if iid else None, st))
            await conn.commit()

    async def get(self, task_id: UUID) -> Optional[Task]:
        query = 'SELECT * FROM tasks WHERE id = ?'
        async with self.db.get_connection() as conn:
            async with conn.execute(query, (str(task_id),)) as cursor:
                row = await cursor.fetchone()
                if row:
                    data = dict(zip([col[0] for col in cursor.description], row))
                    return Task.model_validate(data)
                return None

    async def update_status(self, task_id: UUID, status: Any) -> None:
        query = 'UPDATE tasks SET status = ?, updated_at = datetime("now") WHERE id = ?'
        async with self.db.get_connection() as conn:
            await conn.execute(query, (str(status), str(task_id)))
            await conn.commit()

class WorkflowRepository(BaseRepository):
    """Repository for Workflows."""
    async def create(self, workflow_id: UUID, project_id: UUID, name: str) -> None:
        query = 'INSERT INTO workflows (id, project_id, name, created_at) VALUES (?, ?, ?, datetime("now"))'
        async with self.db.get_connection() as conn:
            await conn.execute(query, (str(workflow_id), str(project_id), name))
            await conn.commit()

    async def get_by_name(self, project_id: UUID, name: str) -> Optional[dict]:
        query = 'SELECT * FROM workflows WHERE project_id = ? AND name = ?'
        async with self.db.get_connection() as conn:
            async with conn.execute(query, (str(project_id), name)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(zip([col[0] for col in cursor.description], row))
                return None

    async def list_by_project(self, project_id: UUID) -> List[dict]:
        query = 'SELECT * FROM workflows WHERE project_id = ?'
        async with self.db.get_connection() as conn:
            async with conn.execute(query, (str(project_id),)) as cursor:
                rows = await cursor.fetchall()
                cols = [col[0] for col in cursor.description]
                return [dict(zip(cols, row)) for row in rows]

class CheckpointRepository(BaseRepository):
    """Repository for Checkpoints."""
    async def create(self, checkpoint_id: UUID, execution_id: UUID, data: str) -> None:
        query = 'INSERT INTO checkpoints (id, execution_id, data, created_at) VALUES (?, ?, ?, datetime("now"))'
        async with self.db.get_connection() as conn:
            await conn.execute(query, (str(checkpoint_id), str(execution_id), data))
            await conn.commit()

    async def get_latest(self, execution_id: UUID) -> Optional[dict]:
        query = 'SELECT * FROM checkpoints WHERE execution_id = ? ORDER BY created_at DESC LIMIT 1'
        async with self.db.get_connection() as conn:
            async with conn.execute(query, (str(execution_id),)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(zip([col[0] for col in cursor.description], row))
                return None

    async def get_by_execution(self, execution_id: UUID) -> List[dict]:
        query = 'SELECT * FROM checkpoints WHERE execution_id = ? ORDER BY created_at ASC'
        async with self.db.get_connection() as conn:
            async with conn.execute(query, (str(execution_id),)) as cursor:
                rows = await cursor.fetchall()
                cols = [col[0] for col in cursor.description]
                return [dict(zip(cols, row)) for row in rows]

class MemoryRepository(BaseRepository):
    """Repository for Memory Items."""
    async def create(self, memory_id: UUID, scope: str, key: str, value: str, confidence: float, provenance: str) -> None:
        query = 'INSERT INTO memory_items (id, scope, key, value, confidence, provenance, updated_at) VALUES (?, ?, ?, ?, ?, ?, datetime("now"))'
        async with self.db.get_connection() as conn:
            await conn.execute(query, (str(memory_id), scope, key, value, confidence, provenance))
            await conn.commit()

    async def query_by_scope(self, scope: str) -> List[dict]:
        query = 'SELECT * FROM memory_items WHERE scope = ?'
        async with self.db.get_connection() as conn:
            async with conn.execute(query, (scope,)) as cursor:
                rows = await cursor.fetchall()
                cols = [col[0] for col in cursor.description]
                return [dict(zip(cols, row)) for row in rows]

    async def update_confidence(self, memory_id: UUID, confidence: float) -> None:
        query = 'UPDATE memory_items SET confidence = ?, updated_at = datetime("now") WHERE id = ?'
        async with self.db.get_connection() as conn:
            await conn.execute(query, (confidence, str(memory_id)))
            await conn.commit()

class EventRepository(BaseRepository):
    """Event Repository (wrapper for EventStore)."""
    async def append(self, event: Any) -> None:
        from .events import EventStore
        store = EventStore(self.db)
        await store.append(event)
        
    async def query_by_execution(self, execution_id: UUID) -> List[Any]:
        from .events import EventStore
        store = EventStore(self.db)
        return await store.get_events(execution_id)
