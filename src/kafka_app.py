"""
Football analytics application using Kafka publish-subscribe architecture.
"""
import os
import json
import threading
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

# Configuration
FOOTBALL_DATA_API_KEY = os.getenv('FOOTBALL_DATA_API_KEY')
FOOTBALL_DATA_BASE_URL = 'https://api.football-data.org/v4'
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')

# Kafka topics
KAFKA_TOPIC_MATCHES = 'football-matches'
KAFKA_TOPIC_LIVE_UPDATES = 'football-live-updates'
KAFKA_TOPIC_STANDINGS = 'football-standings'
KAFKA_TOPIC_TEAMS = 'football-teams'
KAFKA_CONSUMER_GROUP = 'football-analytics-group'

# Configure logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import Kafka producer and consumer
from src.kafka_producer import FootballKafkaProducer
from src.kafka_consumer import FootballKafkaConsumer

# API client for Football-Data.org
class FootballDataAPI:
    def __init__(self):
        self.base_url = FOOTBALL_DATA_BASE_URL
        self.headers = {
            'X-Auth-Token': FOOTBALL_DATA_API_KEY
        }
        self.last_request_time = 0
        self.rate_limited = False
        self.rate_limit_reset = 0
        
        # Competition codes
        self.competitions = {
            'PL': 'Premier League',
            'BL1': 'Bundesliga',
            'SA': 'Serie A',
            'PD': 'La Liga',
            'FL1': 'Ligue 1'
        }
    
    def _rate_limit_request(self):
        """Implement rate limiting to respect API limits."""
        current_time = time.time()
        
        # If we've been rate limited, wait until reset time
        if self.rate_limited and current_time < self.rate_limit_reset:
            wait_time = self.rate_limit_reset - current_time
            logger.info(f"Rate limited. Waiting for {wait_time:.2f} seconds before next request")
            time.sleep(wait_time)
            self.rate_limited = False
        
        time_since_last_request = current_time - self.last_request_time
        
        # Ensure at least 15 seconds between requests (4 requests per minute to be very safe)
        if time_since_last_request < 15:
            sleep_time = 15 - time_since_last_request
            logger.info(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _make_request(self, endpoint, params=None, headers=None):
        """Make a request to the Football-Data.org API."""
        self._rate_limit_request()
        url = f"{self.base_url}/{endpoint}"
        
        # Merge default headers with any additional headers
        request_headers = self.headers.copy()
        if headers:
            request_headers.update(headers)
        
        try:
            response = requests.get(url, headers=request_headers, params=params)
            
            # Handle rate limiting
            if response.status_code == 429:
                logger.warning("Rate limit exceeded. Setting cooldown period.")
                self.rate_limited = True
                # Wait for 2 minutes before trying again
                self.rate_limit_reset = time.time() + 120
                return None
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return None
    
    def get_matches(self, competition_code=None, date_from=None, date_to=None, status=None):
        """Get matches for a specific competition or across competitions."""
        if date_from is None:
            date_from = datetime.now().strftime('%Y-%m-%d')
        if date_to is None:
            date_to = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        
        params = {
            'dateFrom': date_from,
            'dateTo': date_to
        }
        
        if status:
            params['status'] = status
        
        if competition_code:
            # Get matches for a specific competition
            endpoint = f'competitions/{competition_code}/matches'
        else:
            # Get matches across competitions
            endpoint = 'matches'
            # Limit to our tracked competitions
            params['competitions'] = ','.join(self.competitions.keys())
        
        response = self._make_request(endpoint, params)
        
        if response:
            if 'matches' in response:
                return response['matches']
            elif isinstance(response, list):
                return response
        
        return []
    
    def get_live_matches(self):
        """Get currently live matches across all tracked competitions."""
        return self.get_matches(status='LIVE')
    
    def get_upcoming_matches(self, days=3):
        """Get upcoming matches for the next few days."""
        today = datetime.now().strftime('%Y-%m-%d')
        future = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
        return self.get_matches(date_from=today, date_to=future, status='SCHEDULED')
    
    def get_match(self, match_id):
        """Get detailed information about a specific match."""
        return self._make_request(f'matches/{match_id}')
    
    def get_standings(self, competition_code):
        """Get current standings for a competition."""
        return self._make_request(f'competitions/{competition_code}/standings')
    
    def get_team(self, team_id):
        """Get detailed information about a specific team."""
        return self._make_request(f'teams/{team_id}')
    
    def get_team_matches(self, team_id, status=None, limit=10):
        """Get matches for a specific team."""
        params = {'limit': limit}
        if status:
            params['status'] = status
        
        return self._make_request(f'teams/{team_id}/matches', params)

# Data collector (Kafka producer)
class FootballDataCollector:
    """
    Collects football data from APIs and publishes it to Kafka topics.
    """
    def __init__(self):
        self.api = FootballDataAPI()
        self.producer = FootballKafkaProducer()
        self.running = False
        self.threads = []
    
    def collect_matches(self):
        """Collect match data and publish to Kafka."""
        logger.info("Collecting match data")
        
        # Get upcoming matches
        upcoming_matches = self.api.get_upcoming_matches()
        if upcoming_matches:
            logger.info(f"Collected {len(upcoming_matches)} upcoming matches")
            self.producer.send_message(KAFKA_TOPIC_MATCHES, {
                'timestamp': datetime.now().isoformat(),
                'type': 'upcoming',
                'matches': upcoming_matches
            })
        
        # Get live matches
        time.sleep(15)  # Wait to avoid rate limiting
        live_matches = self.api.get_live_matches()
        if live_matches:
            logger.info(f"Collected {len(live_matches)} live matches")
            self.producer.send_message(KAFKA_TOPIC_MATCHES, {
                'timestamp': datetime.now().isoformat(),
                'type': 'live',
                'matches': live_matches
            })
            
            # Get detailed match information for live matches
            for match in live_matches:
                match_id = match.get('id')
                if match_id:
                    time.sleep(15)  # Wait to avoid rate limiting
                    match_details = self.api.get_match(match_id)
                    
                    if match_details:
                        self.producer.send_message(KAFKA_TOPIC_LIVE_UPDATES, {
                            'timestamp': datetime.now().isoformat(),
                            'match_id': match_id,
                            'details': match_details
                        })
        else:
            logger.info("No live matches found")
    
    def collect_standings(self):
        """Collect standings data and publish to Kafka."""
        logger.info("Collecting Premier League standings")
        
        standings_data = self.api.get_standings('PL')
        
        if standings_data and 'standings' in standings_data:
            for standing_type in standings_data['standings']:
                if standing_type['type'] == 'TOTAL':
                    self.producer.send_message(KAFKA_TOPIC_STANDINGS, {
                        'timestamp': datetime.now().isoformat(),
                        'competition': 'PL',
                        'standings': standing_type['table']
                    })
                    logger.info("Published Premier League standings to Kafka")
                    break
    
    def collect_team_data(self, team_id):
        """Collect team data and publish to Kafka."""
        logger.info(f"Collecting data for team {team_id}")
        
        team_data = self.api.get_team(team_id)
        
        if team_data:
            self.producer.send_message(KAFKA_TOPIC_TEAMS, {
                'timestamp': datetime.now().isoformat(),
                'team_id': team_id,
                'data': team_data
            })
            logger.info(f"Published team data for team {team_id} to Kafka")
            return team_data
        
        return None
    
    def start_collection(self):
        """Start data collection threads."""
        if self.running:
            logger.warning("Data collection already running")
            return
        
        self.running = True
        
        # Create and start threads
        self.threads = [
            threading.Thread(target=self._collection_loop, args=(self.collect_matches, 300)),  # Every 5 minutes
            threading.Thread(target=self._collection_loop, args=(self.collect_standings, 3600))  # Every hour
        ]
        
        for thread in self.threads:
            thread.daemon = True
            thread.start()
        
        logger.info("Data collection started")
    
    def _collection_loop(self, collection_func, interval):
        """Run a collection function in a loop with the specified interval."""
        while self.running:
            try:
                collection_func()
            except Exception as e:
                logger.error(f"Error in collection function: {e}")
            
            # Sleep for the specified interval
            for _ in range(interval):
                if not self.running:
                    break
                time.sleep(1)
    
    def stop_collection(self):
        """Stop data collection threads."""
        self.running = False
        
        # Wait for threads to finish
        for thread in self.threads:
            thread.join(timeout=5)
        
        self.threads = []
        self.producer.close()
        logger.info("Data collection stopped")

# Data processor (Kafka consumer)
class FootballDataProcessor:
    """
    Processes football data from Kafka topics.
    """
    def __init__(self):
        self.consumer = FootballKafkaConsumer([
            KAFKA_TOPIC_MATCHES,
            KAFKA_TOPIC_LIVE_UPDATES,
            KAFKA_TOPIC_STANDINGS,
            KAFKA_TOPIC_TEAMS
        ])
        self.running = False
        
        # In-memory storage
        self.matches = {}
        self.live_updates = {}
        self.standings = {}
        self.teams = {}
    
    def process_message(self, topic, message):
        """Process a message from Kafka."""
        try:
            if topic == KAFKA_TOPIC_MATCHES:
                self._process_matches(message)
            elif topic == KAFKA_TOPIC_LIVE_UPDATES:
                self._process_live_update(message)
            elif topic == KAFKA_TOPIC_STANDINGS:
                self._process_standings(message)
            elif topic == KAFKA_TOPIC_TEAMS:
                self._process_team(message)
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def _process_matches(self, message):
        """Process matches data."""
        matches_type = message.get('type')
        matches_data = message.get('matches', [])
        
        for match in matches_data:
            match_id = match.get('id')
            if match_id:
                self.matches[match_id] = {
                    'data': match,
                    'type': matches_type,
                    'last_updated': datetime.now()
                }
        
        logger.info(f"Processed {len(matches_data)} {matches_type} matches")
    
    def _process_live_update(self, message):
        """Process a live match update."""
        match_id = message.get('match_id')
        match_details = message.get('details')
        
        if match_id and match_details:
            if match_id not in self.live_updates:
                self.live_updates[match_id] = []
            
            self.live_updates[match_id].append({
                'timestamp': datetime.now(),
                'details': match_details
            })
            
            # Keep only the last 10 updates
            if len(self.live_updates[match_id]) > 10:
                self.live_updates[match_id] = self.live_updates[match_id][-10:]
            
            logger.info(f"Processed live update for match {match_id}")
    
    def _process_standings(self, message):
        """Process standings data."""
        competition = message.get('competition')
        standings_data = message.get('standings')
        
        if competition and standings_data:
            self.standings[competition] = {
                'data': standings_data,
                'last_updated': datetime.now()
            }
            
            logger.info(f"Processed standings for {competition}")
    
    def _process_team(self, message):
        """Process team data."""
        team_id = message.get('team_id')
        team_data = message.get('data')
        
        if team_id and team_data:
            self.teams[team_id] = {
                'data': team_data,
                'last_updated': datetime.now()
            }
            
            logger.info(f"Processed team data for team {team_id}")
    
    def get_live_matches(self):
        """Get a list of currently live matches."""
        live_matches = []
        
        for match_id, match_info in self.matches.items():
            if match_info.get('type') == 'live':
                match_data = match_info.get('data')
                status = match_data.get('status')
                
                if status in ['LIVE', 'IN_PLAY', 'PAUSED']:
                    live_matches.append({
                        'match_id': match_id,
                        'home_team': match_data.get('homeTeam', {}).get('name'),
                        'home_team_id': match_data.get('homeTeam', {}).get('id'),
                        'away_team': match_data.get('awayTeam', {}).get('name'),
                        'away_team_id': match_data.get('awayTeam', {}).get('id'),
                        'score': f"{match_data.get('score', {}).get('fullTime', {}).get('home', 0)} - {match_data.get('score', {}).get('fullTime', {}).get('away', 0)}",
                        'status': status,
                        'competition': match_data.get('competition', {}).get('name')
                    })
        
        return live_matches
    
    def get_upcoming_matches(self):
        """Get a list of upcoming matches."""
        upcoming_matches = []
        
        for match_id, match_info in self.matches.items():
            if match_info.get('type') == 'upcoming':
                match_data = match_info.get('data')
                status = match_data.get('status')
                
                if status == 'SCHEDULED':
                    # Parse the UTC date
                    utc_date = match_data.get('utcDate')
                    match_date = datetime.fromisoformat(utc_date.replace('Z', '+00:00')) if utc_date else None
                    
                    if match_date:
                        # Format the date for display
                        formatted_date = match_date.strftime('%Y-%m-%d %H:%M')
                        
                        upcoming_matches.append({
                            'match_id': match_id,
                            'home_team': match_data.get('homeTeam', {}).get('name'),
                            'home_team_id': match_data.get('homeTeam', {}).get('id'),
                            'away_team': match_data.get('awayTeam', {}).get('name'),
                            'away_team_id': match_data.get('awayTeam', {}).get('id'),
                            'date': formatted_date,
                            'competition': match_data.get('competition', {}).get('name')
                        })
        
        # Sort by date
        upcoming_matches.sort(key=lambda x: x['date'])
        
        return upcoming_matches
    
    def get_match_summary(self, match_id):
        """Get a summary of a match."""
        if match_id not in self.matches:
            return None
        
        match_data = self.matches[match_id]['data']
        
        # Get the latest live update
        latest_update = None
        if match_id in self.live_updates and self.live_updates[match_id]:
            latest_update = self.live_updates[match_id][-1]['details']
        
        return {
            'match_id': match_id,
            'match_data': match_data,
            'latest_update': latest_update,
            'events': []  # Simplified version doesn't have events
        }
    
    def get_standings(self, competition):
        """Get standings for a competition."""
        if competition not in self.standings:
            return None
        
        return self.standings[competition]['data']
    
    def get_team(self, team_id):
        """Get team data."""
        if team_id not in self.teams:
            return None
        
        return self.teams[team_id]['data']
    
    def start_processing(self):
        """Start processing messages from Kafka."""
        if self.running:
            logger.warning("Data processing already running")
            return
        
        self.running = True
        
        # Start consuming messages
        threading.Thread(target=self._consume_messages).start()
        
        logger.info("Data processing started")
    
    def _consume_messages(self):
        """Consume messages from Kafka topics."""
        try:
            self.consumer.consume_forever(self.process_message)
        except Exception as e:
            logger.error(f"Error consuming messages: {e}")
            self.running = False
    
    def stop_processing(self):
        """Stop processing messages from Kafka."""
        self.running = False
        self.consumer.close()
        logger.info("Data processing stopped")

# Main function
def main():
    """Main function."""
    # Create data collector (producer)
    collector = FootballDataCollector()
    
    # Create data processor (consumer)
    processor = FootballDataProcessor()
    
    try:
        # Start data collection
        collector.start_collection()
        
        # Start data processing
        processor.start_processing()
        
        # Keep the main thread running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, stopping application")
        collector.stop_collection()
        processor.stop_processing()
    except Exception as e:
        logger.error(f"Error in main thread: {e}")
        collector.stop_collection()
        processor.stop_processing()

if __name__ == "__main__":
    main()
