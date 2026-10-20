"""Read-only capacity accounting; shared inventory is never counted twice."""


def allocation_capacity(students, resources, housed_student_ids=(), missing_identity=0):
    housed = set(housed_student_ids)
    demand = {"MALE": 0, "FEMALE": 0, "UNKNOWN": 0}
    beds = {"MALE": 0, "FEMALE": 0, "MIXED": 0, "UNKNOWN": 0}
    already_housed = 0
    for student in students:
        if student.id in housed:
            already_housed += 1
            continue
        gender = str(student.gender or "").upper()
        key = "MALE" if gender in {"M", "MALE", "男", "1"} else (
            "FEMALE" if gender in {"F", "FEMALE", "女", "2"} else "UNKNOWN")
        demand[key] += 1
    seen = set()
    for bed, _room, building in resources:
        if bed.id in seen or bed.status != "VACANT" or bed.student_id is not None:
            continue
        seen.add(bed.id)
        key = str(building.gender_limit or "MIXED").upper()
        beds[key if key in beds else "UNKNOWN"] += 1
    rows = [{"gender": key, "label": label, "students": demand[key],
             "dedicatedBeds": beds[key],
             "needsSharedBeds": max(0, demand[key] - beds[key]),
             "surplusDedicatedBeds": max(0, beds[key] - demand[key])}
            for key, label in (("MALE", "男生"), ("FEMALE", "女生"))]
    # This is only a lower bound: room segregation and other constraints can add deficits.
    shortage = max(0, sum(row["needsSharedBeds"] for row in rows) - beds["MIXED"])
    return {"rows": rows, "sharedBeds": beds["MIXED"],
            "unclassifiedBeds": beds["UNKNOWN"], "unknownGenderStudents": demand["UNKNOWN"],
            "missingIdentityStudents": missing_identity, "alreadyHousedStudents": already_housed,
            "minimumShortage": shortage, "totalDemand": sum(demand.values()),
            "availableBeds": sum(beds.values()), "requiresRoomValidation": beds["MIXED"] > 0}
