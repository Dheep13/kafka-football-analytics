"""
Kafka consumer for processing football data from Kafka topics.
"""
from kafka import KafkaConsumer
from src.config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_CONSUMER_GROUP
)
from src.utils import deserialize_from_json, get_logger

logger = get_logger(__name__)

class FootballKafkaConsumer:
    """
    Kafka consumer for football data.
    """
    def __init__(self, topics, group_id=KAFKA_CONSUMER_GROUP, auto_offset_reset='latest'):
        """
        Initialize the Kafka consumer.
        
        Args:
            topics (list): List of Kafka topics to subscribe to.
            group_id (str, optional): Consumer group ID.
            auto_offset_reset (str, optional): Auto offset reset strategy.
        """
        self.topics = topics if isinstance(topics, list) else [topics]
        self.group_id = group_id
        self.auto_offset_reset = auto_offset_reset
        self.consumer = None
        self.connect()
    
    def connect(self):
        """
        Connect to Kafka broker and subscribe to topics.
        """
        try:
            self.consumer = KafkaConsumer(
                *self.topics,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                group_id=self.group_id,
                auto_offset_reset=self.auto_offset_reset,
                value_deserializer=lambda v: deserialize_from_json(v.decode('utf-8'))
            )
            logger.info(f"Connected to Kafka broker at {KAFKA_BOOTSTRAP_SERVERS}")
            logger.info(f"Subscribed to topics: {', '.join(self.topics)}")
        except Exception as e:
            logger.error(f"Failed to connect to Kafka broker: {e}")
            self.consumer = None
    
    def consume_messages(self, callback=None, timeout_ms=1000):
        """
        Consume messages from subscribed topics.
        
        Args:
            callback (callable, optional): Callback function to process messages.
            timeout_ms (int, optional): Poll timeout in milliseconds.
            
        Returns:
            list: List of consumed messages if no callback is provided.
        """
        if not self.consumer:
            logger.error("Kafka consumer not connected")
            return []
        
        try:
            messages = []
            message_pack = self.consumer.poll(timeout_ms=timeout_ms)
            
            for topic_partition, partition_messages in message_pack.items():
                for message in partition_messages:
                    if callback:
                        callback(message.topic, message.value)
                    else:
                        messages.append((message.topic, message.value))
            
            if not callback:
                return messages
        except Exception as e:
            logger.error(f"Error consuming messages: {e}")
            return []
    
    def consume_forever(self, callback):
        """
        Continuously consume messages and process them with the callback.
        
        Args:
            callback (callable): Callback function to process messages.
        """
        if not self.consumer:
            logger.error("Kafka consumer not connected")
            return
        
        try:
            for message in self.consumer:
                try:
                    callback(message.topic, message.value)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        except Exception as e:
            logger.error(f"Error in consumer loop: {e}")
        finally:
            self.close()
    
    def close(self):
        """
        Close the Kafka consumer.
        """
        if self.consumer:
            self.consumer.close()
            logger.info("Kafka consumer closed")
            self.consumer = None
