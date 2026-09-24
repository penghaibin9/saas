<template>
  <div class="scn-wrap">
    <div class="scn-bar no-print">
      <AppButton @click="$router.back()">返回</AppButton>
      <AppPrintButton variant="primary" :handler="printNotice" :disabled="!canPrint" label="打印通知单" />
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
      <p class="scn-foot">本单据展示正式审批记录。{{ canPrint ? '课表变更已生效；师生送达情况须以正式通知回执核对。' : '申请尚未生效，不作为课表变更或通知送达凭证。' }}</p>
    </div>
  </div>
</template>

<script>
/** 调停课通知单打印页（/admin/academic-affairs/print/schedule-change/:id/notice，D7 独立打印路由）。
 * 校名抬头复用 academicAffairsApi.getContext()（对齐 AaStatusChangePrintView.vue 既有范式，D-14）；
 * 打印动作仅在 status=APPLIED 时可用（三级施工卡 05 §5.2/§6：非生效态隐藏/禁用打印，显示提示文案）。 */
import { LoadingState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppPrintButton } from '@/components/common'
import { scheduleChangeApi, CHANGE_STATUS } from '@/modules/academicAffairs/api/academic-schedule-change.api'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { currentUserFromToken } from '@/services/http/client'

export default {
  name: 'AaScheduleChangeNoticePrintView',
  components: { LoadingState, ErrorState, AppButton, AppPrintButton },
  data() { return { loading: true, error: '', data: null, schoolName: '', loadSeq: 0 } },
  computed: {
    identityKey() { return JSON.stringify(currentUserFromToken()) },
    canPrint() { return !this.loading && !this.error && !!this.data && this.data.status === 'APPLIED' && String(this.data.changeId) === String(this.$route.params.id) }
  },
  watch: { '$route.params.id'() { this.load() }, identityKey() { this.load() } },
  created() { this.load() },
  beforeUnmount() { this.loadSeq++ },
  methods: {
    statusLabel(s) { return (CHANGE_STATUS.find((x) => x.value === s) || {}).label || (s ? '状态待确认' : '—') },
    parity(p) { return { ALL: '全周', ODD: '单周', EVEN: '双周' }[p] || (p || '') },
    async load() {
      const seq = ++this.loadSeq
      const id = String(this.$route.params.id || '')
      const identity = this.identityKey
      const current = () => seq === this.loadSeq && identity === this.identityKey && id === String(this.$route.params.id || '')
      this.loading = true; this.error = ''; this.data = null; this.schoolName = ''
      try {
        const [ctxRes, res] = await Promise.all([
          academicAffairsApi.getContext(), scheduleChangeApi.detail(id)
        ])
        if (!current()) return
        if (ctxRes.code !== 0) { this.error = ctxRes.message || '学校信息加载失败'; return }
        this.schoolName = ctxRes.data?.tenantBrandConfig?.schoolName || '学校名称未提供'
        if (res.code !== 0) this.error = res.message || '通知单加载失败'
        else if (String(res.data?.changeId) !== id) this.error = '单据身份不一致，请重新加载'
        else this.data = res.data
      } catch (error) { if (current()) this.error = error?.message || '通知单加载失败' }
      finally { if (current()) this.loading = false }
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
