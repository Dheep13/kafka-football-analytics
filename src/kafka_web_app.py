"""
Flask web application using Kafka architecture for football analytics.
"""
import os
import json
import threading
import time
from datetime import datetime
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import Kafka processor
from src.kafka_app import FootballDataProcessor, FootballDataCollector

# Initialize Flask app
app = Flask(__name__, template_folder='../templates')
app.config['SECRET_KEY'] = 'football_analytics_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Create data processor (consumer)
processor = FootballDataProcessor()

# Create data collector (producer)
collector = FootballDataCollector()

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

@app.route('/team/<team_id>')
def team_profile(team_id):
    """Render the team profile page."""
    return render_template('team_profile.html', team_id=team_id)

# API routes
@app.route('/api/matches/live')
def api_live_matches():
    """Get a list of currently live matches."""
    return jsonify(processor.get_live_matches())

@app.route('/api/matches/upcoming')
def api_upcoming_matches():
    """Get a list of upcoming matches."""
    return jsonify(processor.get_upcoming_matches())

@app.route('/api/match/<match_id>')
def api_match_summary(match_id):
    """Get a summary of a match."""
    summary = processor.get_match_summary(match_id)
    
    if summary:
        return jsonify(summary)
    else:
        return jsonify({'error': 'Match not found'}), 404

@app.route('/api/standings/pl')
def api_pl_standings():
    """Get Premier League standings."""
    standings = processor.get_standings('PL')
    
    if standings:
        return jsonify(standings)
    else:
        # If we don't have standings in memory, try to collect them
        collector.collect_standings()
        standings = processor.get_standings('PL')
        if standings:
            return jsonify(standings)
        else:
            return jsonify({'error': 'Standings not available'}), 404

@app.route('/api/team/<team_id>')
def api_team(team_id):
    """Get team details."""
    try:
        team_id_int = int(team_id)
    except ValueError:
        return jsonify({'error': 'Invalid team ID'}), 400
    
    team_data = processor.get_team(team_id_int)
    
    if team_data:
        return jsonify(team_data)
    else:
        # If we don't have team data in memory, try to collect it
        team_data = collector.collect_team_data(team_id_int)
        if team_data:
            return jsonify(team_data)
        else:
            return jsonify({'error': 'Team not found'}), 404

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

# Background thread for emitting updates
def background_thread():
    """Background thread for emitting updates to connected clients."""
    while True:
        try:
            # Emit live matches
            live_matches = processor.get_live_matches()
            socketio.emit('live_matches_update', json.dumps(live_matches, default=str))
            
            # Emit upcoming matches
            upcoming_matches = processor.get_upcoming_matches()
            socketio.emit('upcoming_matches_update', json.dumps(upcoming_matches, default=str))
            
            # Emit standings if available
            standings = processor.get_standings('PL')
            if standings:
                socketio.emit('standings_update', json.dumps(standings, default=str))
            
            # Emit match updates for live matches
            for match in live_matches:
                match_id = match.get('match_id')
                if match_id:
                    summary = processor.get_match_summary(match_id)
                    if summary:
                        socketio.emit(f'match_update_{match_id}', json.dumps(summary, default=str))
            
            # Sleep for 10 seconds before next update
            time.sleep(10)
        except Exception as e:
            print(f"Error in background thread: {e}")
            time.sleep(10)

# Start the application
if __name__ == '__main__':
    # Start data collection
    collector.start_collection()
    
    # Start data processing
    processor.start_processing()
    
    # Start background thread for emitting updates
    thread = threading.Thread(target=background_thread)
    thread.daemon = True
    thread.start()
    
    # Start the Flask application
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
