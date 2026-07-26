import { computed, reactive } from 'vue'

const LABELS = {
  overview: '毕设总览', topic: '选题', taskbook: '任务书', proposal: '开题',
  midterm: '中期检查', final: '成果提交', defense: '答辩安排', grade: '成绩',
  peer: '成果互查', archive: '材料归档'
}

const state = reactive({ errors: {} })

export function graduationSectionForPath(path) {
  const value = String(path || '').split('?')[0]
  if (value === '/mobile/graduation/my') return 'overview'
  if (value.includes('/graduation/active-round') || value.includes('/graduation/topics') || value.includes('/graduation/change-request')) return 'topic'
  if (value.includes('/graduation/taskbook')) return 'taskbook'
  if (value.includes('/graduation/proposal')) return 'proposal'
  if (value.includes('/graduation/midterm')) return 'midterm'
  if (value.includes('/graduation/final')) return 'final'
  if (value.includes('/graduation/defense')) return 'defense'
  if (value.includes('/graduation/grade')) return 'grade'
  if (value.includes('/graduation/peer')) return 'peer'
  if (value.includes('/graduation/archive')) return 'archive'
  return ''
}

export function clearGraduationSection(key) {
  if (key && state.errors[key]) delete state.errors[key]
}

export function failGraduationSection(key, message) {
  if (!key) return
  state.errors[key] = message || '数据加载失败'
}

export function clearGraduationHealth() {
  Object.keys(state.errors).forEach((key) => delete state.errors[key])
}

export function useGraduationHealth() {
  const items = computed(() => Object.entries(state.errors).map(([key, message]) => ({
    key, label: LABELS[key] || key, message
  })))
  return { state, items, clear: clearGraduationHealth }
}
