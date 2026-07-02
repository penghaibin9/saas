import { defineStore } from 'pinia'
import { getTeacherWorkbench } from '../services/mock'

/**
 * useTeacherWorkbenchStore 教师工作台数据
 * 契约：loading / error / data / refresh() / reset()
 */
export const useTeacherWorkbenchStore = defineStore('teacherWorkbench', {
  state: () => ({
    loading: false,
    error: null,
    data: null
  }),
  getters: {
    viewState(s) {
      if (s.loading) return 'loading'
      if (s.error) return 'error'
      if (!s.data) return 'empty'
      return 'ready'
    },
    todos: (s) => (s.data ? s.data.todos : []),
    riskStudents: (s) => (s.data ? s.data.riskStudents : [])
  },
  actions: {
    async refresh(teacherId) {
      this.loading = true
      this.error = null
      try {
        this.data = await getTeacherWorkbench(teacherId)
      } catch (e) {
        this.error = e.message || '加载失败'
      } finally {
        this.loading = false
      }
    },
    reset() {
      this.loading = false
      this.error = null
      this.data = null
    }
  }
})
