# -*- coding: utf-8 -*-
import os
import uuid
from datetime import datetime

from firebase_admin import firestore, storage
from flask import Blueprint, current_app, jsonify, render_template, request
from flask_jwt_extended import get_jwt_identity, jwt_required

# BadRequest 임포트 추가
from werkzeug.exceptions import BadRequest
from werkzeug.utils import secure_filename

community_bp = Blueprint(
    "community_bp",
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "templates"),
)
PUBLIC_APP_URL = os.getenv("PUBLIC_APP_URL", "http://localhost:8080").rstrip("/")


# ---------- helpers ----------
def get_firestore_client():
    if current_app and hasattr(current_app, "db"):
        return current_app.db
    return firestore.client()


def users_collection():
    return get_firestore_client().collection("users")


def posts_collection():
    return get_firestore_client().collection("community_posts")


def user_ref(uid):
    return users_collection().document(uid)


def post_ref(pid):
    return posts_collection().document(pid)


def get_nickname(uid):
    d = user_ref(uid).get()
    return (d.to_dict() or {}).get("nickname", uid) if d.exists else uid


# get_user_data 헬퍼 추가
def get_user_data(uid):
    d = user_ref(uid).get()
    return d.to_dict() if d.exists else {}


def ts_of(v):
    if hasattr(v, "timestamp"):
        return v.timestamp()
    if isinstance(v, str):
        try:
            return datetime.strptime(v, "%Y-%m-%d %H:%M:%S").timestamp()
        except (OSError, TypeError, ValueError):
            return 0
    return 0


# --- 간결화를 위한 공통 유틸 ---
def jerr(msg, code):
    return jsonify({"error": msg}), code


def ok(msg, **kwargs):
    return jsonify({"message": msg, **kwargs}), 200


def now():
    return datetime.utcnow()


def json_body():
    return request.get_json(silent=True) or {}


def text_value(data, key):
    return (data.get(key) or "").strip()


def doc(ref, notfound_msg):
    d = ref.get()
    return d if d.exists else None, (jerr(notfound_msg, 404))


# --------------------------------


# ---------- pages ----------
@community_bp.route("/community", methods=["GET"])
def community_page():
    return render_template("community.html")


# ---------- posts ----------
# 게시물 작성
@community_bp.route("/community/posts", methods=["POST"])
@jwt_required()
def create_post():  # 함수 이름 변경
    uid = get_jwt_identity()

    content = None
    temperature = "N/A"
    weather = "N/A"
    image_urls = []
    closet_items = []
    reco_item = None

    # 1. Content-Type에 따라 요청 데이터 처리
    try:
        content_type = request.content_type

        if content_type and content_type.startswith("multipart/form-data"):
            content = text_value(request.form, "description")
            temperature = text_value(request.form, "temperature")
            weather = text_value(request.form, "weather")
            image_file = request.files.get("image")

            if image_file:
                try:
                    name = secure_filename(f"{uuid.uuid4()}_{image_file.filename}")
                    bucket = storage.bucket()
                    blob = bucket.blob(f"community_images/{name}")
                    blob.upload_from_file(
                        image_file, content_type=image_file.content_type
                    )
                    blob.make_public()
                    image_urls.append(blob.public_url)
                except Exception:
                    current_app.logger.warning(
                        "Community image upload failed", exc_info=True
                    )

        elif content_type and content_type.startswith("application/json"):
            data = json_body()
            if not data:
                raise BadRequest("Request body must be JSON.")

            content = text_value(data, "description")
            temperature = text_value(data, "temperature")
            weather = text_value(data, "weather")
            if text_value(data, "imageUrl"):
                image_urls.append(text_value(data, "imageUrl"))
            closet_items = data.get("closet_items", [])
            reco_item = data.get("reco_item")

        else:
            return jerr(
                "Unsupported Media Type. Use multipart/form-data or application/json.",
                415,
            )

    except BadRequest as e:
        return jerr(str(e), 400)
    except Exception:
        return jerr("게시물 데이터 처리 중 오류가 발생했습니다.", 500)

    # 2. 최종 유효성 검사
    if not content:
        return jerr("내용을 입력하세요.", 400)
    # 이미지 없어도 등록 가능하게 하려면 아래 라인 주석 처리
    # if not image_urls: return jerr("사진을 추가하세요.", 400)

    # 3. 사용자 정보를 포함해 Firestore에 저장
    user_doc_ref = user_ref(uid)
    user_doc = user_doc_ref.get()
    user_data = user_doc.to_dict() if user_doc.exists else {}
    nickname = user_data.get("nickname", uid)
    profile_image = user_data.get("profile_image")
    age_group = user_data.get("age_group")

    post_data = {
        "user_id": uid,
        "nickname": nickname,
        "profile_image": profile_image,
        "age_group": age_group,
        "content": content,
        "image_urls": image_urls,
        "closet_items": closet_items,
        "reco_item": reco_item,
        "temperature": temperature,
        "weather": weather,
        "created_at": now(),
        "likes": [],
        "likes_count": 0,
        "comment_count": 0,
        "share_count": 0,
    }

    try:
        doc_ref = posts_collection().add(post_data)
        post_id = doc_ref[1].id
        user_doc_ref.update({"post_count": firestore.Increment(1)})

        post_data["id"] = post_id
        if isinstance(post_data["created_at"], datetime):
            post_data["created_at"] = post_data["created_at"].strftime(
                "%Y-%m-%d %H:%M:%S"
            )

        return jsonify(post_data), 201
    except Exception:
        return jerr("게시물 작성 중 오류가 발생했습니다.", 500)


