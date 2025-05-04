"""
Data collector for football data from external APIs.
"""
import time
import threading
from datetime import datetime
from src.football_api import FootballDataAPI, APIFootball
from src.kafka_producer import FootballKafkaProducer
from src.config import (
    KAFKA_TOPIC_MATCHES,
    KAFKA_TOPIC_LIVE_UPDATES,
    KAFKA_TOPIC_STATISTICS,
    API_POLLING_INTERVAL
)
from src.utils import get_logger

logger = get_logger(__name__)

class FootballDataCollector:
    """
    Collects football data from APIs and sends it to Kafka topics.
    """
    def __init__(self):
        """
        Initialize the data collector.
        """
        self.football_data_api = FootballDataAPI()
        self.api_football = APIFootball()
        self.kafka_producer = FootballKafkaProducer()
        self.running = False
        self.threads = []
    
    def collect_matches(self):
        """
        Collect match data and send it to Kafka.
        """
        logger.info("Collecting match data")
        matches = self.football_data_api.get_matches()
        
        if matches:
            logger.info(f"Collected {len(matches)} matches")
            self.kafka_producer.send_message(KAFKA_TOPIC_MATCHES, {
                'timestamp': datetime.now().isoformat(),
                'matches': matches
            })
        else:
            logger.warning("No matches collected")
    
    def collect_live_updates(self):
        """
        Collect live match updates and send them to Kafka.
        """
        logger.info("Collecting live match updates")
        live_matches = self.football_data_api.get_live_matches()
        
        if live_matches:
            logger.info(f"Collected updates for {len(live_matches)} live matches")
            
            for match in live_matches:
                match_id = match.get('id')
                if match_id:
                    # Get detailed match information
                    match_details = self.football_data_api.get_match(match_id)
                    
                    if match_details:
                        self.kafka_producer.send_message(KAFKA_TOPIC_LIVE_UPDATES, {
                            'timestamp': datetime.now().isoformat(),
                            'match_id': match_id,
                            'match_details': match_details
                        })
        else:
            logger.info("No live matches found")
    
    def collect_statistics(self):
        """
        Collect match statistics and send them to Kafka.
        """
        logger.info("Collecting match statistics")
        live_matches = self.football_data_api.get_live_matches()
        
        if live_matches:
            logger.info(f"Collecting statistics for {len(live_matches)} live matches")
            
            for match in live_matches:
                match_id = match.get('id')
                if match_id:
                    # Map Football-Data.org match ID to API-Football fixture ID
                    # This is a simplified approach - in a real application, you would need
                    # a more robust mapping between the two APIs
                    fixture_id = self._map_match_to_fixture(match)
                    
                    if fixture_id:
                        # Get statistics from API-Football
                        statistics = self.api_football.get_fixture_statistics(fixture_id)
                        events = self.api_football.get_fixture_events(fixture_id)
                        
                        if statistics or events:
                            self.kafka_producer.send_message(KAFKA_TOPIC_STATISTICS, {
                                'timestamp': datetime.now().isoformat(),
                                'match_id': match_id,
                                'fixture_id': fixture_id,
                                'statistics': statistics,
                                'events': events
                            })
        else:
            logger.info("No live matches found for statistics collection")
    
    def _map_match_to_fixture(self, match):
        """
        Map a Football-Data.org match to an API-Football fixture.
        
        Args:
            match (dict): Match data from Football-Data.org.
            
        Returns:
            int: API-Football fixture ID or None if not found.
        """
        # This is a simplified approach - in a real application, you would need
        # a more robust mapping between the two APIs
        try:
            home_team = match.get('homeTeam', {}).get('name')
            away_team = match.get('awayTeam', {}).get('name')
            match_date = match.get('utcDate', '').split('T')[0]
            
            if home_team and away_team and match_date:
                # Search for the fixture in API-Football
                fixtures = self.api_football.get_fixtures(date=match_date)
                
                for fixture in fixtures:
                    fixture_data = fixture.get('fixture', {})
                    teams = fixture.get('teams', {})
                    
                    fixture_home = teams.get('home', {}).get('name')
                    fixture_away = teams.get('away', {}).get('name')
                    
                    if (fixture_home and fixture_away and
                        home_team.lower() in fixture_home.lower() and
                        away_team.lower() in fixture_away.lower()):
                        return fixture_data.get('id')
            
            return None
        except Exception as e:
            logger.error(f"Error mapping match to fixture: {e}")
            return None
    
    def start_collection(self):
        """
        Start data collection threads.
        """
        if self.running:
            logger.warning("Data collection already running")
            return
        
        self.running = True
        
        # Create and start threads
        self.threads = [
            threading.Thread(target=self._collection_loop, args=(self.collect_matches, 3600)),  # Hourly
            threading.Thread(target=self._collection_loop, args=(self.collect_live_updates, API_POLLING_INTERVAL)),  # Every minute
            threading.Thread(target=self._collection_loop, args=(self.collect_statistics, API_POLLING_INTERVAL * 2))  # Every 2 minutes
        ]
        
        for thread in self.threads:
            thread.daemon = True
            thread.start()
        
        logger.info("Data collection started")
    
    def _collection_loop(self, collection_func, interval):
        """
        Run a collection function in a loop with the specified interval.
        
        Args:
            collection_func (callable): The collection function to run.
            interval (int): The interval in seconds.
        """
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
        """
        Stop data collection threads.
        """
        self.running = False
        
        # Wait for threads to finish
        for thread in self.threads:
            thread.join(timeout=5)
        
        self.threads = []
        self.kafka_producer.close()
        logger.info("Data collection stopped")


if __name__ == "__main__":
    collector = FootballDataCollector()
    
    try:
        collector.start_collection()
        
        # Keep the main thread running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, stopping data collection")
        collector.stop_collection()
    except Exception as e:
        logger.error(f"Error in main thread: {e}")
        collector.stop_collection()
