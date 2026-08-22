<template>
  <AppInlineAlert v-if="error" type="warning" :description="error" />
  <section v-else-if="loaded" class="sa-sla" aria-label="当前学校办理时限">
    <div class="sa-sla__head">
      <div>
        <span>当前学校办理时限</span>
        <small>风险处置与请假审批的执行标准</small>
      </div>
      <em>学校当前生效标准 · 仅供查看</em>
    </div>

    <div v-if="kind !== 'leave'" class="sa-sla__group">
      <div class="sa-sla__group-title">
        <strong>风险处置时限</strong>
        <span>不同风险等级执行不同的分派、处理和跟进时限</span>
      </div>
      <div class="sa-sla__risk-grid">
        <article v-for="level in riskLevels" :key="level.key" class="sa-sla__risk-card" :class="`is-${level.tone}`">
          <div class="sa-sla__level">
            <i aria-hidden="true"></i>
            <b>{{ level.label }}风险</b>
          </div>
          <div class="sa-sla__metrics">
            <span v-for="metric in riskMetrics(level.value)" :key="metric.key">
              <small>{{ metric.label }}</small>
              <b>{{ metric.value }}</b>
            </span>
          </div>
        </article>
      </div>
    </div>

    <div v-if="kind !== 'risk'" class="sa-sla__group">
      <div class="sa-sla__group-title">
        <strong>请假办理时限</strong>
        <span>审批、提醒、销假和续假分别计算</span>
      </div>
      <div class="sa-sla__leave-grid">
        <article v-for="item in leaveItems" :key="item.key">
          <span>{{ item.label }}</span>
          <b>{{ leaveTimeText(item) }}</b>
          <small>{{ item.description }}</small>
        </article>
      </div>
    </div>

    <p class="sa-sla__note">办理期限、是否超时及自动升级结果，均以系统实时状态为准。</p>
  </section>
</template>

<script>
import { AppInlineAlert } from '@/components/common'
import { request } from '@/services/http/client'

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
        { key: 'CRITICAL', label: '危急', tone: 'critical', value: source.CRITICAL },
        { key: 'HIGH', label: '高', tone: 'high', value: source.HIGH },
        { key: 'MEDIUM', label: '中', tone: 'medium', value: source.MEDIUM },
        { key: 'LOW', label: '低', tone: 'low', value: source.LOW }
      ]
    },
    leaveItems() {
      const source = this.config.leave || {}
      return [
        { key: 'approvalHours', label: '请假审批', description: '完成请假申请审批', value: source.approvalHours },
        { key: 'nearDueHours', label: '临近超时提醒', description: '在审批超时前发出提醒', value: source.nearDueHours, advance: true },
        { key: 'cancelHours', label: '销假审批', description: '完成学生销假审批', value: source.cancelHours },
        { key: 'extensionApprovalHours', label: '续假审批', description: '完成学生续假审批', value: source.extensionApprovalHours }
      ]
    }
  },
  created() { this.load() },
  methods: {
    async load() {
      try {
        this.config = await request('/student-affairs/sla-config') || { risk: {}, leave: {} }
        this.loaded = true
      } catch (error) {
        this.error = error?.message || '当前学校办理时限读取失败'
      }
    },
    hourText(value) {
      return value == null || value === '' ? '未配置' : `${value}小时`
    },
    riskMetrics(value = {}) {
      return [
        { key: 'assignHours', label: '分派', value: this.hourText(value?.assignHours) },
        { key: 'processHours', label: '处理', value: this.hourText(value?.processHours) },
        { key: 'followHours', label: '跟进', value: this.hourText(value?.followHours) }
      ]
    },
    leaveTimeText(item) {
      if (item.value == null || item.value === '') return '未配置'
      return item.advance ? `提前${item.value}小时` : `${item.value}小时内`
    }
  }
}
</script>

<style scoped>
.sa-sla {
  display: grid;
  gap: 16px;
  padding: 16px;
  border: 1px solid var(--border-light, #dce5f1);
  border-radius: 14px;
  background: linear-gradient(135deg, #f8fbff 0%, #f4f7fc 100%);
}
.sa-sla__head { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.sa-sla__head > div { display: grid; gap: 3px; }
.sa-sla__head span { color: var(--text-primary, #0f172a); font-size: 16px; font-weight: 750; }
.sa-sla__head small { color: var(--text-tertiary, #64748b); font-size: 12px; }
.sa-sla__head em {
  padding: 5px 10px;
  border: 1px solid #d6e3f5;
  border-radius: 999px;
  background: #fff;
  color: #55708f;
  font-size: 12px;
  font-style: normal;
  white-space: nowrap;
}
.sa-sla__group { display: grid; gap: 9px; }
.sa-sla__group-title { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.sa-sla__group-title strong { color: var(--text-secondary, #334155); font-size: 13px; }
.sa-sla__group-title span { color: var(--text-tertiary, #7b8ba3); font-size: 12px; }
.sa-sla__risk-grid, .sa-sla__leave-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.sa-sla__risk-card, .sa-sla__leave-grid article {
  min-width: 0;
  padding: 11px 12px;
  border: 1px solid #e0e7f0;
  border-radius: 10px;
  background: rgba(255, 255, 255, .92);
}
.sa-sla__level { display: flex; align-items: center; gap: 7px; margin-bottom: 9px; color: #334155; font-size: 13px; }
.sa-sla__level i { width: 7px; height: 7px; border-radius: 50%; background: #94a3b8; }
.sa-sla__risk-card.is-critical .sa-sla__level i { background: #dc2626; }
.sa-sla__risk-card.is-high .sa-sla__level i { background: #ea580c; }
.sa-sla__risk-card.is-medium .sa-sla__level i { background: #d89b08; }
.sa-sla__risk-card.is-low .sa-sla__level i { background: #2f80a3; }
.sa-sla__metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; }
.sa-sla__metrics span { display: grid; gap: 2px; padding-left: 7px; border-left: 1px solid #e5eaf1; }
.sa-sla__metrics small, .sa-sla__leave-grid small { color: #7b8ba3; font-size: 11px; }
.sa-sla__metrics b { color: #1e3a5f; font-size: 12px; white-space: nowrap; }
.sa-sla__leave-grid article { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: baseline; gap: 4px 10px; }
.sa-sla__leave-grid article > span { color: #475569; font-size: 12px; }
.sa-sla__leave-grid article > b { color: #174f91; font-size: 14px; white-space: nowrap; }
.sa-sla__leave-grid article > small { grid-column: 1 / -1; }
.sa-sla__note { margin: -2px 0 0; color: var(--text-tertiary, #7b8ba3); font-size: 12px; }
@media (max-width: 1100px) {
  .sa-sla__risk-grid, .sa-sla__leave-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 720px) {
  .sa-sla__head { align-items: flex-start; flex-direction: column; }
  .sa-sla__risk-grid, .sa-sla__leave-grid { grid-template-columns: 1fr; }
}
</style>
