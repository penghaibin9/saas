<template>
  <ModulePageShell
    title="消息设置"
    subtitle="仅控制外部打扰渠道；站内正式消息不会因关闭推送而消失"
  >
    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else-if="data" class="mc-settings">
      <p class="mc-settings__note">{{ data.note }}</p>

      <section class="mc-panel">
        <h3>分类偏好</h3>
        <div v-for="p in data.preferences || []" :key="p.key" class="pref-row">
          <span>{{ p.label }}</span>
          <button
            type="button"
            class="switch"
            :class="{ on: p.enabled }"
            :disabled="busy"
            @click="toggle(p)"
          >
            <span />
          </button>
        </div>
      </section>

      <section class="mc-panel">
        <h3>渠道</h3>
        <div v-for="c in data.channels || []" :key="c.key" class="ch-row">
          <div>
            <div class="ch-title">{{ c.label }}</div>
            <div class="ch-hint">{{ c.hint }}</div>
          </div>
          <strong :class="{ warn: c.status === 'NOT_CONFIGURED' }">
            {{ statusLabel(c.status) }}
          </strong>
        </div>
      </section>

      <section class="mc-panel">
        <h3>静默时段</h3>
        <p class="ch-hint">
          {{ (data.quietHours && data.quietHours.hint) || '紧急消息可绕过静默时段' }}
          （{{ data.quietHours && data.quietHours.start }} – {{ data.quietHours && data.quietHours.end }}）
          <template v-if="data.quietHours && data.quietHours.inQuietNow"> · 当前处于静默窗</template>
        </p>
      </section>

      <section class="mc-panel">
        <h3>发布频控</h3>
        <p class="ch-hint">
          {{ (data.rateLimit && data.rateLimit.hint) || '同发布人滚动窗口内限制发布次数' }}
          （上限 {{ (data.rateLimit && data.rateLimit.maxPerHour) || 20 }} 次/小时）
        </p>
      </section>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import {
  fetchMessageSettings,
  setMessagePreference
} from '@/modules/messageCenter/api/message-campaign.api'

export default {
  name: 'MessageSettingsView',
  components: { ModulePageShell, LoadingState, ErrorState },
  data() {
    return { loading: false, error: '', data: null, busy: false }
  },
  created() { this.load() },
  methods: {
    statusLabel(s) {
      return ({ FORCE_ON: '强制开启', READY: '可用', NOT_CONFIGURED: '未配置' })[s] || s
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        this.data = await fetchMessageSettings()
      } catch (e) {
        this.error = (e && e.message) || '加载设置失败'
      } finally {
        this.loading = false
      }
    },
    async toggle(p) {
      this.busy = true
      try {
        const next = !p.enabled
        await setMessagePreference({ key: p.key, enabled: next })
        p.enabled = next
      } catch (e) {
        this.error = (e && e.message) || '保存失败'
      } finally {
        this.busy = false
      }
    }
  }
}
</script>

<style scoped>
.mc-settings__note {
  margin: 0 0 var(--space-4);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: 1.6;
}
.mc-panel {
  border: 1px solid var(--border-base); border-radius: 8px;
  padding: 14px 16px; margin-bottom: 12px; background: var(--bg-card); max-width: 640px;
}
.mc-panel h3 { margin: 0 0 10px; font-size: 14px; }
.pref-row, .ch-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 0; border-bottom: 1px solid var(--border-base);
}
.ch-title { font-size: 13.5px; }
.ch-hint { font-size: 12px; color: var(--text-tertiary); margin-top: 2px; }
.warn { color: #b45309; }
.switch {
  width: 40px; height: 22px; border-radius: 11px; border: none;
  background: #dde1e8; position: relative; cursor: pointer; padding: 0;
}
.switch.on { background: var(--primary-500, #2563eb); }
.switch span {
  position: absolute; top: 2px; left: 2px; width: 18px; height: 18px;
  border-radius: 50%; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.2);
  transition: left .15s;
}
.switch.on span { left: 20px; }
.switch:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
