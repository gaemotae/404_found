# 웹 서버와 django 간의 인터페이스를 설정
"""
WSGI config for weather_project project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'weather_project.settings')

application = get_wsgi_application()
