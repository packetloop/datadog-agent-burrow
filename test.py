# stdlib
from collections import defaultdict

# 3p
from kafka.client import KafkaClient
from kafka.consumer import SimpleConsumer

kafka_conn = KafkaClient("kafka:9092")
consumer = SimpleConsumer(kafka_conn, "sample_check", "test-topic",
                          auto_commit=True)

for message in consumer.get_messages(count=10):
    print message.offset
    consumer.commit()
