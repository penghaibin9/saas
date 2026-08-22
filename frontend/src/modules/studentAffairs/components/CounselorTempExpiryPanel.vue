<template>
  <section class="temp-expiry" aria-label="临时代班到期治理">
    <div class="temp-expiry__copy">
      <strong>临时代班到期治理</strong>
      <span>生产环境由定时任务自动结束到期 TEMP；这里提供人工立即同步兜底，服务端幂等并保留 TEMP_EXPIRE 审计。</span>
    </div>
    <div class="temp-expiry__actions">
      <span v-if="result" class="temp-expiry__result">{{ result }}</span>
      <button type="button" :disabled="busy || !allowed" @click="scan">
        {{ busy ? '同步中…' : '同步到期代班' }}
      </button>
    </div>
    <AppInlineAlert v-if="error" type="warning" :description="error" />
  </section>
</template>

<script>
import { AppInlineAlert } from '@/components/common'
import { request } from '@/services/http/client'
import { matchPermission } from '@/config/navPlan'

export default {
  name: 'CounselorTempExpiryPanel',
  components: { AppInlineAlert },
  props: { ctx: { type: Object, default: null } },
  data() { return { busy: false, result: '', error: '' } },
  computed: {
    allowed() {
      const patterns = this.ctx?.permissionPatterns
      return Array.isArray(patterns) && matchPermission(patterns, 'studentAffairs.class.create')
    }
  },
  methods: {
    async scan() {
      if (this.busy || !this.allowed) return
      this.busy = true
      this.result = ''
      this.error = ''
      try {
        const data = await request('/student-affairs/counselor-assignments/scan-expired', { method: 'POST', body: {} })
        this.result = `本次结束 ${Number(data?.ended || 0)} 条；可安全重复执行`
        this.$emit('synced', data || {})
      } catch (error) {
        this.error = error?.message || '到期代班同步失败'
      } finally {
        this.busy = false
      }
    }
  }
}
</script>

<style scoped>
.temp-expiry { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px 16px; align-items: center; margin: 0 0 12px; padding: 11px 13px; border: 1px solid var(--border-light, #e5e7eb); border-radius: 10px; background: var(--bg-section, #f8fafc); }
.temp-expiry__copy { min-width: 0; display: grid; gap: 3px; }
.temp-expiry__copy strong { color: var(--text-primary, #0f172a); font-size: 13px; }
.temp-expiry__copy span, .temp-expiry__result { color: var(--text-tertiary, #64748b); font-size: 12px; }
.temp-expiry__actions { display: flex; align-items: center; justify-content: flex-end; gap: 8px; flex-wrap: wrap; }
.temp-expiry button { border: 1px solid var(--primary-300, #93c5fd); border-radius: 8px; background: var(--bg-card, #fff); color: var(--primary-700, #1d4ed8); padding: 7px 10px; cursor: pointer; }
.temp-expiry button:disabled { cursor: not-allowed; opacity: .55; }
.temp-expiry :deep(.app-inline-alert) { grid-column: 1 / -1; }
@media (max-width: 760px) { .temp-expiry { grid-template-columns: 1fr; } .temp-expiry__actions { justify-content: flex-start; } }
</style>