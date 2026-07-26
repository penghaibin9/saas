import { defineStore } from 'pinia'
import { teacherInternshipContext } from '@/services/internshipApi'

const STORAGE_KEY = 'gx_internship_context_v1'

function matches(code, patterns) {
  return (patterns || []).some((p) => {
    if (p === '*' || p === code) return true
    if (p.endsWith('.*')) return code === p.slice(0, -2) || code.startsWith(p.slice(0, -1))
    if (p.startsWith('*.')) return code.endsWith(p.slice(1))
    return false
  })
}

export const useInternshipContextStore = defineStore('internshipContext', {
  state: () => ({
    loaded: false,
    loading: false,
    error: '',
    roleCode: '',
    permissionPatterns: [],
    permissionVersion: '',
    batches: [],
    selectedBatchId: ''
  }),
  getters: {
    selectedBatch: (s) => s.batches.find((b) => String(b.id) === String(s.selectedBatchId)) || null
  },
  actions: {
    can(code) {
      return matches(code, this.permissionPatterns)
    },
    persist() {
      try {
        uni.setStorageSync(STORAGE_KEY, JSON.stringify({
          selectedBatchId: this.selectedBatchId,
          roleCode: this.roleCode,
          permissionVersion: this.permissionVersion
        }))
      } catch (e) {}
    },
    restore() {
      try {
        const raw = uni.getStorageSync(STORAGE_KEY)
        if (!raw) return
        const saved = JSON.parse(raw)
        this.selectedBatchId = saved.selectedBatchId || ''
        this.roleCode = saved.roleCode || ''
        this.permissionVersion = saved.permissionVersion || ''
      } catch (e) {}
    },
    async load(force = false) {
      if (this.loading) return this.selectedBatchId
      if (this.loaded && !force) return this.selectedBatchId
      this.loading = true
      this.error = ''
      try {
        const data = await teacherInternshipContext()
        const oldRole = this.roleCode
        this.roleCode = data.roleCode || ''
        this.permissionPatterns = data.permissionPatterns || []
        this.permissionVersion = data.permissionVersion || ''
        this.batches = data.batches || []
        const exists = this.batches.some((b) => String(b.id) === String(this.selectedBatchId))
        if (!exists || (oldRole && oldRole !== this.roleCode)) {
          this.selectedBatchId = data.defaultBatchId || (this.batches[0] && String(this.batches[0].id)) || ''
        }
        this.loaded = true
        this.persist()
        return this.selectedBatchId
      } catch (e) {
        this.loaded = false
        this.error = (e && e.message) || '实习批次加载失败'
        throw e
      } finally {
        this.loading = false
      }
    },
    selectBatch(batchId) {
      const value = String(batchId || '')
      if (value && !this.batches.some((b) => String(b.id) === value)) return false
      this.selectedBatchId = value
      this.persist()
      return true
    },
    clear() {
      this.loaded = false
      this.loading = false
      this.error = ''
      this.roleCode = ''
      this.permissionPatterns = []
      this.permissionVersion = ''
      this.batches = []
      this.selectedBatchId = ''
      try { uni.removeStorageSync(STORAGE_KEY) } catch (e) {}
    }
  }
})

export default useInternshipContextStore
