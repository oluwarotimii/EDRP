import math
from typing import Tuple, Optional

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    using the Haversine formula.
    
    Args:
        lat1: Latitude of point 1
        lon1: Longitude of point 1
        lat2: Latitude of point 2
        lon2: Longitude of point 2
        
    Returns:
        Distance between the points in meters
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371000  # Earth radius in meters
    
    return c * r

def verify_location(lat1: float, lon1: float, lat2: float, lon2: float, radius: Optional[int] = None) -> float:
    """
    Verify if a location (lat1, lon1) is within the specified radius of another location (lat2, lon2).
    
    Args:
        lat1: Latitude of point to check
        lon1: Longitude of point to check
        lat2: Latitude of reference point
        lon2: Longitude of reference point
        radius: Maximum allowed distance in meters. If None, just returns the distance.
        
    Returns:
        Distance between the points in meters
    """
    distance = calculate_distance(lat1, lon1, lat2, lon2)
    
    return distance

def is_within_radius(lat1: float, lon1: float, lat2: float, lon2: float, radius: int) -> Tuple[bool, float]:
    """
    Check if a location (lat1, lon1) is within the specified radius of another location (lat2, lon2).
    
    Args:
        lat1: Latitude of point to check
        lon1: Longitude of point to check
        lat2: Latitude of reference point
        lon2: Longitude of reference point
        radius: Maximum allowed distance in meters
        
    Returns:
        Tuple of (is_within_radius, distance)
    """
    distance = calculate_distance(lat1, lon1, lat2, lon2)
    return distance <= radius, distance
