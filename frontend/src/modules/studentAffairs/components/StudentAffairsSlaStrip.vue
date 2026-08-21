<template>
  <AppInlineAlert v-if="error" type="warning" :description="error" />
  <section v-else-if="loaded" class="sa-sla" aria-label="当前学校SLA规则">
    <div class="sa-sla__head">
      <span>当前学校 SLA</span>
      <small>服务器生效口径 · 只读</small>
    </div>
    <div v-if="kind === 'risk'" class="sa-sla__items">
      <span v-for="level in riskLevels" :key="level.key">
        <strong>{{ level.label }}</strong>{{ display(level.value) }}
      </span>
    </div>
    <div v-else class="sa-sla__items">
      <span v-for="item in leaveItems" :key="item.key">
        <strong>{{ item.label }}</strong>{{ display(item.value) }}
      </span>
    </div>
    <p>页面不自行计算超时；列表的 dueAt / overdue 等状态以后端事实为准。</p>
  </section>
</template>

<script>
import { AppInlineAlert } from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'

function titleCase(key) {
  return String(key || '').replace(/([A-Z])/g, ' $1').replace(/^./, (s) => s.toUpperCase()).trim()
}

export default {
  name: 'StudentAffairsSlaStrip',
  components: { AppInlineAlert },
  props: {
    kind: { type: String, default: 'risk', validator: (v) => ['risk', 'leave'].includes(v) }
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
      const res = await studentAffairsApi.getSlaConfig()
      if (res.code !== 0) { this.error = res.message || '当前学校 SLA 读取失败'; return }
      this.config = res.data || { risk: {}, leave: {} }
      this.loaded = true
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
.sa-sla__items { display: flex; flex-wrap: wrap; gap: 8px 16px; font-size: 13px; }
.sa-sla__items span { display: inline-flex; gap: 5px; }
.sa-sla__items strong { color: var(--text-secondary, #475569); }
.sa-sla p { margin: 0; }
</style>
