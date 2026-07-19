<template>
  <AppPageShell
    title="谈心谈话台账"
    subtitle="全量谈话记录只读台账，按类型 / 状态筛选。心理类谈话原文由后端按角色脱敏。"
    role-name="学工处 / 学院 / 辅导员"
    data-scope-name="按数据范围（辅导员限绑定学生）"
    watermark-purpose="谈话台账查看"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载谈话台账..." @retry="load"
                    @back="$router.push('/admin/student-affairs/talk')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>

      <AppSectionCard title="谈话记录">
        <div class="tl-filters">
          <div class="tl-fgroup">
            <button v-for="f in typeFilters" :key="f.key" type="button" class="tl-chip"
                    :class="{ 'is-on': activeType === f.key }" @click="setType(f.key)">{{ f.label }}</button>
          </div>
          <div class="tl-fgroup">
            <button v-for="f in statusFilters" :key="f.key" type="button" class="tl-chip tl-chip--st"
                    :class="{ 'is-on': activeStatus === f.key }" @click="setStatus(f.key)">{{ f.label }}</button>
          </div>
        </div>
        <table class="sa-table">
          <thead><tr><th>学生</th><th>学号</th><th>类型</th><th>主题</th><th>谈话时间</th><th>需跟进</th><th>状态</th></tr></thead>
          <tbody>
            <tr v-for="t in items" :key="t.talkId">
              <td><strong>{{ t.realName || ('学生#' + t.studentId) }}</strong></td>
              <td>{{ t.studentNo || '—' }}</td>
              <td>
                {{ typeLabel(t.talkType) }}
                <span v-if="t.psyMasked" class="tl-psy" title="心理谈话原文受限">🔒</span>
              </td>
              <td class="tl-topic">{{ t.topic || '—' }}</td>
              <td><AppDateDisplay :value="t.talkAt" mode="datetime" empty-text="—" /></td>
              <td>{{ t.needFollow ? '是' : '—' }}</td>
              <td><StatusTag :type="statusType(t.status)" :label="t.statusLabel || t.status" dot /></td>
            </tr>
            <tr v-if="!items.length"><td colspan="7" class="sa-empty">当前范围与筛选下暂无谈话记录</td></tr>
          </tbody>
        </table>
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppDateDisplay, AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard, AppStatusTag } from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'

const TYPE_LABELS = { ACADEMIC: '学业', PSYCHOLOGY: '心理', LIFE: '生活', CAREER: '就业', DISCIPLINE: '违纪', ECONOMIC: '经济', IDEOLOGY: '思想', SAFETY: '安全', ROUTINE: '常规', OTHER: '其他' }
const TYPE_FILTERS = [{ key: '', label: '全部类型' }, { key: 'ACADEMIC', label: '学业' }, { key: 'PSYCHOLOGY', label: '心理' }, { key: 'LIFE', label: '生活' }, { key: 'DISCIPLINE', label: '违纪' }]
const STATUS_FILTERS = [
  { key: '', label: '全部状态' },
  { key: 'PLANNED', label: '计划中' },
  { key: 'COMPLETED', label: '已完成' },
  { key: 'FOLLOW_UP', label: '跟进中' },
  { key: 'CLOSED', label: '已关闭' }
]

export default {
  name: 'TalkLedgerView',
  components: { AppDateDisplay, AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard, StatusTag: AppStatusTag },
  data() {
    return { loading: true, errorMessage: '', items: [], counts: { total: 0 }, activeType: '', activeStatus: '', typeFilters: TYPE_FILTERS, statusFilters: STATUS_FILTERS }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const need = this.items.filter((x) => x.needFollow).length
      const planned = this.items.filter((x) => x.status === 'PLANNED').length
      return [
        { key: 't', label: '当前列表数', value: this.items.length, accent: 'primary' },
        { key: 'p', label: '计划中', value: planned, accent: 'warning' },
        { key: 'n', label: '需跟进', value: need, accent: need ? 'risk' : 'success' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      // 分页说明：/student-affairs/talks 后端已支持 page/pageSize/total 真分页，
      // 但本页顶部统计卡（当前列表数/计划中/需跟进）按已加载全部过滤结果实时计算；
      // 若接入逐页 AppPagination，卡片语义会变成“本页”而非“当前筛选下全部”，需产品确认展示口径后再引入。
      // 暂维持 pageSize=500 上限一次性加载（超过 500 条时会截断，暂无提示）。
      const params = { pageSize: 500 }
      if (this.activeType) params.talkType = this.activeType
      if (this.activeStatus) params.status = this.activeStatus
      const res = await studentAffairsApi.getTalks(params)
      if (res.code === 0 && res.data) {
        this.items = res.data.items || []
      } else {
        this.errorMessage = res.message || '谈话台账加载失败'
      }
      this.loading = false
    },
    setType(k) { if (this.activeType === k) return; this.activeType = k; this.load() },
    setStatus(k) { if (this.activeStatus === k) return; this.activeStatus = k; this.load() },
    typeLabel(t) { return TYPE_LABELS[t] || t || '—' },
    statusType(s) {
      if (s === 'COMPLETED' || s === 'CLOSED') return 'success'
      if (s === 'FOLLOW_UP') return 'processing'
      if (s === 'PLANNED') return 'warning'
      return 'default'
    }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.tl-filters { display: flex; flex-direction: column; gap: var(--space-2); margin-bottom: var(--space-3); }
.tl-fgroup { display: flex; gap: var(--space-2); flex-wrap: wrap; }
.tl-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 4px 14px; font-size: var(--font-size-sm); cursor: pointer; }
.tl-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-3); text-align: left; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.tl-topic { color: var(--text-secondary); max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tl-psy { font-size: var(--font-size-xs); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } }
</style>
