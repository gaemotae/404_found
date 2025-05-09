import requests
from django.http import JsonResponse
from datetime import datetime
from django.conf import settings
from pytz import timezone
import os
import time
import platform
from firebase_admin import firestore

db = firestore.client()

# ✅ 자외선 등급 계산 함수
def uvi_level(uvi):
    if uvi is None:
        return "Unknown"
    if uvi <= 2:
        return "Low"
    elif uvi <= 5:
        return "Moderate"
    elif uvi <= 7:
        return "High"
    elif uvi <= 10:
        return "Very High"
    else:
        return "Extreme"

# ✅ 위도/경도 변환 함수 (도시명 기준)
def get_lat_lon(city_name, api_key):
    try:
        geo_url = "http://api.openweathermap.org/geo/1.0/direct"
        params = {'q': city_name, 'limit': 1, 'appid': api_key}
        response = requests.get(geo_url, params=params)
        response.raise_for_status()
        data = response.json()
        if data:
            return data[0]['lat'], data[0]['lon']
    except Exception as e:
        print(f"[Geo Error] {e}")
    return None, None

# ✅ 날씨 예보 저장 (하루 단위 문서 + current + alerts 포함, 위경도 저장 X)
def weather_forecast(request):
    city_name = request.GET.get('city', 'Seoul')
    API_KEY = settings.OPENWEATHER_API_KEY
    lat, lon = get_lat_lon(city_name, API_KEY)

    if lat is None or lon is None:
        return JsonResponse({'error': '도시명을 찾을 수 없습니다.'}, status=400)

    url = "https://api.openweathermap.org/data/3.0/onecall"
    params = {
        'lat': lat,
        'lon': lon,
        'appid': API_KEY,
        'units': 'metric',
        'exclude': 'minutely'
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        if platform.system() != 'Windows':
            os.environ['TZ'] = 'Asia/Seoul'
            time.tzset()
        kst = timezone('Asia/Seoul')

        hourly_data = data.get("hourly", [])[:48]
        alerts = data.get("alerts", [])

        # ✅ 날짜별 그룹핑
        daily_groups = {}

        for hour in hourly_data:
            dt_obj = datetime.utcfromtimestamp(hour.get("dt", 0)).replace(tzinfo=timezone("UTC")).astimezone(kst)
            date_str = dt_obj.strftime("%Y%m%d")
            time_str = dt_obj.strftime("%Y-%m-%d %H:%M:%S")

            entry = {
                "time": time_str,
                "temp": hour.get("temp"),
                "feels_like": hour.get("feels_like"),
                "humidity": hour.get("humidity"),
                "wind_speed": hour.get("wind_speed"),
                "uvi_level": uvi_level(hour.get("uvi")),
                "sunlight": hour.get("clouds"),  # clouds 수치 사용
                "pop": hour.get("pop"),
                "rain": hour.get("rain", {}).get("1h", 0),
                "snow": hour.get("snow", {}).get("1h", 0),
                "clouds": hour.get("clouds"),
                "weather": hour.get("weather", [{}])[0]
            }

            daily_groups.setdefault(date_str, []).append(entry)

        # ✅ Firestore에 날짜별로 저장
        for date_str, entries in daily_groups.items():
            doc_key = f"{city_name}_{date_str}"
            db.collection("weather_forecasts").document(doc_key).set({
                "city": city_name,
                "date": date_str,
                "hourly_forecasts": entries,
                "alerts": alerts  # 하루에 한 번 포함
            })

        return JsonResponse({
            "message": "날씨 데이터가 저장되었습니다.",
            "saved_dates": list(daily_groups.keys())
        })

    except requests.RequestException as e:
        return JsonResponse({'error': str(e)}, status=500)

def air_pollution(request):
    city_name = request.GET.get('city', 'Seoul')
    API_KEY = settings.OPENWEATHER_API_KEY
    lat, lon = get_lat_lon(city_name, API_KEY)

    if lat is None or lon is None:
        return JsonResponse({'error': '도시명을 찾을 수 없습니다.'}, status=400)

    url = f"http://api.openweathermap.org/data/2.5/air_pollution"
    params = {
        'lat': lat,
        'lon': lon,
        'appid': API_KEY
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        air_info = data.get("list", [])[0] if data.get("list") else {}

        # ✅ 현재 날짜 구하기
        kst = timezone("Asia/Seoul")
        today = datetime.now(kst).strftime("%Y%m%d")
        doc_key = f"{city_name}_{today}"

        # ✅ Firestore 저장
        db.collection("air_quality").document(doc_key).set({
            "city": city_name,
            "date": today,
            "air": air_info
        })

        return JsonResponse({
            "message": "대기오염 정보가 저장되었습니다.",
            "document": doc_key,
            "air": air_info
        })

    except requests.RequestException as e:
        return JsonResponse({'error': str(e)}, status=500)

