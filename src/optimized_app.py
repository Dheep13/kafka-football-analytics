"""
Optimized Flask web application for football analytics dashboard.
This version better utilizes the Football-Data.org API based on their documentation.
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
competition_standings = {}

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
    
    def _make_request(self, endpoint, params=None):
        """Make a request to the Football-Data.org API."""
        self._rate_limit_request()
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            
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
        """
        Get matches for a specific competition or across competitions.
        
        Args:
            competition_code (str, optional): Competition code (e.g., 'PL' for Premier League)
            date_from (str, optional): Start date in YYYY-MM-DD format
            date_to (str, optional): End date in YYYY-MM-DD format
            status (str, optional): Match status (SCHEDULED, LIVE, IN_PLAY, FINISHED, etc.)
            
        Returns:
            list: List of matches
        """
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
        """
        Get current standings for a competition.
        
        Args:
            competition_code (str): Competition code (e.g., 'PL' for Premier League)
            
        Returns:
            dict: Competition standings
        """
        return self._make_request(f'competitions/{competition_code}/standings')
    
    def get_team_matches(self, team_id, status=None):
        """
        Get matches for a specific team.
        
        Args:
            team_id (int): Team ID
            status (str, optional): Match status
            
        Returns:
            list: List of team matches
        """
        params = {}
        if status:
            params['status'] = status
        
        response = self._make_request(f'teams/{team_id}/matches', params)
        
        if response and 'matches' in response:
            return response['matches']
        
        return []

# Initialize API client
football_api = FootballDataAPI()

# Data collection functions
def collect_matches():
    """Collect match data."""
    logger.info("Collecting match data")
    
    # Get upcoming matches
    upcoming_matches = football_api.get_upcoming_matches()
    if upcoming_matches:
        logger.info(f"Collected {len(upcoming_matches)} upcoming matches")
        for match in upcoming_matches:
            match_id = match.get('id')
            if match_id:
                matches[match_id] = {
                    'data': match,
                    'last_updated': datetime.now()
                }
    
    # Get live matches (if any)
    time.sleep(15)  # Wait to avoid rate limiting
    live_matches = football_api.get_live_matches()
    if live_matches:
        logger.info(f"Collected {len(live_matches)} live matches")
        for match in live_matches:
            match_id = match.get('id')
            if match_id:
                matches[match_id] = {
                    'data': match,
                    'last_updated': datetime.now()
                }
                
                # Get detailed match information
                time.sleep(15)  # Wait to avoid rate limiting
                match_details = football_api.get_match(match_id)
                
                if match_details:
                    if match_id not in live_updates:
                        live_updates[match_id] = []
                    
                    live_updates[match_id].append({
                        'timestamp': datetime.now(),
                        'details': match_details
                    })
                    
                    # Keep only the last 5 updates
                    if len(live_updates[match_id]) > 5:
                        live_updates[match_id] = live_updates[match_id][-5:]
    else:
        logger.info("No live matches found")

def collect_standings():
    """Collect standings for Premier League."""
    logger.info("Collecting Premier League standings")
    
    standings_data = football_api.get_standings('PL')
    
    if standings_data and 'standings' in standings_data:
        for standing_type in standings_data['standings']:
            if standing_type['type'] == 'TOTAL':
                competition_standings['PL'] = {
                    'data': standing_type['table'],
                    'last_updated': datetime.now()
                }
                logger.info("Collected Premier League standings")
                break

# Background data collection thread
def data_collection_thread():
    """Background thread for data collection."""
    while True:
        try:
            # Collect matches
            collect_matches()
            
            # Collect standings (once per day is enough)
            if 'PL' not in competition_standings or (datetime.now() - competition_standings['PL']['last_updated']).days >= 1:
                time.sleep(15)  # Wait to avoid rate limiting
                collect_standings()
            
            # Emit updates to connected clients
            live_matches = get_live_matches()
            upcoming_matches = get_upcoming_matches()
            
            socketio.emit('live_matches_update', json.dumps(live_matches, default=str))
            socketio.emit('upcoming_matches_update', json.dumps(upcoming_matches, default=str))
            
            if 'PL' in competition_standings:
                socketio.emit('standings_update', json.dumps(competition_standings['PL']['data'], default=str))
            
            for match in live_matches:
                match_id = match.get('match_id')
                if match_id:
                    summary = get_match_summary(match_id)
                    if summary:
                        socketio.emit(f'match_update_{match_id}', json.dumps(summary, default=str))
            
            # Sleep for 5 minutes before next collection to avoid rate limiting
            logger.info("Sleeping for 5 minutes before next data collection")
            time.sleep(300)
        except Exception as e:
            logger.error(f"Error in data collection thread: {e}")
            time.sleep(300)  # Sleep on error

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

def get_upcoming_matches():
    """Get a list of upcoming matches."""
    upcoming_matches = []
    
    for match_id, match_info in matches.items():
        match_data = match_info['data']
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
                    'away_team': match_data.get('awayTeam', {}).get('name'),
                    'date': formatted_date,
                    'competition': match_data.get('competition', {}).get('name')
                })
    
    # Sort by date
    upcoming_matches.sort(key=lambda x: x['date'])
    
    return upcoming_matches

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

@app.route('/standings')
def standings():
    """Render the standings page."""
    return render_template('standings.html')

@app.route('/api/matches/live')
def api_live_matches():
    """Get a list of currently live matches."""
    return jsonify(get_live_matches())

@app.route('/api/matches/upcoming')
def api_upcoming_matches():
    """Get a list of upcoming matches."""
    return jsonify(get_upcoming_matches())

@app.route('/api/match/<match_id>')
def api_match_summary(match_id):
    """Get a summary of a match."""
    summary = get_match_summary(match_id)
    
    if summary:
        return jsonify(summary)
    else:
        return jsonify({'error': 'Match not found'}), 404

@app.route('/api/standings/pl')
def api_pl_standings():
    """Get Premier League standings."""
    if 'PL' in competition_standings:
        return jsonify(competition_standings['PL']['data'])
    else:
        return jsonify({'error': 'Standings not available'}), 404

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
    
    # Try to collect standings
    try:
        collect_standings()
    except Exception as e:
        logger.error(f"Error collecting initial standings: {e}")
    
    # Start data collection thread
    collection_thread = threading.Thread(target=data_collection_thread)
    collection_thread.daemon = True
    collection_thread.start()
    
    # Start the Flask application
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
