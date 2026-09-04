import os
from datetime import datetime

import firebase_admin
from config import Config, get_firebase_credential, get_firebase_web_config
from firebase_admin import auth, firestore
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, set_access_cookies

app = Flask(__name__)
app.config.from_object(Config)

CORS(
    app,
    resources={r"/*": {"origins": app.config["CORS_ORIGINS"]}},
    supports_credentials=True,
    expose_headers=["Authorization"],
    allow_headers=["Authorization", "Content-Type"],
)
JWTManager(app)


credential = get_firebase_credential()
if credential and not firebase_admin._apps:
    firebase_options = {}
    if app.config["FIREBASE_STORAGE_BUCKET"]:
        firebase_options["storageBucket"] = app.config["FIREBASE_STORAGE_BUCKET"]
    firebase_admin.initialize_app(credential, firebase_options)

app.db = firestore.client() if firebase_admin._apps else None


# Firebase initialization must complete before blueprints use the shared client.
from community.community import community_bp  # noqa: E402
from recommend.outfits_history import outfits_history_bp  # noqa: E402
from recommend.recommendation import recommendation_bp  # noqa: E402
from upload.image import image_bp  # noqa: E402

from com.example.login import login_bp  # noqa: E402
from com.example.register import register_bp  # noqa: E402
from com.example.user_edit import user_edit_bp  # noqa: E402

app.register_blueprint(login_bp)
app.register_blueprint(register_bp)
app.register_blueprint(user_edit_bp)
app.register_blueprint(image_bp, url_prefix="/upload")
app.register_blueprint(recommendation_bp, url_prefix="/api/recommend")
app.register_blueprint(outfits_history_bp, url_prefix="/api/history")
app.register_blueprint(community_bp, url_prefix="/")


@app.before_request
def log_request():
    """Log request metadata without exposing authorization credentials."""
    app.logger.info("%s %s", request.method, request.path)


@app.route("/ping")
def ping():
    return {"message": "pong"}, 200


@app.route("/auth/firebase/", methods=["POST"])
def verify_firebase_token():
    if app.db is None:
        return jsonify({"error": "Firebase is not configured"}), 503

    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return jsonify({"error": "ID token missing"}), 401

    try:
        decoded_token = auth.verify_id_token(authorization.removeprefix("Bearer "))
        uid = decoded_token["uid"]
        email = decoded_token.get("email", "")
        jwt_token = create_access_token(identity=uid)

        app.db.collection("auth_logs").add(
            {"email": email, "uid": uid, "timestamp": datetime.utcnow()}
        )

        response = jsonify(
            {
                "message": "인증 성공",
                "uid": uid,
                "email": email,
                "token": jwt_token,
            }
        )
        set_access_cookies(response, jwt_token)
        return response, 200
    except Exception:
        app.logger.exception("Firebase authentication failed")
        return jsonify({"error": "Authentication failed"}), 401


@app.route("/")
def index():
    return render_template(
        "login.html",
        firebase_config=get_firebase_web_config(),
    )


@app.route("/recommendation")
def recommendation_page():
    return render_template("recommendation.html")


@app.route("/api/recommendations/same_day", methods=["GET"])
def redirect_to_history_page():
    return (
        jsonify(
            {
                "redirect": "/api/history/outfits_history",
                "message": "경로가 변경되었습니다. /api/history/outfits_history 를 이용하세요.",
            }
        ),
        302,
        {"Location": "/api/history/outfits_history"},
    )


if __name__ == "__main__":
    app.run(
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "8080")),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )
