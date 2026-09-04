import json
import logging
import os
import uuid
from datetime import datetime

import requests
from firebase_admin import firestore, storage
from flask import Blueprint, jsonify, render_template, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from werkzeug.utils import secure_filename

template_dir = os.path.join(os.path.dirname(__file__), "templates")
image_bp = Blueprint("image", __name__, template_folder=template_dir)

AI_SERVER = os.getenv("AI_SERVER_URL", "http://localhost:5001/analyze")
logger = logging.getLogger(__name__)

# 앱 입력값과 AI 응답에 공통 적용하는 표준 소재 목록
STANDARD_MATERIALS = {
    "면",
    "데님",
    "린넨/마",
    "가죽",
    "퍼/털",
    "시폰/얇은 원단",
    "실크/새틴",
    "스판덱스/스포츠 원단",
    "나일론/방수",
    "울/정장소재",
    "니트/스웨터소재",
    "벨벳",
    "트위드",
}


# ------------------- 공통 유틸 -------------------
def get_db():
    return firestore.client()


def user_ref(uid):
    return get_db().collection("users").document(uid)


def closet_ref(uid):
    return user_ref(uid).collection("closet")


def json_body():
    return request.get_json(silent=True) or {}


def text_value(data, key):
    return (data.get(key) or "").strip()


def jerr(msg, code=400, **kw):
    return jsonify({"error": msg, **kw}), code


def ok(msg, **kw):
    return jsonify({"message": msg, **kw}), 200


def tmpdir():
    t = "/tmp" if os.name != "nt" else os.environ.get("TEMP", r"C:\Temp")
    os.makedirs(t, exist_ok=True)
    return t


def safe_rm(p):
    try:
        os.remove(p)
    except OSError:
        return


def parse_colors(maybe):
    """colors 입력을 안전하게 리스트로 파싱"""
    if maybe is None:
        return []
    if isinstance(maybe, list):
        return maybe
    s = str(maybe).strip()
    if not s:
        return []
    try:
        v = json.loads(s)
        if isinstance(v, list):
            return v
    except json.JSONDecodeError:
        v = None
    return [x.strip() for x in s.split(",") if x.strip()] if "," in s else [s]


def doc_to_item(doc):
    d = doc.to_dict() or {}
    return {
        "id": doc.id,
        "filename": d.get("filename"),
        "url": d.get("url"),
        "type": d.get("type", ""),
        "category": d.get("category", ""),
        "colors": d.get("colors", []),
        "material": d.get("material", ""),
        "suitable_temperature": d.get("suitable_temperature", ""),
        "uploaded_at": d.get("uploaded_at", ""),
    }


# ------------------- 소재 검증 공통 -------------------
def is_valid_material(m: str | None) -> bool:
    return bool(m) and m in STANDARD_MATERIALS


def ensure_valid_material(m: str | None, *, on_invalid_empty: bool = False):
    """
    - 폼/JSON에서 받은 material(m)이 표준 목록에 있으면 그대로 반환
    - 표준에 없으면:
      - on_invalid_empty=True: "" 반환(프론트 재선택 유도)
      - on_invalid_empty=False: 오류 응답(업데이트/입력 검증용)
    """
    if not m:
        return ""
    if m in STANDARD_MATERIALS:
        return m
    return "" if on_invalid_empty else None


# ------------------- AI 연동 -------------------
def analyze_clothing(image_path: str):
    """
    AI 서버로 이미지 전달 후 원본 결과 반환 (상세 로깅/에러 처리 포함)
    """
    try:
        with open(image_path, "rb") as f:
            res = requests.post(AI_SERVER, files={"image": f}, timeout=30)
        if res.status_code != 200:
            return None
        result = res.json()
        return result
    except requests.exceptions.Timeout:
        return None
    except requests.exceptions.ConnectionError:
        return None
    except Exception:
        logger.exception("Unexpected error while calling the clothing analysis API")
        return None


def normalize_ai_result(raw: dict) -> dict:
    """
    모델 응답을 앱 표준 스키마로 변환 (상세 로깅 포함)
    """
    raw = raw or {}
    success = raw.get("success", True)
    _type = raw.get("type") or raw.get("clothing_big_type") or ""
    category = raw.get("category") or raw.get("clothing_type") or ""
    out = {
        "success": success,
        "type": _type,
        "category": category,
        "colors": raw.get("colors", []),
        "material": raw.get("material", ""),
        "suitable_temperature": raw.get("suitable_temperature", ""),
    }
    return out


# ------------------- Pages -------------------
@image_bp.route("/", methods=["GET"])
def upload_page():
    return render_template("upload.html")


@image_bp.route("/my_images_page", methods=["GET"])
def my_images_page():
    return render_template("my_images.html")


