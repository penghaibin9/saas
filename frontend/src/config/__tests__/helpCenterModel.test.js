import { describe, expect, it } from 'vitest'
import {
  ALL_HELP_ENTRIES,
  getHelpOverview,
  getHelpSections,
  getPriorityHelp,
  isHelpVisibleForRole,
  normalizeHelpRole,
  resolveHelpRole,
  searchHelpCenter
} from '../helpCenterModel'

describe('helpCenterModel', () => {
  it('keeps runtime help ids unique', () => {
    const ids = ALL_HELP_ENTRIES.map((entry) => entry.id)
    expect(new Set(ids).size).toBe(ids.length)
    expect(ids.length).toBeGreaterThan(20)
  })

  it('maps runtime role codes and user-facing labels to help roles', () => {
    expect(resolveHelpRole('SCHOOL_ADMIN')).toBe('school-admin')
    expect(resolveHelpRole('COUNSELOR')).toBe('student-affairs')
    expect(resolveHelpRole('GRADUATION_TEACHER')).toBe('teacher')
    expect(resolveHelpRole('', '教务管理员')).toBe('academic')
    expect(normalizeHelpRole('学生')).toBe('student')
  })

  it('does not use help filtering as an access-control boundary', () => {
    const legacyItem = { roles: ['未登记的新角色'] }
    expect(isHelpVisibleForRole(legacyItem, 'teacher')).toBe(true)
    expect(isHelpVisibleForRole({ roles: ['学生'] }, 'student')).toBe(true)
    expect(isHelpVisibleForRole({ roles: ['学生'] }, 'teacher')).toBe(false)
    expect(isHelpVisibleForRole({ roles: ['学生'] }, 'school-admin')).toBe(true)
  })

  it('searches operational details beyond title and keywords', () => {
    const results = searchHelpCenter('限期整改', { role: 'all' })
    expect(results.length).toBeGreaterThan(0)
    expect(results.some((entry) => entry.searchText.includes('限期整改'))).toBe(true)
  })

  it('returns valid priority entries and role-aware sections', () => {
    const priority = getPriorityHelp('school-admin', 6)
    expect(priority).toHaveLength(6)
    expect(priority.every((entry) => ALL_HELP_ENTRIES.includes(entry))).toBe(true)

    const sections = getHelpSections('student', '')
    expect(sections.length).toBeGreaterThan(0)
    expect(sections.every((section) => section.items.length > 0)).toBe(true)
  })

  it('reports a truthful overview from the runtime source', () => {
    const overview = getHelpOverview('all')
    expect(overview.total).toBe(ALL_HELP_ENTRIES.length)
    expect(overview.taskCards).toBeGreaterThan(0)
    expect(overview.flowGuides).toBeGreaterThan(0)
    expect(overview.visualGuides).toBeGreaterThan(0)
  })

  it('keeps embedded visual guides under the dedicated public help path', () => {
    const embedded = ALL_HELP_ENTRIES.filter((entry) => entry.item.embed)
    expect(embedded.length).toBeGreaterThan(0)
    expect(embedded.every((entry) => entry.item.embed.startsWith('/help/'))).toBe(true)
  })
})
