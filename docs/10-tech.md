# 10. 기술 구조

## 1. 원칙
- **혼자서도 만들 수 있는 구조**: 관리형 서비스 적극 활용
- **웹 먼저, 앱은 같은 코드로**
- **실용 기능은 가볍게, 산은 예쁘게**: 시간표·게시판은 일반 웹 UI, 산만 3D. 3D가 안 되는 기기에서도 모든 기능을 쓸 수 있어야 한다

## 2. 기술 스택

| 영역 | 선택 | 이유 |
|---|---|---|
| 프론트엔드 | **Next.js (React) + TypeScript** | 생태계, 웹 표준 |
| 3D 산 | **Three.js + React Three Fiber + drei** | 이전 프로토타입으로 검증 |
| 산 생성 | 부지 윤곽 폴리곤 → 안쪽 오프셋 등고선 → 계단식 지형 메시 (빌드 시 생성, glb로 저장) | 학교마다 손으로 만들지 않음 |
| 부지 데이터 | **OpenStreetMap** 대학 부지 폴리곤 (Overpass API로 한 번 추출) | 무료, 전국 대학 대부분 존재. ODbL 출처 표기 |
| 3D 에셋 | Blender → glTF(.glb), 압축 | 캐릭터, 랜드마크, 소품 |
| 앱 | Capacitor (v1) | 웹 코드 그대로 iOS/Android |
| 백엔드 / DB | **Supabase** (PostgreSQL + Auth + Realtime + Storage) | 인증, DB, 파일, 실시간 |
| 배치 | Supabase Edge Functions + pg_cron | 기여 집계, 안개 판정, 주간 등반대 정산 |
| 이메일 인증 | 트랜잭션 메일 서비스 | 학교 메일 인증 |
| 분석 | 이벤트 테이블 또는 PostHog | [09 문서](09-mvp-and-validation.md)의 이벤트 |
| 배포 | Vercel + Supabase | 파일럿 규모는 저비용 |

## 3. 산 생성 파이프라인

```
OSM 부지 폴리곤 ─→ 단순화 (점 개수 줄이기) ─→ 안쪽 오프셋 4~5겹 (= 고도 구역)
     ─→ 각 겹을 높이만큼 올려 계단식 지형 + 부드러운 경사 ─→ 잔디·흙 텍스처
     ─→ 구역별 장소 슬롯 자동 배치 ─→ 학교 산 데이터(JSON) + glb 저장
```

- 부지가 너무 길쭉하거나 여러 조각이면 가장 큰 조각을 쓰고, 비율을 보정한다.
- 정상 위치 = 가장 안쪽 등고선의 중심. 랜드마크를 놓는다.
- 안개는 구역별 볼류메트릭 대신 **반투명 구름 메시 + 포그**로 가볍게 표현한다.

```json
{
  "school": "sungkyul",
  "name": "성결산",
  "colors": { "primary": "#1D2C50", "secondary": "#ADDEF8" },
  "outline": "osm/way/000000",
  "zones": [
    { "id": 0, "name": "베이스캠프", "places": ["timetable", "reviews", "board", "qna", "cafeteria"] },
    { "id": 1, "name": "산길", "places": ["market", "study", "club"] },
    { "id": 4, "name": "정상", "landmark": "landmarks/sungkyul-jaerim.glb" }
  ]
}
```

## 4. 성능 등급

| 등급 | 대상 | 설정 |
|---|---|---|
| 높음 | 최신 폰, PC | 그림자, 장식 전부, 해상도 2배 |
| 보통 | 대부분의 폰 | 그림자 해상도 ↓, 장식 절반 |
| 낮음 | 오래된 폰 | 그림자 끔, 장식 최소, 주민 수 제한 |
| 리스트 | WebGL 불가 / 사용자 선택 | 3D 없이 카드와 목록만 |

- 홈의 작은 산은 **정지 화면에 가깝게** 그린다 (가벼움). 전체 화면에서만 캐릭터 조작과 애니메이션.
- 3D 에셋은 산을 처음 열 때만 받는다. 리스트 모드는 3D 파일을 받지 않는다.

## 5. 데이터 모델 (초안)

```
schools            id, name, email_domain, student_count, league, colors, mountain(json)
animal_types       id, key, name, category
colleges           id, school_id, name, animal_type_id, group_id     ← 30명 미만 학과 묶음
users              id, school_id, college_id, email_hash, verified_at, nickname,
                   avatar(json), tier, total_contribution, show_rank(bool), quality_tier

-- 1층 실용
courses            id, school_id, term, code, name, professor, schedule(json), room, source(official/user)
timetables         user_id, term, course_ids[]
reviews            id, course_id, author_id, rating, workload, exam_style, attendance, body, status
meals              id, school_id, date, place, menu, photo_url, avg_rating
academic_events    id, school_id, title, date, type

-- 2층 소통
boards             id, school_id, college_id(null=전체), type, anon_policy
posts              id, board_id, author_id, is_anonymous, show_animal, title, body, status
comments           id, post_id, author_id, anon_index, body, status
questions          id, school_id, author_id, title, body, accepted_answer_id
answers            id, question_id, author_id, body, show_badge, status
campus_reports     id, school_id, author_id, type, place_key, body, expires_at, helpful_count, wrong_count

-- 3층 연결
market_items       id, school_id, seller_id, title, price, status, buyer_id, reviewed_at

-- 4층 기여
contributions      id, user_id, school_id, college_id, action, points, ref_id, valid, created_at
school_progress    school_id, total_points, contributors, unlocked_zone, updated_at
college_weekly     college_id, week, points, members, rank
seasons            id, starts_at, ends_at
season_school      season_id, school_id, climb_score, rank
daily_goals        user_id, date, goals(json), done(json)

-- 운영
reactions, reports, blocks, sanctions, analytics_events
mountain_residents school_id, avatar(json), refreshed_at              ← 작성자 연결 없음
```

- Row Level Security로 "자기 학교 데이터만 쓰기"
- `author_id`는 다른 사용자에게 내려보내지 않는다
- `contributions`에 모든 기여를 쌓고 배치로 집계 → 점수표를 바꿔도 다시 계산 가능

## 6. 학교 인증
1. `schools.email_domain`으로 메일 인증
2. 학과 선택 → 학과 동물 지정
3. 메일은 인증 후 해시 보관 검토
4. 매년 재인증 (졸업생 구분)
