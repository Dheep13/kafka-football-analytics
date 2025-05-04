"""
Window processor for football data analytics.
Implements basic tumbling window functionality for match statistics.
"""
import time
import logging
import threading
from collections import defaultdict
from datetime import datetime, timedelta

class TumblingWindowProcessor:
    """
    Processes football match data in tumbling windows.
    A tumbling window is a fixed-size, non-overlapping time window.
    """
    
    def __init__(self, window_size_seconds=300):  # Default: 5-minute windows
        """
        Initialize the tumbling window processor.
        
        Args:
            window_size_seconds: Size of each window in seconds
        """
        self.window_size = window_size_seconds
        self.current_window_start = int(time.time()) // window_size_seconds * window_size_seconds
        self.window_data = defaultdict(lambda: defaultdict(int))
        self.processed_windows = []
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        
        # Start the window processing thread
        self.running = True
        self.processor_thread = threading.Thread(target=self._window_processor)
        self.processor_thread.daemon = True
        self.processor_thread.start()
        
        self.logger.info(f"Tumbling window processor started with {window_size_seconds}s windows")
    
    def add_event(self, event_type, event_data):
        """
        Add an event to the current window.
        
        Args:
            event_type: Type of event (e.g., 'goal', 'card', 'match_update')
            event_data: Data associated with the event
        """
        with self.lock:
            current_time = int(time.time())
            window_start = current_time // self.window_size * self.window_size
            
            # If we've moved to a new window, process the old one
            if window_start > self.current_window_start:
                self._process_window()
                self.current_window_start = window_start
            
            # Add event to current window
            self.window_data[event_type]['count'] += 1
            
            # Add specific metrics based on event type
            if event_type == 'match_update':
                if 'status' in event_data:
                    status = event_data.get('status', 'UNKNOWN')
                    self.window_data['match_status'][status] += 1
                    
                if 'score' in event_data and event_data['score']:
                    # Count goals in this window
                    home_score = event_data['score'].get('fullTime', {}).get('home', 0) or 0
                    away_score = event_data['score'].get('fullTime', {}).get('away', 0) or 0
                    total_score = home_score + away_score
                    self.window_data['goals']['total'] += total_score
    
    def _process_window(self):
        """Process the current window and store the results."""
        window_end = self.current_window_start + self.window_size
        
        # Create a window summary
        window_summary = {
            'window_start': self.current_window_start,
            'window_end': window_end,
            'window_start_time': datetime.fromtimestamp(self.current_window_start).isoformat(),
            'window_end_time': datetime.fromtimestamp(window_end).isoformat(),
            'metrics': dict(self.window_data)
        }
        
        # Store the processed window
        self.processed_windows.append(window_summary)
        if len(self.processed_windows) > 100:  # Keep only the last 100 windows
            self.processed_windows.pop(0)
        
        # Log window processing
        self.logger.info(f"Processed window {window_summary['window_start_time']} to {window_summary['window_end_time']}")
        
        # Reset window data
        self.window_data = defaultdict(lambda: defaultdict(int))
    
    def _window_processor(self):
        """Background thread that processes windows when they expire."""
        while self.running:
            current_time = int(time.time())
            window_start = current_time // self.window_size * self.window_size
            
            # If we've moved to a new window, process the old one
            if window_start > self.current_window_start:
                with self.lock:
                    self._process_window()
                    self.current_window_start = window_start
            
            # Sleep until the next window
            next_window = (window_start + self.window_size) - current_time
            time.sleep(min(next_window, 1))  # Sleep until next window or 1 second, whichever is less
    
    def get_window_metrics(self, num_windows=5):
        """
        Get metrics for the most recent windows.
        
        Args:
            num_windows: Number of recent windows to return
            
        Returns:
            List of window metrics
        """
        with self.lock:
            return self.processed_windows[-num_windows:] if self.processed_windows else []
    
    def get_aggregated_metrics(self, num_windows=12):
        """
        Get aggregated metrics across multiple recent windows.
        
        Args:
            num_windows: Number of recent windows to aggregate
            
        Returns:
            Dictionary of aggregated metrics
        """
        with self.lock:
            if not self.processed_windows:
                return {}
            
            # Get the most recent windows
            recent_windows = self.processed_windows[-num_windows:] if len(self.processed_windows) >= num_windows else self.processed_windows
            
            # Aggregate metrics
            aggregated = defaultdict(lambda: defaultdict(int))
            for window in recent_windows:
                for event_type, metrics in window['metrics'].items():
                    for metric_name, value in metrics.items():
                        aggregated[event_type][metric_name] += value
            
            # Calculate time span
            if recent_windows:
                start_time = recent_windows[0]['window_start_time']
                end_time = recent_windows[-1]['window_end_time']
            else:
                start_time = end_time = datetime.now().isoformat()
            
            return {
                'start_time': start_time,
                'end_time': end_time,
                'num_windows': len(recent_windows),
                'window_size_seconds': self.window_size,
                'metrics': dict(aggregated)
            }
    
    def shutdown(self):
        """Shutdown the window processor."""
        self.running = False
        if self.processor_thread.is_alive():
            self.processor_thread.join(timeout=5)
        self.logger.info("Tumbling window processor shut down")
