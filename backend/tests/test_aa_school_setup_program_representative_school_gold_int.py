"""A-W4 representative-school Program import Gold contract.

Uses the repository's 20K sandbox-school curriculum-closure constants rather than
inventing a toy credit plan. The package is 37 ProgramCourses / 140 credits:
PUBLIC_BASIC=30, MAJOR_CORE=64, PRACTICE=46. The test proves the complete local
owner chain that can be sealed before shared File Exchange/schema wiring:

normalize -> source/reference/quality -> CREATE DRAFT write intent -> authoritative
reread hash -> receipt -> published BINDING create -> relationship reread ->
second independent identical job -> DEFINITION REUSE zero write -> BINDING REUSE
zero write.

The repeated job deliberately uses the same source digest but still reruns every
authority/reconciliation stage. Digest equality itself never grants reuse.
"""
from __future__ import annotations

from decimal import Decimal


def _services():
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_binding_write_plan as binding_write_plan
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_definition_write_plan as definition_write_plan
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_import_adapter as adapter
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_import_receipt as receipt
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_post_confirm_reconciliation as post_confirm
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_preflight_pipeline as pipeline
    from app.modules.academic_affairs.services import academic_affairs_school_setup_program_preview_adapter as preview

    return {
        "adapter": adapter,
        "pipeline": pipeline,
        "definition_write_plan": definition_write_plan,
        "binding_write_plan": binding_write_plan,
        "post_confirm": post_confirm,
        "preview": preview,
        "receipt": receipt,
    }


def _representative_school_package():
    from app.services import sandbox_school_academic_affairs_seed as seed
    from app.services import sandbox_school_curriculum_closure as closure

    major_id = 10
    major_code = "SBX01"
    major_name = "软件技术"
    series_key = "SBX-SOFTWARE-2026"
    grade_year = "2026"

    courses = []
    for code, name, _category, _nature, credit, _hours, _exam in seed.PUBLIC_COURSES:
        courses.append({
            "code": code,
            "name": name,
            "credit": Decimal(str(credit)),
            "module": "PUBLIC_BASIC",
        })
    for code, name, credit in closure.PUBLIC_EXPANSION:
        courses.append({
            "code": code,
            "name": name,
            "credit": Decimal(str(credit)),
            "module": "PUBLIC_BASIC",
        })

    for suffix, label, _category, _nature, credit, _hours, _exam in seed.MAJOR_COURSE_TEMPLATES:
        courses.append({
            "code": f"{major_code}-{suffix}",
            "name": f"{major_name}{label}",
            "credit": Decimal(str(credit)),
            "module": "MAJOR_CORE",
        })
    for index, label in enumerate(closure.ADVANCED_MAJOR_COURSE_LABELS, start=7):
        courses.append({
            "code": f"{major_code}-{index:02d}",
            "name": f"{major_name}{label}",
            "credit": Decimal("4"),
            "module": "MAJOR_CORE",
        })
    for suffix, label, credit in closure.MAJOR_EXPANSION:
        courses.append({
            "code": f"{major_code}-{suffix}",
            "name": f"{major_name}{label}",
            "credit": Decimal(str(credit)),
            "module": "MAJOR_CORE",
        })
    for index, (label, _segment_type, _weeks, credit) in enumerate(
        closure.PRACTICE_LABELS,
        start=18,
    ):
        courses.append({
            "code": f"{major_code}-{index:02d}",
            "name": f"{major_name}{label}",
            "credit": Decimal(str(credit)),
            "module": "PRACTICE",
        })

    assert len(courses) == 37
    module_credit = {
        module: sum(
            (row["credit"] for row in courses if row["module"] == module),
            Decimal("0"),
        )
        for module in ("PUBLIC_BASIC", "MAJOR_CORE", "PRACTICE")
    }
    assert module_credit == {
        "PUBLIC_BASIC": Decimal("30"),
        "MAJOR_CORE": Decimal("64"),
        "PRACTICE": Decimal("46"),
    }
    assert sum((row["credit"] for row in courses), Decimal("0")) == Decimal("140")

    public_codes = [row["code"] for row in courses if row["module"] == "PUBLIC_BASIC"]
    major_codes = [row["code"] for row in courses if row["module"] != "PUBLIC_BASIC"]
    term_by_code = closure._term_assignments(grade_year, public_codes, major_codes)
    assert set(term_by_code) == {row["code"] for row in courses}
    assert 1 <= min(term_by_code.values()) <= max(term_by_code.values()) <= 6

    grouped = {
        "MAIN": [{
            "programSeriesKey": series_key,
            "programVersion": 1,
            "programName": f"{major_name}{grade_year}级人才培养方案",
            "majorId": major_id,
            "gradeYear": grade_year,
            "totalCredits": 140,
            "educationYears": 3,
        }],
        "COURSE": [{
            "programSeriesKey": series_key,
            "programVersion": 1,
            "courseCode": row["code"],
            "courseVersion": 1,
            "openTermNo": term_by_code[row["code"]],
            "module": row["module"],
            # Explicit source plan truth; never inferred from course nature/name.
            "formationMode": "ADMIN_FIXED",
            # Deliberately blank: exact Course-version credit is authoritative.
            "creditSnapshot": "",
        } for row in courses],
        "CREDIT_REQUIREMENT": [{
            "programSeriesKey": series_key,
            "programVersion": 1,
            "module": item["module"],
            "creditTarget": item["creditTarget"],
        } for item in closure.CREDIT_STRUCTURE],
        "PRACTICE": [{
            "programSeriesKey": series_key,
            "programVersion": 1,
            "segmentName": f"{major_name}{label}",
            "segmentType": segment_type,
            "openTermNo": term_by_code[f"{major_code}-{18 + index:02d}"],
            "weeks": weeks,
            "credit": credit,
            "orgMode": "DISTRIBUTED" if segment_type == "POST_INTERNSHIP" else "CENTRALIZED",
            "assessmentMode": "CHECK",
            "location": "校内实训中心/合作企业",
            "sortOrder": index,
        } for index, (label, segment_type, weeks, credit) in enumerate(closure.PRACTICE_LABELS)],
        "GRADUATION": [{
            "programSeriesKey": series_key,
            "programVersion": 1,
            "category": category,
            "content": template.format(major=major_name),
            "sortOrder": index,
        } for index, (category, template) in enumerate(closure.GRADUATION_ITEMS)],
        "BINDING": [{
            "programSeriesKey": series_key,
            "programVersion": 1,
            "majorId": major_id,
            "gradeYear": grade_year,
            "bindingScope": "MAJOR_GRADE",
            "classId": "",
        }],
    }

    snapshots = [{
        "courseId": 1000 + index,
        "courseCode": row["code"],
        "version": 1,
        "courseName": row["name"],
        "status": "ENABLED",
        "credit": row["credit"],
    } for index, row in enumerate(courses, start=1)]
    return grouped, snapshots


