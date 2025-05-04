# Save this as src/test_pubsub.py
import json
import threading
import time
from datetime import datetime
import os
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

# Configuration
API_KEY = os.getenv('FOOTBALL_DATA_API_KEY')
BASE_URL = "https://api.football-data.org/v4"

# In-memory message queue (simulating Kafka)
message_queue = {
    "football-matches": [],
    "football-live-updates": [],
    "football-standings": [],
    "football-teams": []
}

# Publisher (simulating Kafka producer)
def publish_message(topic, message):
    """Publish a message to a topic."""
    message_queue[topic].append({
        "timestamp": datetime.now().isoformat(),
        "value": message
    })
    print(f"Published message to topic '{topic}'")

# Subscriber (simulating Kafka consumer)
def subscribe_to_topic(topic, callback):
    """Subscribe to a topic and process messages."""
    def consumer_thread():
        last_processed = 0
        while True:
            messages = message_queue[topic]
            if len(messages) > last_processed:
                for i in range(last_processed, len(messages)):
                    callback(messages[i]["value"])
                last_processed = len(messages)
            time.sleep(1)
    
    thread = threading.Thread(target=consumer_thread)
    thread.daemon = True
    thread.start()
    print(f"Subscribed to topic '{topic}'")

# API client
def fetch_data(endpoint, params=None):
    """Fetch data from the Football-Data.org API."""
    headers = {"X-Auth-Token": API_KEY}
    url = f"{BASE_URL}/{endpoint}"
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 429:
            print("Rate limit exceeded. Waiting for 60 seconds...")
            time.sleep(60)
            return fetch_data(endpoint, params)  # Retry after waiting
            
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

# Publisher functions
def collect_matches():
    """Collect match data and publish to topic."""
    print("Collecting matches...")
    today = datetime.now().strftime('%Y-%m-%d')
    future = (datetime.now().replace(day=datetime.now().day + 7)).strftime('%Y-%m-%d')
    
    matches = fetch_data("matches", {"dateFrom": today, "dateTo": future})
    if matches and "matches" in matches:
        publish_message("football-matches", {
            "type": "upcoming",
            "matches": matches["matches"]
        })
        print(f"Published {len(matches['matches'])} matches")
    else:
        print("No matches found or error fetching matches")

def collect_standings():
    """Collect standings data and publish to topic."""
    print("Collecting standings...")
    standings = fetch_data("competitions/PL/standings")
    if standings and "standings" in standings:
        for standing_type in standings["standings"]:
            if standing_type["type"] == "TOTAL":
                publish_message("football-standings", {
                    "competition": "PL",
                    "standings": standing_type["table"]
                })
                print(f"Published standings with {len(standing_type['table'])} teams")
                break
    else:
        print("No standings found or error fetching standings")

def collect_team(team_id):
    """Collect team data and publish to topic."""
    print(f"Collecting team data for team {team_id}...")
    team = fetch_data(f"teams/{team_id}")
    if team:
        publish_message("football-teams", {
            "team_id": team_id,
            "data": team
        })
        print(f"Published team data for {team.get('name')}")
    else:
        print(f"No team data found or error fetching team {team_id}")

# Subscriber callbacks
def process_matches(message):
    """Process match data."""
    match_type = message.get("type")
    matches = message.get("matches", [])
    print(f"SUBSCRIBER: Processed {len(matches)} {match_type} matches")
    
    # Print some sample match data
    if matches:
        sample_match = matches[0]
        print(f"Sample match: {sample_match.get('homeTeam', {}).get('name')} vs {sample_match.get('awayTeam', {}).get('name')}")

def process_standings(message):
    """Process standings data."""
    competition = message.get("competition")
    standings = message.get("standings", [])
    print(f"SUBSCRIBER: Processed standings for {competition} with {len(standings)} teams")
    
    # Print top 3 teams
    if standings and len(standings) >= 3:
        print("Top 3 teams:")
        for i in range(3):
            team = standings[i]
            print(f"{i+1}. {team.get('team', {}).get('name')} - {team.get('points')} points")

def process_team(message):
    """Process team data."""
    team_id = message.get("team_id")
    team_data = message.get("data", {})
    print(f"SUBSCRIBER: Processed team data for team {team_id}: {team_data.get('name')}")
    
    # Print some team details
    print(f"Team details: {team_data.get('name')}, Founded: {team_data.get('founded')}, Venue: {team_data.get('venue')}")
    
    # Print squad size if available
    if "squad" in team_data:
        print(f"Squad size: {len(team_data['squad'])}")

# Main function
def main():
    # Subscribe to topics
    subscribe_to_topic("football-matches", process_matches)
    subscribe_to_topic("football-standings", process_standings)
    subscribe_to_topic("football-teams", process_team)
    
    # Wait a bit for subscribers to start
    time.sleep(1)
    
    # Collect and publish data with delays to avoid rate limiting
    collect_matches()
    time.sleep(15)  # Wait to avoid rate limiting
    
    collect_standings()
    time.sleep(15)  # Wait to avoid rate limiting
    
    collect_team(65)  # Manchester City
    
    # Keep the main thread running to see all the subscriber outputs
    try:
        print("\nPress Ctrl+C to exit...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting...")

if __name__ == "__main__":
    main()
