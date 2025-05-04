"""
Simplified Flask web application for football analytics dashboard without Kafka.
"""
import json
import threading
import time
from datetime import datetime, timedelta
import os
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
FOOTBALL_DATA_API_KEY = os.getenv('FOOTBALL_DATA_API_KEY')
FOOTBALL_DATA_BASE_URL = 'https://api.football-data.org/v4'
FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'football_analytics_secret_key')

# Initialize Flask app
app = Flask(__name__, template_folder='../templates')
app.config['SECRET_KEY'] = FLASK_SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*")

# In-memory storage for match data
matches = {}
live_updates = {}
match_statistics = {}

# Logging setup
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

        # Ensure at least 10 seconds between requests (6 requests per minute limit to be safe)
        if time_since_last_request < 10:
            sleep_time = 10 - time_since_last_request
            logger.info(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _make_request(self, endpoint, params=None):
        """Make a request to the Football-Data.org API."""
        self._rate_limit_request()
        url = f"{self.base_url}/{endpoint}"

        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return None

    def get_matches(self, date_from=None, date_to=None, status=None):
        """Get matches within a date range."""
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

        # Reduced list of leagues to avoid rate limiting
        leagues = [
            2021,  # Premier League
            2014,  # La Liga
        ]

        all_matches = []
        for league_id in leagues:
            league_matches = self._make_request(f'competitions/{league_id}/matches', params)
            if league_matches and 'matches' in league_matches:
                all_matches.extend(league_matches['matches'])

        return all_matches

    def get_live_matches(self):
        """Get currently live matches."""
        return self.get_matches(status='LIVE')

    def get_match(self, match_id):
        """Get detailed information about a specific match."""
        return self._make_request(f'matches/{match_id}')

# Initialize API client
football_api = FootballDataAPI()

# Data collection functions
def collect_matches():
    """Collect match data."""
    logger.info("Collecting match data")
    collected_matches = football_api.get_matches()

    if collected_matches:
        logger.info(f"Collected {len(collected_matches)} matches")
        for match in collected_matches:
            match_id = match.get('id')
            if match_id:
                matches[match_id] = {
                    'data': match,
                    'last_updated': datetime.now()
                }
    else:
        logger.warning("No matches collected")

def collect_live_updates():
    """Collect live match updates."""
    logger.info("Collecting live match updates")
    live_matches = football_api.get_live_matches()

    if live_matches:
        logger.info(f"Collected updates for {len(live_matches)} live matches")

        for match in live_matches:
            match_id = match.get('id')
            if match_id:
                # Get detailed match information
                match_details = football_api.get_match(match_id)

                if match_details:
                    if match_id not in live_updates:
                        live_updates[match_id] = []

                    live_updates[match_id].append({
                        'timestamp': datetime.now(),
                        'details': match_details
                    })

                    # Keep only the last 10 updates
                    if len(live_updates[match_id]) > 10:
                        live_updates[match_id] = live_updates[match_id][-10:]
    else:
        logger.info("No live matches found")

# Background data collection thread
def data_collection_thread():
    """Background thread for data collection."""
    while True:
        try:
            collect_matches()
            collect_live_updates()

            # Emit updates to connected clients
            live_matches = get_live_matches()
            socketio.emit('live_matches_update', json.dumps(live_matches, default=str))

            for match in live_matches:
                match_id = match.get('match_id')
                if match_id:
                    summary = get_match_summary(match_id)
                    if summary:
                        socketio.emit(f'match_update_{match_id}', json.dumps(summary, default=str))

            # Sleep for 3 minutes before next collection to avoid rate limiting
            logger.info("Sleeping for 3 minutes before next data collection")
            time.sleep(180)
        except Exception as e:
            logger.error(f"Error in data collection thread: {e}")
            time.sleep(60)  # Sleep on error

# Helper functions
def get_live_matches():
    """Get a list of currently live matches."""
    live_matches = []

    for match_id, match_info in matches.items():
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

def get_match_summary(match_id):
    """Get a summary of a match."""
    if match_id not in matches:
        return None

    match_data = matches[match_id]['data']

    # Get the latest live update
    latest_update = None
    if match_id in live_updates and live_updates[match_id]:
        latest_update = live_updates[match_id][-1]['details']

    return {
        'match_id': match_id,
        'match_data': match_data,
        'latest_update': latest_update,
        'events': []  # Simplified version doesn't have events
    }

# Flask routes
@app.route('/')
def index():
    """Render the main dashboard page."""
    return render_template('index.html')

@app.route('/match/<match_id>')
def match_details(match_id):
    """Render the match details page."""
    return render_template('match_details.html', match_id=match_id)

@app.route('/api/matches/live')
def api_live_matches():
    """Get a list of currently live matches."""
    return jsonify(get_live_matches())

@app.route('/api/match/<match_id>')
def api_match_summary(match_id):
    """Get a summary of a match."""
    summary = get_match_summary(match_id)

    if summary:
        return jsonify(summary)
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

# Start the application
if __name__ == '__main__':
    # Collect initial data
    collect_matches()

    # Start data collection thread
    collection_thread = threading.Thread(target=data_collection_thread)
    collection_thread.daemon = True
    collection_thread.start()

    # Start the Flask application
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
