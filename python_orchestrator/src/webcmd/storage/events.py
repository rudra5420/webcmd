import asyncio
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID, uuid4
from datetime import datetime, timezone
from pydantic import BaseModel, Field

class DomainEvent(BaseModel):
    """Base domain event."""
    event_id: UUID = Field(default_factory=uuid4)
    execution_id: UUID
    event_type: str
    sequence_number: int = Field(default=0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: Dict[str, Any] = Field(default_factory=dict)

class ExecutionCreated(DomainEvent):
    event_type: str = "ExecutionCreated"

class ExecutionStatusChanged(DomainEvent):
    event_type: str = "ExecutionStatusChanged"

class StepStarted(DomainEvent):
    event_type: str = "StepStarted"

class StepStatusChanged(DomainEvent):
    event_type: str = "StepStatusChanged"

class StepCompleted(DomainEvent):
    event_type: str = "StepCompleted"

class ObservationCaptured(DomainEvent):
    event_type: str = "ObservationCaptured"

class VerificationEvaluated(DomainEvent):
    event_type: str = "VerificationEvaluated"

class CheckpointCreated(DomainEvent):
    event_type: str = "CheckpointCreated"

class RecoveryAttempted(DomainEvent):
    event_type: str = "RecoveryAttempted"

class HandoffRequested(DomainEvent):
    event_type: str = "HandoffRequested"

class PolicyEvaluated(DomainEvent):
    event_type: str = "PolicyEvaluated"

class ApprovalRequested(DomainEvent):
    event_type: str = "ApprovalRequested"

class ApprovalDecided(DomainEvent):
    event_type: str = "ApprovalDecided"

class HumanVerificationRequested(DomainEvent):
    event_type: str = "HumanVerificationRequested"

class HumanVerificationDecided(DomainEvent):
    event_type: str = "HumanVerificationDecided"

class WorkflowCompiled(DomainEvent):
    event_type: str = "WorkflowCompiled"

class MemoryUpdated(DomainEvent):
    event_type: str = "MemoryUpdated"

class PlanCreated(DomainEvent):
    event_type: str = "PlanCreated"

class EventStore:
    """Event store interface to be implemented by a repository or manager."""
    def __init__(self, db_manager):
        self.db = db_manager
        self._listeners: List[Callable[[DomainEvent], Any]] = []

    def add_listener(self, listener: Callable[[DomainEvent], Any]) -> None:
        """Register a subscriber callback for new events."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[DomainEvent], Any]) -> None:
        """Unregister a subscriber callback."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    async def append(self, event: DomainEvent) -> None:
        """Persist an event to the store and broadcast to active listeners."""
        import json
        async with self.db.get_connection() as conn:
            if event.sequence_number == 0:
                async with conn.execute(
                    "SELECT COALESCE(MAX(sequence_number), 0) + 1 FROM domain_events WHERE execution_id = ?",
                    (str(event.execution_id),)
                ) as cursor:
                    row = await cursor.fetchone()
                    event.sequence_number = row[0] if row else 1

            query = '''
                INSERT INTO domain_events (event_id, execution_id, event_type, sequence_number, timestamp, payload)
                VALUES (?, ?, ?, ?, ?, ?)
            '''
            await conn.execute(query, (
                str(event.event_id),
                str(event.execution_id),
                event.event_type,
                event.sequence_number,
                event.timestamp.isoformat(),
                json.dumps(event.payload)
            ))
            await conn.commit()

        # Notify subscribers
        for listener in list(self._listeners):
            try:
                res = listener(event)
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
            except Exception:
                pass

    async def get_events(self, execution_id: UUID) -> List[DomainEvent]:
        """Retrieve all events for an execution."""
        return await self.get_events_since(execution_id, 0)

    async def get_events_since(self, execution_id: UUID, sequence: int) -> List[DomainEvent]:
        """Get events after a sequence number."""
        query = '''
            SELECT event_id, execution_id, event_type, sequence_number, timestamp, payload
            FROM domain_events
            WHERE execution_id = ? AND sequence_number > ?
            ORDER BY sequence_number ASC
        '''
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(query, (str(execution_id), sequence))
            rows = await cursor.fetchall()
            
        import json
        events = []
        for row in rows:
            events.append(DomainEvent(
                event_id=UUID(row[0]),
                execution_id=UUID(row[1]),
                event_type=row[2],
                sequence_number=row[3],
                timestamp=datetime.fromisoformat(row[4]),
                payload=json.loads(row[5])
            ))
        return events

    async def replay(self, execution_id: UUID) -> Any:
        """Replay events to reconstruct state. (Returns a basic reconstructed view)."""
        events = await self.get_events(execution_id)
        # Simplified reconstruction logic
        state = {}
        for event in events:
            # Apply event logic
            pass
        return state
