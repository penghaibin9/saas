/** 全局 UI 状态：加载/全局错误提示（轻量）。 */
import { defineStore } from 'pinia'

export const useUiStore = defineStore('sp-ui', {
  state: () => ({ loading: false, toast: '' }),
  actions: {
    setLoading(v) { this.loading = !!v },
    notify(msg) {
      this.toast = msg || ''
      if (msg) setTimeout(() => { this.toast = '' }, 2600)
    }
  }
})
