import { useGraduationBatchStore } from '@/stores/graduationBatch'

/**
 * 学校端毕业设计请求的唯一批次参数解析器。
 * batchId 是业务安全条件，不是展示参数；旧链接/并行标签页必须由后端二次校验。
 */
export function withGraduationBatch(params = {}, required = true) {
  const store = useGraduationBatchStore()
  const batchId = params.batchId || store.selectedBatchId
  if (required && !batchId) throw new Error('请先选择毕业设计批次')
  return batchId ? { ...params, batchId: String(batchId) } : { ...params }
}

export default withGraduationBatch
