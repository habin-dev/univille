"""성결대학교 강의시간표 PDF를 과목 데이터로 바꾸는 변환기.

학사 공지 "OO학년도 O학기 강의시간표 안내"에 첨부된 시간표 PDF를 읽어
분반 단위의 레코드(과목코드, 과목명, 교수, 요일·교시·시간, 강의실·건물)를 만든다.

사용법:
    python timetable.py 시간표.pdf --term 2026-2 --out data/2026-2

출력:
    sections.json  분반 목록 (앱 과목 DB에 넣는 원본)
    sections.csv   같은 내용의 표 (엑셀로 확인용)
    report.md      건수, 건물별·학과별 통계, 해석하지 못한 값 목록
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

# 강의시간표 안내문의 교시표 (1~9교시 Ⅰ부, 10~15교시 Ⅱ부 포함)
PERIODS = {
    1: ("09:00", "09:50"), 2: ("09:55", "10:45"), 3: ("10:50", "11:40"),
    4: ("11:55", "12:45"), 5: ("12:50", "13:40"), 6: ("13:45", "14:35"),
    7: ("14:40", "15:30"), 8: ("15:35", "16:25"), 9: ("16:30", "17:20"),
    10: ("17:40", "18:30"), 11: ("18:30", "19:20"), 12: ("19:20", "20:10"),
    13: ("20:15", "21:05"), 14: ("21:05", "21:55"), 15: ("21:55", "22:45"),
}

DAYS = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}

# 강의실 표기법 (안내문): 중=중생관, 성=성결관, 기=기념관, 영=영암관, 재=재림관, 학술=학술정보관
# "학"은 안내문에 없다. 체육관·무도실이 학생회관에 있어서 학생회관으로 추정한다.
BUILDINGS = {
    "학술": ("학술정보관", False),
    "중": ("중생관", False),
    "성": ("성결관", False),
    "기": ("기념관", False),
    "영": ("영암관", False),
    "재": ("재림관", False),
    "학": ("학생회관", True),
}

KINDS = {"전선": "전공선택", "전필": "전공필수", "교선": "교양선택", "교필": "교양필수", "교직": "교직"}

SCHEDULE_RE = re.compile(r"([월화수목금토일])\s*(\d{1,2})(?:\s*-\s*(\d{1,2}))?")
ROOM_RE = re.compile(r"^(학술|중|성|기|영|재|학)\s*(B?)(\d{2,4})\s*호?\s*(.*)$")


@dataclass
class Meeting:
    day: str
    weekday: int
    start_period: int
    end_period: int
    start: str
    end: str


@dataclass
class Room:
    raw: str
    building_code: str | None = None
    building: str | None = None
    building_guessed: bool = False
    floor: int | None = None
    number: str | None = None
    note: str | None = None


@dataclass
class Section:
    term: str
    department: str
    evening: bool
    year: str
    kind_code: str
    kind: str
    course_code: str
    section: str
    name: str
    credits: str
    professor: str
    schedule_raw: str
    meetings: list[Meeting] = field(default_factory=list)
    room: Room = field(default_factory=lambda: Room(raw=""))
    general_area: str = ""
    page: int = 0

    @property
    def id(self) -> str:
        return f"{self.term}:{self.course_code}-{self.section}"


def parse_schedule(raw: str) -> list[Meeting]:
    """'월1-3' 같은 수업시간 표기를 요일·교시·시각으로 바꾼다. 해석할 수 없으면 빈 목록."""
    meetings = []
    for day, a, b in SCHEDULE_RE.findall(raw or ""):
        start, end = int(a), int(b or a)
        if start not in PERIODS or end not in PERIODS or end < start:
            continue
        meetings.append(Meeting(day, DAYS[day], start, end, PERIODS[start][0], PERIODS[end][1]))
    return meetings


def parse_room(raw: str) -> Room:
    """'중201', '성B01(정통)', '재507호 강의실(혁신)', 'XR 1강의실(학술1층)' 같은 표기를 건물·층·호실로 나눈다."""
    text = re.sub(r"\s+", " ", (raw or "")).strip()
    room = Room(raw=text)
    if not text:
        return room
    m = ROOM_RE.match(text)
    if m:
        code, basement, digits, rest = m.groups()
        name, guessed = BUILDINGS[code]
        room.building_code, room.building, room.building_guessed = code, name, guessed
        room.number = f"{basement}{digits}"
        room.floor = -1 if basement else (int(digits[:-2]) if len(digits) >= 3 else None)
        rest = rest.strip()
        if rest.startswith("(") and rest.endswith(")"):
            rest = rest[1:-1].strip()
        room.note = rest or None
        return room
    full = re.match(r"^(" + "|".join(n for n, _ in BUILDINGS.values()) + r")\s*(?:(\d+)\s*층)?\s*(\d{2,4})?\s*호?\s*(.*)$", text)
    if full and (full.group(2) or full.group(3)):  # 예: 기념관 2층238호 교수연구실
        name, fl, num, rest = full.groups()
        code = next(k for k, (n, _) in BUILDINGS.items() if n == name)
        room.building_code, room.building, room.building_guessed = code, name, BUILDINGS[code][1]
        room.number = num
        room.floor = int(fl) if fl else (int(num[:-2]) if num and len(num) >= 3 else None)
        room.note = rest.strip() or None
        return room
    if "학술" in text:  # 예: XR 1강의실(학술1층)
        room.building_code, room.building = "학술", "학술정보관"
        f = re.search(r"학술\s*(\d+)\s*층", text)
        room.floor = int(f.group(1)) if f else None
        room.note = text
    return room


def _clean(cell: str | None) -> str:
    # 셀 안 줄바꿈은 좁은 칸에서 단어가 잘린 것이라 붙여서 합친다.
    return re.sub(r"\s*\n\s*", "", cell or "").strip()


def _department_above(page, table_top: float) -> str:
    area = page.crop((0, max(0, table_top - 90), page.width, table_top))
    lines = [ln.strip() for ln in (area.extract_text() or "").split("\n") if ln.strip()]
    return lines[-1] if lines else ""


def parse_pdf(pdf_path: Path, term: str) -> list[Section]:
    import pdfplumber  # 무거운 의존성이라 실제로 PDF를 읽을 때만 불러온다

    sections: list[Section] = []
    department = ""
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            for table in page.find_tables(table_settings={"text_x_tolerance": 1.2}):
                header = _department_above(page, table.bbox[1])
                if header:
                    department = header
                for row in table.extract(x_tolerance=1.2):
                    cells = [_clean(c) for c in row]
                    if len(cells) < 10 or cells[0].startswith("학년") or not re.fullmatch(r"\d{5}", cells[2]):
                        continue
                    year, kind_code, code, sec, name, credits, prof, sched, room_raw, area = cells[:10]
                    evening = "(2부)" in department
                    dept = department.replace("(2부)", "").strip()
                    sections.append(Section(
                        term=term, department=dept, evening=evening, year=year,
                        kind_code=kind_code, kind=KINDS.get(kind_code, kind_code),
                        course_code=code, section=sec, name=name, credits=credits,
                        professor=prof, schedule_raw=sched, meetings=parse_schedule(sched),
                        room=parse_room(room_raw), general_area=area, page=page_no,
                    ))
    return sections


def to_record(s: Section) -> dict:
    d = asdict(s)
    d["id"] = s.id
    return d


def write_outputs(sections: list[Section], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    records = [to_record(s) for s in sections]
    (out_dir / "sections.json").write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")

    with (out_dir / "sections.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["id", "학과", "2부", "학년", "이수구분", "과목코드", "분반", "과목명", "학점", "교수", "수업시간",
                    "요일", "시작", "끝", "강의실", "건물", "층", "교양영역"])
        for s in sections:
            m = s.meetings[0] if s.meetings else None
            w.writerow([s.id, s.department, "Y" if s.evening else "", s.year, s.kind, s.course_code, s.section, s.name,
                        s.credits, s.professor, s.schedule_raw, m.day if m else "", m.start if m else "",
                        m.end if m else "", s.room.raw, s.room.building or "", "" if s.room.floor is None else s.room.floor,
                        s.general_area])

    (out_dir / "report.md").write_text(build_report(sections), encoding="utf-8")


def build_report(sections: list[Section]) -> str:
    term = sections[0].term if sections else "?"
    no_time = [s for s in sections if not s.meetings]
    bad_time = [s for s in sections if s.schedule_raw and not s.meetings]
    no_room = [s for s in sections if not s.room.raw]
    bad_room = [s for s in sections if s.room.raw and not s.room.building]
    by_building = Counter(s.room.building or "(없음)" for s in sections)
    by_dept = Counter(s.department for s in sections)
    by_day = Counter(m.day for s in sections for m in s.meetings)

    out = [f"# 강의시간표 변환 결과 ({term})", ""]
    out += [
        "| 항목 | 값 |", "|---|---|",
        f"| 분반 | {len(sections)} |",
        f"| 과목 (과목코드 기준) | {len({s.course_code for s in sections})} |",
        f"| 학과 (2부 제외 이름 기준) | {len(by_dept)} |",
        f"| 수업시간 해석 성공 | {len(sections) - len(no_time)} |",
        f"| 수업시간 없음 (미배정 등) | {len(no_time) - len(bad_time)} |",
        f"| 수업시간 해석 실패 | {len(bad_time)} |",
        f"| 강의실 해석 성공 | {len(sections) - len(no_room) - len(bad_room)} |",
        f"| 강의실 없음 | {len(no_room)} |",
        f"| 강의실 해석 실패 | {len(bad_room)} |",
        "",
        "## 건물별 분반 수", "", "| 건물 | 분반 |", "|---|---|",
    ]
    out += [f"| {b} | {n} |" for b, n in by_building.most_common()]
    out += ["", "## 요일별 수업 수", "", "| 요일 | 수업 |", "|---|---|"]
    out += [f"| {d} | {by_day[d]} |" for d in DAYS if by_day[d]]
    out += ["", "## 학과별 분반 수", "", "| 학과 | 분반 |", "|---|---|"]
    out += [f"| {d} | {n} |" for d, n in by_dept.most_common()]
    if bad_time or bad_room:
        out += ["", "## 해석하지 못한 값", ""]
        out += [f"- 수업시간 `{s.schedule_raw}` ({s.id} {s.name})" for s in bad_time]
        out += [f"- 강의실 `{s.room.raw}` ({s.id} {s.name})" for s in bad_room]
    guessed = sorted({s.room.building for s in sections if s.room.building_guessed})
    if guessed:
        out += ["", "## 추정한 건물", "", *[f"- {g}: 안내문 약자표에 없어 시설 위치로 추정" for g in guessed]]
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="성결대 강의시간표 PDF → 과목 데이터")
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--term", required=True, help="예: 2026-2")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    sections = parse_pdf(args.pdf, args.term)
    write_outputs(sections, args.out)
    print(f"{len(sections)}개 분반 → {args.out}")


if __name__ == "__main__":
    main()
