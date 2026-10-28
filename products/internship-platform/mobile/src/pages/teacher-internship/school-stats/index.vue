<template>
  <view class="mobile-page mobile-teacher page-wrap teacher-stats">
    <MobileNavBar variant="teacher" title="校级实习统计" show-back />
    <view class="page-pad ss__context">
      <view v-if="batches.length" class="ss__batch">
        <text class="t-md t-bold">{{ batches[batchIndex]?.name || '请选择批次' }}</text>
        <picker class="mobile-picker" v-if="batches.length > 1" :range="batchLabels" :value="batchIndex" @change="onBatch">
          <text class="ss__switch">切换 ▾</text>
        </picker>
      </view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view v-if="data" class="page-pad stack">
        <MobileInlineAlert type="info"
          description="专业对口与岗位分配分别统计；工资按币种分别计算。" />
        <view class="card stack"><text>统计范围：当前账号获授权的本批次学生，共 {{ data.scope?.recordCount ?? '—' }} 人。</text><text v-if="readAt" class="ss__ratio-note">读取于 {{ readAt }}</text></view>

        <view v-for="group in data.groups" :key="group.key" class="card ss">
          <view class="row-between ss__head">
            <view><text class="ss__eyebrow">{{ groupKey(group.key) }}</text><text class="t-lg t-bold">{{ group.label }}</text></view>

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
                <view class="flex-1"><text class="ss__ratio-title">{{ item.label }}</text></view>
                <text class="ss__ratio-value">{{ rateText(item) }}</text>
              </view>
              <view class="ss__bar"><view :style="{ width: barWidth(item) }" /></view>
              <text class="ss__ratio-fact">{{ item.numerator }} / {{ item.denominator }}</text>
            </view>
          </view>

          <view v-if="group.distribution?.length" class="ss__distribution">
            <view v-for="item in group.distribution" :key="item.key">
              <text>{{ item.label }}</text><text>{{ item.value }}</text>
            </view>
          </view>

          <view v-if="group.cityTop10" class="ss__cities">
            <text class="ss__section-title">实际工作城市前十</text>
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
              <view class="row-between"><text class="ss__ratio-title">{{ item.label }}</text><text class="ss__ratio-value">{{ rateText(item) }}</text></view>
              <view class="ss__bar"><view :style="{ width: item.rate == null ? '0%' : Math.min(100, Math.max(0, item.rate)) + '%' }" /></view>
              <text class="ss__ratio-fact">{{ item.numerator }} / {{ item.denominator }}</text>
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
                <text class="ss__wage-amount">{{ currencyLabel(item.currency) }} {{ Number(item.averageActualAmount).toFixed(2) }}</text>
                <text class="ss__ratio-fact">{{ item.count }} 条 · 合计 {{ currencyLabel(item.currency) }} {{ Number(item.totalActualAmount).toFixed(2) }}</text>
              </view>
            </view>
            <text v-else class="ss__empty">暂无已确认工资单</text>
            <text class="ss__ratio-note">{{ group.wageNote }}</text>
          </view>
        </view>

        <button class="mobile-control ss__toggle" :aria-expanded="definitionsOpen" @click="definitionsOpen=!definitionsOpen">{{ definitionsOpen ? '收起口径说明' : '查看口径说明' }}</button>
        <view v-if="definitionsOpen" class="card ss__definitions">
          <view v-for="(item,index) in definitionRows" :key="index"><text>{{ item.labels.join('、') }}</text><text>{{ item.note }}</text></view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherInternshipProcurementStats } from '@/services/internshipApi'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { toast } from '@/utils/nav'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'

