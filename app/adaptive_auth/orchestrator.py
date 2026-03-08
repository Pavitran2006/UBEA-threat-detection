from __future__ import annotations

import asyncio
import json
import logging
import os
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)

try:
    from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
except Exception:  # pragma: no cover
    AIOKafkaConsumer = None
    AIOKafkaProducer = None


class AdaptiveAuthOrchestrator:
    def __init__(self) -> None:
        self.bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        self._producer: AIOKafkaProducer | None = None
        self._consumer: AIOKafkaConsumer | None = None
        self._consumer_task: asyncio.Task | None = None
        self._pending: dict[str, asyncio.Future] = {}
        self.latest_risk_by_user: dict[int, dict[str, Any]] = {}
        self.high_risk_alerts: dict[int, list[dict[str, Any]]] = defaultdict(list)
        self.invalidated_users: dict[int, dict[str, Any]] = {}
        self.locked_accounts: dict[int, dict[str, Any]] = {}
        self._subscribers: list[asyncio.Queue] = []

    @property
    def enabled(self) -> bool:
        return AIOKafkaProducer is not None and AIOKafkaConsumer is not None

    async def start(self) -> None:
        if not self.enabled:
            logger.warning("aiokafka not available; adaptive auth falls back to local scoring")
            return
        try:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
            await self._producer.start()

            self._consumer = AIOKafkaConsumer(
                "risk_updates",
                "session_invalidation",
                "account_lock",
                bootstrap_servers=self.bootstrap,
                group_id="auth-service-risk-consumer",
                auto_offset_reset="latest",
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            )
            await self._consumer.start()
            self._consumer_task = asyncio.create_task(self._consume_events())
            logger.info("Adaptive auth Kafka orchestrator started")
        except Exception:
            logger.exception("Unable to start Kafka orchestrator; falling back to local risk scoring")
            await self.stop()

    async def stop(self) -> None:
        if self._consumer_task:
            self._consumer_task.cancel()
            self._consumer_task = None
        if self._consumer:
            await self._consumer.stop()
            self._consumer = None
        if self._producer:
            await self._producer.stop()
            self._producer = None

    async def publish_login_event(self, event: dict[str, Any]) -> None:
        if not self._producer:
            return
        try:
            await self._producer.send_and_wait("login_events", event)
        except Exception:
            logger.exception("Failed to publish login event to Kafka")

    async def publish_session_event(self, event: dict[str, Any]) -> None:
        if not self._producer:
            return
        try:
            await self._producer.send_and_wait("session_events", event)
        except Exception:
            logger.exception("Failed to publish session event to Kafka")

    async def wait_for_risk(self, correlation_id: str, timeout: float = 5.0) -> dict[str, Any] | None:
        future = asyncio.get_running_loop().create_future()
        self._pending[correlation_id] = future
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            self._pending.pop(correlation_id, None)

    async def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    async def _broadcast(self, payload: dict[str, Any]) -> None:
        for queue in list(self._subscribers):
            try:
                if queue.full():
                    _ = queue.get_nowait()
                queue.put_nowait(payload)
            except Exception:
                self.unsubscribe(queue)

    async def _consume_events(self) -> None:
        if not self._consumer:
            return
        async for message in self._consumer:
            data = message.value
            topic = message.topic
            user_id = data.get("user_id")

            if topic == "risk_updates":
                correlation_id = data.get("correlation_id")
                risk_score = float(data.get("risk_score", 0.0))
                if isinstance(user_id, int):
                    self.latest_risk_by_user[user_id] = data
                    if risk_score > 70:
                        self.high_risk_alerts[user_id].append(data)
                        if len(self.high_risk_alerts[user_id]) > 20:
                            self.high_risk_alerts[user_id] = self.high_risk_alerts[user_id][-20:]
                if correlation_id and correlation_id in self._pending and not self._pending[correlation_id].done():
                    self._pending[correlation_id].set_result(data)
                await self._broadcast({"type": "risk_update", **data})
            elif topic == "session_invalidation":
                if isinstance(user_id, int):
                    self.invalidated_users[user_id] = data
                await self._broadcast({"type": "session_invalidation", **data})
            elif topic == "account_lock":
                if isinstance(user_id, int):
                    self.locked_accounts[user_id] = data
                await self._broadcast({"type": "account_lock", **data})
