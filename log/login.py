# 사용자 자격 증명을 저장하는 사전
users = {
    "user1": "password1",
    "user2": "password2",
    "admin": "adminpass"
}

def get_user_credentials():
    """
    사용자로부터 사용자 ID와 비밀번호를 입력받는 함수
    """
    userId = input("사용자 ID를 입력하세요: ")
    passwd = input("비밀번호를 입력하세요: ")
    return userId, passwd

def authenticate_user(userId, passwd):
    """
    입력된 사용자 ID와 비밀번호가 유효한지 확인하는 함수
    """
    if userId in users and users[userId] == passwd:
        return True
    return False

def main():
    MAX_ATTEMPTS = 3  # 최대 시도 횟수
    attempts = 0       # 현재 시도 횟수

    while attempts < MAX_ATTEMPTS:
        userId, passwd = get_user_credentials()
        if authenticate_user(userId, passwd):
            print(f"로그인 성공! 환영합니다, {userId}님.")
            break
        else:
            attempts += 1
            remaining = MAX_ATTEMPTS - attempts
            print(f"로그인 실패! 남은 시도 횟수: {remaining}")
    else:
        print("시도 횟수가 초과되었습니다. 나중에 다시 시도해주세요.")

if __name__ == "__main__":
    main()