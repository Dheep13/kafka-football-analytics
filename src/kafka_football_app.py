"""
Football analytics application using Kafka for publish-subscribe architecture.
Includes tumbling window processing and metrics collection.
"""
import os
import json
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
import requests
from kafka import KafkaProducer, KafkaConsumer

# Import our custom components
from window_processor import TumblingWindowProcessor
from metrics_collector import MetricsCollector

# Load environment variables
load_dotenv()

# Configuration
FOOTBALL_DATA_API_KEY = os.getenv('FOOTBALL_DATA_API_KEY')
FOOTBALL_DATA_BASE_URL = 'https://api.football-data.org/v4'
KAFKA_BOOTSTRAP_SERVERS = ['localhost:9092']

# Kafka topics
KAFKA_TOPIC_MATCHES = 'football-matches'
KAFKA_TOPIC_LIVE_UPDATES = 'football-live-updates'
KAFKA_TOPIC_STANDINGS = 'football-standings'
KAFKA_TOPIC_TEAMS = 'football-teams'

# Initialize Flask app
app = Flask(__name__, template_folder='../templates')
app.config['SECRET_KEY'] = 'football_analytics_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Configure logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# In-memory storage for processed data
matches_data = {}
standings_data = {}
teams_data = {}

# Initialize metrics collector and window processor
metrics = MetricsCollector(reporting_interval=60)  # Report metrics every minute
window_processor = TumblingWindowProcessor(window_size_seconds=300)  # 5-minute windows

# API client for Football-Data.org
class FootballDataAPI:
    def __init__(self):
        self.base_url = FOOTBALL_DATA_BASE_URL
        self.headers = {
            'X-Auth-Token': FOOTBALL_DATA_API_KEY
        }
        self.last_request_time = 0

    def _rate_limit_request(self):
        """Implement rate limiting to respect API limits."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        # Ensure at least 6 seconds between requests (10 requests per minute)
        if time_since_last_request < 6:
            sleep_time = 6 - time_since_last_request
            logger.info(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def get_matches(self, date_from=None, date_to=None, status=None):
        """Get matches across competitions."""
        self._rate_limit_request()

        # Record API call in metrics
        metrics.record_api_call('matches')

        start_time = time.time()

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

        url = f"{self.base_url}/matches"

        try:
            response = requests.get(url, headers=self.headers, params=params)

            if response.status_code == 429:
                logger.warning("Rate limit exceeded. Waiting for 60 seconds.")
                metrics.record_error('rate_limit_exceeded')
                time.sleep(60)
                return self.get_matches(date_from, date_to, status)

            response.raise_for_status()
            result = response.json()

            # Record processing time
            processing_time = (time.time() - start_time) * 1000  # Convert to ms
            metrics.record_processing_time('api_matches', processing_time)

            # Record data count
            if result and 'matches' in result:
                metrics.record_data_count('matches', len(result['matches']))

            return result
        except Exception as e:
            logger.error(f"Error getting matches: {e}")
            metrics.record_error('api_error')
            return None

    def get_standings(self, competition_code='PL'):
        """Get standings for a competition."""
        self._rate_limit_request()

        url = f"{self.base_url}/competitions/{competition_code}/standings"

        try:
            response = requests.get(url, headers=self.headers)

            if response.status_code == 429:
                logger.warning("Rate limit exceeded. Waiting for 60 seconds.")
                time.sleep(60)
                return self.get_standings(competition_code)

            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting standings: {e}")
            return None

    def get_team(self, team_id):
        """Get team details."""
        self._rate_limit_request()

        url = f"{self.base_url}/teams/{team_id}"

        try:
            response = requests.get(url, headers=self.headers)

            if response.status_code == 429:
                logger.warning("Rate limit exceeded. Waiting for 60 seconds.")
                time.sleep(60)
                return self.get_team(team_id)

            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting team: {e}")
            return None

# Kafka producer for publishing football data
class FootballKafkaProducer:
    def __init__(self):
        self.producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v, default=self._serialize_datetime).encode('utf-8')
        )
        logger.info("Kafka producer initialized")

    def _serialize_datetime(self, obj):
        """JSON serializer for datetime objects."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")

    def publish_matches(self, matches_data):
        """Publish matches data to Kafka."""
        message = {
            'timestamp': datetime.now().isoformat(),
            'data': matches_data
        }

        # Serialize the message to calculate its size
        serialized_message = json.dumps(message, default=self._serialize_datetime).encode('utf-8')
        message_size = len(serialized_message)

        # Send the message
        self.producer.send(KAFKA_TOPIC_MATCHES, message)

        # Record metrics
        metrics.record_kafka_message(KAFKA_TOPIC_MATCHES, message_size)

        logger.info(f"Published matches data to Kafka topic {KAFKA_TOPIC_MATCHES}")

    def publish_standings(self, standings_data):
        """Publish standings data to Kafka."""
        self.producer.send(KAFKA_TOPIC_STANDINGS, {
            'timestamp': datetime.now().isoformat(),
            'data': standings_data
        })
        logger.info(f"Published standings data to Kafka topic {KAFKA_TOPIC_STANDINGS}")

    def publish_team(self, team_id, team_data):
        """Publish team data to Kafka."""
        self.producer.send(KAFKA_TOPIC_TEAMS, {
            'timestamp': datetime.now().isoformat(),
            'team_id': team_id,
            'data': team_data
        })
        logger.info(f"Published team data for team {team_id} to Kafka topic {KAFKA_TOPIC_TEAMS}")

    def close(self):
        """Close the Kafka producer."""
        self.producer.close()
        logger.info("Kafka producer closed")

