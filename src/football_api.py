"""
API client for fetching football data from external APIs.
"""
import requests
import time
from datetime import datetime, timedelta
from src.config import (
    FOOTBALL_DATA_API_KEY, FOOTBALL_DATA_BASE_URL,
    RAPID_API_KEY, RAPID_API_HOST, RAPID_API_BASE_URL,
    LEAGUES_TO_TRACK
)
from src.utils import get_logger

logger = get_logger(__name__)

class FootballDataAPI:
    """
    Client for the Football-Data.org API.
    """
    def __init__(self):
        self.base_url = FOOTBALL_DATA_BASE_URL
        self.headers = {
            'X-Auth-Token': FOOTBALL_DATA_API_KEY
        }
        self.rate_limit = 10  # requests per minute
        self.last_request_time = 0
    
    def _rate_limit_request(self):
        """
        Implement rate limiting to respect API limits.
        """
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        # Ensure at least 60/10 = 6 seconds between requests
        if time_since_last_request < 6:
            sleep_time = 6 - time_since_last_request
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _make_request(self, endpoint, params=None):
        """
        Make a request to the Football-Data.org API.
        
        Args:
            endpoint (str): API endpoint to call.
            params (dict, optional): Query parameters.
            
        Returns:
            dict: API response data.
        """
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
        """
        Get matches within a date range.
        
        Args:
            date_from (str, optional): Start date in YYYY-MM-DD format.
            date_to (str, optional): End date in YYYY-MM-DD format.
            status (str, optional): Match status (SCHEDULED, LIVE, IN_PLAY, PAUSED, FINISHED).
            
        Returns:
            list: List of matches.
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
        
        matches = []
        for league_id in LEAGUES_TO_TRACK:
            league_matches = self._make_request(f'competitions/{league_id}/matches', params)
            if league_matches and 'matches' in league_matches:
                matches.extend(league_matches['matches'])
        
        return matches
    
    def get_live_matches(self):
        """
        Get currently live matches.
        
        Returns:
            list: List of live matches.
        """
        return self.get_matches(status='LIVE')
    
    def get_match(self, match_id):
        """
        Get detailed information about a specific match.
        
        Args:
            match_id (int): The ID of the match.
            
        Returns:
            dict: Match details.
        """
        return self._make_request(f'matches/{match_id}')
    
    def get_team(self, team_id):
        """
        Get information about a specific team.
        
        Args:
            team_id (int): The ID of the team.
            
        Returns:
            dict: Team details.
        """
        return self._make_request(f'teams/{team_id}')


class APIFootball:
    """
    Client for the API-Football API via RapidAPI.
    """
    def __init__(self):
        self.base_url = RAPID_API_BASE_URL
        self.headers = {
            'x-rapidapi-key': RAPID_API_KEY,
            'x-rapidapi-host': RAPID_API_HOST
        }
        self.rate_limit = 100  # requests per day
        self.last_request_time = 0
    
    def _rate_limit_request(self):
        """
        Implement rate limiting to respect API limits.
        """
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        # Ensure at least 24*60*60/100 = 864 seconds between requests
        if time_since_last_request < 864:
            sleep_time = 864 - time_since_last_request
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _make_request(self, endpoint, params=None):
        """
        Make a request to the API-Football API.
        
        Args:
            endpoint (str): API endpoint to call.
            params (dict, optional): Query parameters.
            
        Returns:
            dict: API response data.
        """
        self._rate_limit_request()
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return None
    
    def get_fixtures(self, date=None, live=False, league_id=None):
        """
        Get fixtures (matches) for a specific date or live matches.
        
        Args:
            date (str, optional): Date in YYYY-MM-DD format.
            live (bool, optional): Whether to get only live fixtures.
            league_id (int, optional): ID of the league.
            
        Returns:
            list: List of fixtures.
        """
        params = {}
        
        if live:
            params['live'] = 'all'
        elif date:
            params['date'] = date
        
        if league_id:
            params['league'] = league_id
        
        response = self._make_request('fixtures', params)
        
        if response and 'response' in response:
            return response['response']
        return []
    
    def get_fixture_statistics(self, fixture_id):
        """
        Get statistics for a specific fixture.
        
        Args:
            fixture_id (int): The ID of the fixture.
            
        Returns:
            dict: Fixture statistics.
        """
        params = {'fixture': fixture_id}
        response = self._make_request('fixtures/statistics', params)
        
        if response and 'response' in response:
            return response['response']
        return []
    
    def get_fixture_events(self, fixture_id):
        """
        Get events for a specific fixture (goals, cards, etc.).
        
        Args:
            fixture_id (int): The ID of the fixture.
            
        Returns:
            list: List of fixture events.
        """
        params = {'fixture': fixture_id}
        response = self._make_request('fixtures/events', params)
        
        if response and 'response' in response:
            return response['response']
        return []