# 게시물 삭제
@community_bp.route("/community/posts/<post_id>", methods=["DELETE"])
@jwt_required()
def delete_post(post_id):
    uid = get_jwt_identity()
    post_ref_obj = post_ref(post_id)
    post_doc = post_ref_obj.get()

    if not post_doc.exists:
        return jerr("글이 존재하지 않습니다.", 404)

    post_data = post_doc.to_dict()
    if post_data.get("user_id") != uid:
        return jerr("본인 글만 삭제할 수 있습니다.", 403)

    try:
        post_ref_obj.delete()
        user_ref_obj = user_ref(uid)
        user_ref_obj.update({"post_count": firestore.Increment(-1)})
        return ok("삭제 완료")
    except Exception:
        return jerr("게시물 삭제 중 오류가 발생했습니다.", 500)


# 게시물 수정
@community_bp.route("/community/posts/<post_id>", methods=["PUT"])
@jwt_required()
def edit_post(post_id):
    uid = get_jwt_identity()
    data = json_body()
    if not data or "content" not in data:
        return jerr("Missing content in request body", 400)
    content = text_value(data, "content")

    post_ref_obj = post_ref(post_id)
    post_doc = post_ref_obj.get()

    if not post_doc.exists:
        return jerr("글이 존재하지 않습니다.", 404)
    if post_doc.to_dict().get("user_id") != uid:
        return jerr("본인 글만 수정할 수 있습니다.", 403)

    try:
        post_ref_obj.update({"content": content})
        return ok("수정 완료")
    except Exception:
        return jerr("게시물 수정 중 오류가 발생했습니다.", 500)


# ❌ [삭제] upload_image 함수: create_post 내부에 통합되었으므로 제거
# @community_bp.route("/community/upload_image", methods=["POST"]) ...