def _definition_rows_from_plan(normalized_rows, plan_item, *, program_id="501"):
    result = []
    for payload in plan_item["writes"]["courses"]:
        result.append({
            "programId": program_id,
            "logicalGroup": "COURSE",
            "payload": dict(payload),
        })
    for row in normalized_rows:
        group = row["logicalGroup"]
        if group in {"CREDIT_REQUIREMENT", "PRACTICE", "GRADUATION"}:
            result.append({
                "programId": program_id,
                "logicalGroup": group,
                "payload": dict(row["payload"]),
            })
    return result


def _program_snapshot(plan_item, *, program_id="501", status="DRAFT"):
    write = dict(plan_item["writes"]["program"])
    return {
        "programId": program_id,
        "seriesKey": write["seriesKey"],
        "version": write["version"],
        "programName": write["programName"],
        "majorId": write["majorId"],
        "gradeYear": write["gradeYear"],
        "totalCredits": write["totalCredits"],
        "prevVersionId": None,
        "prevProgramId": write["prevProgramId"],
        "status": status,
    }


def _definition_preflight(services, normalized, course_snapshots, *, existing_programs=(), definitions=()):
    calls = []

    def scope():
        calls.append(("scope", ()))
        return None

    def major(keys):
        calls.append(("major", tuple(keys)))
        return [{"majorId": 10, "educationYears": 3, "status": "ACTIVE"}]

    def course(keys):
        calls.append(("course", tuple(keys)))
        expected = tuple(sorted(f"{row['courseCode']}@v1" for row in course_snapshots))
        assert tuple(keys) == expected
        return list(course_snapshots)

    def program(keys):
        calls.append(("program", tuple(keys)))
        assert tuple(keys) == ("SBX-SOFTWARE-2026",)
        return list(existing_programs)

    def definition(keys):
        calls.append(("definitions", tuple(keys)))
        assert tuple(keys) == ("501",)
        return list(definitions)

    result = services["pipeline"].run_program_import_preflight(
        normalized,
        phase="DEFINITION",
        load_allowed_major_ids=scope,
        load_major_snapshots=major,
        load_class_snapshots=lambda _keys: (_ for _ in ()).throw(
            AssertionError("DEFINITION must not load SchoolClass")
        ),
        load_course_snapshots=course,
        load_program_snapshots=program,
        load_existing_definition_rows=definition,
        load_program_status_by_id=lambda _keys: (_ for _ in ()).throw(
            AssertionError("DEFINITION must not load Program status")
        ),
        load_active_binding_snapshots=lambda _keys: (_ for _ in ()).throw(
            AssertionError("DEFINITION must not load active bindings")
        ),
    )
    return result, calls


