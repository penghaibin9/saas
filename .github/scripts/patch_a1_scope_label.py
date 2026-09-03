from pathlib import Path

view_path = Path('frontend/src/modules/studentAffairs/views/StudentAffairsDashboardView.vue')
view = view_path.read_text(encoding='utf-8')
old_css = """.sa-v6-risk-numbers dd {
  white-space: nowrap;
  overflow-wrap: normal;
  font-size: var(--font-size-xl);
  font-variant-numeric: tabular-nums;
}
"""
new_css = """.sa-v6-scope-grid dd {
  min-width: 0;
  overflow: hidden;
  overflow-wrap: normal;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-v6-risk-numbers dd {
  white-space: nowrap;
  overflow-wrap: normal;
  font-size: var(--font-size-xl);
  font-variant-numeric: tabular-nums;
}
"""
if old_css in view:
    view = view.replace(old_css, new_css, 1)
elif new_css not in view:
    raise SystemExit('A1 scope CSS contract does not match audited head')
view_path.write_text(view, encoding='utf-8')

e2e_path = Path('e2e/specs/student-affairs-v6-a1.spec.mjs')
e2e = e2e_path.read_text(encoding='utf-8')
old_e2e = """  await expect(page.locator('[data-metric=\"pendingTodo\"] dd')).toHaveText('123,456')
})
"""
new_e2e = """  await expect(page.locator('[data-metric=\"pendingTodo\"] dd')).toHaveText('123,456')
  const scopeValue = page.locator('.sa-v6-scope-grid > div:nth-child(2) dd')
  const scopeVisual = await scopeValue.evaluate((element) => {
    const style = getComputedStyle(element)
    const rect = element.getBoundingClientRect()
    return {
      text: element.textContent,
      title: element.getAttribute('title'),
      height: rect.height,
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
      overflow: style.overflow,
      textOverflow: style.textOverflow,
      whiteSpace: style.whiteSpace
    }
  })
  expect(scopeVisual.title).toBe(scopeVisual.text)
  expect(scopeVisual.whiteSpace).toBe('nowrap')
  expect(scopeVisual.overflow).toBe('hidden')
  expect(scopeVisual.textOverflow).toBe('ellipsis')
  expect(scopeVisual.height).toBeLessThanOrEqual(24)
  expect(scopeVisual.scrollWidth).toBeGreaterThan(scopeVisual.clientWidth)
})
"""
if old_e2e in e2e:
    e2e = e2e.replace(old_e2e, new_e2e, 1)
elif new_e2e not in e2e:
    raise SystemExit('A1 extreme-data E2E contract does not match audited head')
e2e_path.write_text(e2e, encoding='utf-8')

unit_path = Path('frontend/tests/studentAffairs.v6Dashboard.test.mjs')
unit = unit_path.read_text(encoding='utf-8')
old_unit = """  assert.match(source, /<ul class=\"sa-v6-queue\"/); assert.match(source, /:focus-visible/)
})
"""
new_unit = """  assert.match(source, /<ul class=\"sa-v6-queue\"/); assert.match(source, /:focus-visible/)
  assert.match(source, /\\.sa-v6-scope-grid dd\\s*\\{[\\s\\S]*?overflow:\\s*hidden;[\\s\\S]*?text-overflow:\\s*ellipsis;[\\s\\S]*?white-space:\\s*nowrap;/)
})
"""
if old_unit in unit:
    unit = unit.replace(old_unit, new_unit, 1)
elif new_unit not in unit:
    raise SystemExit('A1 static visual contract does not match audited head')
unit_path.write_text(unit, encoding='utf-8')
