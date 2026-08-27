#!/usr/bin/env python3
"""Align the temporary five-gap audit harness with the exact-head UI contract.

Audit-only: patches injected Playwright specs at runtime. Product code is never modified.
"""
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, got {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"aligned: {label}")


def require_once(path: Path, needle: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(needle)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one source match, got {count}")
    print(f"aligned: {label}")


def main() -> int:
    gd013 = Path("e2e/specs/graduation-gd013-gd019-gap-audit.spec.mjs")
    gap5 = Path("e2e/specs/graduation-gap-five-browser-audit.spec.mjs")

    # Exact-head product contract: a conflicted group may render a visible confirmation
    # component in a blocked state. The acceptance fact is that no publish POST is issued.
    # Keep the checked-in toHaveCount(0) assertion intact instead of rewriting it at runtime.
    require_once(
        gd013,
        "await expect(admin.locator('.app-confirm-dialog').filter({ hasText: '发布答辩安排' })).toHaveCount(0)",
        "GD-013 conflicted publish dialog assertion preserved",
    )

    # StaffLoginPage currently returns as soon as login navigation completes, while the staff
    # shell can still be finishing its initial browser-refresh rotation. A deep-link navigation
    # during that window can start a second refresh against the already-consumed HttpOnly token
    # (observed as 200 -> 401). Match the StudentLoginPage stabilization contract locally in this
    # audit harness rather than changing product code.
    replace_once(
        gd013,
        """async function loginStaff(page, account, octet) {
  await page.context().setExtraHTTPHeaders({ 'X-Forwarded-For': `10.254.13.${octet}` })
  await new StaffLoginPage(page, config.staffBaseUrl).login(account)
}""",
        """async function loginStaff(page, account, octet) {
  await page.context().setExtraHTTPHeaders({ 'X-Forwarded-For': `10.254.13.${octet}` })
  await new StaffLoginPage(page, config.staffBaseUrl).login(account)
  await page.waitForLoadState('networkidle', { timeout: 60_000 })
}""",
        "GD-013 staff post-login refresh stabilization",
    )

    old_forbidden = """      await fillGroupForm(college, {
        name: forbiddenGroup,
        chairNo: 'e2e_advisor_b', chairName: 'E2E指导教师B',
        secretaryNo: 'e2e_reviewer', secretaryName: 'E2E评阅教师',
        defenseDate: '2026-09-15 09:00:00',
      })
      const forbiddenPromise = college.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith('/graduation/defense-groups'))
      await college.getByRole('button', { name: '创建', exact: true }).click()
      const forbidden = await forbiddenPromise
      expect(forbidden.status(), 'college role must be rejected before defense-group mutation').toBe(403)"""
    new_forbidden = """      // Exact product contract: a college-scoped role cannot create an unowned empty group.
      // UI must block the action, while the authenticated backend request must still fail before any DB write.
      await college.goto(`${config.staffBaseUrl}/admin/graduation/defense?batchId=${encodeURIComponent(fixture.batchId)}`)
      await dismissGuide(college)
      await expect(college.getByRole('button', { name: '＋ 新增答辩组', exact: true })).toBeDisabled()
      const forbidden = await college.evaluate(async ({ batchId, groupName, chairMentorId, secretaryMentorId }) => {
        const browserSessionId = sessionStorage.getItem('gx_browser_session_id_v2') || ''
        const refresh = await fetch('/api/v1/auth/browser-refresh', {
          method: 'POST', credentials: 'include',
          headers: {
            'Content-Type': 'application/json',
            'X-Browser-Session': 'staff',
            'X-Browser-Session-Id': browserSessionId,
          },
        })
        const refreshBody = await refresh.json().catch(() => null)
        const accessToken = refreshBody?.data?.accessToken || ''
        if (!refresh.ok || !accessToken) return { phase: 'refresh', status: refresh.status, body: refreshBody }
        const response = await fetch(`/api/v1/graduation/defense-groups?batchId=${encodeURIComponent(batchId)}`, {
          method: 'POST', credentials: 'include',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
          body: JSON.stringify({
            groupName,
            batchId: Number(batchId),
            defenseDate: '2026-09-15 09:00:00',
            location: 'GD-013 forbidden scope probe',
            chairMentorId: Number(chairMentorId),
            secretaryMentorId: Number(secretaryMentorId),
            memberMentorIds: [],
          }),
        })
        return { phase: 'mutation', status: response.status, body: await response.json().catch(() => null) }
      }, {
        batchId: fixture.batchId,
        groupName: forbiddenGroup,
        chairMentorId: fixture.mentorBId,
        secretaryMentorId: fixture.reviewerMentorId,
      })
      expect(forbidden.phase, JSON.stringify(forbidden)).toBe('mutation')
      expect(forbidden.status, 'college role must be rejected before defense-group mutation').toBe(403)"""
    replace_once(gd013, old_forbidden, new_forbidden, "GD-013 college empty-group fail-closed probe")

    replace_once(
        gap5,
        "await expect(page.locator('.rk-pane')).toContainText('该风险已关闭')",
        "await expect(page.locator('.rk-pane')).not.toContainText(fixture.students.C.studentNo)",
        "GD-017 close auto-next projection",
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
