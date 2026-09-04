from django.http import JsonResponse

from .services import save_air_pollution, save_weather_forecast


def weather_forecast(request):
    city_name = request.GET.get("city", "Seoul")
    try:
        save_weather_forecast(city_name)
        return JsonResponse({"message": f"{city_name} 날씨 데이터 저장 완료"})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def air_pollution(request):
    city_name = request.GET.get("city", "Seoul")
    try:
        save_air_pollution(city_name)
        return JsonResponse({"message": f"{city_name} 대기오염 데이터 저장 완료"})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def save_daily_weather(request):
    city_name = request.GET.get("city", "Seoul")
    try:
        save_weather_forecast(city_name)  # 일별 날씨 저장 함수 호출
        return JsonResponse({"message": f"{city_name} 일별 날씨 데이터 저장 완료"})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