# Kafka consumer for processing football data
class FootballKafkaConsumer:
    def __init__(self):
        self.consumers = {}
        self.running = True

        # Start consumer threads
        self._start_matches_consumer()
        self._start_standings_consumer()
        self._start_teams_consumer()

        logger.info("Kafka consumers initialized")

    def _start_matches_consumer(self):
        """Start a consumer for the matches topic."""
        def consumer_thread():
            consumer = KafkaConsumer(
                KAFKA_TOPIC_MATCHES,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                auto_offset_reset='latest',
                value_deserializer=lambda x: json.loads(x.decode('utf-8'))
            )

            logger.info(f"Started consumer for topic {KAFKA_TOPIC_MATCHES}")

            for message in consumer:
                if not self.running:
                    break

                try:
                    self._process_matches_message(message.value)
                except Exception as e:
                    logger.error(f"Error processing matches message: {e}")

            consumer.close()
            logger.info(f"Closed consumer for topic {KAFKA_TOPIC_MATCHES}")

        thread = threading.Thread(target=consumer_thread)
        thread.daemon = True
        thread.start()

        self.consumers[KAFKA_TOPIC_MATCHES] = thread

    def _start_standings_consumer(self):
        """Start a consumer for the standings topic."""
        def consumer_thread():
            consumer = KafkaConsumer(
                KAFKA_TOPIC_STANDINGS,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                auto_offset_reset='latest',
                value_deserializer=lambda x: json.loads(x.decode('utf-8'))
            )

            logger.info(f"Started consumer for topic {KAFKA_TOPIC_STANDINGS}")

            for message in consumer:
                if not self.running:
                    break

                try:
                    self._process_standings_message(message.value)
                except Exception as e:
                    logger.error(f"Error processing standings message: {e}")

            consumer.close()
            logger.info(f"Closed consumer for topic {KAFKA_TOPIC_STANDINGS}")

        thread = threading.Thread(target=consumer_thread)
        thread.daemon = True
        thread.start()

        self.consumers[KAFKA_TOPIC_STANDINGS] = thread

    def _start_teams_consumer(self):
        """Start a consumer for the teams topic."""
        def consumer_thread():
            consumer = KafkaConsumer(
                KAFKA_TOPIC_TEAMS,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                auto_offset_reset='latest',
                value_deserializer=lambda x: json.loads(x.decode('utf-8'))
            )

            logger.info(f"Started consumer for topic {KAFKA_TOPIC_TEAMS}")

            for message in consumer:
                if not self.running:
                    break

                try:
                    self._process_team_message(message.value)
                except Exception as e:
                    logger.error(f"Error processing team message: {e}")

            consumer.close()
            logger.info(f"Closed consumer for topic {KAFKA_TOPIC_TEAMS}")

        thread = threading.Thread(target=consumer_thread)
        thread.daemon = True
        thread.start()

        self.consumers[KAFKA_TOPIC_TEAMS] = thread

    def _process_matches_message(self, message):
        """Process a matches message."""
        global matches_data

        start_time = time.time()

        data = message.get('data')
        if data and 'matches' in data:
            matches = data['matches']

            # Update matches data
            for match in matches:
                match_id = match.get('id')
                if match_id:
                    matches_data[match_id] = match

                    # Add to tumbling window for analytics
                    window_processor.add_event('match_update', match)

                    # Add specific events based on match status
                    status = match.get('status', 'UNKNOWN')
                    if status in ['LIVE', 'IN_PLAY']:
                        window_processor.add_event('live_match', match)
                    elif status == 'FINISHED':
                        window_processor.add_event('finished_match', match)

            # Record processing time
            processing_time = (time.time() - start_time) * 1000  # Convert to ms
            metrics.record_processing_time('process_matches', processing_time)

            logger.info(f"Processed {len(matches)} matches")

            # Emit update to connected clients
            socketio.emit('matches_update', json.dumps({
                'count': len(matches),
                'matches': matches[:5]  # Send first 5 matches as a preview
            }, default=str))

    def _process_standings_message(self, message):
        """Process a standings message."""
        global standings_data

        data = message.get('data')
        if data and 'standings' in data:
            for standing in data['standings']:
                if standing.get('type') == 'TOTAL':
                    standings_data['PL'] = standing.get('table', [])

                    logger.info(f"Processed standings with {len(standings_data['PL'])} teams")

                    # Emit update to connected clients
                    socketio.emit('standings_update', json.dumps({
                        'count': len(standings_data['PL']),
                        'standings': standings_data['PL'][:5]  # Send first 5 teams as a preview
                    }, default=str))

                    break

    def _process_team_message(self, message):
        """Process a team message."""
        global teams_data

        team_id = message.get('team_id')
        data = message.get('data')

        if team_id and data:
            teams_data[team_id] = data

            logger.info(f"Processed team data for team {team_id}")

            # Emit update to connected clients
            socketio.emit(f'team_update_{team_id}', json.dumps({
                'team_id': team_id,
                'name': data.get('name'),
                'crest': data.get('crest')
            }, default=str))

    def close(self):
        """Close all Kafka consumers."""
        self.running = False

        # Wait for threads to finish
        for topic, thread in self.consumers.items():
            thread.join(timeout=5)

        logger.info("Kafka consumers closed")

