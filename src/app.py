"""
Flask web application for football analytics dashboard.
"""
import json
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
import threading
import time
from src.match_analyzer import MatchAnalyzer
from src.config import FLASK_SECRET_KEY, FLASK_DEBUG
from src.utils import get_logger, serialize_datetime

logger = get_logger(__name__)

app = Flask(__name__, template_folder='../templates')
app.config['SECRET_KEY'] = FLASK_SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize the match analyzer
analyzer = MatchAnalyzer()

@app.route('/')
def index():
    """
    Render the main dashboard page.
    """
    return render_template('index.html')

@app.route('/match/<match_id>')
def match_details(match_id):
    """
    Render the match details page.
    
    Args:
        match_id (str): The match ID.
    """
    return render_template('match_details.html', match_id=match_id)

@app.route('/api/matches/live')
def get_live_matches():
    """
    Get a list of currently live matches.
    
    Returns:
        JSON: List of live matches.
    """
    live_matches = analyzer.get_live_matches()
    return jsonify(live_matches)

@app.route('/api/match/<match_id>')
def get_match_summary(match_id):
    """
    Get a summary of a match.
    
    Args:
        match_id (str): The match ID.
        
    Returns:
        JSON: Match summary.
    """
    summary = analyzer.get_match_summary(match_id)
    
    if summary:
        return jsonify(summary)
    else:
        return jsonify({'error': 'Match not found'}), 404

@app.route('/api/match/<match_id>/possession')
def get_possession_analysis(match_id):
    """
    Get possession analysis for a match.
    
    Args:
        match_id (str): The match ID.
        
    Returns:
        JSON: Possession analysis.
    """
    possession = analyzer.analyze_possession(match_id)
    
    if possession:
        return jsonify(possession)
    else:
        return jsonify({'error': 'Possession data not available'}), 404

@app.route('/api/match/<match_id>/shots')
def get_shots_analysis(match_id):
    """
    Get shots analysis for a match.
    
    Args:
        match_id (str): The match ID.
        
    Returns:
        JSON: Shots analysis.
    """
    shots = analyzer.analyze_shots(match_id)
    
    if shots:
        return jsonify(shots)
    else:
        return jsonify({'error': 'Shots data not available'}), 404

def background_update():
    """
    Background thread to send updates to connected clients.
    """
    while True:
        try:
            # Get live matches
            live_matches = analyzer.get_live_matches()
            
            # Send updates to clients
            socketio.emit('live_matches_update', json.dumps(live_matches, default=serialize_datetime))
            
            # Send individual match updates
            for match in live_matches:
                match_id = match.get('match_id')
                if match_id:
                    summary = analyzer.get_match_summary(match_id)
                    if summary:
                        socketio.emit(f'match_update_{match_id}', json.dumps(summary, default=serialize_datetime))
            
            # Sleep for a short time
            time.sleep(10)
        except Exception as e:
            logger.error(f"Error in background update thread: {e}")
            time.sleep(30)  # Longer sleep on error

@socketio.on('connect')
def handle_connect():
    """
    Handle client connection.
    """
    logger.info('Client connected')
    emit('connected', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    """
    Handle client disconnection.
    """
    logger.info('Client disconnected')

def start_app():
    """
    Start the Flask application and background threads.
    """
    # Start the match analyzer
    analyzer.start_analysis()
    
    # Start the background update thread
    update_thread = threading.Thread(target=background_update)
    update_thread.daemon = True
    update_thread.start()
    
    # Start the Flask application
    socketio.run(app, host='0.0.0.0', port=5000, debug=FLASK_DEBUG)

if __name__ == '__main__':
    try:
        start_app()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, stopping application")
        analyzer.stop_analysis()
    except Exception as e:
        logger.error(f"Error starting application: {e}")
        analyzer.stop_analysis()
