import datetime
import logging
import os
import time
import uuid

import requests
from firebase_admin import firestore
from flask import Blueprint, jsonify, render_template, request
from flask_jwt_extended import get_jwt_identity, jwt_required

recommendation_bp = Blueprint(
    "recommendation_bp",
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "templates"),
)


# -----------------------------
# 유틸: 위치명 정규화 (로깅용으로 유지)
# -----------------------------
def normalize_location(raw: str) -> str:
    """프론트에서 상세 위치를 보내므로, 단순하게 문자열 정리만 수행"""
    if not raw:
        return "알 수 없는 위치"
    result = raw.strip()
    return result


# -----------------------------
# 유틸: wearther-api 호출 (재시도+타임아웃+Correlation-Id 로깅)
# -----------------------------
AI_SERVICE_BASE_URL = os.getenv("WEARTHER_AI_BASE_URL", "http://localhost:6000").rstrip(
    "/"
)
WEARTHER_URL = f"{AI_SERVICE_BASE_URL}/recommend"
EXPLANATION_URL = f"{AI_SERVICE_BASE_URL}/explain"
logger = logging.getLogger(__name__)


# 외부 AI 추천 API 호출: 재시도, 타임아웃, correlation ID 적용
def call_wearther(
    user_id: str,
    weather_data: dict,
    use_feedback: bool,
    replace: dict | None = None,
    retry: int = 2,
    timeout: int = 60,
):
    corr_id = str(uuid.uuid4())
    headers = {
        "Content-Type": "application/json",
        "X-Correlation-Id": corr_id,
        "X-Client": "recommendation-api",
    }

    # 외부 AI 서버 명세에 맞춘 요청 payload
    payload = {
        "user_id": user_id,
        "weather": weather_data,  # ⬅️ 단일 객체 전달
        "use_feedback": use_feedback,
    }

    if replace:
        payload["replace"] = replace

    last_error = None

    for attempt in range(1, retry + 1):
        try:
            res = requests.post(
                WEARTHER_URL, json=payload, headers=headers, timeout=timeout
            )

            if res.status_code >= 500:
                last_error = f"5xx from wearther-api (status={res.status_code})"
                time.sleep(0.5 * attempt)
                continue

            if res.status_code >= 400:
                last_error = f"4xx from wearther-api (status={res.status_code})"
                continue

            res.raise_for_status()
            response_json = res.json()
            return response_json, corr_id

        except requests.exceptions.Timeout as e:
            last_error = f"Timeout: {e}"
            time.sleep(0.5 * attempt)

        except requests.exceptions.ConnectionError as e:
            last_error = f"Connection Error: {e}"
            time.sleep(0.5 * attempt)

        except requests.exceptions.RequestException as e:
            last_error = str(e)
            time.sleep(0.5 * attempt)

    error_msg = (
        f"wearther-api failed after {retry} attempts (corr={corr_id}): {last_error}"
    )
    raise RuntimeError(error_msg)


@recommendation_bp.route("/recommendation", methods=["GET"])
def recommendation_page():
    return render_template("recommendation.html")


