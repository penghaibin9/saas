/**
 * 报到工作台待办队列（瞬态，仅前端内存）。
 *
 * 用途：从「报到进度跟踪」等列表页进入某个学生的一站式报到工作台时，把当前列表顺序的
 * 学生 id 队列带过来，供工作台提供「上一个 / 下一个待办」流水线导航，办完一个直接翻下一个，
 * 不用退回列表再找人。纯前端瞬态队列，刷新即清空，不落库、不含任何敏感信息（仅记录 id 顺序）。
 */
export const orientationWorklist = { ids: [], label: '' }

/** 进入工作台前由列表页调用，登记当前队列顺序（id 数组）。 */
export function setOrientationWorklist(ids, label = '报到进度') {
  orientationWorklist.ids = Array.isArray(ids) ? ids.map((v) => String(v)) : []
  orientationWorklist.label = label
}