# ------------------- APIs (조회/삭제 로직 수정) -------------------
@image_bp.route("/my_closet", methods=["GET"])
@jwt_required()
def get_my_closet():
    uid = get_jwt_identity()
    # 응답 크기 제한
    items = [doc_to_item(d) for d in closet_ref(uid).limit(100).get()]
    return jsonify(items), 200


@image_bp.route("/my_images", methods=["GET"])
@jwt_required()
def get_my_images():
    uid = get_jwt_identity()
    # 응답 크기 제한
    items = [doc_to_item(d) for d in closet_ref(uid).limit(100).get()]
    return jsonify({"images": items}), 200


# ------------------- 🔹 1단계: AI 분석만 (DB 저장 X, 미리보기 용) -------------------
@image_bp.route("/analyze", methods=["POST"])
@jwt_required()
def analyze_only():
    """이미지 분석만 수행하고 결과 반환 (DB 저장 X, 키 통일: type/category)"""
    if "image" not in request.files:
        return jerr("No image file provided")
    image = request.files["image"]
    filename = secure_filename(image.filename)
    if not filename:
        return jerr("Invalid filename")

    local_path = os.path.join(tmpdir(), f"{uuid.uuid4()}_{filename}")
    image.save(local_path)

    try:
        raw = analyze_clothing(local_path)
        safe_rm(local_path)
        if not raw:
            return jsonify({"success": False, "error": "AI analysis failed"}), 500
        norm = normalize_ai_result(raw)
        if not norm.get("success", True):
            return jsonify(
                {"success": False, "error": raw.get("error", "AI analysis failed")}
            ), 500
        return jsonify(
            {
                "success": True,
                "type": norm["type"],
                "category": norm["category"],
                "colors": norm["colors"],
                "material": norm["material"],
                "suitable_temperature": norm["suitable_temperature"],
            }
        ), 200
    except Exception as e:
        logger.exception("Clothing analysis request failed")
        safe_rm(local_path)
        return jerr(str(e), 500)


# ------------------- 🔹 2단계: 최종 업로드 (사용자 수정값 반영하여 저장) -------------------
@image_bp.route("/", methods=["POST"])
@jwt_required()
def upload_file():
    """최종 업로드 (Firestore 저장) - 표준 소재 목록 검증"""
    uid = get_jwt_identity()
    if "image" not in request.files:
        return jerr("No image file provided")
    image = request.files["image"]
    filename = secure_filename(image.filename)
    if not filename:
        return jerr("Invalid filename")

    form = request.form or {}
    # 프론트와 AI 모델의 필드명을 표준 스키마로 정규화
    user_type = text_value(form, "type") or text_value(form, "clothing_big_type")
    user_category = text_value(form, "category") or text_value(form, "clothing_type")
    user_material = form.get("material")
    user_suitable_temperature = form.get("suitable_temperature")
    user_colors = parse_colors(form.get("colors"))

    # 폼 입력 소재 검증
    if user_material and not is_valid_material(user_material):
        return jerr(
            f"유효하지 않은 소재입니다. 다음 중 선택해야 합니다: {', '.join(STANDARD_MATERIALS)}",
            400,
        )

    local_path = os.path.join(tmpdir(), f"{uuid.uuid4()}_{filename}")
    image.save(local_path)

    try:
        # 사용자가 확정값을 보냈다면 그대로 사용, 아니면 AI 백업 수행
        if any(
            [
                user_type,
                user_category,
                user_material,
                user_suitable_temperature,
                user_colors,
            ]
        ):
            ai_norm = {
                "success": True,
                "type": user_type or "",
                "category": user_category or "",
                "colors": user_colors or [],
                "material": user_material or "",
                "suitable_temperature": user_suitable_temperature or "",
            }
        else:
            raw = analyze_clothing(local_path)
            if not raw:
                safe_rm(local_path)
                return jsonify({"success": False, "error": "AI analysis failed"}), 500
            ai_norm = normalize_ai_result(raw)
            if not ai_norm.get("success", True):
                safe_rm(local_path)
                return jsonify(
                    {"success": False, "error": raw.get("error", "AI analysis failed")}
                ), 500
            # 알 수 없는 AI 소재는 비워 두어 클라이언트에서 재선택하도록 합니다.
            ai_norm["material"] = ensure_valid_material(
                ai_norm.get("material"), on_invalid_empty=True
            )

        bucket = storage.bucket()
        unique = os.path.basename(local_path)
        blob = bucket.blob(f"images/{unique}")
        blob.upload_from_filename(local_path)
        blob.make_public()
        image_url = blob.public_url

        # Firestore 저장
        doc_data = {
            "filename": unique,
            "url": image_url,
            "user_id": uid,
            "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": ai_norm.get("type", ""),
            "category": ai_norm.get("category", ""),
            "colors": ai_norm.get("colors", []),
            "material": ai_norm.get("material", ""),
            "suitable_temperature": ai_norm.get("suitable_temperature", ""),
        }

        doc_ref = closet_ref(uid).document()
        doc_ref.set(doc_data)
        safe_rm(local_path)

        return jsonify(
            {
                "success": True,
                "message": "Upload successful",
                "url": image_url,
                "ai_result": doc_data | {"id": doc_ref.id},
                "id": doc_ref.id,
            }
        ), 200

    except Exception as e:
        logger.exception("Clothing upload failed")
        safe_rm(local_path)
        return jerr(str(e), 500)


