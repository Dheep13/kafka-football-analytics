"""
Utility functions for the football analytics application.
"""
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def get_logger(name):
    """
    Get a logger with the specified name.
    
    Args:
        name (str): The name of the logger.
        
    Returns:
        logging.Logger: A configured logger instance.
    """
    return logging.getLogger(name)

def serialize_datetime(obj):
    """
    JSON serializer for datetime objects.
    
    Args:
        obj: The object to serialize.
        
    Returns:
        str: ISO format string if obj is a datetime, otherwise raises TypeError.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

def serialize_to_json(data):
    """
    Serialize data to JSON string, handling datetime objects.
    
    Args:
        data (dict): The data to serialize.
        
    Returns:
        str: JSON string representation of the data.
    """
    return json.dumps(data, default=serialize_datetime)

def deserialize_from_json(json_str):
    """
    Deserialize JSON string to Python object.
    
    Args:
        json_str (str): The JSON string to deserialize.
        
    Returns:
        dict: The deserialized data.
    """
    return json.loads(json_str)

def parse_iso_datetime(datetime_str):
    """
    Parse ISO format datetime string to datetime object.
    
    Args:
        datetime_str (str): ISO format datetime string.
        
    Returns:
        datetime: The parsed datetime object.
    """
    return datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))

def format_datetime(dt, format_str='%Y-%m-%d %H:%M:%S'):
    """
    Format datetime object to string.
    
    Args:
        dt (datetime): The datetime to format.
        format_str (str): The format string.
        
    Returns:
        str: The formatted datetime string.
    """
    return dt.strftime(format_str)
