import firebase_admin
from firebase_admin import credentials, firestore

# ✅ Firestore 연결 (서비스 계정 키 사용)
cred = credentials.Certificate("C:/Users/ggyyu/wearther/wearther-404found-firebase-adminsdk-fbsvc-a6379fb165.json")
firebase_admin.initialize_app(cred)

# ✅ Firestore 데이터베이스 객체 생성
db = firestore.client()

# ✅ Firestore에 사용자 추가 함수
def add_user():
    doc_ref = db.collection("users").document("user123")
    doc_ref.set({
        "email": "user@example.com",
        "username": "패션러버",
        "profile_img": "https://image.url",
        "created_at": firestore.SERVER_TIMESTAMP
    })
    print("✅ 사용자 추가 완료")

add_user()