# 이미지 삭제
@image_bp.route("/delete_image/<image_id>", methods=["DELETE"])
@jwt_required()
def delete_image(image_id):
    uid = get_jwt_identity()

    doc_ref = closet_ref(uid).document(image_id)
    doc = doc_ref.get()
    if not doc.exists:
        return jerr("이미지가 존재하지 않습니다.", 404)

    data = doc.to_dict() or {}
    if "filename" in data:
        try:
            storage.bucket().blob(f"images/{data['filename']}").delete()
        except Exception:
            logger.warning("Storage object deletion failed", exc_info=True)

    doc_ref.delete()
    return ok("삭제 성공!")


# 이미지 정보 수정 (JSON 방식, Android/API용)
@image_bp.route("/update_image/<image_id>", methods=["PATCH"])
@jwt_required()
def update_image(image_id):
    """
    이미지 메타데이터만 수정 (JSON 방식, Android 앱용) - 표준 소재 목록 검증
    """
    uid = get_jwt_identity()

    doc_ref = closet_ref(uid).document(image_id)
    doc = doc_ref.get()
    if not doc.exists:
        return jsonify({"success": False, "error": "Image not found"}), 404

    data = json_body()
    update_fields = {}

    if t := data.get("type"):
        update_fields["type"] = t
    if c := data.get("category"):
        update_fields["category"] = c
    if "colors" in data:
        update_fields["colors"] = (
            data["colors"] if isinstance(data["colors"], list) else []
        )
    if st := data.get("suitable_temperature"):
        update_fields["suitable_temperature"] = st

    # JSON 소재 값 검증
    if "material" in data:
        ensured = ensure_valid_material(data.get("material"))
        if ensured is None:
            return jsonify(
                {
                    "success": False,
                    "error": "유효하지 않은 소재입니다. 표준 목록 중에서 선택하세요.",
                }
            ), 400
        update_fields["material"] = ensured  # 정상일 때만 저장

    if not update_fields:
        return jsonify({"success": False, "error": "No fields to update"}), 400

    try:
        doc_ref.update(update_fields)
        return jsonify(
            {
                "success": True,
                "message": "Updated successfully",
                "id": image_id,
                "updated_fields": list(update_fields.keys()),
            }
        ), 200
    except Exception as e:
        logger.exception("Closet metadata update failed")
        return jsonify({"success": False, "error": str(e)}), 500


# 이미지 정보 수정 (FormData 기반, 웹용)
@image_bp.route("/edit_image/<image_id>", methods=["PUT"])
@jwt_required()
def edit_image(image_id):
    """이미지 정보 수정 (Form Data 방식, 웹용) - 표준 소재 목록 검증 추가"""
    uid = get_jwt_identity()

    doc_ref = closet_ref(uid).document(image_id)
    if not doc_ref.get().exists:
        return jerr("이미지가 존재하지 않습니다.", 404)

    data = request.form
    update_fields = {}
    _type = text_value(data, "type") or text_value(data, "clothing_big_type")
    _category = text_value(data, "category") or text_value(data, "clothing_type")
    if _type:
        update_fields["type"] = _type
    if _category:
        update_fields["category"] = _category
    if "suitable_temperature" in data:
        update_fields["suitable_temperature"] = data["suitable_temperature"]
    if "colors" in data:
        update_fields["colors"] = parse_colors(data["colors"])

    # FormData 소재 값 검증
    if "material" in data:
        ensured = ensure_valid_material(data.get("material"))
        if ensured is None:
            return jerr(
                f"유효하지 않은 소재입니다. 다음 중 선택해야 합니다: {', '.join(STANDARD_MATERIALS)}",
                400,
            )
        update_fields["material"] = ensured

    if not update_fields:
        return jerr("수정할 값이 없습니다.", 400)

    doc_ref.update(update_fields)
    return jsonify({"message": "수정 성공!", "updated": update_fields}), 200
