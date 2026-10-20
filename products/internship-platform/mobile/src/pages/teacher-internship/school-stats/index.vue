<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="校级实习统计" subtitle="概况 · 去向 · 活动 · 质量" show-back />
    <view class="page-pad ss__context">
      <view v-if="batches.length" class="card ss__batch">
        <view><text class="ss__label">当前批次</text><text class="t-md t-bold">{{ batches[batchIndex]?.name || '请选择批次' }}</text></view>
        <picker :range="batchLabels" :value="batchIndex" @change="onBatch">
          <text class="ss__switch">切换 ▾</text>
        </picker>
      </view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view v-if="data" class="page-pad stack">
        <MobileInlineAlert type="info"
          description="所有比率均来自服务端全范围事实；零分母显示暂无数据。专业对口不等于已分配岗位，工资不跨币种混算。" />

        <view v-for="group in data.groups" :key="group.key" class="card ss">
          <view class="row-between ss__head">
            <view><text class="ss__eyebrow">{{ groupKey(group.key) }}</text><text class="t-lg t-bold">{{ group.label }}</text></view>
            <text class="ss__scope">{{ data.scope?.recordCount || 0 }} 人范围</text>
          </view>

          <view v-if="group.counters?.length" class="ss__counters">
            <view v-for="item in group.counters" :key="item.key">
              <text :class="{ 'is-danger': item.key === 'risk' && item.value }">{{ item.value }}</text>
              <text>{{ item.label }}</text>
            </view>
          </view>

          <view v-if="group.ratios?.length" class="ss__ratios">
            <view v-for="item in group.ratios" :key="item.key" class="ss__ratio">
              <view class="row-between">
                <view class="flex-1"><text class="ss__ratio-title">{{ item.label }}</text><text class="ss__ratio-note">{{ item.note }}</text></view>
                <text class="ss__ratio-value">{{ rateText(item) }}</text>
              </view>
              <view class="ss__bar"><view :style="{ width: barWidth(item) }" /></view>
              <text class="ss__ratio-fact">{{ item.numerator }}/{{ item.denominator }} · {{ item.source || '正式业务事实' }}</text>
            </view>
          </view>

          <view v-if="group.distribution?.length" class="ss__distribution">
            <view v-for="item in group.distribution" :key="item.key">
              <text>{{ item.label }}</text><text>{{ item.value }}</text>
            </view>
          </view>

          <view v-if="group.cityTop10" class="ss__cities">
            <text class="ss__section-title">实际工作城市 TOP10</text>
            <view v-if="group.cityTop10.length">
              <view v-for="item in group.cityTop10" :key="item.city" class="ss__city">
                <text>{{ item.city }}</text>
                <view class="ss__city-bar"><view :style="{ width: cityWidth(item.count, group.cityTop10) }" /></view>
                <text>{{ item.count }}</text>
              </view>
            </view>
            <text v-else class="ss__empty">暂无已审核实际工作城市数据</text>
          </view>

          <view v-if="group.metrics?.length" class="ss__ratios">
            <view v-for="item in group.metrics" :key="item.key" class="ss__ratio">
              <view class="row-between"><text class="ss__ratio-title">{{ item.label }}</text><text class="ss__ratio-value">{{ item.rate == null ? '暂无数据' : item.rate + '%' }}</text></view>
              <view class="ss__bar"><view :style="{ width: item.rate == null ? '0%' : Math.min(100, Math.max(0, item.rate)) + '%' }" /></view>
              <text class="ss__ratio-fact">{{ item.numerator }}/{{ item.denominator }} · {{ item.note }}</text>
            </view>
          </view>

          <view v-if="group.weeklyReportTasks" class="ss__task-fact">
            <text>周报频率 {{ frequencyLabel(group.weeklyReportTasks.frequency) }}</text>
            <text>应交 {{ group.weeklyReportTasks.expected }} · 已交 {{ group.weeklyReportTasks.submitted }}</text>
          </view>

          <view v-if="group.wageByCurrency" class="ss__wages">
            <text class="ss__section-title">当前有效工资版本</text>
            <view v-if="group.wageByCurrency.length" class="ss__wage-grid">
              <view v-for="item in group.wageByCurrency" :key="item.currency">
                <text class="ss__wage-amount">{{ item.currency }} {{ Number(item.averageActualAmount).toFixed(2) }}</text>
                <text class="ss__ratio-fact">{{ item.count }} 条 · 合计 {{ item.currency }} {{ Number(item.totalActualAmount).toFixed(2) }}</text>
              </view>
            </view>
            <text v-else class="ss__empty">暂无已确认工资单</text>
            <text class="ss__ratio-note">{{ group.wageNote }}</text>
          </view>
        </view>

        <view class="card ss__definitions">
          <text class="ss__section-title">口径说明</text>
          <view v-for="(value,key) in data.metricDefinitions" :key="key"><text>{{ definitionLabel(key) }}</text><text>{{ value }}</text></view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherInternshipProcurementStats } from '@/services/internshipApi'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { toast } from '@/utils/nav'

