"""
Kafka producer for sending football data to Kafka topics.
"""
from kafka import KafkaProducer
from src.config import KAFKA_BOOTSTRAP_SERVERS
from src.utils import serialize_to_json, get_logger

logger = get_logger(__name__)

class FootballKafkaProducer:
    """
    Kafka producer for football data.
    """
    def __init__(self):
        """
        Initialize the Kafka producer.
        """
        self.producer = None
        self.connect()
    
    def connect(self):
        """
        Connect to Kafka broker.
        """
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: serialize_to_json(v).encode('utf-8')
            )
            logger.info(f"Connected to Kafka broker at {KAFKA_BOOTSTRAP_SERVERS}")
        except Exception as e:
            logger.error(f"Failed to connect to Kafka broker: {e}")
            self.producer = None
    
    def send_message(self, topic, message):
        """
        Send a message to a Kafka topic.
        
        Args:
            topic (str): The Kafka topic to send the message to.
            message (dict): The message to send.
            
        Returns:
            bool: True if the message was sent successfully, False otherwise.
        """
        if not self.producer:
            logger.error("Kafka producer not connected")
            return False
        
        try:
            future = self.producer.send(topic, message)
            # Wait for the message to be sent
            future.get(timeout=10)
            logger.debug(f"Message sent to topic {topic}")
            return True
        except Exception as e:
            logger.error(f"Failed to send message to topic {topic}: {e}")
            return False
    
    def close(self):
        """
        Close the Kafka producer.
        """
        if self.producer:
            self.producer.close()
            logger.info("Kafka producer closed")
            self.producer = None
