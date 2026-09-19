"""Event bus for Server-Sent Events (SSE)

Manages pub/sub for real-time task updates. Backend publishes events,
frontend subscribes via SSE endpoint for instant updates.
"""

import asyncio
from datetime import datetime
from typing import AsyncGenerator, List
from collections import deque


class EventBus:
    """Async event bus for SSE subscriptions"""

    def __init__(self, max_queue_size: int = 1000):
        """Initialize event bus

        Args:
            max_queue_size: Maximum events to hold in memory
        """
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self.subscriber_count = 0
        self.events_published = 0
        self.last_event_time = None
        self.event_history: deque = deque(
            maxlen=100
        )  # Keep last 100 events for debugging

    async def publish(self, event_type: str, data: dict) -> None:
        """Publish event to all subscribers

        Args:
            event_type: Type of event (e.g., "task:created", "task:started")
            data: Event payload
        """
        try:
            event = {
                "type": event_type,
                "data": data,
                "timestamp": datetime.now().isoformat(),
            }

            # Add to history for debugging
            self.event_history.append(event)

            # Try to add to queue (non-blocking, drop if full)
            try:
                self.queue.put_nowait(event)
                self.events_published += 1
                self.last_event_time = datetime.now()
            except asyncio.QueueFull:
                print(f"[EventBus] Queue full, dropping event: {event_type}")
        except Exception as e:
            print(f"[EventBus] Error publishing event: {e}")

    async def subscribe(self, timeout: int = 30) -> AsyncGenerator:
        """Subscribe to event stream

        Args:
            timeout: Keepalive ping interval in seconds

        Yields:
            Event dictionaries
        """
        self.subscriber_count += 1
        try:
            while True:
                try:
                    event = await asyncio.wait_for(self.queue.get(), timeout=timeout)
                    yield event
                except asyncio.TimeoutError:
                    # Keepalive ping
                    yield {
                        "type": "ping",
                        "data": {},
                        "timestamp": datetime.now().isoformat(),
                    }
        finally:
            self.subscriber_count -= 1

    def get_stats(self) -> dict:
        """Get event bus statistics"""
        return {
            "subscribers": self.subscriber_count,
            "events_published": self.events_published,
            "queue_size": self.queue.qsize(),
            "last_event": (
                self.last_event_time.isoformat() if self.last_event_time else None
            ),
        }

    def get_recent_events(self, limit: int = 10) -> List[dict]:
        """Get recent events for debugging"""
        return list(self.event_history)[-limit:]


# Global event bus instance
event_bus = EventBus()


async def publish_task_created(
    task_id: str, agent: str, dept: str, title: str, status: str
) -> None:
    """Publish task:created event"""
    await event_bus.publish(
        "task:created",
        {
            "id": task_id,
            "agent": agent,
            "dept": dept,
            "title": title,
            "status": status,
        },
    )


async def publish_task_started(task_id: str, agent: str) -> None:
    """Publish task:started event"""
    await event_bus.publish(
        "task:started",
        {
            "id": task_id,
            "agent": agent,
        },
    )


async def publish_task_progress(task_id: str, progress: float) -> None:
    """Publish task:progress event"""
    await event_bus.publish(
        "task:progress",
        {
            "id": task_id,
            "progress": progress,
        },
    )


async def publish_task_completed(
    task_id: str, result: str, error: bool = False
) -> None:
    """Publish task:completed event"""
    await event_bus.publish(
        "task:completed",
        {
            "id": task_id,
            "result": result,
            "error": error,
        },
    )


async def publish_task_failed(task_id: str, error: str) -> None:
    """Publish task:failed event"""
    await event_bus.publish(
        "task:failed",
        {
            "id": task_id,
            "error": error,
        },
    )