export default {
  data() {
    return { state: 'loading', data: null, batches: [], batchId: '', batchIndex: 0 }
  },
  computed: {
    context() { return useInternshipContextStore() },
    batchLabels() { return this.batches.map((b) => `${b.name} · ${b.studentCount}人`) }
  },
  onLoad() { this.load() },
  onPullDownRefresh() { this.load(() => uni.stopPullDownRefresh()) },
  methods: {
    groupKey(key) { return ({ overview: '01', destination: '02', activity: '03', quality: '04' })[key] || '' },
    definitionLabel(key) { return ({ majorMatch: '专业对口', reportCompletion: '报告完成', transfer: '转企转岗', wage: '工资', excellent: '优秀率' })[key] || key },
    frequencyLabel(value) { return value === 'BIWEEKLY' ? '每两周1篇' : value === 'WEEKLY' ? '每周1篇' : value || '未配置' },
    rateText(item) { return item.denominator ? `${item.rate}%` : '暂无数据' },
    barWidth(item) { return item.denominator ? Math.min(100, Math.max(0, Number(item.rate || 0))) + '%' : '0%' },
    cityWidth(count, items) {
      const max = Math.max(1, ...(items || []).map((item) => Number(item.count || 0)))
      return Math.round(Number(count || 0) / max * 100) + '%'
    },
    async load(done) {
      this.state = 'loading'
      try {
        this.context.restore()
        await this.context.load(true)
        if (!this.context.can('internship.stats.view')) {
          this.state = 'forbidden'; this.data = null; return
        }
        this.batches = this.context.batches || []
        this.batchId = this.context.selectedBatchId || ''
        this.batchIndex = Math.max(0, this.batches.findIndex((b) => String(b.id) === String(this.batchId)))
        if (!this.batchId) { this.data = null; this.state = 'ready'; return }
        this.data = await teacherInternshipProcurementStats(this.batchId)
        this.state = 'ready'
      } catch (e) { this.data = null; this.state = 'error'; toast(e?.message || '校级统计加载失败') }
      finally { if (done) done() }
    },
    async onBatch(e) {
      this.batchIndex = Number(e.detail.value) || 0
      this.context.selectBatch(this.batches[this.batchIndex]?.id)
      this.batchId = this.context.selectedBatchId
      await this.load()
    }
  }
}
</script>

<style scoped>
.ss__context{padding-bottom:0}.ss__batch{display:flex;align-items:center;justify-content:space-between;padding:12px}.ss__label,.ss__eyebrow,.ss__scope,.ss__ratio-note,.ss__ratio-fact,.ss__empty{display:block;font-size:10px;color:var(--text-tertiary);line-height:1.55}.ss__switch{color:var(--teacher-700);font-size:12px}.ss{display:flex;flex-direction:column;gap:12px;padding:14px}.ss__head{padding-bottom:4px}.ss__eyebrow{color:var(--teacher-700);font-weight:700}.ss__counters{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}.ss__counters view{padding:9px;border-radius:8px;background:var(--gray-50);text-align:center}.ss__counters text{display:block}.ss__counters text:first-child{font-size:21px;font-weight:700}.ss__counters text:last-child{margin-top:2px;font-size:9px;color:var(--text-tertiary)}.ss__counters .is-danger{color:var(--danger-600)}.ss__ratios{display:flex;flex-direction:column;gap:12px}.ss__ratio-title{display:block;font-size:13px;font-weight:600}.ss__ratio-value{font-size:18px;font-weight:700;color:var(--teacher-700)}.ss__bar{height:6px;margin:7px 0;border-radius:99px;background:var(--gray-100);overflow:hidden}.ss__bar view{height:100%;border-radius:99px;background:var(--teacher-600)}.ss__distribution{display:grid;grid-template-columns:repeat(2,1fr);gap:6px}.ss__distribution view{display:flex;justify-content:space-between;padding:9px;border-radius:8px;background:var(--gray-50);font-size:12px}.ss__distribution text:last-child{font-weight:700}.ss__section-title{display:block;font-size:13px;font-weight:600;margin-bottom:8px}.ss__cities{padding-top:4px}.ss__city{display:grid;grid-template-columns:80px 1fr 28px;gap:8px;align-items:center;margin:7px 0;font-size:11px}.ss__city-bar{height:7px;border-radius:99px;background:var(--gray-100);overflow:hidden}.ss__city-bar view{height:100%;background:var(--teacher-500)}.ss__task-fact{display:flex;justify-content:space-between;padding:9px;border-radius:8px;background:var(--primary-50);font-size:11px;color:var(--text-secondary)}.ss__wage-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:7px}.ss__wage-grid>view{padding:9px;border-radius:8px;background:var(--gray-50)}.ss__wage-amount{display:block;font-size:14px;font-weight:700}.ss__definitions{padding:14px}.ss__definitions>view{display:grid;grid-template-columns:72px 1fr;gap:8px;padding:7px 0;border-bottom:1px solid var(--border-light);font-size:11px;line-height:1.55}.ss__definitions>view text:first-child{color:var(--text-tertiary)}
</style>
