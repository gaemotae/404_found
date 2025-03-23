from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials
from flask_jwt_extended import JWTManager, create_access_token
import requests
from datetime import timedelta
import os

app = Flask(__name__)
CORS(app, resources={r"/login": {"origins": "http://yourfrontend.com"}})

app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'your_jwt_secret_key')  
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
jwt = JWTManager(app)

cred = credentials.Certificate("firebase_credentials.json") 
firebase_admin.initialize_app(cred)

FIREBASE_API_KEY = os.getenv('FIREBASE_API_KEY', 'your_firebase_api_key')

def verify_user(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    headers = {
        "Content-Type": "application/json"
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json()['idToken']
    else:
        print(response.json())  # 오류 메시지를 로그로 기록
        return None

@app.route('/login', methods=['POST'])
def login_user():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"msg": "이메일과 패스워드를 모두 입력해주세요."}), 400

    id_token = verify_user(email, password)
    if id_token:
        access_token = create_access_token(identity={"email": email})
        return jsonify(access_token=access_token), 200
    else:
        return jsonify({"msg": "이메일 또는 패스워드가 올바르지 않습니다."}), 401

if __name__ == '__main__':
    app.run(debug=True)

"""
개선 사항

비밀 키와 API 키 관리:
your_jwt_secret_key와 your_firebase_api_key는 환경 변수나 안전한 비밀 관리 시스템을 통해 관리하는 것이 좋습니다. 코드에 직접 작성하면 보안 문제가 발생할 수 있습니다.

에러 처리 개선:
verify_user 함수에서 Firebase API의 오류 메시지를 로그로 남기거나 반환하면 문제를 진단하는 데 도움이 됩니다. 예를 들어, 응답 본문을 확인하여 어떤 오류가 발생했는지 알 수 있습니다.
if response.status_code != 200:
    print(response.json())  # 오류 메시지를 로그로 기록

JWT 토큰 유효 기간 설정:
JWT 토큰의 유효 기간을 설정하여 보안을 강화할 수 있습니다. 예를 들어, app.config['JWT_ACCESS_TOKEN_EXPIRES']를 설정할 수 있습니다.
from datetime import timedelta

app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)  # 1시간 후 만료

로그인 시도 제한:
로그인 시도가 실패할 경우, 일정 횟수 이상 실패하면 계정을 잠그거나 일시적으로 로그인 시도를 제한하는 로직을 추가할 수 있습니다. 이는 brute-force 공격을 방지하는 데 도움이 됩니다.

CORS 설정:
CORS를 사용할 때는 허용할 출처를 명시적으로 설정하는 것이 좋습니다. 예를 들어, CORS(app, resources={r"/login": {"origins": "http://yourfrontend.com"}})와 같이 설정할 수 있습니다."
"""