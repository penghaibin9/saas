/**
 * 学工待办下钻公共筛选语义单测。
 */
import { describe, expect, it } from 'vitest'
import {
  resolveTodoStatus,
  rowMatchesTodoStatus,
  readStudentFilter
} from '@/modules/studentAffairs/utils/todoFilterSemantics.js'

describe('todoFilterSemantics', () => {
  it('resolveTodoStatus aid PENDING → REVIEW', () => {
    const r = resolveTodoStatus('aid', 'PENDING')
    expect(r.activeKey).toBe('REVIEW')
    expect(r.matchStatuses).toContain('CLASS_REVIEW')
    expect(r.matchStatuses).toContain('SCHOOL_REVIEW')
  })

  it('resolveTodoStatus aid ADJUST_PENDING → ADJUST_REVIEW', () => {
    expect(resolveTodoStatus('aid', 'ADJUST_PENDING').activeKey).toBe('ADJUST_REVIEW')
  })

  it('resolveTodoStatus discipline REMOVE_PENDING → REMOVE_REVIEW', () => {
    expect(resolveTodoStatus('discipline', 'REMOVE_PENDING').activeKey).toBe('REMOVE_REVIEW')
  })

  it('resolveTodoStatus risk PENDING maps 待处置', () => {
    const r = resolveTodoStatus('risk', 'PENDING')
    expect(r.activeKey).toBe('PENDING')
    expect(r.matchStatuses).toEqual(expect.arrayContaining(['NEW', 'ASSIGNED']))
  })

  it('resolveTodoStatus dormException PENDING → PENDING_HANDLE', () => {
    expect(resolveTodoStatus('dormException', 'PENDING').activeKey).toBe('PENDING_HANDLE')
  })

  it('rowMatchesTodoStatus honors matchStatuses', () => {
    const r = resolveTodoStatus('funding', 'PENDING')
    expect(rowMatchesTodoStatus('COUNSELOR_REVIEW', r)).toBe(true)
    expect(rowMatchesTodoStatus('GRANTED', r)).toBe(false)
  })

  it('readStudentFilter reads studentId', () => {
    expect(readStudentFilter({ studentId: '12', studentNo: 'A001' })).toEqual({
      studentId: '12',
      studentNo: 'A001',
      studentName: ''
    })
  })
})
