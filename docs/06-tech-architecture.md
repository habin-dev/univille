# 06. 기술 구조

## 1. 원칙

- **혼자서도 개발할 수 있는 구조**: 관리형 서비스를 적극 활용한다
- **웹 먼저, 앱은 같은 코드로**: 하나의 코드베이스로 웹 + iOS + Android
- **게시판은 가볍게, 섬은 예쁘게**: 게시판은 일반 웹 UI, 섬만 3D 엔진을 쓴다. 섬이 못 돌아가는 기기에서도 게시판은 반드시 써야 한다

## 2. 기술 스택

| 영역 | 선택 | 이유 |
|---|---|---|
| 프론트엔드 | **Next.js (React) + TypeScript** | 웹 표준, 생태계 |
| 3D 섬 | **Three.js + React Three Fiber + drei** | 프로토타입이 Three.js로 검증됨. React 컴포넌트로 섬·건물·캐릭터를 관리 |
| 3D 에셋 | **Blender → glTF(.glb)**, Draco/meshopt 압축 | 프로토타입의 코드 도형을 실제 모델로 교체 |
| 앱 | **Capacitor**로 웹앱을 iOS/Android로 패키징 (v1) | WebGL이 앱 안에서도 동작, 코드 하나로 출시 |
| 스타일 | Tailwind CSS | 빠른 UI 개발 |
| 백엔드 / DB | **Supabase** (PostgreSQL + Auth + Realtime + Storage) | 인증, DB, 실시간, 파일 저장 |
| 실시간 섬 (v1~) | Supabase Realtime Presence → 사용자가 늘면 **Colyseus** 게임 서버 | 다른 학생 캐릭터 위치 동기화 |
| 배치 작업 | Supabase Edge Functions + pg_cron | 활성도 점수, 학과 대항, 비동기 주민 목록 계산 |
| 이메일 인증 | 트랜잭션 메일 서비스 (예: Resend) | 학교 메일 인증 코드 |
| 분석 | 이벤트 로그 테이블 또는 PostHog | [12 문서](12-mvp-and-validation.md)의 측정 이벤트 |
| 배포 | Vercel + Supabase | 파일럿 규모는 무료~저가 요금제로 가능 |

## 3. 시스템 구조

```
┌──────────────────────────────────────┐
│  클라이언트 (Next.js, PWA)             │
│  ├─ 섬 화면 (React Three Fiber)        │
│  │    ├─ 성능 등급별 렌더링 (아래 4장)   │
│  │    └─ 섬 데이터: 레이아웃 JSON + glb  │
│  ├─ 게시판 / 리스트 모드 (React)        │
│  └─ (v1) Capacitor → iOS/Android      │
└───────────────┬──────────────────────┘
                │ HTTPS / WebSocket
┌───────────────▼──────────────────────┐
│  Supabase                             │
│  ├─ Auth (학교 메일 인증)               │
│  ├─ PostgreSQL (+ RLS)                │
│  ├─ Realtime (v1: 접속자 위치)          │
│  ├─ Storage (이미지, 3D 에셋)           │
│  └─ Edge Functions / pg_cron          │
│      ├─ 활성도 점수 (매일)               │
│      ├─ 학과 대항 정산 (매주)             │
│      ├─ 비동기 주민 목록 (10분마다)        │
│      └─ 어뷰징 탐지                     │
└──────────────────────────────────────┘
```

## 4. 성능 등급

3D는 오래된 휴대폰에서 느리거나 배터리를 많이 쓴다. 첫 실행 때 기기를 측정해서 등급을 정하고, 설정에서 바꿀 수 있게 한다.

| 등급 | 대상 | 설정 |
|---|---|---|
| 높음 | 최신 폰, PC | 그림자, 꽃·풀 전부, 꽃잎·나비 효과, 해상도 2배 |
| 보통 | 대부분의 폰 | 그림자 해상도 ↓, 꽃 절반, 효과 일부 |
| 낮음 | 오래된 폰 | 그림자 끔, 장식 최소, 해상도 1배, 주민 수 제한 |
| 리스트 | WebGL 불가 / 사용자가 선택 | 섬 없이 게시판만 |

