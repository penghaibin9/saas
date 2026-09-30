"""Incremental locality scores for class, major and college allocation preferences."""
from collections import Counter


class AllocationNeighborhood:
    def __init__(self):
        self.population = Counter()

    @staticmethod
    def locations(room, building):
        return (("room", int(room.id)),
                ("floor", int(building.id), int(room.floor_no or 0)),
                ("building", int(building.id)))

    def add(self, student, room, building):
        for field in ("class_id", "major_id", "college_id"):
            value = getattr(student, field, None)
            if value:
                for location in self.locations(room, building):
                    self.population[(field, value, location)] += 1

    def score(self, student, room, building, rules):
        # Class concentration outranks major/college even when a room has many other peers.
        scores = []
        for rule, field in (("sameClass", "class_id"), ("sameMajor", "major_id"),
                            ("sameCollege", "college_id")):
            value = getattr(student, field, None)
            scores.extend(self.population[(field, value, location)] if rules.get(rule) and value else 0
                          for location in self.locations(room, building))
        return tuple(scores)