# ---------- comments & replies ----------
# 댓글 조회
@community_bp.route("/community/posts/<post_id>/comments", methods=["GET"])
@jwt_required(optional=True)
def get_comments(post_id):
    uid = get_jwt_identity()
    q = post_ref(post_id).collection("comments").order_by("created_at")

    comments_list = []
    for c in q.stream():
        c_dict = c.to_dict()
        likes = c_dict.get("likes", [])

        likes_count = c_dict.get("likes_count", len(likes))
        is_liked = (uid in likes) if uid else False

        created_at = c_dict.get("created_at")
        created_at_str = (
            created_at.strftime("%Y-%m-%d %H:%M:%S")
            if hasattr(created_at, "strftime")
            else str(created_at)
        )

        # 댓글 작성자 프로필 이미지 조회
        profile_image = None
        comment_user_id = c_dict.get("user_id")
        if comment_user_id:
            user_doc = user_ref(comment_user_id).get()
            if user_doc.exists:
                profile_image = user_doc.to_dict().get("profile_image")

        comments_list.append(
            {
                "id": c.id,  # id -> String 타입 확인 (프론트 Comment DTO)
                "userId": comment_user_id,
                "userName": c_dict.get("nickname"),
                "userProfileImage": profile_image,  # 프로필 이미지 포함
                "content": c_dict.get("content"),
                "timestamp": created_at_str,  # timestamp로 필드명 변경 (프론트 DTO)
                "likeCount": likes_count,
                "isLiked": is_liked,
            }
        )

    return jsonify(comments_list), 200


# 댓글 작성
@community_bp.route("/community/posts/<post_id>/comments", methods=["POST"])
@jwt_required()
def add_comment(post_id):
    uid = get_jwt_identity()
    data = json_body()  # json_body() 헬퍼 사용
    content = text_value(data, "content")  # text_value() 헬퍼 사용
    if not content:
        return jerr("댓글 내용을 입력하세요.", 400)

    try:
        doc_ref = (
            post_ref(post_id)
            .collection("comments")
            .add(
                {
                    "user_id": uid,
                    "nickname": get_nickname(uid),  # get_nickname() 사용
                    "content": content,
                    "created_at": now(),  # now() 헬퍼 사용
                    "reply_count": 0,
                    "likes": [],
                    "likes_count": 0,
                }
            )
        )
        post_ref(post_id).update({"comment_count": firestore.Increment(1)})
        return jsonify({"message": "댓글 작성 완료", "id": doc_ref[1].id}), 201
    except Exception:
        return jerr("댓글 작성 중 오류가 발생했습니다.", 500)


# 댓글 삭제
@community_bp.route(
    "/community/posts/<post_id>/comments/<comment_id>", methods=["DELETE"]
)
@jwt_required()
def delete_comment(post_id, comment_id):
    uid = get_jwt_identity()
    comment_ref = post_ref(post_id).collection("comments").document(comment_id)
    comment_doc = comment_ref.get()

    if not comment_doc.exists:
        return jerr("댓글이 존재하지 않습니다.", 404)
    if comment_doc.to_dict().get("user_id") != uid:
        return jerr("본인 댓글만 삭제할 수 있습니다.", 403)

    try:
        comment_ref.delete()
        post_ref(post_id).update({"comment_count": firestore.Increment(-1)})
        return ok("댓글 삭제 완료")
    except Exception:
        return jerr("댓글 삭제 중 오류가 발생했습니다.", 500)


# 댓글 좋아요 토글
@community_bp.route(
    "/community/posts/<post_id>/comments/<comment_id>/like", methods=["POST"]
)
@jwt_required()
def toggle_comment_like(post_id, comment_id):
    uid = get_jwt_identity()
    cr = post_ref(post_id).collection("comments").document(comment_id)
    d, err = doc(cr, "댓글이 존재하지 않습니다.")
    if not d:
        return err

    c = d.to_dict()
    likes = set(c.get("likes", []))
    liked = uid not in likes

    op = firestore.ArrayUnion([uid]) if liked else firestore.ArrayRemove([uid])

    try:
        d.reference.update(
            {"likes": op, "likes_count": firestore.Increment(1 if liked else -1)}
        )
        count = c.get("likes_count", len(likes)) + (1 if liked else -1)
        # 프론트엔드 반환 형식에 맞춤
        return jsonify(liked=liked, likes_count=max(count, 0)), 200
    except Exception:
        return jerr("댓글 좋아요 처리 중 오류가 발생했습니다.", 500)


