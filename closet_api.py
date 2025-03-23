from flask import Blueprint, request, jsonify
from firebase_config import db
import firebase_admin
from firebase_admin import firestore

closet_api = Blueprint("closet_api", __name__)

@closet_api.route("/closet/<user_id>", methods=["POST"])
def add_closet_item(user_id):
    try:
        data = request.get_json()
        closet_ref = db.collection("closet").document()
        closet_ref.set({
            "user_id": user_id,
            "image_url": data.get("image_url"),
            "category": data.get("category"),
            "color": data.get("color"),
            "season_tag": data.get("season_tag"),
            "created_at": firestore.SERVER_TIMESTAMP
        })
        return jsonify({"message": f"✅ 사용자 {user_id}의 옷 추가 완료"}), 201

    except Exception as e:
        print("🔥 오류 발생:", str(e))
        return jsonify({"error": "서버 내부 오류", "details": str(e)}), 500
