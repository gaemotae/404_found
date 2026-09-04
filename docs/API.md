# API 요약

세부 요청·응답 스키마는 각 라우트 구현을 기준으로 하며, 아래 표는 포트폴리오 검토를 위한 주요 엔드포인트 요약입니다.

## Application API (`app-api`)

### 인증 및 회원

| Method | Path | 설명 | 인증 |
| --- | --- | --- | --- |
| `POST` | `/register` | Firebase Authentication 및 Firestore 회원 등록 | - |
| `POST` | `/login` | 이메일·비밀번호 로그인 및 JWT 발급 | - |
| `POST` | `/auth/firebase/` | Firebase ID Token 검증 후 서비스 JWT 발급 | Firebase ID Token |
| `GET` | `/auth/verify_token` | JWT 유효성 확인 | JWT |
| `POST` | `/logout` | 로그아웃 이력 기록 | JWT |
| `GET` | `/user/settings` | 사용자 설정 조회 | JWT |
| `PUT` | `/user/settings` | 닉네임·비밀번호·알림·연령대 수정 | JWT |
| `POST` | `/user/profile_image` | 프로필 이미지 업로드 | JWT |

### 옷장

| Method | Path | 설명 | 인증 |
| --- | --- | --- | --- |
| `GET` | `/upload/my_closet` | 옷장 목록 조회 | JWT |
| `POST` | `/upload/analyze` | 이미지 분석만 수행 | JWT |
| `POST` | `/upload/` | 옷 이미지와 분석 결과 저장 | JWT |
| `PATCH` | `/upload/update_image/{image_id}` | 옷 메타데이터 수정 | JWT |
| `PUT` | `/upload/edit_image/{image_id}` | FormData 기반 옷 정보 수정 | JWT |
| `DELETE` | `/upload/delete_image/{image_id}` | 옷 이미지 및 데이터 삭제 | JWT |

### 추천 및 이력

| Method | Path | 설명 | 인증 |
| --- | --- | --- | --- |
| `POST` | `/api/recommend/recommendations/ai` | 날씨·옷장 기반 추천 서버 호출 및 결과 저장 | JWT |
| `POST` | `/api/recommend/recommendations/feedback` | 추천 결과에 대한 피드백 저장 | JWT |
| `POST` | `/api/recommend/recommendations/comment` | 추천 코디 설명 생성 요청 | JWT |
| `POST` | `/api/history/recommendations/same_day` | 과거 같은 날짜의 추천 조회 | JWT |
| `POST` | `/api/history/recommendations/all` | 전체 추천 이력 조회 | JWT |
| `POST` | `/api/history/recommendations/delete` | 추천 이력 삭제 | JWT |

### 커뮤니티

`/community` 아래에서 게시글·댓글·답글 CRUD, 좋아요, 공유, 사용자 검색, 팔로우·언팔로우, 팔로워·팔로잉 조회, 차단·해제 API를 제공합니다.

## Weather API (`weather-api`)

| Method | Path | 설명 |
| --- | --- | --- |
| `GET` | `/weather/weather_forecast/?city=Seoul` | 위치 좌표 조회 후 시간별·일별 날씨를 Firestore에 저장 |
| `GET` | `/weather/air_pollution/?city=Seoul` | 위치의 대기질 정보를 Firestore에 저장 |
| `GET` | `/weather/save_daily_weather/?city=Seoul` | 일별 날씨 저장 작업 실행 |

관리 명령 `python manage.py update_weather`를 사용하면 서울의 날씨와 대기질 저장 작업을 한 번에 실행할 수 있습니다.
