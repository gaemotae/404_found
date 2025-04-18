# django 프로젝트 관리(실행)
#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'weather_project.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()

""" 
Django 프로젝트를 생성하면 기본적으로 두 개의 파일로 나뉘어지는 이유는 다음과 같습니다:

프로젝트와 앱의 구분: Django는 "프로젝트(구조)"와 "앱(기능)"이라는 개념을 명확히 구분합니다.

프로젝트는 전체 웹 애플리케이션을 의미하며, 여러 개의 앱을 포함할 수 있습니다.
앱은 특정 기능이나 서비스를 제공하는 모듈로, 독립적으로 재사용할 수 있습니다.
"""