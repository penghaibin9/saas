import { defineStore } from 'pinia'

export const useUiStore = defineStore('internship-student-ui', {
  state: () => ({ toast: '' }),
  actions: {
    notify(message) {
      this.toast = String(message || '')
      if (this.toast) setTimeout(() => { this.toast = '' }, 2600)
    }
  }
})
