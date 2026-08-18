from langchain_core.tools import tool
from datetime import datetime
from zoneinfo import ZoneInfo
import openmeteo_requests
import requests_cache

from retry_requests import retry

@tool
def calculator(expression: str) -> str:
    """
    Performs basic mathematical calculations.
    Example: 10 + 5, 20 * 3, 100 / 4
    """
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception:
        return "Invalid mathematical expression."
    
    
    #date and time tool  
   



@tool
def get_current_datetime(timezone: str = "Asia/Karachi") -> str:
    """
    Get the current date and time for a given timezone.
    Example timezone: Asia/Karachi
    """
    try:
        current_time = datetime.now(ZoneInfo(timezone))

        return current_time.strftime(
            "%A, %d %B %Y, %I:%M:%S %p"
        )

    except Exception:
        return "Invalid timezone."
    
    
    #weather caling tool 




# Open-Meteo client setup
cache_session = requests_cache.CachedSession(
    ".cache",
    expire_after=3600
)

retry_session = retry(
    cache_session,
    retries=5,
    backoff_factor=0.2
)

openmeteo = openmeteo_requests.Client(
    session=retry_session
)


@tool
def get_weather(latitude: float, longitude: float) -> str:
    """
    Get current and hourly weather information using Open-Meteo.

    Provide latitude and longitude of the location.
    """

    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": [
            "temperature_2m",
            "rain",
        ],
        "hourly": [
            "temperature_2m",
            "rain",
        ],
        "timezone": "auto",
    }

    try:
        responses = openmeteo.weather_api(url, params=params)

        response = responses[0]

        current = response.Current()

        temperature = current.Variables(0).Value()
        rain = current.Variables(1).Value()

        return (
            f"Temperature: {temperature}°C\n"
            f"Rain: {rain} mm"
        )

    except Exception as e:
        return f"Weather tool error: {str(e)}"
    
    
    