# ==================================================================
# 코디 추천
# ==================================================================
@recommendation_bp.route("/recommendations/ai", methods=["POST"])
@jwt_required()
def ai_recommend():

    # 최초 추천과 사용자 코멘트 기반 재추천에 함께 사용하는 상태
    new_recommend = None
    replace_json = None
    TIMEOUT_SEC = 60

    data = request.get_json() or {}

    # =======================================================
    # 요청 데이터 파싱 및 검증
    # =======================================================
    raw_uid = data.get("user_id")
    weather_data_obj = data.get("weather")
    use_feedback_flag = data.get("use_feedback", False)

    if not raw_uid or not isinstance(raw_uid, str):
        return jsonify(
            {"error": "필수 필드 user_id가 누락되었거나 유효하지 않습니다."}
        ), 400
    if raw_uid != get_jwt_identity():
        return jsonify(
            {"error": "다른 사용자의 추천 데이터에는 접근할 수 없습니다."}
        ), 403
    uid = raw_uid
    if not isinstance(weather_data_obj, dict) or not weather_data_obj:
        return jsonify(
            {"error": "필수 필드 weather가 잘못되었습니다. 단일 객체여야 합니다."}
        ), 400

    location = "N/A"
    day_index = None

    # Firestore 사용자 확인
    db = firestore.client()
    try:
        user_doc = db.collection("users").document(uid).get()
        if not user_doc.exists:
            return jsonify({"error": "유효하지 않은 사용자"}), 403
    except Exception as e:
        return jsonify({"error": f"데이터베이스 오류: {str(e)}"}), 500

    weather_data_for_save = weather_data_obj

    # ===== 1. 기본 추천 모델 호출 (새로운 명세로 호출) =====

    try:
        ai_result, corr_id = call_wearther(
            uid, weather_data_obj, use_feedback_flag, replace=None, timeout=TIMEOUT_SEC
        )

    except RuntimeError as e:
        error_detail = str(e)
        corr_id_match = (
            error_detail.split("corr=")[-1].split(")")[0]
            if "corr=" in error_detail
            else "unknown"
        )
        return jsonify(
            {
                "error": "AI 추천 서비스가 일시적으로 사용할 수 없습니다",
                "detail": error_detail,
                "correlation_id": corr_id_match,
            }
        ), 502

    # =======================================================
    # AI 응답의 log_id를 저장 문서와 클라이언트 응답에 공통 사용
    # =======================================================
    log_id_from_ai = ai_result.get("log_id")
    now_str_fallback = datetime.datetime.now().strftime(
        "%Y-%m-%d_%H-%M-%S"
    )  # 비상용 ID

    if not log_id_from_ai:
        log_id_from_ai = now_str_fallback

    # =======================================================
    # 추천 모델 응답 파싱
    # =======================================================
    if ai_result.get("status") != "success" or "recommendation" not in ai_result:
        return jsonify({"error": "AI 추천 결과 형식이 유효하지 않습니다"}), 502

    reco_data = ai_result["recommendation"]
    ai_comment = "추천 코디에 대해 AI가 분석 중입니다..."  # 로딩 메시지

    final_client_response = {
        "recommended": {
            "top": reco_data.get("top", {}),
            "bottom": reco_data.get("bottom", {}),
            "outer": reco_data.get("outer", reco_data.get("outerwear", {})),
            "dress": reco_data.get("dress", None),
        },
        "comment": ai_comment,
        "score": reco_data.get("score", 0.0),
        "weather_code": weather_data_for_save.get("main_weather", "N/A"),
    }

    # ===== 2. Firestore에 저장 준비 (기본 추천) =====
    save_data = {
        "user_id": uid,
        "recommended": final_client_response["recommended"],
        "comment": final_client_response["comment"],
        "score": reco_data.get("score", 0.0),
        "created_at": datetime.datetime.utcnow(),
        "location": location,
        "day_index": day_index,
        "input_weather": weather_data_for_save,
        "log_id": log_id_from_ai,  # log_id도 필드에 저장 (중복이지만 유용)
    }

    # =======================================================
    # 사용자 코멘트가 있으면 교체 조건을 포함해 재추천 실행
    # =======================================================
    comment = data.get("comment", "").strip() if "comment" in data else ""
    if comment:
        try:
            # 사용자 코멘트를 외부 추천 API의 교체 조건으로 전달합니다.
            replace_json = {
                "replace": {
                    "comment_request": comment  # AI가 이 코멘트를 보고 처리하도록 전달
                }
            }
            if replace_json and isinstance(replace_json.get("replace"), dict):
                try:
                    new_reco_json, corr2 = call_wearther(
                        uid,
                        weather_data_obj,
                        use_feedback_flag,
                        replace=replace_json.get("replace"),
                        retry=2,
                        timeout=TIMEOUT_SEC,
                    )
                    if (
                        new_reco_json.get("status") == "success"
                        and "recommendation" in new_reco_json
                    ):
                        new_recommend = new_reco_json

                        # 재추천 결과를 저장 데이터에 포함
                        save_data["new_recommend"] = new_recommend["recommendation"]
                except RuntimeError as e:
                    logger.warning("Re-recommendation request failed: %s", e)

        except Exception:
            logger.exception("Recommendation feedback processing failed")

    # ===== 4. 최종 Firestore 저장 (버그 수정 반영) =====
    try:
        # 클라이언트에 반환하는 log_id와 동일한 문서 ID로 저장
        db.collection("users").document(uid).collection("recommendation").document(
            log_id_from_ai
        ).set(save_data)
    except Exception:
        logger.exception("Recommendation result could not be saved")

    # 최종 클라이언트 응답
    final_output = {
        "recommended": final_client_response["recommended"],
        "comment": final_client_response["comment"],
        "score": final_client_response["score"],
        "weather_code": final_client_response["weather_code"],
        "log_id": log_id_from_ai,
    }

    if new_recommend:
        # 재추천이 있었다면 응답에도 포함
        final_output["new_recommend"] = new_recommend.get("recommendation")

    return jsonify(final_output), 200