# Data collector for fetching football data
class FootballDataCollector:
    def __init__(self):
        self.api = FootballDataAPI()
        self.producer = FootballKafkaProducer()
        self.running = True
        self.threads = []

        logger.info("Football data collector initialized")

    def start_collection(self):
        """Start data collection threads."""
        # Create and start threads
        self.threads = [
            threading.Thread(target=self._collect_matches_periodically),
            threading.Thread(target=self._collect_standings_periodically)
        ]

        for thread in self.threads:
            thread.daemon = True
            thread.start()

        logger.info("Data collection started")

    def _collect_matches_periodically(self):
        """Collect matches data periodically (every 1 minute)."""
        while self.running:
            try:
                self._collect_matches()
            except Exception as e:
                logger.error(f"Error collecting matches: {e}")

            # Sleep for 1 minute
            for _ in range(60):
                if not self.running:
                    break
                time.sleep(1)

    def _collect_standings_periodically(self):
        """Collect standings data periodically."""
        while self.running:
            try:
                self._collect_standings()
            except Exception as e:
                logger.error(f"Error collecting standings: {e}")

            # Sleep for 1 hour
            for _ in range(3600):
                if not self.running:
                    break
                time.sleep(1)

    def _collect_matches(self):
        """Collect matches data and publish to Kafka."""
        logger.info("Collecting matches data")

        matches_data = self.api.get_matches()

        if matches_data:
            self.producer.publish_matches(matches_data)
            logger.info(f"Collected and published {len(matches_data.get('matches', []))} matches")
        else:
            logger.warning("Failed to collect matches data")

    def _collect_standings(self):
        """Collect standings data and publish to Kafka."""
        logger.info("Collecting standings data")

        standings_data = self.api.get_standings()

        if standings_data:
            self.producer.publish_standings(standings_data)
            logger.info("Collected and published standings data")
        else:
            logger.warning("Failed to collect standings data")

    def collect_team(self, team_id):
        """Collect team data and publish to Kafka."""
        logger.info(f"Collecting data for team {team_id}")

        team_data = self.api.get_team(team_id)

        if team_data:
            self.producer.publish_team(team_id, team_data)
            logger.info(f"Collected and published data for team {team_id}")
            return team_data
        else:
            logger.warning(f"Failed to collect data for team {team_id}")
            return None

    def stop_collection(self):
        """Stop data collection."""
        self.running = False

        # Wait for threads to finish
        for thread in self.threads:
            thread.join(timeout=5)

        # Close producer
        self.producer.close()

        logger.info("Data collection stopped")

