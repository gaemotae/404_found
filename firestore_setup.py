import firebase_admin
from firebase_admin import credentials, firestore

# ✅ Firestore 연결 설정
if not firebase_admin._apps:
    cred = credentials.Certificate("C:/Users/ggyyu/wearther/wearther-404found-firebase-adminsdk-fbsvc-a6379fb165.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()
print("✅ Firestore 연결 성공")

# ✅ 기본 데이터 추가 함수 정의
def create_collections():
    # ✅ 1. outfits 컬렉션 (사용자가 직접 조합한 코디)
    outfit_ref = db.collection("outfits").document("outfit123")
    outfit_ref.set({
        "user_id": "user123",
        "items": ["jacket_001", "jeans_002", "shoes_003"],
        "weather_condition": "rainy",
        "createdAt": firestore.SERVER_TIMESTAMP
    })

    # ✅ 2. weather_logs 컬렉션 (사용자의 지역 날씨 기록)
    weather_log_ref = db.collection("weather_logs").document("log001")
    weather_log_ref.set({
        "user_id": "user123",
        "location": "Seoul",
        "temperature": 12,
        "humidity": 80,
        "condition": "cloudy",
        "createdAt": firestore.SERVER_TIMESTAMP
    })

    # ✅ 3. community 컬렉션 (사용자 게시글)
    community_ref = db.collection("community").document("post001")
    community_ref.set({
        "user_id": "user123",
        "image_url": "https://image.url",
        "caption": "오늘의 코디!",
        "likes": 0,
        "comments": [],
        "createdAt": firestore.SERVER_TIMESTAMP
    })

    # ✅ 4. favorites 컬렉션 (즐겨찾기 스타일)
    favorites_ref = db.collection("favorites").document("fav001")
    favorites_ref.set({
        "user_id": "user123",
        "outfit_id": "outfit123",
        "createdAt": firestore.SERVER_TIMESTAMP
    })

    print("✅ Firestore 컬렉션 및 초기 데이터 생성 완료!")

# ✅ Firestore 컬렉션 생성 실행
create_collections()
