from pathlib import Path


def replace_exact(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one replacement, found {count}: {old[:80]!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


# 1) Archive domain policy: freeze four-state semantics at the rule source.
policy = "backend/app/modules/academic_affairs/services/academic_affairs_archive_domain_policy.py"
replace_exact(
    policy,
    '''def _legacy_result(count, passed, remark):
    return _core._result(int(count or 0), bool(passed), str(remark or ""))


def _safe(code, fn):
    try:
        return fn()
    except Exception as exc:
        return _legacy_result(0, False, f"该域语义检查失败：{type(exc).__name__}")
''',
    '''_ARCHIVE_RESULT_STATES = {"PASS", "BLOCKED", "NOT_APPLICABLE", "UNKNOWN"}
_BLOCKING_RESULTS = {"BLOCKED", "UNKNOWN"}


def _legacy_result(count, passed, remark):
    return _core._result(int(count or 0), bool(passed), str(remark or ""))


def _state_result(code, state, remark, *, count=0, blocking_count=None, rule_code=None, evidence=None):
    state = str(state or "UNKNOWN").upper()
    if state not in _ARCHIVE_RESULT_STATES:
        state = "UNKNOWN"
    if blocking_count is None:
        blocking_count = 1 if state in _BLOCKING_RESULTS else 0
    blocking_count = max(1, int(blocking_count or 0)) if state in _BLOCKING_RESULTS else 0
    return {
        "recordCount": int(count or 0),
        "present": state == "PASS",
        "remark": str(remark or ""),
        "result": state,
        "ruleCode": rule_code or f"{code}_SEMANTIC_GATE",
        "summary": str(remark or ""),
        "blockingCount": blocking_count,
        "route": ROUTES.get(code, "/admin/academic-affairs/archive/precheck"),
        "evidence": list(evidence or []),
    }


def _safe(code, fn):
    try:
        return fn()
    except Exception as exc:
        return _state_result(
            code,
            "UNKNOWN",
            f"该域语义检查失败：{type(exc).__name__}",
            rule_code=f"{code}_EVALUATION_ERROR",
        )
''',
)

replace_exact(
    policy,
    '''def evaluate_graduation(db, term_id):
    """毕业审核批次没有term_id时只按学期日期窗口核验，禁止用全校历史阻断当前学期。"""
    from app.models import AaGraduationAuditBatch, AaTerm

    if not term_id:
        return _legacy_result(0, True, "未指定学期；毕业审核批次暂无term_id，本次不跨学期阻断")
    term = db.query(AaTerm).filter(
        AaTerm.id == int(term_id),
        AaTerm.tenant_id == _tid(),
        AaTerm.is_deleted.is_(False),
    ).first()
    if not term:
        return _legacy_result(0, False, "学期不存在，无法核验毕业审核范围")
    start_at = _day_start(getattr(term, "start_date", None))
    end_at = _day_end(getattr(term, "end_date", None))
    if not start_at or not end_at:
        return _legacy_result(0, True, "学期起止日期不完整；已停止使用全校历史毕业批次作阻断")

    rows = []
    for row in db.query(AaGraduationAuditBatch).filter(
        AaGraduationAuditBatch.tenant_id == _tid(),
        AaGraduationAuditBatch.is_deleted.is_(False),
    ).all():
        occurred_at = getattr(row, "generate_at", None) or getattr(row, "created_at", None)
        if occurred_at and start_at <= occurred_at <= end_at:
            rows.append(row)
    if not rows:
        return _legacy_result(0, True, "本学期未发现可按时间归属的毕业审核批次（非毕业学期不阻断）")
    unfinished = [row for row in rows if str(row.status or "").upper() != "ARCHIVED"]
    return _legacy_result(
        len(rows),
        not unfinished,
        "本学期毕业审核批次均已归档" if not unfinished else f"本学期仍有 {len(unfinished)} 个毕业审核批次未归档",
    )
''',
    '''def evaluate_graduation(db, term_id):
    """Graduation archive gate is four-state and never promotes missing scope evidence to PASS."""
    from app.models import AaGraduationAuditBatch, AaTerm

    if not term_id:
        return _state_result(
            "GRADUATION",
            "UNKNOWN",
            "未指定学期，无法确定毕业审核批次的归档范围",
            rule_code="GRADUATION_TERM_SCOPE_UNKNOWN",
        )
    term = db.query(AaTerm).filter(
        AaTerm.id == int(term_id),
        AaTerm.tenant_id == _tid(),
        AaTerm.is_deleted.is_(False),
    ).first()
    if not term:
        return _state_result(
            "GRADUATION",
            "BLOCKED",
            "学期不存在，无法核验毕业审核范围",
            rule_code="GRADUATION_TERM_NOT_FOUND",
        )
    start_at = _day_start(getattr(term, "start_date", None))
    end_at = _day_end(getattr(term, "end_date", None))
    if not start_at or not end_at:
        return _state_result(
            "GRADUATION",
            "UNKNOWN",
            "学期起止日期不完整，无法证明毕业审核批次是否属于本学期",
            rule_code="GRADUATION_TERM_DATES_UNKNOWN",
        )

    rows = []
    for row in db.query(AaGraduationAuditBatch).filter(
        AaGraduationAuditBatch.tenant_id == _tid(),
        AaGraduationAuditBatch.is_deleted.is_(False),
    ).all():
        occurred_at = getattr(row, "generate_at", None) or getattr(row, "created_at", None)
        if occurred_at and start_at <= occurred_at <= end_at:
            rows.append(row)
    if not rows:
        return _state_result(
            "GRADUATION",
            "NOT_APPLICABLE",
            "本学期未发现可按时间归属的毕业审核批次（非毕业学期不阻断）",
            rule_code="GRADUATION_NOT_APPLICABLE",
        )
    unfinished = [row for row in rows if str(row.status or "").upper() != "ARCHIVED"]
    if unfinished:
        return _state_result(
            "GRADUATION",
            "BLOCKED",
            f"本学期仍有 {len(unfinished)} 个毕业审核批次未归档",
            count=len(rows),
            blocking_count=len(unfinished),
            rule_code="GRADUATION_BATCH_UNARCHIVED",
        )
    return _state_result(
        "GRADUATION",
        "PASS",
        "本学期毕业审核批次均已归档",
        count=len(rows),
        rule_code="GRADUATION_BATCH_ARCHIVED",
    )
''',
)

replace_exact(
    policy,
    '''def evaluate_selection(db, term_id):
    from app.models import AaSelectionBatch, AaSelectionCourse, AaSelectionRecord, AaSelectionRound

    query = db.query(AaSelectionBatch).filter(
''',
    '''def evaluate_selection(db, term_id):
    from app.models import AaSelectionBatch, AaSelectionCourse, AaSelectionRecord, AaSelectionRound

    if not term_id:
        return _state_result(
            "SELECTION", "UNKNOWN", "未指定学期，无法核验选课名单归档范围",
            rule_code="SELECTION_TERM_SCOPE_UNKNOWN",
        )
    query = db.query(AaSelectionBatch).filter(
''',
)
replace_exact(
    policy,
    '''    if not batches:
        return _legacy_result(0, True, "本学期未启用选课批次，不作为归档阻断")
''',
    '''    if not batches:
        return _state_result(
            "SELECTION", "NOT_APPLICABLE", "本学期未启用选课批次，不作为归档阻断",
            rule_code="SELECTION_NOT_APPLICABLE",
        )
''',
)
replace_exact(
    policy,
    '''    if not term_id and not term_code:
        return _legacy_result(0, False, "未指定学期，无法核验补考重修免修")
''',
    '''    if not term_id and not term_code:
        return _state_result(
            "MAKEUP", "UNKNOWN", "未指定学期，无法核验补考重修免修",
            rule_code="MAKEUP_TERM_SCOPE_UNKNOWN",
        )
''',
)
replace_exact(
    policy,
    '''    if not term_id:
        return _legacy_result(0, False, "未指定学期，无法核验学生评教")
''',
    '''    if not term_id:
        return _state_result(
            "EVALUATION", "UNKNOWN", "未指定学期，无法核验学生评教",
            rule_code="EVALUATION_TERM_SCOPE_UNKNOWN",
        )
''',
)
replace_exact(
    policy,
    '''    if not batches:
        return _legacy_result(0, True, "本学期未启用学生评教，不作为归档阻断")
''',
    '''    if not batches:
        return _state_result(
            "EVALUATION", "NOT_APPLICABLE", "本学期未启用学生评教，不作为归档阻断",
            rule_code="EVALUATION_NOT_APPLICABLE",
        )
''',
)
replace_exact(
    policy,
    '''    if not term_id:
        return _legacy_result(0, False, "未指定学期，无法核验教材业务")
''',
    '''    if not term_id:
        return _state_result(
            "TEXTBOOK", "UNKNOWN", "未指定学期，无法核验教材业务",
            rule_code="TEXTBOOK_TERM_SCOPE_UNKNOWN",
        )
''',
)
replace_exact(
    policy,
    '''    if not orders:
        return _legacy_result(0, True, "本学期未启用教材征订，不作为归档阻断")
''',
    '''    if not orders:
        return _state_result(
            "TEXTBOOK", "NOT_APPLICABLE", "本学期未启用教材征订，不作为归档阻断",
            rule_code="TEXTBOOK_NOT_APPLICABLE",
        )
''',
)

# 2) Normalizer must preserve explicit zero blockingCount for NOT_APPLICABLE.
evaluator = "backend/app/modules/academic_affairs/services/academic_affairs_archive_rule_evaluator.py"
replace_exact(
    evaluator,
    '''def normalize_legacy_result(code: str, result: dict) -> dict:
    source = dict(result or {})
    passed = bool(source.get("present"))
    summary = str(source.get("remark") or "")
    return {
        **source,
        "result": source.get("result") or ("PASS" if passed else "BLOCKED"),
        "ruleCode": source.get("ruleCode") or f"{code}_SEMANTIC_GATE",
        "summary": source.get("summary") or summary,
        "blockingCount": int(source.get("blockingCount") or (0 if passed else 1)),
        "route": source.get("route") or _ROUTE.get(code, "/admin/academic-affairs/archive/precheck"),
        "evidence": list(source.get("evidence") or []),
    }
''',
    '''def normalize_legacy_result(code: str, result: dict) -> dict:
    source = dict(result or {})
    state = str(source.get("result") or ("PASS" if source.get("present") else "BLOCKED")).upper()
    if state not in {"PASS", "BLOCKED", "NOT_APPLICABLE", "UNKNOWN"}:
        state = "UNKNOWN"
    blocking = source.get("blockingCount")
    if blocking is None:
        blocking = 1 if state in {"BLOCKED", "UNKNOWN"} else 0
    blocking = max(1, int(blocking or 0)) if state in {"BLOCKED", "UNKNOWN"} else 0
    summary = str(source.get("summary") or source.get("remark") or "")
    return {
        **source,
        "present": state == "PASS",
        "result": state,
        "ruleCode": source.get("ruleCode") or f"{code}_SEMANTIC_GATE",
        "summary": summary,
        "remark": summary,
        "blockingCount": blocking,
        "route": source.get("route") or _ROUTE.get(code, "/admin/academic-affairs/archive/precheck"),
        "evidence": list(source.get("evidence") or []),
    }
''',
)

# 3) Public archive service: term-less archive is UNKNOWN, N/A is non-blocking, UNKNOWN stays visible.
service = "backend/app/modules/academic_affairs/services/academic_affairs_archive_service.py"
replace_exact(
    service,
    '''_DOMAINS = list(_policy.DOMAINS)
_ROUTE = dict(_policy.ROUTES)
''',
    '''_DOMAINS = list(_policy.DOMAINS)
_ROUTE = dict(_policy.ROUTES)
_ARCHIVE_RESULT_STATES = {"PASS", "BLOCKED", "NOT_APPLICABLE", "UNKNOWN"}
_BLOCKING_RESULTS = {"BLOCKED", "UNKNOWN"}
_NON_BLOCKING_RESULTS = {"PASS", "NOT_APPLICABLE"}
''',
)
replace_exact(
    service,
    '''    if right["result"] == "PASS":
        left["evidence"] = [
            *left["evidence"],
            {"type": rule_code, "result": "PASS", "summary": right["summary"]},
        ]
        return left
    left["present"] = False
    left["result"] = "BLOCKED"
    left["ruleCode"] = rule_code
    left["blockingCount"] = int(left["blockingCount"] or 0) + max(1, int(right["blockingCount"] or 0))
''',
    '''    if right["result"] in _NON_BLOCKING_RESULTS:
        left["evidence"] = [
            *left["evidence"],
            {"type": rule_code, "result": right["result"], "summary": right["summary"]},
        ]
        return left
    left["present"] = False
    left["result"] = "BLOCKED" if "BLOCKED" in {left["result"], right["result"]} else "UNKNOWN"
    left["ruleCode"] = rule_code
    left["blockingCount"] = int(left["blockingCount"] or 0) + max(1, int(right["blockingCount"] or 0))
''',
)
replace_exact(
    service,
    '''        {"type": rule_code, "result": "BLOCKED", "summary": right["summary"]},
''',
    '''        {"type": rule_code, "result": right["result"], "summary": right["summary"]},
''',
)
replace_exact(
    service,
    '''def _evaluate_domains(db, term_id, term_code, college_ids=None):
    results = _policy.evaluate_domains(db, term_id, term_code, college_ids)
''',
    '''def _evaluate_domains(db, term_id, term_code, college_ids=None):
    if not term_id:
        return {
            code: _public_result(code, {
                "recordCount": 0,
                "present": False,
                "result": "UNKNOWN",
                "ruleCode": "ARCHIVE_TERM_SCOPE_UNKNOWN",
                "summary": "未解析到归档学期，禁止跨学期猜测业务完成状态",
                "blockingCount": 1,
                "route": _ROUTE.get(code),
            })
            for code, _label in _DOMAINS
        }
    results = _policy.evaluate_domains(db, term_id, term_code, college_ids)
''',
)
replace_exact(
    service,
    '''def _public_result(code: str, result: dict) -> dict:
    row = dict(result or {})
    row["domain"] = code
    row["recordCount"] = int(row.get("recordCount") or 0)
    row["present"] = bool(row.get("present"))
    row["result"] = row.get("result") or ("PASS" if row["present"] else "BLOCKED")
    row["ruleCode"] = row.get("ruleCode") or f"{code}_SEMANTIC_GATE"
    row["summary"] = str(row.get("summary") or row.get("remark") or "")
    row["remark"] = row["summary"]
    row["blockingCount"] = int(row.get("blockingCount") or (0 if row["present"] else 1))
    row["route"] = row.get("route") or _ROUTE.get(code, "/admin/academic-affairs/archive/precheck")
    row["evidence"] = list(row.get("evidence") or [])
    return row
''',
    '''def _public_result(code: str, result: dict) -> dict:
    row = dict(result or {})
    row["domain"] = code
    row["recordCount"] = int(row.get("recordCount") or 0)
    state = str(row.get("result") or ("PASS" if row.get("present") else "BLOCKED")).upper()
    if state not in _ARCHIVE_RESULT_STATES:
        state = "UNKNOWN"
    blocking = row.get("blockingCount")
    if blocking is None:
        blocking = 1 if state in _BLOCKING_RESULTS else 0
    blocking = max(1, int(blocking or 0)) if state in _BLOCKING_RESULTS else 0
    row["present"] = state == "PASS"
    row["result"] = state
    row["ruleCode"] = row.get("ruleCode") or f"{code}_SEMANTIC_GATE"
    row["summary"] = str(row.get("summary") or row.get("remark") or "")
    row["remark"] = row["summary"]
    row["blockingCount"] = blocking
    row["route"] = row.get("route") or _ROUTE.get(code, "/admin/academic-affairs/archive/precheck")
    row["evidence"] = list(row.get("evidence") or [])
    return row
''',
)
replace_exact(
    service,
    '''            if result["result"] != "PASS":
                blocked_domains += 1
''',
    '''            if result["result"] in _BLOCKING_RESULTS:
                blocked_domains += 1
''',
)
replace_exact(
    service,
    '''                "status": "OK" if result["result"] == "PASS" else "MISSING",
''',
    '''                "status": {
                    "PASS": "OK",
                    "NOT_APPLICABLE": "NOT_APPLICABLE",
                    "UNKNOWN": "UNKNOWN",
                    "BLOCKED": "MISSING",
                }[result["result"]],
''',
)
replace_exact(
    service,
    '''        blocking_count = sum(int(row["blockingCount"] or 0) for row in domains)
        blocked_domains = sum(1 for row in domains if row["result"] != "PASS")
        return {
            "termId": str(term_id_value) if term_id_value else None,
            "termCode": term_code_value,
            "result": "PASS" if blocked_domains == 0 else "BLOCKED",
''',
    '''        blocking_count = sum(int(row["blockingCount"] or 0) for row in domains)
        blocked_domains = sum(1 for row in domains if row["result"] in _BLOCKING_RESULTS)
        result_states = {row["result"] for row in domains}
        overall_result = (
            "BLOCKED" if "BLOCKED" in result_states
            else "UNKNOWN" if "UNKNOWN" in result_states
            else "PASS"
        )
        return {
            "termId": str(term_id_value) if term_id_value else None,
            "termCode": term_code_value,
            "result": overall_result,
''',
)

# 4) Existing regression must stop treating missing graduation dates as success.
semantic_test = "backend/tests/test_aa_archive_semantic_gates.py"
replace_exact(
    semantic_test,
    '''def test_graduation_gate_does_not_cross_term_when_dates_missing():
    from app.modules.academic_affairs.services import academic_affairs_archive_domain_policy as policy

    term = SimpleNamespace(id=9, tenant_id=1, start_date=None, end_date=None, is_deleted=False)
    result = policy.evaluate_graduation(
        _ArchiveDb(term=term, graduation_batches=[SimpleNamespace(status="DRAFT")]),
        9,
    )

    assert result["present"] is True
    assert "停止使用全校历史" in result["remark"]
''',
    '''def test_graduation_gate_missing_dates_is_unknown_and_fail_closed():
    from app.modules.academic_affairs.services import academic_affairs_archive_domain_policy as policy

    term = SimpleNamespace(id=9, tenant_id=1, start_date=None, end_date=None, is_deleted=False)
    result = policy.evaluate_graduation(
        _ArchiveDb(term=term, graduation_batches=[SimpleNamespace(status="DRAFT")]),
        9,
    )

    assert result["present"] is False
    assert result["result"] == "UNKNOWN"
    assert result["blockingCount"] >= 1
    assert "日期" in result["remark"]
''',
)

# 5) Archive precheck UI: UNKNOWN is warning/pending governance; N/A is neutral/non-blocking.
view = "frontend/src/modules/academicAffairs/views/ArchivePrecheckView.vue"
replace_exact(
    view,
    '''        <strong>{{ overallResult === 'PASS' ? '可以进入归档批次' : '必须先处理阻断项' }}</strong>
''',
    '''        <strong>{{ overallResult === 'PASS' ? '可以进入归档批次' : '必须先处理阻断 / 待治理项' }}</strong>
''',
)
replace_exact(
    view,
    '''          <span>阻断域</span>
          <strong>{{ blockedDomains }}</strong>
          <small>{{ blockedDomains ? '按阻断数量优先处理' : '当前无阻断域' }}</small>
''',
    '''          <span>阻断 / 待治理域</span>
          <strong>{{ blockedDomains }}</strong>
          <small>{{ blockedDomains ? 'BLOCKED 与 UNKNOWN 均不得进入正式归档' : '当前无阻断或待治理域' }}</small>
''',
)
replace_exact(
    view,
    '''            <h3>归档阻断域</h3>
            <p>按阻断项数量从高到低排列；先处理最影响归档闭环的业务域，再重新检查。</p>
''',
    '''            <h3>归档阻断 / 待治理域</h3>
            <p>BLOCKED 是已知业务阻断，UNKNOWN 是证据不足待治理；两者都不得绿色放行，处理后再重新检查。</p>
''',
)
replace_exact(
    view,
    '''          <span class="aapc-count is-danger">{{ blockedDomainRows.length }} 个阻断域</span>
''',
    '''          <span class="aapc-count is-danger">{{ blockedDomainRows.length }} 个阻断 / 待治理域</span>
''',
)
replace_exact(
    view,
    '''            <h3>已通过业务域</h3>
            <p>这些域已满足当前归档语义门禁，保留业务证据供复核，不与阻断项混排。</p>
''',
    '''            <h3>已满足门禁的业务域</h3>
            <p>PASS 表示已证明完成；NOT_APPLICABLE 表示本学期明确不适用。两者均非阻断，但不得混成同一个“通过”。</p>
''',
)
replace_exact(
    view,
    '''          <span class="aapc-count">{{ passedDomainRows.length }} 个通过域</span>
''',
    '''          <span class="aapc-count">{{ passedDomainRows.length }} 个非阻断域</span>
''',
)
replace_exact(
    view,
    '''    passedDomains() {
      return Math.max(this.domains.length - this.blockedDomains, 0)
    },
    blockedDomainRows() {
      return this.domains
        .filter((domain) => domain.result !== 'PASS')
        .slice()
        .sort((a, b) => Number(b.blockingCount || 0) - Number(a.blockingCount || 0))
    },
    passedDomainRows() {
      return this.domains.filter((domain) => domain.result === 'PASS')
    },
''',
    '''    passedDomains() {
      return this.domains.filter((domain) => domain.result === 'PASS').length
    },
    blockedDomainRows() {
      return this.domains
        .filter((domain) => ['BLOCKED', 'UNKNOWN'].includes(domain.result))
        .slice()
        .sort((a, b) => Number(b.blockingCount || 0) - Number(a.blockingCount || 0))
    },
    passedDomainRows() {
      return this.domains.filter((domain) => ['PASS', 'NOT_APPLICABLE'].includes(domain.result))
    },
''',
)
replace_exact(
    view,
    '''      return `仍有 ${this.blockedDomains} 个业务域、${this.blockingCount} 个阻断项需要处理；本页展示系统当前检查结果，不写入归档事实。`
''',
    '''      return `仍有 ${this.blockedDomains} 个阻断 / 待治理业务域、${this.blockingCount} 个阻断项需要处理；UNKNOWN 不会被当成 PASS，本页不写入归档事实。`
''',
)
replace_exact(
    view,
    '''    tagType(domain) { return domain.result === 'PASS' ? 'success' : 'danger' },
    tagLabel(domain) { return domain.result === 'PASS' ? '通过' : '阻断' },
''',
    '''    tagType(domain) {
      return { PASS: 'success', BLOCKED: 'danger', UNKNOWN: 'warning', NOT_APPLICABLE: 'info' }[domain.result] || 'warning'
    },
    tagLabel(domain) {
      return { PASS: '通过', BLOCKED: '阻断', UNKNOWN: '待治理', NOT_APPLICABLE: '不适用' }[domain.result] || '待确认'
    },
''',
)

# 6) Frontend contract explicitly freezes the four visible states.
contract = "frontend/tests/stage-d-archive-precheck-contract.test.mjs"
replace_exact(
    contract,
    '''  assert.match(source, /blockedDomainRows\\(\\)/)
  assert.match(source, /\\.filter\\(\\(domain\\) => domain\\.result !== 'PASS'\\)/)
  assert.match(source, /\\.sort\\(\\(a, b\\) => Number\\(b\\.blockingCount \\|\\| 0\\) - Number\\(a\\.blockingCount \\|\\| 0\\)\\)/)
  assert.match(source, /passedDomainRows\\(\\)/)

  assert.ok(
    source.indexOf('归档阻断域') < source.indexOf('已通过业务域'),
    'blocked domains must render before passed domains'
  )
''',
    '''  assert.match(source, /blockedDomainRows\\(\\)/)
  assert.match(source, /\\['BLOCKED', 'UNKNOWN'\\]\\.includes\\(domain\\.result\\)/)
  assert.match(source, /\\.sort\\(\\(a, b\\) => Number\\(b\\.blockingCount \\|\\| 0\\) - Number\\(a\\.blockingCount \\|\\| 0\\)\\)/)
  assert.match(source, /passedDomainRows\\(\\)/)
  assert.match(source, /\\['PASS', 'NOT_APPLICABLE'\\]\\.includes\\(domain\\.result\\)/)

  assert.ok(
    source.indexOf('归档阻断 / 待治理域') < source.indexOf('已满足门禁的业务域'),
    'blocking and unknown domains must render before non-blocking domains'
  )
''',
)
contract_text = Path(contract).read_text(encoding="utf-8")
append = '''\n\ntest('D-W1 Archive 四态必须在 UI 中可区分且 UNKNOWN 绝不绿色', async () => {\n  const source = await readFile(viewUrl, 'utf8')\n  for (const token of [\n    "PASS: '通过'",\n    "BLOCKED: '阻断'",\n    "UNKNOWN: '待治理'",\n    "NOT_APPLICABLE: '不适用'",\n    "UNKNOWN: 'warning'",\n    "NOT_APPLICABLE: 'info'",\n    'UNKNOWN 不会被当成 PASS',\n    'BLOCKED 与 UNKNOWN 均不得进入正式归档'\n  ]) assert.ok(source.includes(token), `missing D-W1 archive state token: ${token}`)\n})\n'''
if 'D-W1 Archive 四态必须在 UI 中可区分且 UNKNOWN 绝不绿色' in contract_text:
    raise SystemExit('frontend contract already patched unexpectedly')
Path(contract).write_text(contract_text + append, encoding="utf-8")

print('Academic D-W1 deterministic four-state patch applied')