# Initialize components
data_collector = FootballDataCollector()
data_consumer = FootballKafkaConsumer()

# Add shutdown hook to clean up resources
import atexit

@atexit.register
def cleanup():
    """Clean up resources on shutdown."""
    logger.info("Shutting down application...")
    data_collector.stop_collection()
    data_consumer.close()
    metrics.shutdown()
    window_processor.shutdown()
    logger.info("Application shutdown complete.")

# Flask routes
@app.route('/')
def index():
    """Render the main dashboard page."""
    return render_template('index.html')

@app.route('/standings')
def standings():
    """Render the standings page."""
    return render_template('standings.html')

@app.route('/team/<team_id>')
def team_profile(team_id):
    """Render the team profile page."""
    return render_template('team_profile.html', team_id=team_id)

@app.route('/match/<match_id>')
def match_details(match_id):
    """Render the match details page."""
    return render_template('match_details.html', match_id=match_id)

@app.route('/metrics')
def metrics_dashboard():
    """Render the metrics dashboard page."""
    return render_template('metrics.html')

# API routes
@app.route('/api/metrics')
def api_metrics():
    """Get application metrics."""
    return jsonify(metrics.get_metrics_summary())

@app.route('/api/windows')
def api_windows():
    """Get tumbling window data."""
    num_windows = request.args.get('num_windows', default=5, type=int)
    return jsonify(window_processor.get_window_metrics(num_windows))

@app.route('/api/windows/aggregated')
def api_windows_aggregated():
    """Get aggregated window metrics."""
    num_windows = request.args.get('num_windows', default=12, type=int)
    return jsonify(window_processor.get_aggregated_metrics(num_windows))

@app.route('/api/matches')
def api_matches():
    """Get matches data."""
    global matches_data

    # Convert matches_data dictionary to list
    matches_list = list(matches_data.values())

    # Sort by date
    matches_list.sort(key=lambda x: x.get('utcDate', ''))

    return jsonify({'matches': matches_list})

@app.route('/api/matches/live')
def api_matches_live():
    """Get live matches."""
    global matches_data

    # Convert matches_data dictionary to list
    matches_list = list(matches_data.values())

    # Filter live matches
    live_matches = [match for match in matches_list if match.get('status') in ['LIVE', 'IN_PLAY', 'PAUSED']]

    return jsonify({'matches': live_matches})

