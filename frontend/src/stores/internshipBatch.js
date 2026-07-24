import { defineStore } from 'pinia'
import { internshipApi } from '@/modules/internship/api/internship.api'

const STORAGE_KEY = 'internship.selectedBatchId'

function readStoredBatchId() {
  try {
    return window.localStorage.getItem(STORAGE_KEY) || ''
  } catch {
    return ''
  }
}

function writeStoredBatchId(id) {
  try {
    if (id) window.localStorage.setItem(STORAGE_KEY, String(id))
    else window.localStorage.removeItem(STORAGE_KEY)
  } catch { /* ignore */ }
}

/**
 * 岗位实习中心统一批次上下文。
 * 优先级：URL query.batchId → 本地上次选择 → 唯一 RUNNING → 多 RUNNING 须用户选。
 * 禁止把「查询结果第一条」当作永久当前批次。
 */
export const useInternshipBatchStore = defineStore('internshipBatch', {
  state: () => ({
    selectedBatchId: '',
    selectedBatchName: '',
    batchNo: '',
    batchStatus: '',
    startDate: '',
    endDate: '',
    availableBatches: [],
    batchLoading: false,
    batchError: '',
    needsExplicitSelect: false,
    invalidUrlBatch: false,
    initialized: false
  }),
  getters: {
    hasBatch: (s) => !!s.selectedBatchId,
    selectedBatch: (s) => s.availableBatches.find((b) => String(b.id) === String(s.selectedBatchId)) || null,
    canWriteStudents: (s) => {
      const st = s.batchStatus
      return !!s.selectedBatchId && !['VOIDED', 'ARCHIVED', 'CLOSED'].includes(st)
    }
  },
  actions: {
    applyBatch(batch) {
      if (!batch) {
        this.selectedBatchId = ''
        this.selectedBatchName = ''
        this.batchNo = ''
        this.batchStatus = ''
        this.startDate = ''
        this.endDate = ''
        writeStoredBatchId('')
        return
      }
      this.selectedBatchId = String(batch.id)
      this.selectedBatchName = batch.batchName || ''
      this.batchNo = batch.batchNo || ''
      this.batchStatus = batch.status || ''
      this.startDate = (batch.startDate || '').toString().slice(0, 10)
      this.endDate = (batch.endDate || '').toString().slice(0, 10)
      writeStoredBatchId(this.selectedBatchId)
    },
    /**
     * @param {{ batchIdFromUrl?: string, force?: boolean }} opts
     */
    async ensureLoaded(opts = {}) {
      if (this.initialized && !opts.force && !opts.batchIdFromUrl) return
      this.batchLoading = true
      this.batchError = ''
      this.invalidUrlBatch = false
      try {
        const res = await internshipApi.getBatches({ page: 1, pageSize: 200 })
        if (res.code !== 0) {
          this.batchError = res.message || '批次列表加载失败'
          this.availableBatches = []
          this.applyBatch(null)
          this.needsExplicitSelect = false
          return
        }
        const list = (res.data && res.data.list) || []
        this.availableBatches = list.filter((b) => b.status !== 'VOIDED')
        const running = this.availableBatches.filter((b) => b.status === 'RUNNING')
        const urlId = opts.batchIdFromUrl ? String(opts.batchIdFromUrl) : ''
        const storedId = readStoredBatchId()

        let chosen = null
        this.needsExplicitSelect = false

        if (urlId) {
          chosen = this.availableBatches.find((b) => String(b.id) === urlId) || null
          if (!chosen) {
            this.invalidUrlBatch = true
            this.batchError = 'URL 中的批次无效或不属于当前租户，请重新选择'
            this.needsExplicitSelect = true
          }
        }
        if (!chosen && !this.invalidUrlBatch && storedId) {
          chosen = this.availableBatches.find((b) => String(b.id) === storedId) || null
        }
        if (!chosen && !this.invalidUrlBatch) {
          if (running.length === 1) {
            chosen = running[0]
          } else if (running.length > 1) {
            this.needsExplicitSelect = true
            chosen = null
          } else if (this.availableBatches.length === 1) {
            chosen = this.availableBatches[0]
          } else if (this.availableBatches.length > 1) {
            this.needsExplicitSelect = true
            chosen = null
          }
        }
        this.applyBatch(chosen)
        this.initialized = true
      } catch (e) {
        this.batchError = e?.message || '批次列表加载失败'
        this.availableBatches = []
        this.applyBatch(null)
      } finally {
        this.batchLoading = false
      }
    },
    selectBatch(batchOrId) {
      const id = typeof batchOrId === 'object' && batchOrId ? String(batchOrId.id) : String(batchOrId || '')
      const batch = this.availableBatches.find((b) => String(b.id) === id) || null
      this.invalidUrlBatch = false
      this.batchError = ''
      this.needsExplicitSelect = !batch && this.availableBatches.length > 1
      this.applyBatch(batch)
    },
    withBatchQuery(query = {}) {
      const q = { ...query }
      if (this.selectedBatchId) q.batchId = this.selectedBatchId
      else delete q.batchId
      return q
    }
  }
})
