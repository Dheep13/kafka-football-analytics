"""
Standalone team profile application to test the team profile functionality.
"""
import os
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
API_KEY = os.getenv('FOOTBALL_DATA_API_KEY')
BASE_URL = 'https://api.football-data.org/v4'

# Initialize Flask app
app = Flask(__name__, template_folder='../templates')
app.config['SECRET_KEY'] = 'football_analytics_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Headers for API requests
headers = {
    'X-Auth-Token': API_KEY
}

@app.route('/')
def index():
    """Render the index page with popular teams."""
    # Get popular teams from Premier League
    teams = get_popular_teams()
    return render_template('team_list.html', teams=teams)

@app.route('/team/<team_id>')
def team_profile(team_id):
    """Render the team profile page."""
    return render_template('team_profile.html', team_id=team_id)

@app.route('/standings')
def standings():
    """Render the standings page."""
    return render_template('standings.html')

@app.route('/api/team/<team_id>')
def api_team(team_id):
    """Get team details."""
    # Convert team_id to integer if possible
    try:
        team_id_int = int(team_id)
    except ValueError:
        return jsonify({'error': 'Invalid team ID'}), 400

    # Get team data from API
    team_data = get_team_data(team_id_int)

    if team_data:
        return jsonify(team_data)
    else:
        return jsonify({'error': 'Team not found'}), 404

@app.route('/api/team/<team_id>/matches')
def api_team_matches(team_id):
    """Get team matches."""
    # Convert team_id to integer if possible
    try:
        team_id_int = int(team_id)
    except ValueError:
        return jsonify({'error': 'Invalid team ID'}), 400

    # Get team matches from API
    team_matches = get_team_matches(team_id_int)

    if team_matches:
        return jsonify(team_matches)
    else:
        return jsonify({'error': 'Team matches not found'}), 404

@app.route('/api/standings/pl')
def api_pl_standings():
    """Get Premier League standings."""
    standings_data = get_standings()

    if standings_data:
        return jsonify(standings_data)
    else:
        return jsonify({'error': 'Standings not available'}), 404

def get_team_data(team_id):
    """
    Get team data from the Football-Data.org API.

    Args:
        team_id (int): Team ID

    Returns:
        dict: Team data or None if not found
    """
    url = f"{BASE_URL}/teams/{team_id}"

    try:
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error getting team data: {response.status_code}")
            return None
    except Exception as e:
        print(f"Exception getting team data: {e}")
        return None

def get_team_matches(team_id):
    """
    Get team matches from the Football-Data.org API.

    Args:
        team_id (int): Team ID

    Returns:
        dict: Team matches or None if not found
    """
    # Get past matches
    past_url = f"{BASE_URL}/teams/{team_id}/matches?status=FINISHED&limit=5"

    # Get upcoming matches
    upcoming_url = f"{BASE_URL}/teams/{team_id}/matches?status=SCHEDULED&limit=5"

    try:
        past_response = requests.get(past_url, headers=headers)

        # Wait a bit to avoid rate limiting
        import time
        time.sleep(1)

        upcoming_response = requests.get(upcoming_url, headers=headers)

        past_matches = []
        upcoming_matches = []

        if past_response.status_code == 200:
            past_data = past_response.json()
            past_matches = past_data.get('matches', [])

        if upcoming_response.status_code == 200:
            upcoming_data = upcoming_response.json()
            upcoming_matches = upcoming_data.get('matches', [])

        return {
            'past': past_matches,
            'upcoming': upcoming_matches
        }
    except Exception as e:
        print(f"Exception getting team matches: {e}")
        return None

def get_standings():
    """
    Get Premier League standings from the Football-Data.org API.

    Returns:
        list: List of standings or None if not found
    """
    url = f"{BASE_URL}/competitions/PL/standings"

    try:
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            standings_data = response.json()

            # Extract the TOTAL standings
            for standing_type in standings_data.get('standings', []):
                if standing_type.get('type') == 'TOTAL':
                    return standing_type.get('table', [])

            return []
        else:
            print(f"Error getting standings: {response.status_code}")
            return None
    except Exception as e:
        print(f"Exception getting standings: {e}")
        return None

def get_popular_teams():
    """
    Get popular teams from the Premier League.

    Returns:
        list: List of teams
    """
    url = f"{BASE_URL}/competitions/PL/teams"

    try:
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            teams_data = response.json()
            return teams_data.get('teams', [])
        else:
            print(f"Error getting popular teams: {response.status_code}")
            return []
    except Exception as e:
        print(f"Exception getting popular teams: {e}")
        return []

# Socket.IO events
@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    print('Client connected')
    emit('connected', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    print('Client disconnected')

if __name__ == '__main__':
    # Start the Flask application
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)
