"""시간표 데이터로 홈 화면의 "오늘 수업 카드"를 만든다.

사용법 (예시 학생의 시간표를 자동으로 골라서 보여줌):
    python today.py data/2026-2/sections.json --dept 컴퓨터공학과 --year 2 --at "2026-11-24 13:50"

--at 을 빼면 지금 시각 기준.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

DAY_NAMES = "월화수목금토일"


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def pick_sample_timetable(sections: list[dict], dept: str, year: str) -> list[dict]:
    """학과·학년의 전공 과목을 과목당 한 분반씩, 시간이 겹치지 않게 골라 예시 시간표를 만든다."""
    chosen, taken, seen = [], set(), set()
    for s in sections:
        if s["department"] != dept or s["year"] != year or s["evening"] or not s["meetings"]:
            continue
        if s["course_code"] in seen:
            continue
        slots = {(m["weekday"], p) for m in s["meetings"] for p in range(m["start_period"], m["end_period"] + 1)}
        if slots & taken:
            continue
        chosen.append(s)
        taken |= slots
        seen.add(s["course_code"])
    return chosen


def room_label(room: dict) -> str:
    if not room.get("building"):
        return room.get("raw") or "강의실 미정"
    num = room.get("number") or ""
    return f"{room['building']} {num}".strip()


def today_card(timetable: list[dict], now: datetime) -> dict:
    """오늘 수업 목록과 다음 수업(지금 진행 중이면 그 수업)을 돌려준다."""
    wd, cur = now.weekday(), now.hour * 60 + now.minute
    todays = sorted(
        ({"name": s["name"], "start": m["start"], "end": m["end"], "period": f"{m['start_period']}교시",
          "room": room_label(s["room"]), "professor": s["professor"]}
         for s in timetable for m in s["meetings"] if m["weekday"] == wd),
        key=lambda c: c["start"],
    )
    nxt = None
    for c in todays:
        if _minutes(c["end"]) > cur:
            started = _minutes(c["start"]) <= cur
            nxt = dict(c, status="진행 중" if started else f"{_minutes(c['start']) - cur}분 뒤")
            break
    if nxt is None:  # 오늘 수업이 끝났으면 다음 수업일의 첫 수업
        for add in range(1, 8):
            d = (wd + add) % 7
            day = sorted(((s, m) for s in timetable for m in s["meetings"] if m["weekday"] == d), key=lambda x: x[1]["start"])
            if day:
                s, m = day[0]
                nxt = {"name": s["name"], "start": m["start"], "end": m["end"], "period": f"{m['start_period']}교시",
                       "room": room_label(s["room"]), "professor": s["professor"],
                       "status": "내일" if add == 1 else (f"다음 주 {DAY_NAMES[d]}요일" if add == 7 else f"{DAY_NAMES[d]}요일")}
                break
    return {"date": now.strftime("%Y-%m-%d"), "weekday": DAY_NAMES[wd], "today": todays, "next": nxt}


def week_grid(timetable: list[dict]) -> str:
    rows = []
    for d in range(5):
        items = sorted(((m["start"], s["name"], room_label(s["room"])) for s in timetable for m in s["meetings"] if m["weekday"] == d))
        rows.append(f"{DAY_NAMES[d]} | " + (" · ".join(f"{t} {n} ({r})" for t, n, r in items) or "-"))
    return "\n".join(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sections", type=Path)
    ap.add_argument("--dept", required=True)
    ap.add_argument("--year", required=True)
    ap.add_argument("--at", help='예: "2026-11-24 13:50"')
    args = ap.parse_args()
    sections = json.loads(args.sections.read_text(encoding="utf-8"))
    tt = pick_sample_timetable(sections, args.dept, args.year)
    now = datetime.strptime(args.at, "%Y-%m-%d %H:%M") if args.at else datetime.now()
    print(f"[예시 시간표] {args.dept} {args.year}학년 전공 {len(tt)}과목\n")
    print(week_grid(tt))
    card = today_card(tt, now)
    print(f"\n[오늘 수업 카드] {card['date']} ({card['weekday']}) {now:%H:%M} 기준")
    print(f"오늘 수업 {len(card['today'])}개")
    if card["next"]:
        n = card["next"]
        print(f"다음 수업 · {n['status']}: {n['period']} {n['start']} {n['name']} · {n['room']}")


if __name__ == "__main__":
    main()
