<template>
  <div class="scn-wrap">
    <div class="scn-bar no-print">
      <button class="mp-btn" @click="$router.back()">返回</button>
      <button class="mp-btn mp-btn--primary" @click="printNotice" :disabled="!canPrint">打印通知单</button>
    </div>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <div v-else-if="data" class="scn-sheet">
      <h1 class="scn-title">{{ schoolName }}</h1>
      <h2 class="scn-subtitle">调停课通知单</h2>
      <p class="scn-sub">{{ data.changeTypeLabel }} · 单号 {{ data.changeId }} · 状态 {{ statusLabel(data.status) }}</p>
      <p v-if="!canPrint" class="scn-notice">该申请尚未生效，暂无法打印通知单（仅"已生效"状态可打印）</p>

      <table class="scn-tbl">
        <tr><th>课程</th><td>{{ data.courseName || '—' }}</td><th>教学班</th><td>{{ data.className || '—' }}</td></tr>
        <tr><th>任课教师</th><td>{{ data.teacherName || '—' }}</td><th>变更类型</th><td>{{ data.changeTypeLabel }}</td></tr>
        <tr>
          <th>原课位</th>
          <td colspan="3">周{{ data.origin.weekday }} 第{{ data.origin.slotNo }}节 · 第{{ data.origin.startWeek }}-{{ data.origin.endWeek }}周 · {{ parity(data.origin.weekParity) }} · {{ data.origin.classroom || '—' }}</td>
        </tr>
        <tr v-if="data.changeType !== 'STOP'">
          <th>目标课位</th>
          <td colspan="3">周{{ data.target.weekday }} 第{{ data.target.slotNo }}节 · 第{{ data.target.startWeek }}-{{ data.target.endWeek }}周 · {{ parity(data.target.weekParity) }} · {{ data.target.classroom || '—' }}</td>
        </tr>
        <tr v-if="data.makeupPlan"><th>{{ data.changeType === 'STOP' ? '停课后续安排' : '补课/说明' }}</th><td colspan="3">{{ data.makeupPlan }}</td></tr>
        <tr><th>申请原因</th><td colspan="3">{{ data.reason || '—' }}</td></tr>
        <tr><th>生效时间</th><td>{{ data.appliedAt || '—' }}</td><th>申请时间</th><td>{{ data.createdAt || '—' }}</td></tr>
      </table>

      <div class="scn-sign">
        <div>教务处（签章）：____________</div>
        <div>日期：____________</div>
      </div>
      <p class="scn-foot">本通知单由系统依审批结果生成，原课位已在课表中留痕，学生端课表即时反映变更。</p>
    </div>
  </div>
</template>

<script>
/** 调停课通知单打印页（/admin/academic-affairs/print/schedule-change/:id/notice，D7 独立打印路由）。
 * 校名抬头复用 academicAffairsApi.getContext()（对齐 AaStatusChangePrintView.vue 既有范式，D-14）；
 * 打印动作仅在 status=APPLIED 时可用（三级施工卡 05 §5.2/§6：非生效态隐藏/禁用打印，显示提示文案）。 */
import { LoadingState, ErrorState } from '@/components/business'
import { scheduleChangeApi, CHANGE_STATUS } from '@/modules/academicAffairs/api/academic-schedule-change.api'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'

export default {
  name: 'AaScheduleChangeNoticePrintView',
  components: { LoadingState, ErrorState },
  data() { return { loading: true, error: '', data: null, schoolName: '职业院校' } },
  computed: {
    canPrint() { return !!this.data && this.data.status === 'APPLIED' }
  },
  created() { this.load() },
  methods: {
    statusLabel(s) { return (CHANGE_STATUS.find((x) => x.value === s) || {}).label || s },
    parity(p) { return { ALL: '全周', ODD: '单周', EVEN: '双周' }[p] || (p || '') },
    async load() {
      this.loading = true; this.error = ''
      const [ctxRes, res] = await Promise.all([
        academicAffairsApi.getContext(),
        scheduleChangeApi.detail(this.$route.params.id)
      ])
      if (ctxRes.code === 0) this.schoolName = ctxRes.data.tenantBrandConfig.schoolName || '职业院校'
      if (res.code === 0) this.data = res.data
      else this.error = res.message
      this.loading = false
    },
    printNotice() {
      if (!this.canPrint) return
      window.print()
    }
  }
}
</script>

<style scoped>
.scn-wrap { max-width: 780px; margin: 0 auto; padding: var(--space-4); }
.scn-bar { display: flex; justify-content: flex-end; gap: var(--space-2); margin-bottom: var(--space-3); }
.scn-sheet { background: #fff; border: 1px solid var(--line, #e2e8f0); border-radius: 10px; padding: 32px 40px; }
.scn-title { text-align: center; font-size: 22px; margin: 0 0 4px; }
.scn-subtitle { text-align: center; font-size: 16px; font-weight: 500; margin: 0 0 6px; letter-spacing: 4px; color: var(--t2, #1e293b); }
.scn-sub { text-align: center; color: var(--t3, #64748b); font-size: 12px; margin: 0 0 20px; }
.scn-notice { text-align: center; color: var(--danger, #dc2626); font-size: 13px; margin: 0 0 20px; }
.scn-tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.scn-tbl th, .scn-tbl td { border: 1px solid var(--line, #cbd5e1); padding: 9px 12px; text-align: left; }
.scn-tbl th { width: 96px; background: var(--bg2, #f8fafc); color: var(--t2, #475569); font-weight: 600; }
.scn-sign { display: flex; justify-content: space-between; margin-top: 40px; font-size: 13px; }
.scn-foot { margin-top: 24px; font-size: 11px; color: var(--t3, #94a3b8); }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
@media print {
  .no-print { display: none !important; }
  .scn-wrap { padding: 0; }
  .scn-sheet { border: none; }
  @page { size: A4; margin: 1.5cm; }
}
</style>
