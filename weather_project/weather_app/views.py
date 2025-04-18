# 요청 처리 및 반환
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
        response = requests.get(URL, timeout=5)  # 요청 시 타임아웃 설정
        response.raise_for_status()  # HTTP 오류 발생 시 예외 처리

        data = response.json()
        forecast_data = [
            {
                'time': datetime.fromtimestamp(item['dt']).strftime('%Y-%m-%d %H:%M:%S'), 
                'temperature': item['main']['temp'],
                'humidity': item['main']['humidity'],
                'feels_like': item['main']['feels_like'],  # 체감 온도
                'wind_speed': item['wind']['speed'],
                'sunlight': item['clouds']['all'],
            }
            for item in data.get('list', [])
        ]

        return forecast_data

    except requests.exceptions.RequestException as e:
        return {'error': f'API 요청 실패: {str(e)}'}

def weather_forecast(request):
    city_name = request.GET.get('city', 'Seoul')  # 요청에서 도시 이름 가져오기, 기본값은 서울
    weather_data = get_weather_forecast(city_name)

    if isinstance(weather_data, list) and weather_data:  # 에러 응답이 아닌 경우
        daily_data = {}

        for forecast in weather_data:
            # 날짜 추출 및 포맷 변경 (YYYYMMDD)
            forecast_date = forecast['time'].split(' ')[0].replace('-', '')
            daily_data.setdefault(forecast_date, []).append(forecast)

        # Firestore에 데이터 저장
        for date, forecasts in daily_data.items():
            document_key = f"{city_name}_{date}"  # 도시 이름과 날짜를 키로 사용
            db.collection("weather_forecasts").document(document_key).set({
                "date": date,
                "city": city_name,
                "forecasts": forecasts
            })

        return JsonResponse({'message': '데이터가 Firebase에 저장되었습니다.', 'saved_dates': list(daily_data.keys())})
    
    return JsonResponse({'error': '도시를 찾을 수 없거나 API 오류 발생'}, status=400)
