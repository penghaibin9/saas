<template>
  <AppInlineAlert v-if="error" type="warning" :description="error" />
  <section v-else-if="loaded" class="sa-sla" aria-label="当前学校SLA规则">
    <div class="sa-sla__head">
      <span>当前学校 SLA</span>
      <small>服务器生效口径 · 只读</small>
    </div>

    <div v-if="kind !== 'leave'" class="sa-sla__group">
      <strong>风险处置</strong>
      <div class="sa-sla__items">
        <span v-for="level in riskLevels" :key="level.key">
          <b>{{ level.label }}</b>{{ display(level.value) }}
        </span>
      </div>
    </div>

    <div v-if="kind !== 'risk'" class="sa-sla__group">
      <strong>请假审批</strong>
      <div class="sa-sla__items">
        <span v-for="item in leaveItems" :key="item.key">
          <b>{{ item.label }}</b>{{ display(item.value) }}
        </span>
        <span v-if="!leaveItems.length">未配置</span>
      </div>
    </div>

    <p>页面不自行计算超时；dueAt / overdue / 升级等状态以后端事实为准。</p>
  </section>
</template>

<script>
import { AppInlineAlert } from '@/components/common'
import { request } from '@/services/http/client'

function titleCase(key) {
  return String(key || '').replace(/([A-Z])/g, ' $1').replace(/^./, (s) => s.toUpperCase()).trim()
}

export default {
  name: 'StudentAffairsSlaStrip',
  components: { AppInlineAlert },
  props: {
    kind: { type: String, default: 'both', validator: (v) => ['risk', 'leave', 'both'].includes(v) }
  },
  data() { return { loaded: false, error: '', config: { risk: {}, leave: {} } } },
  computed: {
    riskLevels() {
      const source = this.config.risk || {}
      return [
        { key: 'CRITICAL', label: '危急', value: source.CRITICAL },
        { key: 'HIGH', label: '高', value: source.HIGH },
        { key: 'MEDIUM', label: '中', value: source.MEDIUM },
        { key: 'LOW', label: '低', value: source.LOW }
      ]
    },
    leaveItems() {
      const source = this.config.leave || {}
      return Object.entries(source).map(([key, value]) => ({ key, label: titleCase(key), value }))
    }
  },
  created() { this.load() },
  methods: {
    async load() {
      try {
        this.config = await request('/student-affairs/sla-config') || { risk: {}, leave: {} }
        this.loaded = true
      } catch (error) {
        this.error = error?.message || '当前学校 SLA 读取失败'
      }
    },
    display(value) {
      if (value == null || value === '') return '未配置'
      if (typeof value === 'object') {
        return Object.entries(value).map(([k, v]) => `${titleCase(k)}=${v}`).join(' · ') || '未配置'
      }
      return String(value)
    }
  }
}
</script>

<style scoped>
.sa-sla { display: grid; gap: 8px; padding: 11px 13px; border: 1px solid var(--border-light, #e5e7eb); border-radius: 10px; background: var(--bg-section, #f8fafc); }
.sa-sla__head { display: flex; gap: 8px; align-items: baseline; flex-wrap: wrap; }
.sa-sla__head span { font-weight: 700; color: var(--text-primary, #0f172a); }
.sa-sla__head small, .sa-sla p { color: var(--text-tertiary, #64748b); font-size: 12px; }
.sa-sla__group { display: grid; gap: 5px; }
.sa-sla__group > strong { color: var(--text-secondary, #475569); font-size: 12px; }
.sa-sla__items { display: flex; flex-wrap: wrap; gap: 8px 16px; font-size: 13px; }
.sa-sla__items span { display: inline-flex; gap: 5px; }
.sa-sla__items b { color: var(--text-secondary, #475569); }
.sa-sla p { margin: 0; }
</style>