from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials
from flask_jwt_extended import JWTManager, create_access_token
import requests

# Flask 애플리케이션 초기화(생성)
app = Flask(__name__)
CORS(app)

# JWT 설정
app.config['JWT_SECRET_KEY'] = 'your_jwt_secret_key'  # 안전한 비밀 키로 변경하세요
jwt = JWTManager(app)

# Firebase 서비스 계정 키 로드
cred = credentials.Certificate("firebase_credentials.json") 
firebase_admin.initialize_app(cred)

# Firebase 프로젝트의 API 키
FIREBASE_API_KEY = 'your_firebase_api_key'  # Firebase 콘솔에서 확인 가능

# 사용자 인증 함수
def verify_user(email, password):
    """
    Firebase Auth REST API를 사용하여 사용자를 인증합니다.
    이메일과 패스워드를 받아 Firebase로 요청을 보내고,
    성공 시 ID 토큰을 반환합니다.
    """
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
        return None

# 로그인 엔드포인트
@app.route('/login', methods=['POST'])
def login_user():
    """
    사용자의 이메일과 패스워드를 받아 인증하고,
    성공 시 JWT 토큰을 생성하여 반환합니다.
    """
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"msg": "이메일과 패스워드를 모두 입력해주세요."}), 400

    id_token = verify_user(email, password)
    if id_token:
        # 사용자를 식별할 수 있는 정보를 JWT의 identity로 설정
        access_token = create_access_token(identity={"email": email})
        return jsonify(access_token=access_token), 200
    else:
        return jsonify({"msg": "이메일 또는 패스워드가 올바르지 않습니다."}), 401

if __name__ == '__main__':
    app.run(debug=True)

""" 
필요한 라이브러리 임포트:
Flask, request, jsonify 등 웹 서버와 요청 처리를 위한 라이브러리.
flask_cors를 통해 CORS 설정.
firebase_admin을 사용하여 Firebase와 연동.
flask_jwt_extended를 이용해 JWT 토큰 생성 및 관리.
requests 라이브러리를 사용해 Firebase Auth REST API에 요청을 보냄.

Flask 애플리케이션 초기화 및 CORS 설정:
Flask 앱을 생성하고, CORS(app)을 통해 모든 도메인에서의 요청을 허용.

JWT 설정:
JWT_SECRET_KEY를 설정하여 JWT 토큰의 서명을 보호. 실제 배포 시 안전한 비밀 키로 변경 필요.
JWTManager를 초기화하여 JWT 관련 기능을 사용할 준비.

Firebase 초기화:
firebase_credentials.json 파일을 통해 Firebase Admin SDK를 초기화.
이 파일은 Firebase 콘솔에서 서비스 계정 키를 생성하여 다운로드 받을 수 있음.

Firebase API 키 설정:
Firebase 프로젝트의 API 키를 FIREBASE_API_KEY 변수에 설정. 이는 Firebase 콘솔의 프로젝트 설정에서 확인 가능.

사용자 인증 함수 (verify_user):
사용자의 이메일과 패스워드를 받아 Firebase Auth REST API에 POST 요청을 보냄.
성공 시 Firebase에서 반환하는 idToken을 반환하고, 실패 시 None을 반환.

로그인 엔드포인트 (/login):
클라이언트로부터 email과 password를 JSON 형식으로 받아옴.
입력값이 모두 존재하는지 확인. 누락 시 400 에러 반환.
verify_user 함수를 통해 사용자의 자격 증명을 확인.
인증에 성공하면 create_access_token을 사용해 JWT 토큰을 생성하고, 이를 클라이언트에 반환.
인증에 실패하면 401 에러 메시지를 반환.

애플리케이션 실행:
스크립트가 직접 실행될 경우, Flask 개발 서버를 디버그 모드로 실행.
이 프로그램은 iOS 앱과 연동되어 Firebase를 통해 사용자 로그인을 처리하는 백엔드 서버를 제공합니다. 사용자가 로그인 요청을 보내면, 서버는 Firebase Auth를 통해 자격 증명을 확인하고, 성공 시 JWT 토큰을 생성하여 반환함으로써 이후의 인증된 요청을 가능하게 합니다. 
"""