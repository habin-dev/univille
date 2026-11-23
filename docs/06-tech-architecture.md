# 06. 기술 구조

## 1. 원칙

- **혼자서도 개발할 수 있는 구조**: 관리형 서비스 적극 활용
- **웹 먼저, 앱은 같은 코드로**: 하나의 코드베이스로 웹 + iOS + Android
- **게시판은 가볍게, 섬은 예쁘게**: 게시판은 일반 웹 UI, 섬만 2D 렌더링 엔진 사용

## 2. 추천 기술 스택

| 영역 | 선택 | 이유 |
|---|---|---|
| 프론트엔드 | **Next.js (React) + TypeScript** | 웹 표준, SEO, 생태계 |
| 섬 렌더링 | **PixiJS** (2D WebGL) | 아이소메트릭 맵, 스프라이트 애니메이션에 적합하고 가벼움 |
| 아바타 색상 | 스프라이트 레이어 분리 + 틴트(tint) | 동물 1종 스프라이트에 학교 색을 런타임에 입혀 아트 비용 절감 |
| 앱 | **Capacitor**로 웹앱을 iOS/Android로 패키징 | 코드 하나로 스토어 출시, 푸시 알림 지원 |
| 스타일 | Tailwind CSS | 빠른 UI 개발 |
| 백엔드 / DB | **Supabase** (PostgreSQL + Auth + Realtime + Storage) | 인증, DB, 실시간, 파일 저장을 한 번에 |
| 실시간 섬 (v1~) | Supabase Realtime Presence → 사용자 증가 시 **Colyseus** 게임 서버로 분리 | 아바타 위치 동기화 |
| 배치 작업 | Supabase Edge Functions + pg_cron | 활성도 점수 일일 계산 |
| 이메일 인증 | Resend 등 트랜잭션 메일 서비스 | 학교 메일 인증 코드 발송 |
| 배포 | Vercel (웹) + Supabase | 무료 티어로 시작 가능 |
| 아트 | 오리지널 2D 아이소메트릭 일러스트 (외주 또는 직접) | 브랜드 정체성의 핵심 |

> 대안: 앱 경험이 더 중요해지면 **React Native (Expo) + react-native-skia**로 전환을 검토. 처음부터 웹 + Capacitor가 개발 속도 면에서 유리하다.

## 3. 시스템 구조

```
┌─────────────────────────────┐
│  클라이언트 (Next.js)         │
│  ├─ 섬 화면 (PixiJS)          │
│  ├─ 게시판 화면 (React)       │
│  └─ Capacitor → iOS/Android  │
└──────────────┬──────────────┘
               │ HTTPS / WebSocket
┌──────────────▼──────────────┐
│  Supabase                    │
│  ├─ Auth (학교 이메일 인증)    │
│  ├─ PostgreSQL (+ RLS)       │
│  ├─ Realtime (접속자, 알림)    │
│  ├─ Storage (이미지)          │
│  └─ Edge Functions           │
│      ├─ 활성도 점수 계산 (매일) │
│      ├─ 어뷰징 탐지            │
│      └─ 시즌 정산              │
└─────────────────────────────┘
```

## 4. 데이터 모델 (초안)

```
schools        id, name, email_domain, student_count, league, region,
               primary_color, secondary_color, landmark_asset_key, island_layout(json)
animal_types   id, key(beaver/owl/...), name, category(공학/인문/...)
colleges       id, school_id, name, animal_type_id        ← 학교별 학부 → 동물 매핑
users          id, school_id, college_id, email_verified_at, nickname,
               avatar(json: 무늬/표정/옷/소품), coins, created_at
boards         id, school_id(null=전국), type(free/info/market/promo), building_key
posts          id, board_id, author_id, is_anonymous, title, body, status, created_at
comments       id, post_id, author_id, is_anonymous, body, status, created_at
reactions      id, target_type, target_id, user_id, type, created_at
reports        id, target_type, target_id, reporter_id, reason, status
attendance     user_id, date
activity_events id, user_id, school_id, type, weight, valid(bool), created_at   ← 점수 원천 로그
school_daily_stats  school_id, date, dau, posts, comments, interactions, retention, new_users, score
college_daily_stats college_id, date, dau, ..., score       ← 학부 대항용
seasons        id, name, starts_at, ends_at, status
season_standings    season_id, school_id, league, cumulative_score, rank, landmark_stage, island_size
items / inventories  아바타, 가구 아이템 (v1)
```

- 모든 테이블은 **Row Level Security**로 "자기 학교 데이터만 쓰기 가능" 보장
- `activity_events`에 모든 활동을 기록하고, 배치로 `school_daily_stats`를 집계 → 점수 공식을 바꿔도 재계산 가능

## 5. 학교 인증

1. 학교 이메일 도메인 목록을 `schools.email_domain`에 등록
2. 인증 코드 발송 → 확인 시 학부 선택 → 학부 동물이 지정되고 해당 학교 섬에 입주
3. 졸업생/학교 메일이 없는 경우: 학생증 사진 인증(수동 검토) 옵션 (v1)
4. 재인증 주기: 매년 1회 (졸업생 구분)
