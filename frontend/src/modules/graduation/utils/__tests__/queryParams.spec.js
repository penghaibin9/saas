/**
 * 毕业设计查询参数构造：列表与导出共用，空串剔除、布尔转换、批次注入。
 */
import { describe, expect, it } from 'vitest'
import {
  buildStudentQuery,
  buildMaterialQuery,
  buildTopicLibQuery,
  exportFilenameHint
} from '@/modules/graduation/utils/queryParams.js'

describe('graduation queryParams', () => {
  it('buildStudentQuery omits empty and coerces bools', () => {
    const q = buildStudentQuery({
      keyword: '张',
      batchId: '',
      stage: 'GUIDING',
      hasTopic: 'false',
      materialComplete: 'true',
      riskLevel: ''
    }, { batchId: '99', page: 2, pageSize: 10 })
    expect(q).toEqual({
      keyword: '张',
      batchId: '99',
      stage: 'GUIDING',
      hasTopic: false,
      materialComplete: true,
      page: 2,
      pageSize: 10
    })
  })

  it('buildMaterialQuery passes status and batch', () => {
    expect(buildMaterialQuery({ status: 'PENDING_REVIEW', keyword: '' }, { batchId: '7' }))
      .toEqual({ status: 'PENDING_REVIEW', batchId: '7' })
  })

  it('buildTopicLibQuery handles uncategorized', () => {
    const q = buildTopicLibQuery({ category: '__uncat__', reviewStatus: 'PENDING' }, { batchId: '1' })
    expect(q.missingCategory).toBe(true)
    expect(q.category).toBeUndefined()
    expect(q.batchId).toBe('1')
  })

  it('exportFilenameHint sanitizes', () => {
    expect(exportFilenameHint('2026/届A', '材料不完整')).toBe('2026_届A_材料不完整')
  })
})
