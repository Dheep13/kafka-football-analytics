"""
Test script to verify that Kafka is working.
"""
import json
import time
from kafka import KafkaProducer, KafkaConsumer

def test_kafka_producer():
    """Test Kafka producer."""
    print("Testing Kafka producer...")

    try:
        # Create producer
        producer = KafkaProducer(
            bootstrap_servers=['localhost:9092'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

        # Send a test message
        producer.send('test-topic', {'message': 'Hello, Kafka!'})
        producer.flush()

        print("Successfully sent message to Kafka")
        return True
    except Exception as e:
        print(f"Error sending message to Kafka: {e}")
        return False

def test_kafka_consumer():
    """Test Kafka consumer."""
    print("Testing Kafka consumer...")

    try:
        # Create consumer
        consumer = KafkaConsumer(
            'test-topic',
            bootstrap_servers=['localhost:9092'],
            auto_offset_reset='earliest',
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            consumer_timeout_ms=10000  # 10 seconds timeout
        )

        # Try to get a message
        print("Waiting for messages...")
        for message in consumer:
            print(f"Received message: {message.value}")
            return True

        print("No messages received within timeout")
        return False
    except Exception as e:
        print(f"Error consuming message from Kafka: {e}")
        return False

if __name__ == "__main__":
    # Start Kafka containers
    import os
    print("Starting Kafka containers...")
    os.system("docker-compose -f kafka-docker-compose.yml up -d")

    # Wait for Kafka to be ready
    print("Waiting for Kafka to be ready...")
    time.sleep(30)

    # Test producer
    producer_result = test_kafka_producer()

    # Wait for message to be processed
    time.sleep(5)

    # Test consumer
    consumer_result = test_kafka_consumer()

    # Print results
    print("\nResults:")
    print(f"Producer test: {'PASSED' if producer_result else 'FAILED'}")
    print(f"Consumer test: {'PASSED' if consumer_result else 'FAILED'}")

    if producer_result and consumer_result:
        print("\nKafka is working correctly!")
    else:
        print("\nKafka is not working correctly. Please check the error messages above.")
