from django.urls import path
from . import views

urlpatterns = [
    path('weather_forecast/', views.weather_forecast, name='weather_forecast'),
    path('air_pollution/', views.air_pollution, name='air_pollution'),
]
