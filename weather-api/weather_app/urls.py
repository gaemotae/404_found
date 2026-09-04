from django.urls import path

from . import views

urlpatterns = [
    path("weather_forecast/", views.weather_forecast, name="weather_forecast"),
    path("air_pollution/", views.air_pollution, name="air_pollution"),
    path("save_daily_weather/", views.save_daily_weather, name="save_daily_weather"),
]