- 섬 화면은 **처음 들어갈 때만** 에셋을 받는다. 게시판만 쓰는 사람은 3D 파일을 받지 않는다.
- 탭이 백그라운드로 가면 렌더링을 멈춘다.
- 에셋 예산 (초안): 캐릭터 1종 3천 폴리곤 이하, 섬 전체 첫 로딩 5MB 이하.

## 5. 섬 데이터 구조

학교마다 섬을 새로 코딩하지 않도록, 섬은 **데이터 + 공통 에셋**으로 만든다.

```json
{
  "school": "sungkyul",
  "colors": { "primary": "#1D2C50", "secondary": "#ADDEF8" },
  "landmark": { "asset": "landmarks/sungkyul-jaerim.glb", "pos": [0, -6.2], "scale": 1.3 },
  "buildings": [
    { "key": "plaza",   "asset": "buildings/hall-a.glb",    "pos": [-13.5, -6.5], "board": "free" },
    { "key": "library", "asset": "buildings/library-a.glb", "pos": [13.5, -6.5],  "board": "info" }
  ],
  "stairs": [0.55, 2.45, -1.95],
  "dock": { "angle": 0.55 }
}
```

- 건물 에셋은 공통으로 쓰고, **랜드마크만 학교별로** 만든다 ([09 문서](09-island-and-avatar.md)).
- 섬 모양, 나무 위치는 시드값으로 생성해서 학교마다 조금씩 다르게 한다.

## 6. 데이터 모델 (초안)

```
schools        id, name, email_domain, student_count, league, region,
               primary_color, secondary_color, island_layout(json)
animal_types   id, key(beaver/raccoon/...), name, category
colleges       id, school_id, name, animal_type_id, group_id   ← 학교별 학과 → 동물, 작은 학과 묶음
users          id, school_id, college_id, email_hash, email_verified_at, nickname,
               avatar(json), coins, show_rank(bool), quality_tier, created_at
boards         id, school_id(null=전국), type(free/info/market/club/cafe), building_key, anon_policy
posts          id, board_id, author_id, is_anonymous, show_animal(bool), title, body, status, created_at
comments       id, post_id, author_id, is_anonymous, anon_index, body, status, created_at
reactions      id, target_type, target_id, user_id, type, created_at
reports        id, target_type, target_id, reporter_id, reason, status, handled_by, handled_at
blocks         user_id, blocked_user_id
sanctions      id, user_id, level, reason, starts_at, ends_at
attendance     user_id, date
missions       id, date, user_id, mission_key, done_at
activity_events id, user_id, school_id, college_id, type, weight, valid(bool), created_at
school_daily_stats  school_id, date, dau, posts, comments, interactions, retention, new_users, score
college_weekly_stats college_id, week, bricks, score, rank
seasons        id, name, starts_at, ends_at, status
season_standings    season_id, school_id, league, cumulative_score, rank, landmark_stage
island_residents    school_id, avatar(json), refreshed_at      ← 비동기 주민 (작성자 연결 없음)
analytics_events    id, anon_user_id, school_id, name, props(json), created_at
```

- 모든 테이블은 **Row Level Security**로 "자기 학교 데이터만 쓰기" 보장
- `posts.author_id`는 다른 사용자에게 절대 내려보내지 않는다 (익명성, [13 문서](13-community-policy.md))
- `island_residents`는 아바타 모양만 저장하고 사용자 ID를 저장하지 않는다
- `activity_events`에 모든 활동을 쌓고 배치로 집계 → 점수 공식을 바꿔도 다시 계산 가능

## 7. 학교 인증

1. 학교 메일 도메인을 `schools.email_domain`에 등록
2. 인증 코드 발송 → 확인 → 학과 선택 → 학과 동물 지정 → 섬 입주
3. 메일 원문은 인증 후 해시로 바꿔 보관하는 방안을 검토 (중복 가입 방지에는 해시로 충분)
4. 재인증: 매년 1회 (졸업생 구분)
5. 학교 메일이 없는 경우 학생증 인증은 v1 이후 (수동 검토 부담)
