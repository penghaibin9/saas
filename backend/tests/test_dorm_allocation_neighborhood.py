from types import SimpleNamespace as Row

from app.services.dorm_allocation_neighborhood import AllocationNeighborhood


def test_class_continues_on_same_floor_after_room_fills():
    index = AllocationNeighborhood()
    student = Row(class_id=1, major_id=2, college_id=3)
    building = Row(id=10)
    index.add(student, Row(id=101, floor_no=2), building)
    rules = {"sameClass": True, "sameMajor": True, "sameCollege": True}
    same_floor = index.score(student, Row(id=102, floor_no=2), building, rules)
    other_floor = index.score(student, Row(id=201, floor_no=3), building, rules)
    other_building = index.score(student, Row(id=301, floor_no=2), Row(id=20), rules)
    assert same_floor > other_floor > other_building


def test_same_class_outweighs_other_class_roommates_and_can_be_disabled():
    index = AllocationNeighborhood()
    student = Row(class_id=1, major_id=2, college_id=3)
    other = Row(class_id=2, major_id=2, college_id=3)
    building = Row(id=10)
    adjacent = Row(id=102, floor_no=1)
    distant = Row(id=201, floor_no=2)
    index.add(student, Row(id=101, floor_no=1), building)
    for _ in range(5):
        index.add(other, distant, building)
    rules = {"sameClass": True, "sameMajor": True}
    assert index.score(student, adjacent, building, rules) > index.score(student, distant, building, rules)
    rules["sameClass"] = False
    assert index.score(student, adjacent, building, rules) < index.score(student, distant, building, rules)


def test_missing_class_is_not_treated_as_a_shared_class():
    index = AllocationNeighborhood()
    student = Row(class_id=None, major_id=None, college_id=None)
    room, building = Row(id=1, floor_no=1), Row(id=1)
    index.add(student, room, building)
    assert index.score(student, room, building, {"sameClass": True}) == (0,) * 9