# 답글 조회
@community_bp.route(
    "/community/posts/<post_id>/comments/<comment_id>/replies", methods=["GET"]
)
def get_replies(post_id, comment_id):
    replies_ref = (
        post_ref(post_id)
        .collection("comments")
        .document(comment_id)
        .collection("replies")
        .order_by("created_at")
    )

    replies = []
    for doc in replies_ref.stream():
        reply = doc.to_dict()
        reply["id"] = doc.id

        # 대댓글 작성자 프로필 이미지 조회
        profile_image = None
        reply_user_id = reply.get("user_id")
        if reply_user_id:
            user_doc = user_ref(reply_user_id).get()
            if user_doc.exists:
                profile_image = user_doc.to_dict().get("profile_image")
        reply["profile_image"] = profile_image

        replies.append(reply)

    return jsonify(replies), 200


# 답글 작성
@community_bp.route(
    "/community/posts/<post_id>/comments/<comment_id>/replies", methods=["POST"]
)
@jwt_required()
def add_reply(post_id, comment_id):
    uid = get_jwt_identity()
    data = json_body()  # json_body() 헬퍼 사용
    content = text_value(data, "content")  # text_value() 헬퍼 사용
    if not content:
        return jerr("대댓글 내용을 입력하세요.", 400)

    nickname = get_nickname(uid)  # get_nickname() 사용

    reply = {
        "user_id": uid,
        "nickname": nickname,
        "content": content,
        "created_at": now(),  # now() 헬퍼 사용
    }

    try:
        doc_ref = (
            post_ref(post_id)
            .collection("comments")
            .document(comment_id)
            .collection("replies")
            .add(reply)
        )

        # 부모 '댓글'의 reply_count 증가
        comment_ref = post_ref(post_id).collection("comments").document(comment_id)
        comment_ref.update({"reply_count": firestore.Increment(1)})

        return jsonify({"message": "대댓글 작성 완료", "id": doc_ref[1].id}), 201
    except Exception:
        return jerr("대댓글 작성 중 오류가 발생했습니다.", 500)


# 답글 삭제
@community_bp.route(
    "/community/posts/<post_id>/comments/<comment_id>/replies/<reply_id>",
    methods=["DELETE"],
)
@jwt_required()
def delete_reply(post_id, comment_id, reply_id):
    uid = get_jwt_identity()
    reply_ref = (
        post_ref(post_id)
        .collection("comments")
        .document(comment_id)
        .collection("replies")
        .document(reply_id)
    )

    reply_doc = reply_ref.get()

    if not reply_doc.exists:
        return jerr("대댓글이 존재하지 않습니다.", 404)
    if reply_doc.to_dict().get("user_id") != uid:
        return jerr("본인 대댓글만 삭제할 수 있습니다.", 403)

    try:
        reply_ref.delete()

        # 부모 '댓글'의 reply_count 감소
        comment_ref = post_ref(post_id).collection("comments").document(comment_id)
        comment_ref.update({"reply_count": firestore.Increment(-1)})

        return ok("대댓글 삭제 완료")
    except Exception:
        return jerr("대댓글 삭제 중 오류가 발생했습니다.", 500)


# ---------- like (for posts) ----------
# 게시물 좋아요 토글
@community_bp.route("/community/posts/<post_id>/like", methods=["POST"])
@jwt_required()
def toggle_like(post_id):
    uid = get_jwt_identity()
    post_ref_obj = post_ref(post_id)

    try:
        post_doc = post_ref_obj.get()
        if not post_doc.exists:
            return jerr("글이 존재하지 않습니다.", 404)

        post_data = post_doc.to_dict()
        likes = post_data.get("likes", [])
        current_likes_count = post_data.get("likes_count", len(likes))

        if uid in likes:
            post_ref_obj.update(
                {
                    "likes": firestore.ArrayRemove([uid]),
                    "likes_count": firestore.Increment(-1),
                }
            )
            liked = False
            new_count = current_likes_count - 1
        else:
            post_ref_obj.update(
                {
                    "likes": firestore.ArrayUnion([uid]),
                    "likes_count": firestore.Increment(1),
                }
            )
            liked = True
            new_count = current_likes_count + 1

        if new_count < 0:
            new_count = 0

        # 프론트엔드 반환 형식 유지
        return jsonify(liked=liked, likes_count=new_count), 200

    except Exception:
        return jerr("좋아요 처리 중 오류가 발생했습니다.", 500)


