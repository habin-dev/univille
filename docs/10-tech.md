# 10. 기술 구조

## 1. 원칙
- **혼자서도 만들 수 있는 구조**: 관리형 서비스 적극 활용
- **웹 먼저, 앱은 같은 코드로**
- **실용 기능은 가볍게, 캠퍼스는 예쁘게**: 시간표·게시판은 일반 웹 UI, 캠퍼스만 3D. 3D가 안 되는 기기에서도 모든 기능을 쓸 수 있어야 한다

## 2. 기술 스택

| 영역 | 선택 | 이유 |
|---|---|---|
| 프론트엔드 | **Next.js (React) + TypeScript** | 생태계, 웹 표준 |
| 3D 캠퍼스 | **Three.js + React Three Fiber + drei** | 이전 프로토타입으로 검증 |
| 캠퍼스 생성 | OSM 부지·건물 데이터 → 귀여운 로우폴리 건물 자동 생성 (빌드 시, glb로 저장) | 학교마다 손으로 만들지 않음 |
| 지도 데이터 | **OpenStreetMap** (Overpass API로 학교별 한 번 추출) | 무료, ODbL 출처 표기 |
| 3D 에셋 | Blender → glTF(.glb), 압축 | 캐릭터, 랜드마크, 소품, 공사 장비 |
| 앱 | Capacitor (v1) | 웹 코드 그대로 iOS/Android |
| 백엔드 / DB | **Supabase** (PostgreSQL + Auth + Realtime + Storage) | 인증, DB, 파일, 실시간 |
| 배치 | Supabase Edge Functions + pg_cron | 벽돌 집계, 완공 판정, 주간 학과 정산 |
| 이메일 인증 | 트랜잭션 메일 서비스 | 학교 메일 인증 |
| 분석 | 이벤트 테이블 또는 PostHog | [09](09-mvp-and-validation.md)의 이벤트 |
| 배포 | Vercel + Supabase | 파일럿 규모는 저비용 |

## 3. 캠퍼스 생성 파이프라인

```
OSM 부지 폴리곤 + 건물 폴리곤 (모양, 층수 태그)
   ─→ 부지 단순화, 3D 땅 (잔디, 길, 광장)
   ─→ 건물마다: 바닥 모양 단순화 → 모서리 둥글게 → 높이 = 층수 × 귀여운 비율 (실제보다 낮고 통통하게)
              → 외벽 스타일 프리셋 (붉은 벽돌 / 흰 외벽 / 유리 / 석조) + 지붕 프리셋 + 창문 패턴
   ─→ 역할 배정 (도서관, 학생식당…) → 간판·소품 추가
   ─→ 랜드마크만 직접 모델링한 glb로 교체
   ─→ 학교 캠퍼스 데이터(JSON) + glb 저장
```

- OSM 데이터 품질은 학교마다 다르다. 건물이 빠졌거나 층수가 없으면 운영 도구에서 보완한다.
- OSM에 없는 건물(예: 분리한 학생식당)은 `near`로 위치만 지정하고 운영 도구에서 배치한다.
- 공사 단계 표현: 완성 건물 모델을 **아래부터 잘라서 보여주는 방식**(클리핑) + 비계·크레인 소품. 단계마다 모델을 따로 만들 필요가 없다.

```json
{
  "school": "sungkyul",
  "name": "성결 캠퍼스",
  "colors": { "primary": "#1D2C50", "secondary": "#ADDEF8" },
  "outline": "osm/way/000000",
  "buildings": [
    { "osm": "way/000001", "name": "학술정보관", "role": "library", "size": "large", "style": "white" },
    { "osm": "way/000002", "name": "중생관", "role": "lecture", "size": "medium", "style": "brick" },
    { "osm": null, "name": "학생식당", "role": "cafeteria", "size": "small", "near": "중생관" },
    { "osm": "way/000004", "name": "학생 기숙사", "realName": "신유관", "role": "dorm", "size": "medium" },
    { "osm": "way/000003", "name": "재림관", "role": "landmark", "model": "landmarks/sungkyul-jaerim.glb" }
  ],
  "tentArea": { "near": "main-gate" },
  "deptStreet": { "area": "..." }
}
```

## 4. 성능 등급

| 등급 | 대상 | 설정 |
|---|---|---|
| 높음 | 최신 폰, PC | 그림자, 장식 전부, 해상도 2배 |
| 보통 | 대부분의 폰 | 그림자 해상도 ↓, 장식 절반 |
| 낮음 | 오래된 폰 | 그림자 끔, 장식 최소, 주민 수 제한 |
| 리스트 | WebGL 불가 / 사용자 선택 | 3D 없이 카드와 목록만 |

- 홈의 작은 캠퍼스는 **정지 화면에 가깝게** 그린다. 전체 화면에서만 캐릭터 조작과 애니메이션.
- 3D 에셋은 캠퍼스를 처음 열 때만 받는다. 리스트 모드는 3D 파일을 받지 않는다.

## 5. 데이터 모델 (초안)

```
schools            id, name, email_domain, student_count, league, colors, campus(json)
animal_types       id, key, name, category
colleges           id, school_id, name, animal_type_id, group_id     ← 30명 미만 학과 묶음
users              id, school_id, college_id, email_hash, verified_at, nickname,
                   avatar(json), tier, total_bricks, show_name(bool), quality_tier

-- 1층 실용
courses            id, school_id, term, code, name, professor, schedule(json), room, source(official/user)
timetables         user_id, term, course_ids[]
reviews            id, course_id, author_id, rating, workload, exam_style, attendance, body, status
meals              id, school_id, date, place, menu, photo_url, avg_rating
academic_events    id, school_id, title, date, type

-- 2층 소통
boards             id, school_id, college_id(null=전체), type, building_role, anon_policy
posts              id, board_id, author_id, is_anonymous, show_animal, title, body, status
comments           id, post_id, author_id, anon_index, body, status
questions          id, school_id, author_id, title, body, accepted_answer_id
answers            id, question_id, author_id, body, show_badge, status
campus_reports     id, school_id, author_id, type, building_id, body, expires_at, helpful_count, wrong_count

-- 3층 연결
market_items       id, school_id, seller_id, title, price, status, buyer_id, reviewed_at

-- 4층 벽돌·건물
bricks             id, user_id, school_id, college_id, building_id, action, amount, ref_id, valid, created_at
buildings          id, school_id, role, name, size, required_bricks, required_builders,
                   bricks, builders, stage, completed_at
dept_houses        college_group_id, bricks, builders, stage, completed_at
college_weekly     college_group_id, week, bricks, members, rank
seasons            id, starts_at, ends_at
season_school      season_id, school_id, build_score, rank
daily_goals        user_id, date, goals(json), done(json)
nameplates         building_id, user_id                               ← 공개 동의한 사람만

-- 운영
reactions, reports, blocks, sanctions, analytics_events
campus_residents   school_id, avatar(json), refreshed_at              ← 작성자 연결 없음
```

- Row Level Security로 "자기 학교 데이터만 쓰기"
- `author_id`는 다른 사용자에게 내려보내지 않는다
- `bricks`에 모든 기여를 쌓고 배치로 집계 → 점수표를 바꿔도 다시 계산 가능

## 6. 학교 인증
1. `schools.email_domain`으로 메일 인증
2. 학과 선택 → 학과 동물 지정
3. 메일은 인증 후 해시 보관 검토
4. 매년 재인증 (졸업생 구분)
