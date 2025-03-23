import firebase_admin
from firebase_admin import credentials, firestore

# ✅ Firebase 앱이 이미 초기화되었는지 확인 후 초기화
if not firebase_admin._apps:
    cred = credentials.Certificate("C:/Users/ggyyu/wearther/wearther-404found-firebase-adminsdk-fbsvc-a6379fb165.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()