# ------------------------------------------------------------
# 🎯 [추가] 피드백 저장 엔드포인트
# ------------------------------------------------------------
@recommendation_bp.route("/recommendations/feedback", methods=["POST"])
@jwt_required()
def save_feedback():

    data = request.get_json() or {}

    # 필수 필드 검증
    user_id = data.get("user_id")
    log_id = data.get("log_id")
    feedback_obj = data.get("feedback")

    if not user_id or not log_id:
        return jsonify(
            {"error": "필수 필드 user_id 또는 log_id가 누락되었습니다."}
        ), 400
    if user_id != get_jwt_identity():
        return jsonify(
            {"error": "다른 사용자의 추천 데이터에는 접근할 수 없습니다."}
        ), 403

    if (
        not isinstance(feedback_obj, dict)
        or not feedback_obj
        or "text_feedback" not in feedback_obj
    ):
        return jsonify(
            {"error": "필수 필드 feedback 객체 또는 text_feedback이 누락되었습니다."}
        ), 400

    text_feedback = feedback_obj["text_feedback"].strip()

    # ===== Firestore에 피드백 업데이트 =====
    db = firestore.client()
    try:
        # 'recommendation' 컬렉션에서 log_id (문서 이름)를 사용하여 문서에 접근
        doc_ref = (
            db.collection("users")
            .document(user_id)
            .collection("recommendation")
            .document(log_id)
        )

        update_data = {
            "feedback": {
                "text_feedback": text_feedback,
                "timestamp": datetime.datetime.utcnow(),  # 피드백 시간 기록
            }
        }

        doc_ref.set(
            update_data, merge=True
        )  # merge=True로 기존 필드는 유지하고 feedback 필드만 업데이트

    except Exception as e:
        logger.exception("Recommendation feedback could not be saved")
        return jsonify({"error": f"데이터베이스 업데이트 오류: {str(e)}"}), 500

    return jsonify(
        {"status": "success", "message": "피드백이 성공적으로 저장되었습니다."}
    ), 200


# ------------------------------------------------------------
# 🎯 [추가] 코멘트 생성 전용 엔드포인트 (빠른 응답을 위해 분리)
# ------------------------------------------------------------
@recommendation_bp.route("/recommendations/comment", methods=["POST"])
@jwt_required()
def get_comment():
    """
    추천된 옷에 대한 AI 코멘트 생성
    Request: { "outfit": {...}, "weather": {...} }
    """

    data = request.get_json() or {}
    outfit_data = data.get("outfit")
    weather_data = data.get("weather")

    if not outfit_data or not weather_data:
        return jsonify({"error": "필수 필드 outfit, weather가 누락되었습니다."}), 400

    # AI 설명 API 호출
    try:
        explanation_url = EXPLANATION_URL

        explanation_payload = {"outfit": outfit_data, "weather": weather_data}

        explanation_response = requests.post(
            explanation_url, json=explanation_payload, timeout=60
        )

        if explanation_response.status_code == 200:
            try:
                explanation_result = explanation_response.json()

                if explanation_result.get("status") == "success":
                    ai_comment = explanation_result.get(
                        "explanation", "오늘의 추천 코디입니다!"
                    )

                    return jsonify({"status": "success", "comment": ai_comment}), 200
                else:
                    return jsonify(
                        {
                            "status": "error",
                            "comment": "추천 코디에 대해 AI가 분석 중입니다...",
                        }
                    ), 500

            except ValueError:
                return jsonify(
                    {
                        "status": "error",
                        "comment": "추천 코디에 대해 AI가 분석 중입니다...",
                    }
                ), 500
        else:
            return jsonify(
                {"status": "error", "comment": "추천 코디에 대해 AI가 분석 중입니다..."}
            ), 502

    except requests.exceptions.Timeout:
        return jsonify(
            {
                "status": "error",
                "comment": "추천 코디에 대해 AI가 분석 중입니다...",
                "error_detail": "timeout",
            }
        ), 504

    except requests.exceptions.ConnectionError:
        return jsonify(
            {
                "status": "error",
                "comment": "추천 코디에 대해 AI가 분석 중입니다...",
                "error_detail": "connection_error",
            }
        ), 503

    except Exception as e:
        logger.exception("Recommendation explanation request failed")
        return jsonify(
            {
                "status": "error",
                "comment": "추천 코디에 대해 AI가 분석 중입니다...",
                "error_detail": str(e),
            }
        ), 500
