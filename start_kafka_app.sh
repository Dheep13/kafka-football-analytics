#!/bin/bash

# Start Kafka containers if not already running
if [ ! "$(docker ps -q -f name=kafka)" ]; then
    echo "Starting Kafka containers..."
    ./start_kafka.sh
else
    echo "Kafka containers are already running."
fi

# Start the Kafka-based web application
echo "Starting Kafka-based web application..."
python src/kafka_web_app.py
