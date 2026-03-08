import json
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import asyncio
import os

KAFKA_URL = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')

class KafkaManager:
    @staticmethod
    async def get_producer():
        producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_URL,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        await producer.start()
        return producer

    @staticmethod
    async def get_consumer(topic, group_id):
        consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=KAFKA_URL,
            group_id=group_id,
            auto_offset_reset='earliest',
            value_deserializer=lambda v: json.loads(v.decode('utf-8'))
        )
        await consumer.start()
        return consumer
