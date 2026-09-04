from django.core.management.base import BaseCommand
from weather_app.services import save_air_pollution, save_weather_forecast


class Command(BaseCommand):
    help = "모든 날씨, 대기오염 정보 자동 업데이트"

    def handle(self, *args, **kwargs):
        city_name = "Seoul"
        save_weather_forecast(city_name)
        save_air_pollution(city_name)
        self.stdout.write(self.style.SUCCESS("✅ 모든 날씨/대기오염 업데이트 완료"))
