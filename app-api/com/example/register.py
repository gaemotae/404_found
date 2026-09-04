from datetime import datetime

import bcrypt
from firebase_admin import auth
from flask import Blueprint, current_app, jsonify, render_template, request

register_bp = Blueprint("register", __name__)


@register_bp.route("/register", methods=["GET", "POST"])
def register():
    db = current_app.db

    if request.method == "GET":
        return render_template("register.html")

    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    username = data.get("username")
    age_group = data.get("age_group", "20")  # 기본값 20대

    if not email or not password:
        return jsonify({"message": "이메일과 비밀번호를 입력해주세요."}), 400

    # 중복 이메일 검사 (Firestore)
    if db.collection("users").where("email", "==", email).get():
        return jsonify({"message": "이미 존재하는 사용자입니다."}), 409

    try:
        # Firebase Authentication에 사용자 생성
        user_record = auth.create_user(
            email=email, password=password, display_name=username
        )
        user_id = user_record.uid

        # Firestore에 사용자 정보 저장
        hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        db.collection("users").document(user_id).set(
            {
                "email": email,
                "password": hashed_pw.decode(),
                "nickname": username,
                "user_id": user_id,
                "age_group": age_group,
                "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

        return jsonify({"message": "회원가입 성공!", "user_id": user_id}), 201

    except Exception as e:
        return jsonify({"message": f"회원가입 실패: {str(e)}"}), 500
