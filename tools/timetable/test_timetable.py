"""변환기 핵심 규칙 테스트. PDF 없이 돌아간다: python -m unittest test_timetable.py"""

import unittest
from datetime import datetime

from timetable import parse_room, parse_schedule
from today import today_card


class ScheduleTest(unittest.TestCase):
    def test_range(self):
        (m,) = parse_schedule("월1-3")
        self.assertEqual((m.day, m.weekday, m.start_period, m.end_period, m.start, m.end), ("월", 0, 1, 3, "09:00", "11:40"))

    def test_evening_periods(self):
        (m,) = parse_schedule("화10-12")
        self.assertEqual((m.start, m.end), ("17:40", "20:10"))

    def test_single_period(self):
        (m,) = parse_schedule("수2")
        self.assertEqual((m.start_period, m.end_period, m.start, m.end), (2, 2, "09:55", "10:45"))

    def test_empty_and_invalid(self):
        self.assertEqual(parse_schedule(""), [])
        self.assertEqual(parse_schedule("월20-21"), [])


class RoomTest(unittest.TestCase):
    def test_plain(self):
        r = parse_room("중201")
        self.assertEqual((r.building, r.floor, r.number, r.note), ("중생관", 2, "201", None))

    def test_note(self):
        r = parse_room("성301(컴공)")
        self.assertEqual((r.building, r.floor, r.note), ("성결관", 3, "컴공"))

    def test_basement(self):
        r = parse_room("성B101(정통)")
        self.assertEqual((r.building, r.floor, r.number, r.note), ("성결관", -1, "B101", "정통"))
        self.assertEqual(parse_room("성B01").number, "B01")

    def test_ho_suffix(self):
        r = parse_room("재507호 강의실(혁신)")
        self.assertEqual((r.building, r.floor, r.number, r.note), ("재림관", 5, "507", "강의실(혁신)"))

    def test_library_prefix_wins_over_hall(self):
        self.assertEqual(parse_room("학술301(강의공간)").building, "학술정보관")
        hall = parse_room("학401(체육관)")
        self.assertEqual((hall.building, hall.building_guessed), ("학생회관", True))

    def test_full_building_name(self):
        r = parse_room("기념관 2층238호 교수연구실")
        self.assertEqual((r.building, r.floor, r.number, r.note), ("기념관", 2, "238", "교수연구실"))

    def test_xr_room(self):
        r = parse_room("XR 1강의실(학술1층)")
        self.assertEqual((r.building, r.floor), ("학술정보관", 1))

    def test_unknown(self):
        self.assertIsNone(parse_room("온라인").building)


class TodayCardTest(unittest.TestCase):
    TT = [
        {"name": "자료구조", "professor": "A", "room": {"raw": "성301", "building": "성결관", "number": "301"},
         "meetings": [{"weekday": 1, "start_period": 1, "end_period": 3, "start": "09:00", "end": "11:40"}]},
        {"name": "웹프로그래밍", "professor": "B", "room": {"raw": "성B01", "building": "성결관", "number": "B01"},
         "meetings": [{"weekday": 1, "start_period": 7, "end_period": 9, "start": "14:40", "end": "17:20"}]},
    ]

    def test_next_class_later_today(self):
        card = today_card(self.TT, datetime(2026, 11, 24, 13, 50))  # 화요일
        self.assertEqual(len(card["today"]), 2)
        self.assertEqual((card["next"]["name"], card["next"]["status"], card["next"]["room"]), ("웹프로그래밍", "50분 뒤", "성결관 B01"))

    def test_in_progress(self):
        card = today_card(self.TT, datetime(2026, 11, 24, 10, 0))
        self.assertEqual((card["next"]["name"], card["next"]["status"]), ("자료구조", "진행 중"))

    def test_after_last_class_goes_to_next_week(self):
        card = today_card(self.TT, datetime(2026, 11, 24, 18, 0))
        self.assertEqual((card["next"]["name"], card["next"]["status"]), ("자료구조", "다음 주 화요일"))


if __name__ == "__main__":
    unittest.main()