@app.route('/api/matches/upcoming')
def api_matches_upcoming():
    """Get upcoming matches."""
    global matches_data

    # Convert matches_data dictionary to list
    matches_list = list(matches_data.values())

    # Filter upcoming matches
    upcoming_matches = [match for match in matches_list if match.get('status') in ['SCHEDULED', 'TIMED']]

    # Sort by date
    upcoming_matches.sort(key=lambda x: x.get('utcDate', ''))

    # Limit to 10 matches
    upcoming_matches = upcoming_matches[:10]

    return jsonify({'matches': upcoming_matches})

@app.route('/api/standings/pl')
def api_pl_standings():
    """Get Premier League standings."""
    global standings_data

    if 'PL' in standings_data:
        return jsonify(standings_data['PL'])
    else:
        # If we don't have standings data, try to collect it
        standings_data_obj = data_collector.api.get_standings()

        if standings_data_obj and 'standings' in standings_data_obj:
            for standing in standings_data_obj['standings']:
                if standing.get('type') == 'TOTAL':
                    standings_data['PL'] = standing.get('table', [])
                    return jsonify(standings_data['PL'])

        return jsonify({'error': 'Standings not available'}), 404

@app.route('/api/team/<team_id>')
def api_team(team_id):
    """Get team details."""
    global teams_data

    try:
        team_id_int = int(team_id)
    except ValueError:
        return jsonify({'error': 'Invalid team ID'}), 400

    if team_id_int in teams_data:
        return jsonify(teams_data[team_id_int])
    else:
        # If we don't have team data, try to collect it
        team_data = data_collector.collect_team(team_id_int)

        if team_data:
            return jsonify(team_data)
        else:
            return jsonify({'error': 'Team not found'}), 404

@app.route('/api/team/<team_id>/matches')
def api_team_matches(team_id):
    """Get matches for a specific team."""
    try:
        team_id_int = int(team_id)
    except ValueError:
        return jsonify({'error': 'Invalid team ID'}), 400

    # Get all matches
    global matches_data
    matches_list = list(matches_data.values())

    # Filter matches for the specified team
    team_matches = []
    for match in matches_list:
        home_team = match.get('homeTeam', {})
        away_team = match.get('awayTeam', {})

        if (home_team.get('id') == team_id_int or away_team.get('id') == team_id_int):
            team_matches.append(match)

    # Sort matches by date
    team_matches.sort(key=lambda x: x.get('utcDate', ''))

    # Split into past and upcoming matches
    past_matches = []
    upcoming_matches = []

    for match in team_matches:
        if match.get('status') in ['FINISHED', 'AWARDED']:
            past_matches.append(match)
        elif match.get('status') in ['SCHEDULED', 'TIMED', 'IN_PLAY', 'PAUSED', 'SUSPENDED']:
            upcoming_matches.append(match)

    # Take only the last 5 past matches and next 5 upcoming matches
    past_matches = past_matches[-5:] if len(past_matches) > 5 else past_matches
    upcoming_matches = upcoming_matches[:5] if len(upcoming_matches) > 5 else upcoming_matches

    return jsonify({
        'past': past_matches,
        'upcoming': upcoming_matches
    })

@app.route('/api/match/<match_id>')
def api_match(match_id):
    """Get match details."""
    global matches_data

    try:
        match_id_int = int(match_id)
    except ValueError:
        return jsonify({'error': 'Invalid match ID'}), 400

    if match_id_int in matches_data:
        match_data = matches_data[match_id_int]

        # Get the latest live update (not implemented in this version)
        latest_update = None

        return jsonify({
            'match_id': match_id_int,
            'match_data': match_data,
            'latest_update': latest_update,
            'events': []  # Events not implemented in this version
        })
    else:
        return jsonify({'error': 'Match not found'}), 404

# Socket.IO events
@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    logger.info('Client connected')
    emit('connected', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    logger.info('Client disconnected')

# Main function
if __name__ == '__main__':
    try:
        # Start data collection
        data_collector.start_collection()

        # Start the Flask application
        socketio.run(app, host='0.0.0.0', port=5000, debug=True)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, stopping application")
        data_collector.stop_collection()
        data_consumer.close()
    except Exception as e:
        logger.error(f"Error in main thread: {e}")
        data_collector.stop_collection()
        data_consumer.close()