def _binding_preflight(services, normalized, course_snapshots, program_snapshot, definitions, *, active_bindings):
    calls = []

    def record(name, values):
        calls.append((name, tuple(values)))

    result = services["pipeline"].run_program_import_preflight(
        normalized,
        phase="BINDING",
        load_allowed_major_ids=lambda: (record("scope", ()), None)[1],
        load_major_snapshots=lambda keys: (
            record("major", keys),
            [{"majorId": 10, "educationYears": 3, "status": "ACTIVE"}],
        )[1],
        load_class_snapshots=lambda _keys: (_ for _ in ()).throw(
            AssertionError("MAJOR_GRADE binding must not load SchoolClass")
        ),
        load_course_snapshots=lambda keys: (record("course", keys), list(course_snapshots))[1],
        load_program_snapshots=lambda keys: (record("program", keys), [program_snapshot])[1],
        load_existing_definition_rows=lambda keys: (record("definitions", keys), list(definitions))[1],
        load_program_status_by_id=lambda keys: (
            record("status", keys),
            {"501": program_snapshot["status"]},
        )[1],
        load_active_binding_snapshots=lambda keys: (
            record("active_binding", keys),
            list(active_bindings),
        )[1],
    )
    return result, calls


def test_representative_school_program_import_create_bind_and_independent_replay_are_gold():
    services = _services()
    grouped, course_snapshots = _representative_school_package()
    normalized = services["adapter"].normalize_program_import_rows(grouped)

    assert len([row for row in normalized if row["logicalGroup"] == "COURSE"]) == 37
    assert len([row for row in normalized if row["logicalGroup"] == "PRACTICE"]) == 6
    assert len(normalized) == 52

    # ── Job 1 / DEFINITION: fresh stable series -> CREATE DRAFT ──────────────
    first, first_calls = _definition_preflight(
        services,
        normalized,
        course_snapshots,
    )
    assert first["stage"] == "READY"
    assert first["programPreflightSafe"] is True
    assert first["errors"] == []
    assert first["actions"] == [{
        "programKey": "SERIES:SBX-SOFTWARE-2026:v1",
        "action": "CREATE",
        "programId": "",
        "createStatus": "DRAFT",
        "predecessorProgramId": "",
        "requiresDefinitionReconciliation": False,
    }]
    metrics = first["quality"]["programMetrics"][0]
    assert Decimal(metrics["courseCreditSum"]) == Decimal("140")
    assert Decimal(metrics["practiceCreditSum"]) == Decimal("46")
    assert Decimal(metrics["actualCreditSum"]) == Decimal("140")
    assert {
        key: Decimal(value) for key, value in metrics["moduleActualCredits"].items()
    } == {
        "PUBLIC_BASIC": Decimal("30"),
        "MAJOR_CORE": Decimal("64"),
        "PRACTICE": Decimal("46"),
    }
    assert first_calls[:4] == [
        ("scope", ()),
        ("major", (10,)),
        ("course", tuple(sorted(f"{row['courseCode']}@v1" for row in course_snapshots))),
        ("program", ("SBX-SOFTWARE-2026",)),
    ]

    first_plan = services["definition_write_plan"].build_program_definition_write_plan(
        normalized,
        first,
        course_snapshots=course_snapshots,
    )
    assert first_plan["executable"] is False  # shared schema owner is still pending
    create_plan = first_plan["programPlans"][0]
    assert create_plan["action"] == "CREATE"
    assert create_plan["writeCount"] == 48  # Program + 37 Course + 6 Practice + 4 Graduation
    assert create_plan["writes"]["bindings"] == []
    assert sum(
        (row["creditSnapshot"] for row in create_plan["writes"]["courses"]),
        Decimal("0"),
    ) == Decimal("140")

    authoritative_definitions = _definition_rows_from_plan(normalized, create_plan)
    draft_program = _program_snapshot(create_plan, status="DRAFT")
    first_reconcile = services["post_confirm"].reconcile_program_definition_after_confirm(
        normalized,
        first,
        authoritative_program_snapshots=[draft_program],
        authoritative_definition_rows=authoritative_definitions,
        course_snapshots=course_snapshots,
    )
    assert first_reconcile["reconciliationSafe"] is True
    assert first_reconcile["importedPrograms"] == 1
    assert first_reconcile["reusedPrograms"] == 0
    assert first_reconcile["items"][0]["hashMatch"] is True
    assert len(first_reconcile["items"][0]["definitionHash"]) == 64

    first_preview = services["preview"].program_preflight_to_file_exchange_preview(
        normalized,
        first,
    )
    first_receipt = services["receipt"].build_program_import_receipt(
        row_digest="d" * 64,
        preview=first_preview,
        reconciliation=first_reconcile,
        mutation_write_count=create_plan["writeCount"],
    )
    assert first_receipt["importedPrograms"] == 1
    assert first_receipt["reusedPrograms"] == 0
    assert first_receipt["confirmedRows"] == 52
    assert first_receipt["domainMutationWriteCount"] == 48
    assert first_receipt["relationshipReconciled"] is True
    assert first_receipt["idempotency"]["replayNoOp"] is False

    # ── Job 1 / BINDING: after normal publish, attach active scope ────────────
    published_program = dict(draft_program, status="PUBLISHED")
    binding_preflight, binding_calls = _binding_preflight(
        services,
        normalized,
        course_snapshots,
        published_program,
        authoritative_definitions,
        active_bindings=[],
    )
    assert binding_preflight["stage"] == "READY"
    assert binding_preflight["programPreflightSafe"] is True
    assert binding_preflight["actions"][0]["action"] == "REUSE"
    assert binding_preflight["actions"][0]["definitionReconciled"] is True
    assert binding_preflight["binding"]["bindingWriteAllowed"] is True
    assert binding_preflight["binding"]["intents"] == [{
        "row": 2,
        "programKey": "SERIES:SBX-SOFTWARE-2026:v1",
        "programId": "501",
        "scopeKey": "MAJOR:10:GRADE:2026:MAJOR_GRADE",
        "action": "CREATE",
        "supersedeProgramId": "",
    }]
    assert binding_calls[-2:] == [
        ("status", ("501",)),
        ("active_binding", ("MAJOR:10:GRADE:2026:MAJOR_GRADE",)),
    ]

    binding_plan = services["binding_write_plan"].build_program_binding_write_plan(
        binding_preflight
    )
    bind_item = binding_plan["plans"][0]
    assert bind_item["action"] == "CREATE"
    assert bind_item["writeCount"] == 3
    assert bind_item["lockOrder"] == [
        "PROGRAM:501",
        "MAJOR:10",
        "ACTIVE_BINDING_SCOPE:MAJOR:10:GRADE:2026:MAJOR_GRADE",
    ]

    active_binding = {
        "scopeKey": "MAJOR:10:GRADE:2026:MAJOR_GRADE",
        "majorId": 10,
        "gradeYear": "2026",
        "classId": None,
        "programId": "501",
        "status": "ACTIVE",
    }
    bind_reconcile = services["post_confirm"].reconcile_program_bindings_after_confirm(
        binding_preflight,
        authoritative_binding_snapshots=[active_binding],
        authoritative_program_status_by_id={"501": "ENABLED"},
    )
    assert bind_reconcile["reconciliationSafe"] is True
    assert bind_reconcile["createdBindings"] == 1
    assert bind_reconcile["reusedBindings"] == 0
    assert len(bind_reconcile["activeRelationshipHash"]) == 64

    bind_preview = services["preview"].program_preflight_to_file_exchange_preview(
        normalized,
        binding_preflight,
    )
    bind_receipt = services["receipt"].build_program_import_receipt(
        row_digest="d" * 64,
        preview=bind_preview,
        reconciliation=bind_reconcile,
        mutation_write_count=bind_item["writeCount"],
    )
    assert bind_receipt["createdBindings"] == 1
    assert bind_receipt["reusedBindings"] == 0
    assert bind_receipt["domainMutationWriteCount"] == 3
    assert bind_receipt["relationshipReconciled"] is True

    # ── Job 2 / same source digest: REVALIDATE, then zero-write REUSE ─────────
    enabled_program = dict(draft_program, status="ENABLED")
    replay, replay_calls = _definition_preflight(
        services,
        normalized,
        course_snapshots,
        existing_programs=[enabled_program],
        definitions=authoritative_definitions,
    )
    assert replay["stage"] == "READY"
    assert replay["programPreflightSafe"] is True
    assert replay["actions"][0]["action"] == "REUSE"
    assert replay["actions"][0]["definitionReconciled"] is True
    assert replay_calls[-1] == ("definitions", ("501",))

    replay_plan = services["definition_write_plan"].build_program_definition_write_plan(
        normalized,
        replay,
        course_snapshots=course_snapshots,
    )
    assert replay_plan["programPlans"] == [{
        "programKey": "SERIES:SBX-SOFTWARE-2026:v1",
        "action": "REUSE",
        "programId": "501",
        "writeCount": 0,
        "writes": {},
    }]

    replay_reconcile = services["post_confirm"].reconcile_program_definition_after_confirm(
        normalized,
        replay,
        authoritative_program_snapshots=[enabled_program],
        authoritative_definition_rows=authoritative_definitions,
        course_snapshots=course_snapshots,
    )
    assert replay_reconcile["reconciliationSafe"] is True
    assert replay_reconcile["importedPrograms"] == 0
    assert replay_reconcile["reusedPrograms"] == 1
    assert replay_reconcile["items"][0]["hashMatch"] is True

    replay_preview = services["preview"].program_preflight_to_file_exchange_preview(
        normalized,
        replay,
    )
    replay_receipt = services["receipt"].build_program_import_receipt(
        row_digest="d" * 64,
        preview=replay_preview,
        reconciliation=replay_reconcile,
        mutation_write_count=0,
    )
    assert replay_receipt["confirmedRows"] == 52
    assert replay_receipt["importedPrograms"] == 0
    assert replay_receipt["reusedPrograms"] == 1
    assert replay_receipt["domainMutationWriteCount"] == 0
    assert replay_receipt["idempotency"]["crossJobDigestShortCircuit"] is False
    assert replay_receipt["idempotency"]["replayPolicy"] == "REVALIDATE_THEN_STABLE_KEY_REUSE"
    assert replay_receipt["idempotency"]["replayNoOp"] is True

    # Repeating the BINDING job likewise revalidates and then performs zero writes.
    replay_binding, _ = _binding_preflight(
        services,
        normalized,
        course_snapshots,
        enabled_program,
        authoritative_definitions,
        active_bindings=[active_binding],
    )
    assert replay_binding["stage"] == "READY"
    assert replay_binding["binding"]["bindingWriteAllowed"] is True
    assert replay_binding["binding"]["intents"][0]["action"] == "REUSE"
    replay_binding_plan = services["binding_write_plan"].build_program_binding_write_plan(
        replay_binding
    )
    assert replay_binding_plan["plans"][0]["writeCount"] == 0
    assert replay_binding_plan["plans"][0]["mutations"] == []

    replay_binding_reconcile = services["post_confirm"].reconcile_program_bindings_after_confirm(
        replay_binding,
        authoritative_binding_snapshots=[active_binding],
        authoritative_program_status_by_id={"501": "ENABLED"},
    )
    replay_binding_receipt = services["receipt"].build_program_import_receipt(
        row_digest="d" * 64,
        preview=services["preview"].program_preflight_to_file_exchange_preview(
            normalized,
            replay_binding,
        ),
        reconciliation=replay_binding_reconcile,
        mutation_write_count=0,
    )
    assert replay_binding_receipt["createdBindings"] == 0
    assert replay_binding_receipt["reusedBindings"] == 1
    assert replay_binding_receipt["domainMutationWriteCount"] == 0
    assert replay_binding_receipt["idempotency"]["replayNoOp"] is True