export default {
  data() {
    return { requestedBatchId: '', state: 'loading', data: null, batches: [], batchId: '', batchIndex: 0, definitionsOpen: false, readAt:'', sequence:0, hidden:false }
  },
  computed: {
    context() { return useInternshipContextStore() },
    definitionRows() {
      const rows=[],seen=new Map(),add=(label,value,key)=>{const note=this.businessNote(value,key);if(!note)return;const row=seen.get(note);if(row){if(!row.labels.includes(label))row.labels.push(label)}else{const item={labels:[label],note};seen.set(note,item);rows.push(item)}}
      for(const group of this.data?.groups || [])for(const item of [...(group.ratios || []),...(group.metrics || [])])if(item.note)add(item.label,item.note,item.key)
      for(const [key,value] of Object.entries(this.data?.metricDefinitions || {}))if(!seen.has(this.businessNote(value,key)))add(this.definitionLabel(key),value,key)
      return rows
    },
    batchLabels() { return this.batches.map((b) => `${b.name} · ${b.studentCount}人`) }
  },
  onLoad(query={}) { this.requestedBatchId=String(query.batchId||'');this.load() },
  onShow() { if(this.hidden){this.hidden=false;this.load()} },
  onHide() { this.hidden=true;this.sequence++;this.data=null;this.readAt='' },
  onUnload() { this.hidden=true;this.sequence++ },
  onPullDownRefresh() { this.load(() => uni.stopPullDownRefresh()) },
  methods: {
    currencyLabel(value) { return ({CNY:'人民币',USD:'美元',JPY:'日元',EUR:'欧元',HKD:'港币'})[value] || (value ? '其他币种（'+value+'）' : '币种待核对') },
    businessNote(value, key='') {
      if (key==='accountBindingRate') return '已有效绑定校园账号的学生比例。'
      if (key==='wechatBindingRate') return '已绑定校园账号的学生中，已有效绑定微信的比例。'
      if (key==='majorMatchRate' || key==='majorMatch') return '按已审核申请中的专业对口结论统计，未知不计入。'
      if (key==='reportTaskCompletionRate' || key==='reportCompletion') return '按本批次应交报告要求统计。'
      return String(value||'').replace(/StudentAccountLink/g,'校园账号绑定记录').replace(/major_match/g,'专业对口结论').replace(/ACTIVE/g,'有效').replace(/APPROVED/g,'已通过').replace(/PUBLISHED/g,'已发布').replace(/>=/g,'≥')
    },
    groupKey(key) { return ({ overview: '01', destination: '02', activity: '03', quality: '04' })[key] || '' },
    definitionLabel(key) { return ({ majorMatch: '专业对口', reportCompletion: '报告完成', transfer: '转企转岗', wage: '工资', excellent: '优秀率' })[key] || '其他口径' },
    frequencyLabel(value) { return value === 'BIWEEKLY' ? '每两周1篇' : value === 'WEEKLY' ? '每周1篇' : value ? '频率待核对' : '未配置' },
    rateText(item) {
      if (item.key==='guidanceCoverRate' && item.rate==null && Number(item.denominator)>0 && Number(item.numerator)>Number(item.denominator)) return '口径待核对'
      return item.denominator && item.rate != null ? `${item.rate}%` : '暂无数据'
    },
    barWidth(item) { return item.denominator ? Math.min(100, Math.max(0, Number(item.rate || 0))) + '%' : '0%' },
    cityWidth(count, items) {
      const max = Math.max(1, ...(items || []).map((item) => Number(item.count || 0)))
      return Math.round(Number(count || 0) / max * 100) + '%'
    },
    async load(done) {
      const sequence=++this.sequence,generation=currentSessionGeneration(),current=()=>!this.hidden && sequence===this.sequence && generation===currentSessionGeneration()
      this.state = 'loading'
      this.data=null;this.readAt=''
      try {
        this.context.restore()
        await this.context.load(true)
        if(!current())return
        if(this.requestedBatchId){if(!this.context.selectBatch(this.requestedBatchId))throw {httpStatus:403,message:'当前批次不在授权范围'};this.requestedBatchId=''}
        if (!this.context.can('internship.stats.view')) {
          this.state = 'forbidden'; this.data = null; return
        }
        this.batches = this.context.batches || []
        this.batchId = this.context.selectedBatchId || ''
        this.batchIndex = Math.max(0, this.batches.findIndex((b) => String(b.id) === String(this.batchId)))
        if (!this.batchId) { this.data = null; this.state = 'ready'; return }
        const batch=this.batchId,data = await teacherInternshipProcurementStats(batch)
        if(!current() || batch!==this.context.selectedBatchId)return
        this.data=data;this.readAt=new Date().toLocaleString('zh-CN',{hour12:false})
        this.state = 'ready'
      } catch (e) { if(current()){this.data = null; this.state = 'error'; toast(e?.message || '校级统计加载失败')} }
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
.teacher-stats .ss__context,.teacher-stats :deep(.page-pad){width:100%;max-width:760px;margin-left:auto;margin-right:auto;box-sizing:border-box}.teacher-stats .card{border-radius:8px;box-shadow:none}.ss__batch{padding:4px 0 12px;border-bottom:1px solid var(--border-light);gap:12px}.ss__batch>text{font-size:15px;line-height:22px;overflow-wrap:anywhere}.ss__switch{display:inline-flex;align-items:center;min-height:44px;font-size:14px}.ss__scope,.ss__ratio-note,.ss__ratio-fact,.ss__empty,.ss__counters>view>text:last-child,.ss__distribution,.ss__task-fact,.ss__definitions>view{font-size:14px;line-height:22px}.ss__ratio-title,.ss__section-title{font-size:16px;line-height:24px}.ss__ratio .row-between{gap:12px}.ss__ratio-value{flex-shrink:0}.ss__toggle{min-height:44px;margin:0;border:1px solid var(--border-light);border-radius:8px;background:var(--bg-card);font-size:15px;color:var(--teacher-700)}.ss__toggle::after{border:0}.ss__definitions>view{gap:14px}
</style>
