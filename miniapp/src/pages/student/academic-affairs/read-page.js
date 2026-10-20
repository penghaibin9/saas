import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'

// Page-local lifecycle for read-only academic screens. No shared cache or polling.
export const academicReadPage = {
  data() { return { readEpoch: 0, readIdentity: currentSessionGeneration(), readHidden: false, listLimit: 20 } },
  onShow() {
    if (this.readHidden || this.readIdentity !== currentSessionGeneration()) {
      this.readHidden = false
      this.load()
    }
  },
  onHide() { this.readHidden = true; this.readEpoch += 1 },
  onUnload() { this.readHidden = true; this.readEpoch += 1 },
  methods: {
    async readAcademic(loader, apply) {
      const identity = currentSessionGeneration()
      if (identity !== this.readIdentity) {
        if ('d' in this) this.d = null
        if ('data' in this) this.data = null
        this.listLimit = 20
        this.readIdentity = identity
        if (this.resetAcademicContext) this.resetAcademicContext()
      }
      const epoch = ++this.readEpoch
      if (this.restoreApplication) this.restoreApplication()
      const current = () => epoch === this.readEpoch && !this.readHidden && identity === currentSessionGeneration()
      this.state = 'loading'
      try {
        const result = await loader()
        if (!current()) return null
        if (!result || typeof result !== 'object') throw new Error('无法核对教务信息')
        apply(result)
        this.state = 'ready'
        return result
      } catch (error) {
        if (current()) {
          const forbidden = Number(error?.httpStatus || error?.statusCode) === 403 || /^403/.test(String(error?.code || '')) || error?.code === 'NO_PERMISSION'
          // Read-only pages opt in so a same-session 403 cannot leave a previous student's data visible.
          if (forbidden && this.clearReadDataOnForbidden) {
            if ('d' in this) this.d = null
            if ('data' in this) this.data = null
          }
          this.state = this.pendingApplication && (this.d || this.data) ? 'ready' : forbidden ? 'forbidden' : 'error'
          if (this.pendingApplication) this.applicationNotice = '结果待核实，本人记录暂时无法更新。已保留操作内容，请稍后重新核对。'
        }
        return null
      }
    }
  }
}
