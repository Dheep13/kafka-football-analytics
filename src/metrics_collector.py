"""
Metrics collector for football data application.
Collects and reports various performance and data metrics.
"""
import time
import logging
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta

class MetricsCollector:
    """
    Collects and reports metrics for the football data application.
    """
    
    def __init__(self, reporting_interval=60):  # Default: report every minute
        """
        Initialize the metrics collector.
        
        Args:
            reporting_interval: How often to log metrics summary (in seconds)
        """
        self.reporting_interval = reporting_interval
        self.metrics = {
            'api_calls': defaultdict(int),
            'kafka_messages': defaultdict(int),
            'processing_times': defaultdict(list),
            'error_counts': defaultdict(int),
            'data_counts': defaultdict(int)
        }
        
        # For calculating rates
        self.message_timestamps = defaultdict(lambda: deque(maxlen=1000))
        
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        
        # Start the reporting thread
        self.running = True
        self.reporter_thread = threading.Thread(target=self._metrics_reporter)
        self.reporter_thread.daemon = True
        self.reporter_thread.start()
        
        self.logger.info(f"Metrics collector started with {reporting_interval}s reporting interval")
    
    def record_api_call(self, endpoint):
        """Record an API call."""
        with self.lock:
            self.metrics['api_calls']['total'] += 1
            self.metrics['api_calls'][endpoint] += 1
    
    def record_kafka_message(self, topic, size_bytes=0):
        """Record a Kafka message."""
        with self.lock:
            self.metrics['kafka_messages']['total'] += 1
            self.metrics['kafka_messages'][topic] += 1
            self.metrics['kafka_messages']['bytes'] += size_bytes
            
            # Record timestamp for rate calculation
            now = time.time()
            self.message_timestamps['total'].append(now)
            self.message_timestamps[topic].append(now)
    
    def record_processing_time(self, operation, duration_ms):
        """Record processing time for an operation."""
        with self.lock:
            self.metrics['processing_times'][operation].append(duration_ms)
            # Keep only the last 1000 measurements
            if len(self.metrics['processing_times'][operation]) > 1000:
                self.metrics['processing_times'][operation].pop(0)
    
    def record_error(self, error_type):
        """Record an error."""
        with self.lock:
            self.metrics['error_counts']['total'] += 1
            self.metrics['error_counts'][error_type] += 1
    
    def record_data_count(self, data_type, count=1):
        """Record data count."""
        with self.lock:
            self.metrics['data_counts'][data_type] += count
    
    def _calculate_message_rate(self, topic):
        """Calculate message rate for a topic."""
        timestamps = self.message_timestamps[topic]
        if len(timestamps) < 2:
            return 0
        
        # Calculate rate based on timestamps in the last minute
        now = time.time()
        recent_timestamps = [ts for ts in timestamps if now - ts <= 60]
        
        if not recent_timestamps:
            return 0
        
        return len(recent_timestamps) / 60  # messages per second
    
    def _calculate_avg_processing_time(self, operation):
        """Calculate average processing time for an operation."""
        times = self.metrics['processing_times'][operation]
        if not times:
            return 0
        return sum(times) / len(times)
    
    def get_metrics_summary(self):
        """Get a summary of current metrics."""
        with self.lock:
            summary = {
                'timestamp': datetime.now().isoformat(),
                'api_calls': dict(self.metrics['api_calls']),
                'kafka_messages': dict(self.metrics['kafka_messages']),
                'error_counts': dict(self.metrics['error_counts']),
                'data_counts': dict(self.metrics['data_counts']),
                'message_rates': {
                    'total': self._calculate_message_rate('total'),
                },
                'avg_processing_times': {}
            }
            
            # Add message rates for each topic
            for topic in self.metrics['kafka_messages']:
                if topic != 'total' and topic != 'bytes':
                    summary['message_rates'][topic] = self._calculate_message_rate(topic)
            
            # Add average processing times
            for operation in self.metrics['processing_times']:
                summary['avg_processing_times'][operation] = self._calculate_avg_processing_time(operation)
            
            return summary
    
    def _metrics_reporter(self):
        """Background thread that periodically reports metrics."""
        last_report_time = time.time()
        
        while self.running:
            current_time = time.time()
            
            # Report metrics at the specified interval
            if current_time - last_report_time >= self.reporting_interval:
                summary = self.get_metrics_summary()
                
                # Log the summary
                self.logger.info(f"Metrics summary: {summary}")
                
                last_report_time = current_time
            
            # Sleep for a bit
            time.sleep(1)
    
    def reset_metrics(self):
        """Reset all metrics."""
        with self.lock:
            self.metrics = {
                'api_calls': defaultdict(int),
                'kafka_messages': defaultdict(int),
                'processing_times': defaultdict(list),
                'error_counts': defaultdict(int),
                'data_counts': defaultdict(int)
            }
            self.message_timestamps = defaultdict(lambda: deque(maxlen=1000))
    
    def shutdown(self):
        """Shutdown the metrics collector."""
        self.running = False
        if self.reporter_thread.is_alive():
            self.reporter_thread.join(timeout=5)
        self.logger.info("Metrics collector shut down")
