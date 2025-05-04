"""
Analyzer for football match data.
"""
import pandas as pd
import numpy as np
import threading
import time
from collections import defaultdict
from src.kafka_consumer import FootballKafkaConsumer
from src.kafka_producer import FootballKafkaProducer
from src.config import (
    KAFKA_TOPIC_MATCHES,
    KAFKA_TOPIC_LIVE_UPDATES,
    KAFKA_TOPIC_STATISTICS
)
from src.utils import get_logger, parse_iso_datetime

logger = get_logger(__name__)

class MatchAnalyzer:
    """
    Analyzes football match data from Kafka topics.
    """
    def __init__(self):
        """
        Initialize the match analyzer.
        """
        self.matches = {}  # Match ID -> Match data
        self.live_updates = defaultdict(list)  # Match ID -> List of updates
        self.statistics = defaultdict(list)  # Match ID -> List of statistics
        
        self.consumer = FootballKafkaConsumer([
            KAFKA_TOPIC_MATCHES,
            KAFKA_TOPIC_LIVE_UPDATES,
            KAFKA_TOPIC_STATISTICS
        ])
        
        self.producer = FootballKafkaProducer()
        self.running = False
        self.lock = threading.Lock()
    
    def process_message(self, topic, message):
        """
        Process a message from Kafka.
        
        Args:
            topic (str): The Kafka topic.
            message (dict): The message data.
        """
        try:
            timestamp = parse_iso_datetime(message.get('timestamp'))
            
            with self.lock:
                if topic == KAFKA_TOPIC_MATCHES:
                    self._process_matches(message, timestamp)
                elif topic == KAFKA_TOPIC_LIVE_UPDATES:
                    self._process_live_update(message, timestamp)
                elif topic == KAFKA_TOPIC_STATISTICS:
                    self._process_statistics(message, timestamp)
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def _process_matches(self, message, timestamp):
        """
        Process matches data.
        
        Args:
            message (dict): The message data.
            timestamp (datetime): The message timestamp.
        """
        matches = message.get('matches', [])
        
        for match in matches:
            match_id = match.get('id')
            if match_id:
                self.matches[match_id] = {
                    'data': match,
                    'last_updated': timestamp
                }
    
    def _process_live_update(self, message, timestamp):
        """
        Process a live match update.
        
        Args:
            message (dict): The message data.
            timestamp (datetime): The message timestamp.
        """
        match_id = message.get('match_id')
        match_details = message.get('match_details')
        
        if match_id and match_details:
            self.live_updates[match_id].append({
                'timestamp': timestamp,
                'details': match_details
            })
            
            # Keep only the last 10 updates
            if len(self.live_updates[match_id]) > 10:
                self.live_updates[match_id] = self.live_updates[match_id][-10:]
    
    def _process_statistics(self, message, timestamp):
        """
        Process match statistics.
        
        Args:
            message (dict): The message data.
            timestamp (datetime): The message timestamp.
        """
        match_id = message.get('match_id')
        statistics = message.get('statistics')
        events = message.get('events')
        
        if match_id:
            self.statistics[match_id].append({
                'timestamp': timestamp,
                'statistics': statistics,
                'events': events
            })
            
            # Keep only the last 10 statistics updates
            if len(self.statistics[match_id]) > 10:
                self.statistics[match_id] = self.statistics[match_id][-10:]
    
    def analyze_possession(self, match_id):
        """
        Analyze possession trends for a match.
        
        Args:
            match_id (str): The match ID.
            
        Returns:
            dict: Possession analysis results.
        """
        if match_id not in self.statistics or not self.statistics[match_id]:
            return None
        
        try:
            # Extract possession data from statistics
            possession_data = []
            
            for stat_update in self.statistics[match_id]:
                stats = stat_update.get('statistics', [])
                timestamp = stat_update.get('timestamp')
                
                for team_stats in stats:
                    team = team_stats.get('team', {}).get('name')
                    
                    for stat in team_stats.get('statistics', []):
                        if stat.get('type') == 'Ball Possession':
                            value = stat.get('value', '0%')
                            # Convert percentage string to float
                            value = float(value.strip('%') if value else 0)
                            
                            possession_data.append({
                                'timestamp': timestamp,
                                'team': team,
                                'possession': value
                            })
            
            if not possession_data:
                return None
            
            # Convert to DataFrame for analysis
            df = pd.DataFrame(possession_data)
            
            # Group by team and calculate statistics
            possession_by_team = df.groupby('team')['possession'].agg([
                'mean', 'min', 'max', 'std'
            ]).reset_index()
            
            # Calculate possession trends over time
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            
            # Get unique teams
            teams = df['team'].unique()
            
            # Calculate trends for each team
            trends = {}
            for team in teams:
                team_data = df[df['team'] == team]
                if len(team_data) >= 2:
                    # Simple linear regression for trend
                    x = np.arange(len(team_data))
                    y = team_data['possession'].values
                    slope = np.polyfit(x, y, 1)[0]
                    trends[team] = {
                        'slope': slope,
                        'increasing': slope > 0,
                        'data_points': list(zip(
                            team_data['timestamp'].dt.strftime('%H:%M:%S').tolist(),
                            team_data['possession'].tolist()
                        ))
                    }
            
            return {
                'match_id': match_id,
                'possession_stats': possession_by_team.to_dict(orient='records'),
                'trends': trends
            }
        except Exception as e:
            logger.error(f"Error analyzing possession: {e}")
            return None
    
    def analyze_shots(self, match_id):
        """
        Analyze shots for a match.
        
        Args:
            match_id (str): The match ID.
            
        Returns:
            dict: Shot analysis results.
        """
        if match_id not in self.statistics or not self.statistics[match_id]:
            return None
        
        try:
            # Extract shots data from statistics
            shots_data = []
            
            for stat_update in self.statistics[match_id]:
                stats = stat_update.get('statistics', [])
                timestamp = stat_update.get('timestamp')
                
                for team_stats in stats:
                    team = team_stats.get('team', {}).get('name')
                    
                    for stat in team_stats.get('statistics', []):
                        if stat.get('type') in ['Total Shots', 'Shots on Goal']:
                            stat_type = stat.get('type')
                            value = stat.get('value', '0')
                            # Convert to integer
                            value = int(value) if value else 0
                            
                            shots_data.append({
                                'timestamp': timestamp,
                                'team': team,
                                'stat_type': stat_type,
                                'value': value
                            })
            
            if not shots_data:
                return None
            
            # Convert to DataFrame for analysis
            df = pd.DataFrame(shots_data)
            
            # Pivot to get shots by team and type
            pivot_df = df.pivot_table(
                index=['team', 'timestamp'],
                columns='stat_type',
                values='value',
                aggfunc='max'
            ).reset_index()
            
            # Rename columns for clarity
            pivot_df.columns.name = None
            if 'Total Shots' not in pivot_df.columns:
                pivot_df['Total Shots'] = 0
            if 'Shots on Goal' not in pivot_df.columns:
                pivot_df['Shots on Goal'] = 0
            
            # Calculate shot accuracy
            pivot_df['Shot Accuracy'] = (
                (pivot_df['Shots on Goal'] / pivot_df['Total Shots']) * 100
            ).fillna(0).round(2)
            
            # Group by team and calculate statistics
            shots_by_team = pivot_df.groupby('team').agg({
                'Total Shots': 'max',
                'Shots on Goal': 'max',
                'Shot Accuracy': 'mean'
            }).reset_index()
            
            # Get the latest shots data for each team
            pivot_df['timestamp'] = pd.to_datetime(pivot_df['timestamp'])
            latest_shots = pivot_df.sort_values('timestamp').groupby('team').last().reset_index()
            
            return {
                'match_id': match_id,
                'shots_stats': shots_by_team.to_dict(orient='records'),
                'latest_shots': latest_shots.to_dict(orient='records')
            }
        except Exception as e:
            logger.error(f"Error analyzing shots: {e}")
            return None
    
    def get_match_summary(self, match_id):
        """
        Get a summary of a match.
        
        Args:
            match_id (str): The match ID.
            
        Returns:
            dict: Match summary.
        """
        with self.lock:
            if match_id not in self.matches:
                return None
            
            match_data = self.matches[match_id]['data']
            
            # Get the latest live update
            latest_update = None
            if match_id in self.live_updates and self.live_updates[match_id]:
                latest_update = self.live_updates[match_id][-1]['details']
            
            # Get the latest statistics
            latest_stats = None
            if match_id in self.statistics and self.statistics[match_id]:
                latest_stats = self.statistics[match_id][-1]['statistics']
            
            # Get events
            events = []
            if match_id in self.statistics:
                for stat_update in self.statistics[match_id]:
                    if 'events' in stat_update and stat_update['events']:
                        events.extend(stat_update['events'])
            
            # Analyze possession and shots
            possession_analysis = self.analyze_possession(match_id)
            shots_analysis = self.analyze_shots(match_id)
            
            return {
                'match_id': match_id,
                'match_data': match_data,
                'latest_update': latest_update,
                'latest_stats': latest_stats,
                'events': events,
                'possession_analysis': possession_analysis,
                'shots_analysis': shots_analysis
            }
    
    def get_live_matches(self):
        """
        Get a list of currently live matches.
        
        Returns:
            list: List of live matches.
        """
        live_matches = []
        
        with self.lock:
            for match_id, match_info in self.matches.items():
                match_data = match_info['data']
                status = match_data.get('status')
                
                if status in ['LIVE', 'IN_PLAY', 'PAUSED']:
                    live_matches.append({
                        'match_id': match_id,
                        'home_team': match_data.get('homeTeam', {}).get('name'),
                        'away_team': match_data.get('awayTeam', {}).get('name'),
                        'score': f"{match_data.get('score', {}).get('fullTime', {}).get('home', 0)} - {match_data.get('score', {}).get('fullTime', {}).get('away', 0)}",
                        'status': status,
                        'competition': match_data.get('competition', {}).get('name')
                    })
        
        return live_matches
    
    def start_analysis(self):
        """
        Start the analysis process.
        """
        if self.running:
            logger.warning("Analysis already running")
            return
        
        self.running = True
        
        # Start the consumer thread
        self.consumer_thread = threading.Thread(target=self._consume_messages)
        self.consumer_thread.daemon = True
        self.consumer_thread.start()
        
        logger.info("Match analysis started")
    
    def _consume_messages(self):
        """
        Consume messages from Kafka topics.
        """
        try:
            self.consumer.consume_forever(self.process_message)
        except Exception as e:
            logger.error(f"Error in consumer thread: {e}")
            self.running = False
    
    def stop_analysis(self):
        """
        Stop the analysis process.
        """
        self.running = False
        
        # Wait for the consumer thread to finish
        if hasattr(self, 'consumer_thread'):
            self.consumer_thread.join(timeout=5)
        
        self.consumer.close()
        self.producer.close()
        logger.info("Match analysis stopped")


if __name__ == "__main__":
    analyzer = MatchAnalyzer()
    
    try:
        analyzer.start_analysis()
        
        # Keep the main thread running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, stopping analysis")
        analyzer.stop_analysis()
    except Exception as e:
        logger.error(f"Error in main thread: {e}")
        analyzer.stop_analysis()
