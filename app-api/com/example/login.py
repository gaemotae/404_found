from datetime import datetime

import bcrypt
from config import get_firebase_web_config
from flask import Blueprint, current_app, jsonify, render_template, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
)

login_bp = Blueprint("login", __name__)


@login_bp.route("/login", methods=["GET"])
def login_page():
    return render_template(
        "login.html",
        firebase_config=get_firebase_web_config(),
    )


@login_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"message": "이메일과 비밀번호를 입력해주세요."}), 400

    users = current_app.db.collection("users").where("email", "==", email).get()
    if not users:
        return jsonify({"message": "잘못된 이메일 또는 비밀번호입니다."}), 401

    user_doc = users[0]
    user = user_doc.to_dict()
    if not bcrypt.checkpw(password.encode(), user["password"].encode()):
        return jsonify({"message": "잘못된 이메일 또는 비밀번호입니다."}), 401

    user_id = user_doc.id
    token = create_access_token(identity=user_id)
    current_app.db.collection("auth_logs").add(
        {"email": email, "uid": user_id, "timestamp": datetime.utcnow()}
    )

    response = jsonify(
        {
            "message": "로그인 성공!",
            "nickname": user.get("nickname", "닉네임 없음"),
            "token": token,
        }
    )
    set_access_cookies(response, token)
    return response, 200


@login_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    current_user = get_jwt_identity()
    current_app.db.collection("auth_logs").add(
        {
            "email": current_user,
            "action": "logout",
            "timestamp": datetime.utcnow(),
        }
    )
    return jsonify({"message": "서버에서 로그아웃 기록 완료"}), 200


@login_bp.route("/auth/verify_token", methods=["GET"])
@jwt_required()
def verify_token():
    user_id = get_jwt_identity()
    return jsonify({"valid": True, "user_id": user_id, "email": user_id}), 200
