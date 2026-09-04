import uuid

import bcrypt
from firebase_admin import storage
from flask import Blueprint, current_app, jsonify, render_template, request
from flask_jwt_extended import get_jwt_identity, jwt_required

user_edit_bp = Blueprint("user_edit", __name__)


@user_edit_bp.route("/user/settings_page", methods=["GET"])
def settings_page():
    return render_template("settings.html")


@user_edit_bp.route("/user/settings", methods=["GET"])
@jwt_required()
def get_settings():
    uid = get_jwt_identity()
    user_doc = current_app.db.collection("users").document(uid).get()
    if not user_doc.exists:
        return jsonify({"message": "사용자 없음"}), 404

    user = user_doc.to_dict()
    return jsonify(
        {
            "push_notifications_enabled": user.get("push_notifications_enabled", False),
            "nickname": user.get("nickname", ""),
            "profile_image": user.get("profile_image", ""),
            "age_group": user.get("age_group", "20"),
        }
    ), 200


@user_edit_bp.route("/user/settings", methods=["PUT"])
@jwt_required()
def update_settings():
    uid = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    editable_fields = [
        "push_notifications_enabled",
        "nickname",
        "password",
        "age_group",
    ]
    if not any(data.get(key) is not None for key in editable_fields):
        return jsonify({"message": "수정할 값이 없습니다."}), 400

    user_ref = current_app.db.collection("users").document(uid)
    if not user_ref.get().exists:
        return jsonify({"message": "사용자 없음"}), 404

    updates = {}
    if data.get("push_notifications_enabled") is not None:
        updates["push_notifications_enabled"] = data["push_notifications_enabled"]
    if data.get("nickname"):
        updates["nickname"] = data["nickname"]
    if data.get("password"):
        hashed_password = bcrypt.hashpw(data["password"].encode(), bcrypt.gensalt())
        updates["password"] = hashed_password.decode()
    if data.get("age_group"):
        updates["age_group"] = data["age_group"]

    user_ref.update(updates)
    return jsonify({"message": "설정이 성공적으로 업데이트되었습니다."}), 200


@user_edit_bp.route("/user/profile_image", methods=["POST"])
@jwt_required()
def upload_profile_image():
    uid = get_jwt_identity()
    if "image" not in request.files:
        return jsonify({"message": "이미지 파일이 필요합니다."}), 400

    image = request.files["image"]
    filename = f"profile_{uid}_{uuid.uuid4().hex}.jpg"
    blob = storage.bucket().blob(f"profile_images/{filename}")
    blob.upload_from_file(image, content_type=image.content_type)
    blob.make_public()

    current_app.db.collection("users").document(uid).update(
        {"profile_image": blob.public_url}
    )
    return jsonify(
        {"message": "프로필 이미지가 변경되었습니다.", "url": blob.public_url}
    ), 200
