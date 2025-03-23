from flask import Blueprint, request, jsonify
from firebase_config import db
import firebase_admin
from firebase_admin import firestore

recommendations_api = Blueprint("recommendations_api", __name__)

@recommendations_api.route("/recommendations/<user_id>", methods=["POST"])
def save_recommendation(user_id):
    try:
        data = request.get_json()
        rec_ref = db.collection("ai_recommendations").document()
        rec_ref.set({
            "user_id": user_id,
            "suggested_items": data.get("suggested_items"),
            "created_at": firestore.SERVER_TIMESTAMP
        })
        return jsonify({"message": f"✅ AI 추천 결과 저장 완료"}), 201

    except Exception as e:
        print("🔥 오류 발생:", str(e))
        return jsonify({"error": "서버 내부 오류", "details": str(e)}), 500
