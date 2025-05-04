#!/bin/bash

# Start Kafka containers
echo "Starting Kafka containers..."
docker-compose -f kafka-docker-compose.yml up -d

# Wait for Kafka to be ready
echo "Waiting for Kafka to be ready..."
sleep 20

# List topics
echo "Kafka topics:"
docker exec kafka /opt/kafka/bin/kafka-topics.sh --list --bootstrap-server localhost:9092

echo "Kafka is ready!"
