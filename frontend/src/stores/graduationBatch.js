import { defineStore } from 'pinia'
import { graduationBatchApi } from '@/modules/graduation/api/graduation-batch.api'

const STORAGE_KEY = 'graduation.selectedBatchId'

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
 * 毕业设计中心统一批次上下文。
 * 选择优先级：URL query.batchId → 本地上次选择 → 唯一 RUNNING → 多 RUNNING 须用户选 → 全部有效批次。
 * 禁止把「查询结果第一条」当作永久当前批次。
 */
export const useGraduationBatchStore = defineStore('graduationBatch', {
  state: () => ({
    selectedBatchId: '',
    selectedBatchName: '',
    academicYear: '',
    gradeYear: '',
    batchStatus: '',
    currentStage: '',
    availableBatches: [],
    batchLoading: false,
    batchError: '',
    needsExplicitSelect: false,
    initialized: false
  }),
  getters: {
    hasBatch: (s) => !!s.selectedBatchId,
    selectedBatch: (s) => s.availableBatches.find((b) => String(b.id) === String(s.selectedBatchId)) || null
  },
  actions: {
    applyBatch(batch) {
      if (!batch) {
        this.selectedBatchId = ''
        this.selectedBatchName = ''
        this.academicYear = ''
        this.gradeYear = ''
        this.batchStatus = ''
        this.currentStage = ''
        writeStoredBatchId('')
        return
      }
      this.selectedBatchId = String(batch.id)
      this.selectedBatchName = batch.batchName || ''
      this.academicYear = batch.academicYear || ''
      this.gradeYear = batch.gradeYear || ''
      this.batchStatus = batch.status || ''
      this.currentStage = batch.currentStage || batch.stage || ''
      writeStoredBatchId(this.selectedBatchId)
    },
    /**
     * @param {{ batchIdFromUrl?: string, force?: boolean }} opts
     */
    async ensureLoaded(opts = {}) {
      if (this.initialized && !opts.force && !opts.batchIdFromUrl) return
      this.batchLoading = true
      this.batchError = ''
      try {
        const res = await graduationBatchApi.getBatches({ page: 1, pageSize: 200 })
        if (res.code !== 0) {
          this.batchError = res.message || '批次列表加载失败'
          this.availableBatches = []
          this.applyBatch(null)
          this.needsExplicitSelect = false
          return
        }
        const list = (res.data && res.data.list) || []
        // 有效批次：未作废
        this.availableBatches = list.filter((b) => b.status !== 'VOIDED')
        const running = this.availableBatches.filter((b) => b.status === 'RUNNING')
        const urlId = opts.batchIdFromUrl ? String(opts.batchIdFromUrl) : ''
        const storedId = readStoredBatchId()

        let chosen = null
        this.needsExplicitSelect = false

        if (urlId) {
          chosen = this.availableBatches.find((b) => String(b.id) === urlId) || null
        }
        if (!chosen && storedId) {
          chosen = this.availableBatches.find((b) => String(b.id) === storedId) || null
        }
        if (!chosen) {
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
      this.applyBatch(batch)
      this.needsExplicitSelect = !batch && this.availableBatches.length > 1
    },
    clearSelection() {
      this.applyBatch(null)
      this.needsExplicitSelect = this.availableBatches.length > 1
    }
  }
})