# ---------- feed ----------
# 커뮤니티 피드 조회
@community_bp.route("/community/posts", methods=["GET"])
@jwt_required(optional=True)
def get_posts():
    uid = get_jwt_identity()
    user_age_group = None
    blocked_ids = set()
    following_ids = set()  # friend_ids -> following_ids로 명확히 변경

    # --- 사용자 정보와 팔로우 목록 로드 ---
    if uid:
        user_doc_ref = user_ref(uid)
        user_doc = user_doc_ref.get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            user_age_group = user_data.get("age_group")
            blocked_ref = user_doc_ref.collection("blocked_users")
            blocked_ids = {doc.id for doc in blocked_ref.stream()}
            following_ref = user_doc_ref.collection("following")
            following_ids = {doc.id for doc in following_ref.stream()}
    # --- 사용자 정보 로드 끝 ---

    posts_ref = posts_collection().order_by(
        "created_at", direction=firestore.Query.DESCENDING
    )
    all_posts = []
    user_profiles_cache = {}

    # --- 게시물 데이터 가공 ---
    for doc in posts_ref.stream():
        post = doc.to_dict()
        post_id = doc.id
        post["id"] = post_id

        if uid and post.get("user_id") in blocked_ids:
            continue

        # --- 캐시를 사용한 사용자 프로필 조인 ---
        post_user_id = post.get("user_id")
        if post_user_id:
            if post_user_id not in user_profiles_cache:
                try:
                    user_doc = user_ref(post_user_id).get()
                    if user_doc.exists:
                        user_data = user_doc.to_dict()
                        user_profiles_cache[post_user_id] = {
                            "nickname": user_data.get("nickname", post_user_id),
                            "profile_image": user_data.get("profile_image"),
                            "age_group": user_data.get("age_group"),
                        }
                    else:
                        user_profiles_cache[post_user_id] = {
                            "nickname": post.get("nickname", post_user_id),
                            "profile_image": post.get("profile_image"),
                            "age_group": post.get("age_group"),
                        }
                except Exception:
                    user_profiles_cache[post_user_id] = {
                        "nickname": post.get("nickname", post_user_id),
                        "profile_image": post.get("profile_image"),
                        "age_group": post.get("age_group"),
                    }

            post["nickname"] = user_profiles_cache[post_user_id]["nickname"]
            post["profile_image"] = user_profiles_cache[post_user_id]["profile_image"]
            # 연령대 기반 정렬을 위한 age_group 포함
            post["age_group"] = user_profiles_cache[post_user_id].get("age_group")
        # --- 사용자 프로필 조인 끝 ---

        # --- 파생 필드 계산 및 형식 변환 ---
        likes = post.get("likes", [])
        post["likes_count"] = post.get("likes_count", len(likes))
        post["liked_by_me"] = uid in likes if uid else False
        post["comment_count"] = post.get("comment_count", 0)
        post["share_count"] = post.get("share_count", 0)

        # 저장된 이미지 URL 유지
        post["image_urls"] = post.get("image_urls", [])

        # 날씨 메타데이터 기본값 적용
        post["temperature"] = post.get("temperature", "N/A")
        post["weather"] = post.get("weather", "N/A")

        # 날짜 형식 변환 및 정렬용 타임스탬프 계산
        created_at = post.get("created_at")
        post_timestamp = 0
        if isinstance(created_at, datetime):
            post["created_at"] = created_at.strftime("%Y-%m-%d %H:%M:%S")
            try:
                post_timestamp = created_at.timestamp()
            except (OSError, TypeError, ValueError):
                post_timestamp = 0
        elif isinstance(created_at, str):
            try:
                dt_obj = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
                post_timestamp = dt_obj.timestamp()
            except (OSError, TypeError, ValueError):
                post_timestamp = 0

        post["_ts"] = post_timestamp  # 정렬용 타임스탬프
        # --- 필드 계산 및 형식 변환 끝 ---

        all_posts.append(post)
    # --- 게시물 순회 끝 ---

    # --- 팔로우 및 연령대를 반영한 정렬 ---
    priority_posts = []
    same_age_posts = []
    diff_age_posts = []

    for post in all_posts:
        # 본인과 팔로우한 사용자의 게시물을 우선 정렬
        if uid and (post.get("user_id") == uid or post.get("user_id") in following_ids):
            priority_posts.append(post)
        elif user_age_group and post.get("age_group") == user_age_group:
            same_age_posts.append(post)
        else:
            diff_age_posts.append(post)

    priority_posts.sort(key=lambda p: -p.get("_ts", 0))
    same_age_posts.sort(key=lambda p: -p.get("_ts", 0))
    diff_age_posts.sort(key=lambda p: -p.get("_ts", 0))

    result_posts = priority_posts + same_age_posts + diff_age_posts
    # --- 정렬 로직 끝 ---

    return jsonify(result_posts), 200  # 최종 가공된 post 리스트를 반환


