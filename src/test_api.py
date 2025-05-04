"""
Test script to verify the Football-Data.org API is working correctly.
"""
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
API_KEY = os.getenv('FOOTBALL_DATA_API_KEY')
BASE_URL = 'https://api.football-data.org/v4'

# Headers
headers = {
    'X-Auth-Token': API_KEY
}

def test_team_endpoint(team_id):
    """Test the team endpoint."""
    url = f"{BASE_URL}/teams/{team_id}"
    print(f"Testing team endpoint: {url}")
    
    try:
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            team_data = response.json()
            print(f"Success! Team found: {team_data.get('name')}")
            print(f"Short name: {team_data.get('shortName')}")
            print(f"Founded: {team_data.get('founded')}")
            print(f"Venue: {team_data.get('venue')}")
            return True
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"Exception: {e}")
        return False

def find_popular_teams():
    """Find some popular teams to use as examples."""
    url = f"{BASE_URL}/competitions/PL/teams"
    print(f"Finding popular teams from Premier League: {url}")
    
    try:
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            teams_data = response.json()
            teams = teams_data.get('teams', [])
            
            print(f"Found {len(teams)} teams")
            
            for team in teams[:5]:  # Show first 5 teams
                print(f"ID: {team.get('id')}, Name: {team.get('name')}")
            
            return teams
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
            return []
    except Exception as e:
        print(f"Exception: {e}")
        return []

if __name__ == "__main__":
    # Test with some team IDs
    test_ids = [65, 86, 61, 57]
    
    for team_id in test_ids:
        print(f"\nTesting team ID: {team_id}")
        test_team_endpoint(team_id)
    
    print("\nFinding popular teams:")
    find_popular_teams()
