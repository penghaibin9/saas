from types import SimpleNamespace as Row

from app.services.dorm_allocation_capacity import allocation_capacity


def students(male, female):
    return [Row(id=i, gender="M" if i < male else "F") for i in range(male + female)]


def resources(male, female, mixed=0):
    return [(Row(id=i, status="VACANT", student_id=None), Row(),
             Row(gender_limit="MALE" if i < male else "FEMALE" if i < male + female else "MIXED"))
            for i in range(male + female + mixed)]


def test_two_thousand_total_does_not_hide_gender_shortage():
    result = allocation_capacity(students(1200, 800), resources(1000, 1000))
    assert result["totalDemand"] == result["availableBeds"] == 2000
    assert result["minimumShortage"] == 200
    assert result["rows"][1]["surplusDedicatedBeds"] == 200
    balanced = allocation_capacity(students(1200, 800), resources(1200, 800))
    assert balanced["minimumShortage"] == 0


def test_shared_pool_is_not_promised_to_both_groups():
    result = allocation_capacity(students(100, 100), resources(50, 50, 60))
    assert result["minimumShortage"] == 40
    assert sum(row["needsSharedBeds"] for row in result["rows"]) == 100
    assert result["requiresRoomValidation"] is True


def test_unavailable_beds_duplicates_housed_and_missing_data():
    pool = resources(2, 1, 1)
    pool[0][0].status = "LOCKED"
    pool[1][0].student_id = 77
    pool += [pool[2]]
    people = students(2, 1) + [Row(id=10, gender=None)]
    result = allocation_capacity(people, pool, housed_student_ids=[0], missing_identity=3)
    assert result["availableBeds"] == 2
    assert result["totalDemand"] == 3
    assert result["alreadyHousedStudents"] == 1
    assert result["unknownGenderStudents"] == 1
    assert result["missingIdentityStudents"] == 3
