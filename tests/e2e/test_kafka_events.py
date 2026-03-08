import pytest
import asyncio
from shared.kafka_utils import KafkaManager
import uuid
import datetime

@pytest.mark.asyncio
async def test_kafka_login_event_production():
    producer = await KafkaManager.get_producer()
    correlation_id = str(uuid.uuid4())
    event = {
        "correlation_id": correlation_id,
        "tenant_id": "test_tenant",
        "user_id": 999,
        "username": "test_user",
        "email": "test@example.com",
        "ip_address": "127.0.0.1",
        "device_fingerprint": "pytest-tester",
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    
    # Send and wait for ack
    await producer.send_and_wait("login_events", event)
    await producer.stop()

@pytest.mark.asyncio
async def test_anomaly_event_consumption():
    consumer = await KafkaManager.get_consumer("anomaly_events", "test-group")
    # This test expects the analytics service to be running and process a login event
    try:
        # We'll wait for a timeout if no event comes
        async with asyncio.timeout(10.0):
            async for msg in consumer:
                assert "anomaly_score" in msg.value
                assert "user_id" in msg.value
                break
    except asyncio.TimeoutError:
        pytest.fail("Timed out waiting for anomaly event from Kafka")
    finally:
        await consumer.stop()
