import requests
from django.http import JsonResponse
from datetime import datetime
from firebase_admin import firestore

# Firestore 클라이언트 초기화
db = firestore.client()

def get_weather_forecast(city_name):
    API_KEY = "ba38daa4af28d548e94343c4f966b457"
    URL = f'http://api.openweathermap.org/data/2.5/forecast?q={city_name}&appid={API_KEY}&units=metric'

    try:
        response = requests.get(URL, timeout=5)
        response.raise_for_status()
        data = response.json()

        forecast_data = [
            {
                'time': datetime.fromtimestamp(item['dt']).strftime('%Y-%m-%d %H:%M:%S'),
                'temperature': item['main']['temp'],
                'humidity': item['main']['humidity'],
                'feels_like': item['main']['feels_like'],
                'wind_speed': item['wind']['speed'],
                'sunlight': item['clouds']['all'],
            }
            for item in data.get('list', [])
        ]

        return forecast_data

    except requests.exceptions.RequestException as e:
        return {'error': f'API 요청 실패: {str(e)}'}

def weather_forecast(request):
    city_name = request.GET.get('city', 'Seoul')
    weather_data = get_weather_forecast(city_name)

    if isinstance(weather_data, list) and weather_data:
        daily_data = {}

        for forecast in weather_data:
            forecast_date = forecast['time'].split(' ')[0].replace('-', '')
            daily_data.setdefault(forecast_date, []).append(forecast)

        # Firestore에 저장
        for date, forecasts in daily_data.items():
            document_key = f"{city_name}_{date}"
            db.collection("weather_forecasts").document(document_key).set({
                "date": date,
                "city": city_name,
                "forecasts": forecasts
            })

        # ✅ 오늘 날짜 기준으로 필터링한 결과만 반환
        today = datetime.now().strftime('%Y%m%d')
        forecasts_today = daily_data.get(today, [])

        return JsonResponse({
            "date": today,
            "city": city_name,
            "forecasts": forecasts_today
        })

    # 에러 발생 시
    return JsonResponse({'error': '도시를 찾을 수 없거나 API 오류 발생'}, status=400)
