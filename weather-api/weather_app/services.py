from datetime import datetime
from zoneinfo import ZoneInfo

import firebase_admin
import requests
from django.conf import settings
from firebase_admin import firestore

OPENWEATHER_BASE_URL = "https://api.openweathermap.org"
REQUEST_TIMEOUT_SECONDS = 20
KST = ZoneInfo("Asia/Seoul")
UTC = ZoneInfo("UTC")


def uvi_level(uvi):
    if uvi is None:
        return "Unknown"
    if uvi <= 2:
        return "Low"
    if uvi <= 5:
        return "Moderate"
    if uvi <= 7:
        return "High"
    if uvi <= 10:
        return "Very High"
    return "Extreme"


def get_firestore_client():
    if not firebase_admin._apps:
        raise RuntimeError("Firebase credentials are not configured.")
    return firestore.client()


def get_openweather_api_key() -> str:
    api_key = settings.OPENWEATHER_API_KEY
    if not api_key:
        raise RuntimeError("OPENWEATHER_API_KEY is not configured.")
    return api_key


def get_lat_lon(city_name, api_key):
    response = requests.get(
        f"{OPENWEATHER_BASE_URL}/geo/1.0/direct",
        params={"q": city_name, "limit": 1, "appid": api_key},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()
    if data:
        return data[0]["lat"], data[0]["lon"]
    return None, None


def save_weather_forecast(city_name):
    api_key = get_openweather_api_key()
    lat, lon = get_lat_lon(city_name, api_key)
    if lat is None or lon is None:
        raise ValueError("도시명을 찾을 수 없습니다.")

    response = requests.get(
        f"{OPENWEATHER_BASE_URL}/data/3.0/onecall",
        params={
            "lat": lat,
            "lon": lon,
            "appid": api_key,
            "units": "metric",
            "exclude": "minutely",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()

    hourly_groups = {}
    for hour in data.get("hourly", [])[:48]:
        timestamp = datetime.fromtimestamp(hour.get("dt", 0), tz=UTC).astimezone(KST)
        date_str = timestamp.strftime("%Y%m%d")
        entry = {
            "time": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "temp": hour.get("temp"),
            "feels_like": hour.get("feels_like"),
            "humidity": hour.get("humidity"),
            "wind_speed": hour.get("wind_speed"),
            "uvi_level": uvi_level(hour.get("uvi")),
            "sunlight": hour.get("clouds"),
            "pop": hour.get("pop"),
            "rain": hour.get("rain", {}).get("1h", 0),
            "snow": hour.get("snow", {}).get("1h", 0),
            "clouds": hour.get("clouds"),
            "weather": hour.get("weather", [{}])[0],
        }
        hourly_groups.setdefault(date_str, []).append(entry)

    daily_groups = {}
    for day in data.get("daily", []):
        date_str = datetime.fromtimestamp(day["dt"], tz=UTC).strftime("%Y%m%d")
        daily_groups[date_str] = {
            "city": city_name,
            "date": date_str,
            "temperature": day["temp"]["day"],
            "min_temp": day["temp"]["min"],
            "max_temp": day["temp"]["max"],
            "humidity": day["humidity"],
            "weather_description": day["weather"][0]["description"],
            "wind_speed": day["wind_speed"],
            "rain": day.get("rain", 0),
            "snow": day.get("snow", 0),
        }

    db = get_firestore_client()
    alerts = data.get("alerts", [])
    for date_str, entries in hourly_groups.items():
        document_id = f"{city_name}_hourly_{date_str}"
        db.collection("weather_forecasts").document(document_id).set(
            {
                "city": city_name,
                "date": date_str,
                "hourly_forecasts": entries,
                "alerts": alerts,
            }
        )

    for date_str, daily_forecast in daily_groups.items():
        document_id = f"{city_name}_daily_{date_str}"
        db.collection("weather_forecasts_daily").document(document_id).set(
            daily_forecast
        )

    return "Weather data saved successfully"


def save_air_pollution(city_name):
    api_key = get_openweather_api_key()
    lat, lon = get_lat_lon(city_name, api_key)
    if lat is None or lon is None:
        raise ValueError("도시명을 찾을 수 없습니다.")

    response = requests.get(
        f"{OPENWEATHER_BASE_URL}/data/2.5/air_pollution",
        params={"lat": lat, "lon": lon, "appid": api_key},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    air_info = payload.get("list", [])[0] if payload.get("list") else {}

    today = datetime.now(KST).strftime("%Y%m%d")
    document_id = f"{city_name}_{today}"
    get_firestore_client().collection("air_quality").document(document_id).set(
        {"city": city_name, "date": today, "air": air_info}
    )
