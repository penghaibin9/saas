from pathlib import Path


def replace_exact(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one replacement, found {count}: {old[:100]!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


view = "frontend/src/modules/academicAffairs/views/ArchivePrecheckView.vue"
replace_exact(
    view,
    '<span class="aapc-eyebrow">完成证据</span>',
    '<span class="aapc-eyebrow">非阻断证据</span>',
)
replace_exact(
    view,
    '<article v-for="d in passedDomainRows" :key="d.domain" class="aapc-card is-ok">',
    '<article v-for="d in passedDomainRows" :key="d.domain" :class="[\'aapc-card\', d.result === \'NOT_APPLICABLE\' ? \'is-na\' : \'is-ok\']">',
)
replace_exact(
    view,
    '''        this.overallResult = data.result || (this.domains.every((d) => d.result === 'PASS') ? 'PASS' : 'BLOCKED')
        this.blockingCount = Number(data.blockingCount || 0)
        this.blockedDomains = Number(data.blockedDomains || this.domains.filter((d) => d.result !== 'PASS').length)
''',
    '''        const states = new Set(this.domains.map((d) => d.result))
        this.overallResult = data.result || (states.has('BLOCKED') ? 'BLOCKED' : states.has('UNKNOWN') ? 'UNKNOWN' : 'PASS')
        this.blockingCount = Number(data.blockingCount ?? 0)
        const fallbackBlockedDomains = this.domains.filter((d) => ['BLOCKED', 'UNKNOWN'].includes(d.result)).length
        this.blockedDomains = Number(data.blockedDomains ?? fallbackBlockedDomains)
''',
)
replace_exact(
    view,
    '''.aapc-card.is-missing { border-color: #efcccc; background: #fffafa; }
.aapc-card.is-ok { border-color: #d7e7dc; background: #fbfefc; }
''',
    '''.aapc-card.is-missing { border-color: #efcccc; background: #fffafa; }
.aapc-card.is-ok { border-color: #d7e7dc; background: #fbfefc; }
.aapc-card.is-na { border-color: #d8e2ef; background: #f8fbff; }
.aapc-card.is-na .aapc-card-title { color: #405a78; }
''',
)

contract = "frontend/tests/stage-d-archive-precheck-contract.test.mjs"
p = Path(contract)
text = p.read_text(encoding="utf-8")
needle = '''    'BLOCKED 与 UNKNOWN 均不得进入正式归档'\n  ]) assert.ok(source.includes(token), `missing D-W1 archive state token: ${token}`)\n})\n'''
replacement = '''    'BLOCKED 与 UNKNOWN 均不得进入正式归档',\n    "d.result === 'NOT_APPLICABLE' ? 'is-na' : 'is-ok'",\n    'data.blockedDomains ?? fallbackBlockedDomains',\n    "['BLOCKED', 'UNKNOWN'].includes(d.result)",\n    '.aapc-card.is-na'\n  ]) assert.ok(source.includes(token), `missing D-W1 archive state token: ${token}`)\n  assert.ok(!source.includes('data.blockedDomains ||'), 'blockedDomains=0 must never fall through to legacy non-PASS counting')\n})\n'''
if text.count(needle) != 1:
    raise SystemExit(f"{contract}: expected contract insertion point once, got {text.count(needle)}")
p.write_text(text.replace(needle, replacement), encoding="utf-8")

print('Academic D-W1 UI zero-value and N/A visual semantics patched')
