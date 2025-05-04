"""
Configuration settings for the football analytics application.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Configuration
FOOTBALL_DATA_API_KEY = os.getenv('FOOTBALL_DATA_API_KEY')
FOOTBALL_DATA_BASE_URL = 'https://api.football-data.org/v4'

RAPID_API_KEY = os.getenv('RAPID_API_KEY')
RAPID_API_HOST = 'api-football-v1.p.rapidapi.com'
RAPID_API_BASE_URL = f'https://{RAPID_API_HOST}/v3'

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
KAFKA_TOPIC_MATCHES = 'football-matches'
KAFKA_TOPIC_LIVE_UPDATES = 'football-live-updates'
KAFKA_TOPIC_STATISTICS = 'football-statistics'
KAFKA_CONSUMER_GROUP = 'football-analytics-group'

# Flask Configuration
FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev_key')
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() in ('true', '1', 't')

# Data Collection Configuration
API_POLLING_INTERVAL = 60  # seconds
LEAGUES_TO_TRACK = [
    2021,  # Premier League
    2014,  # La Liga
    2019,  # Serie A
    2002,  # Bundesliga
    2015,  # Ligue 1
]