# ---------- profile ----------
# 사용자 프로필 조회
@community_bp.route("/community/profile/<user_id>", methods=["GET"])
@jwt_required(optional=True)
def profile_page(user_id):
    u = user_ref(user_id).get()
    if not u.exists:
        return jerr("사용자를 찾을 수 없습니다.", 404)

    user_data = u.to_dict() or {}

    # 팔로워·팔로잉 수 조회
    follower_count = user_data.get("follower_count", 0)
    following_count = user_data.get("following_count", 0)

    cur = get_jwt_identity()
    is_following = False
    if cur and cur != user_id:
        is_following = (
            user_ref(cur).collection("following").document(user_id).get().exists
        )

    # 실제 게시물 수 계산
    user_posts_query = (
        posts_collection()
        .where("user_id", "==", user_id)
        .order_by("created_at", direction=firestore.Query.DESCENDING)
    )

    posts_list = []
    actual_post_count = 0

    for d in user_posts_query.stream():
        actual_post_count += 1

        # 화면에 표시할 게시물은 최대 10개만
        if len(posts_list) < 10:
            p_raw = d.to_dict()

            created_at = p_raw.get("created_at")
            created_at_str = (
                created_at.strftime("%Y-%m-%d %H:%M:%S")
                if hasattr(created_at, "strftime")
                else str(created_at)
            )

            posts_list.append(
                {
                    "id": d.id,
                    "user_id": p_raw.get("user_id"),
                    "nickname": p_raw.get("nickname"),
                    "profile_image": user_data.get("profile_image"),
                    "created_at": created_at_str,
                    "content": p_raw.get("content"),
                    "image_urls": p_raw.get("image_urls", []),
                    "temperature": p_raw.get("temperature", "N/A"),
                    "weather": p_raw.get("weather", "N/A"),
                    "likes_count": p_raw.get("likes_count", 0),
                    "comment_count": p_raw.get("comment_count", 0),
                    "liked_by_me": (cur in p_raw.get("likes", [])) if cur else False,
                }
            )

    # 저장된 post_count와 실제 개수가 다르면 동기화
    stored_post_count = user_data.get("post_count", 0)
    if stored_post_count != actual_post_count:
        try:
            user_ref(user_id).update({"post_count": actual_post_count})
        except Exception:
            current_app.logger.warning(
                "Post count synchronization failed", exc_info=True
            )

    profile_json = {
        "userId": user_id,
        "userName": user_data.get("nickname"),
        "userEmail": user_data.get("email"),
        "userProfileImage": user_data.get("profile_image"),
        "bio": user_data.get("bio", ""),
        "followerCount": follower_count,
        "followingCount": following_count,
        "postCount": actual_post_count,
        "isFollowing": is_following,
        "posts": posts_list,
    }

    return jsonify(profile_json), 200


