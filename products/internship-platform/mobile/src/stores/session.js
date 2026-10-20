import { defineStore } from 'pinia'
function readIdentity() {
  try {
    const raw = uni.getStorageSync('gx_session_v1')
    if (raw && typeof raw === 'object') return raw.identity || raw
  } catch (e) {}
  return {}
}
export const useSessionStore = defineStore('standalone-session', {
  state: () => ({ identity: readIdentity() }),
  actions: {
    restore() { this.identity = readIdentity(); return this.identity },
    setIdentity(value) { this.identity = value && typeof value === 'object' ? value : {} }
  }
})
