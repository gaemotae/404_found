import firebase_admin
from flask import Flask, request, jsonify
from firebase_admin import credentials, firestore
from firebase_config import db  # Firestore 연결 파일 import
from flask import Flask
from closet_api import closet_api
from recommendations_api import recommendations_api

# ✅ Firestore 연결 (이미 초기화되었는지 확인 후 실행)
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate("C:/Users/ggyyu/wearther/wearther-404found-firebase-adminsdk-fbsvc-a6379fb165.json")
        firebase_admin.initialize_app(cred)
        print("✅ Firestore 연결 성공")
    except Exception as e:
        print("🔥 Firestore 연결 오류:", str(e))

# ✅ Flask 앱 초기화
app = Flask(__name__)

# ✅ 사용자 추가 API (POST /users)
@app.route("/users", methods=["POST"])
def add_user():
    try:
        data = request.json  # JSON 데이터 받기
        print("받은 데이터:", data)  # 🔥 서버에서 데이터 출력

        user_id = data.get("user_id")
        email = data.get("email")
        username = data.get("username")
        profile_img = data.get("profile_img", "")

        if not user_id or not email or not username:
            return jsonify({"error": "필수 필드가 누락되었습니다."}), 400

        user_ref = db.collection("users").document(user_id)
        user_ref.set({
            "user_id": user_id,
            "email": email,
            "username": username,
            "profile_img": profile_img,
            "createdAt": firestore.SERVER_TIMESTAMP
        })

        return jsonify({"message": "✅ 사용자 등록 완료", "user_id": user_id}), 201

    except Exception as e:
        print("🔥 오류 발생:", str(e))  # 🔥 오류 출력
        return jsonify({"error": "서버 내부 오류", "details": str(e)}), 500

# ✅ 사용자 목록 조회 API (GET /users)
@app.route("/users", methods=["GET"])
def get_users():
    try:
        users_ref = db.collection("users")
        docs = users_ref.stream()
        users = [{doc.id: doc.to_dict()} for doc in docs]
        return jsonify({"users": users})

    except Exception as e:
        print("🔥 오류 발생:", str(e))
        return jsonify({"error": "서버 내부 오류", "details": str(e)}), 500

# ✅ Flask 서버 실행 (중복 제거)
if __name__ == "__main__":
    app.run(debug=True, port=5000)

# ✅ Blueprint 등록 (API 모듈 연결)
app.register_blueprint(closet_api)
app.register_blueprint(recommendations_api)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