# ---------- share ----------
@community_bp.route("/community/posts/<post_id>/share", methods=["POST"])
@jwt_required()
def share_post(post_id):
    uid = get_jwt_identity()
    post_ref_obj = post_ref(post_id)

    try:
        # 게시물 존재 확인
        post_doc = post_ref_obj.get()
        if not post_doc.exists:
            return jerr("글이 존재하지 않습니다.", 404)

        # 현재 공유 수 조회
        post_data = post_doc.to_dict()
        current_count = post_data.get("share_count", 0)

        # 공유 수와 공유 사용자 갱신
        post_ref_obj.update(
            {
                "share_count": firestore.Increment(1),
                "shared_by": firestore.ArrayUnion([uid]),
            }
        )

        new_share_count = current_count + 1
        post_url = f"{PUBLIC_APP_URL}/community/posts/{post_id}"
        return jsonify(
            message="공유 완료", share_count=new_share_count, url=post_url
        ), 200

    except Exception:
        current_app.logger.exception("Post sharing failed")
        return jerr("공유 처리 중 오류가 발생했습니다.", 500)


# ---------- search/block/follow/unfollow/list ----------
# 닉네임 접두어 검색과 팔로우 상태 조회
@community_bp.route("/community/search_friend", methods=["GET"])  # URL 유지
@jwt_required(optional=True)
def search_friend():  # 함수 이름 유지
    keyword = text_value(request.args, "nickname")
    if not keyword:
        return jerr("닉네임을 입력하세요.", 400)

    q = (
        users_collection()
        .where("nickname", ">=", keyword)
        .where("nickname", "<", keyword + "\uf8ff")
        .limit(20)
    )

    results = []
    cur_uid = get_jwt_identity()

    for d in q.stream():
        user_data = d.to_dict()
        user_id = d.id

        if cur_uid and user_id == cur_uid:
            continue

        is_following = False
        if cur_uid:
            is_following = (
                user_ref(cur_uid).collection("following").document(user_id).get().exists
            )

        # 프론트 User DTO 구조에 맞춤 (CamelCase)
        results.append(
            {
                "userId": user_id,
                "userName": user_data.get("nickname", user_id),
                "profileImage": user_data.get("profile_image"),  # profileImage로 변경
                "bio": user_data.get("bio", ""),
                "isFollowing": is_following,
            }
        )

    return jsonify(results), 200  # 리스트 직접 반환


# ❌ [삭제] 기존 친구 관련 API (add_friend_by_nickname, delete_friend_by_nickname) 삭제


# 팔로우 시스템 API
@community_bp.route("/community/users/<target_id>/follow", methods=["POST"])
@jwt_required()
def follow_user(target_id):
    uid = get_jwt_identity()
    if uid == target_id:
        return jerr("본인을 팔로우할 수 없습니다.", 400)

    if not user_ref(target_id).get().exists:
        return jerr("대상을 찾을 수 없습니다.", 404)

    following_ref = user_ref(uid).collection("following").document(target_id)
    if following_ref.get().exists:
        return jerr("이미 팔로우 중입니다.", 400)

    try:
        db_client = get_firestore_client()

        @firestore.transactional
        def run_transaction(transaction):
            transaction.set(following_ref, {"followed_at": now()})
            transaction.update(
                user_ref(uid), {"following_count": firestore.Increment(1)}
            )

            follower_ref = user_ref(target_id).collection("followers").document(uid)
            transaction.set(follower_ref, {"follower_at": now()})
            transaction.update(
                user_ref(target_id), {"follower_count": firestore.Increment(1)}
            )

            return ok("팔로우 완료")

        return db_client.transaction(run_transaction)  # 트랜잭션 실행 방식 수정

    except Exception:
        return jerr("팔로우 중 오류가 발생했습니다.", 500)


@community_bp.route("/community/users/<target_id>/unfollow", methods=["DELETE"])
@jwt_required()
def unfollow_user(target_id):
    uid = get_jwt_identity()
    if uid == target_id:
        return jerr("본인을 언팔로우할 수 없습니다.", 400)

    following_ref = user_ref(uid).collection("following").document(target_id)
    if not following_ref.get().exists:
        return jerr("팔로우 중이 아닙니다.", 400)

    try:
        db_client = get_firestore_client()

        @firestore.transactional
        def run_transaction(transaction):
            transaction.delete(following_ref)
            transaction.update(
                user_ref(uid), {"following_count": firestore.Increment(-1)}
            )

            follower_ref = user_ref(target_id).collection("followers").document(uid)
            transaction.delete(follower_ref)
            transaction.update(
                user_ref(target_id), {"follower_count": firestore.Increment(-1)}
            )

            return ok("언팔로우 완료")

        return db_client.transaction(run_transaction)  # 트랜잭션 실행 방식 수정

    except Exception:
        return jerr("언팔로우 중 오류가 발생했습니다.", 500)


