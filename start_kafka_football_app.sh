#!/bin/bash

# Check if Kafka is running
if ! docker ps | grep -q "kafka"; then
    echo "Kafka is not running. Starting Kafka containers..."
    docker-compose -f kafka-docker-compose.yml up -d
    
    # Wait for Kafka to be ready
    echo "Waiting for Kafka to be ready..."
    sleep 20
else
    echo "Kafka is already running."
fi

# Start the Kafka-based football application
echo "Starting Kafka-based football application..."
python src/kafka_football_app.py