@community_bp.route("/community/users/<user_id>/following", methods=["GET"])
@jwt_required(optional=True)
def get_following(user_id):
    cur_uid = get_jwt_identity()
    q = user_ref(user_id).collection("following").stream()

    following_list = []
    for d in q:
        target_id = d.id
        u = get_user_data(target_id)  # get_user_data 헬퍼 사용
        if not u:
            continue  # 사용자 데이터 없으면 스킵

        is_following_by_me = False
        if cur_uid and cur_uid != target_id:
            is_following_by_me = (
                user_ref(cur_uid)
                .collection("following")
                .document(target_id)
                .get()
                .exists
            )

        # 프론트 User DTO 매핑
        following_list.append(
            {
                "userId": target_id,
                "userName": u.get("nickname", target_id),
                "profileImage": u.get("profile_image"),  # profileImage
                "bio": u.get("bio", ""),
                "isFollowing": is_following_by_me,
            }
        )

    return jsonify(following_list), 200  # 리스트 직접 반환


@community_bp.route("/community/users/<user_id>/followers", methods=["GET"])
@jwt_required(optional=True)
def get_followers(user_id):
    cur_uid = get_jwt_identity()
    q = user_ref(user_id).collection("followers").stream()

    followers_list = []
    for d in q:
        follower_id = d.id
        u = get_user_data(follower_id)  # get_user_data 헬퍼 사용
        if not u:
            continue

        is_following_by_me = False
        if cur_uid and cur_uid != follower_id:
            is_following_by_me = (
                user_ref(cur_uid)
                .collection("following")
                .document(follower_id)
                .get()
                .exists
            )

        # 프론트 User DTO 매핑
        followers_list.append(
            {
                "userId": follower_id,
                "userName": u.get("nickname", follower_id),
                "profileImage": u.get("profile_image"),  # profileImage
                "bio": u.get("bio", ""),
                "isFollowing": is_following_by_me,
            }
        )

    return jsonify(followers_list), 200  # 리스트 직접 반환


# 사용자 차단 및 해제
@community_bp.route("/community/block_user", methods=["POST"])
@jwt_required()
def block_user():
    uid = get_jwt_identity()
    data = json_body()  # json_body() 헬퍼 사용
    target = text_value(data, "user_id")  # text_value() 헬퍼 사용

    if not target:
        return jerr("차단할 사용자 ID가 필요합니다.", 400)
    if uid == target:
        return jerr("본인 계정은 차단할 수 없습니다.", 400)

    block_ref = user_ref(uid).collection("blocked_users").document(target)
    block_ref.set({"blocked_at": now()})  # now() 헬퍼 사용

    return ok("계정 차단 완료")


@community_bp.route("/community/unblock_user", methods=["POST"])
@jwt_required()
def unblock_user():
    uid = get_jwt_identity()
    data = json_body()  # json_body() 헬퍼 사용
    target = text_value(data, "user_id")  # text_value() 헬퍼 사용

    if not target:
        return jerr("차단 해제할 사용자 ID가 필요합니다.", 400)

    block_ref = user_ref(uid).collection("blocked_users").document(target)
    # 문서 존재 여부 확인 없이 삭제 시도 (멱등성)
    try:
        block_ref.delete()
    except Exception:
        current_app.logger.warning("Blocked-user record deletion failed", exc_info=True)
        # 이미 삭제되었거나 없는 경우에도 성공으로 간주할 수 있음
        # return jerr("차단 해제 중 오류 발생", 500)

    return ok("계정 차단 해제 완료")  # 메시지 통일
