<template>
  <ModulePageShell
    :title="pageTitle"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions><AppButton variant="primary" @click="togglePanel">{{ panel === 'sessions' ? '查看学生汇总' : '查看考勤场次' }}</AppButton></template>
    <div class="mp-stack">
      <div class="aa-filter">
        <label class="aa-filter-field"><span>视图</span><AppSelect v-model="panel" :options="panelOptions" @change="onPanelChange" /></label>
        <label class="aa-filter-field"><span>行政班</span><AppClassPicker v-model="classId" placeholder="全部班级" /></label>
        <label class="aa-filter-field"><span>学期</span><AppTermCodePicker v-model="termCode" placeholder="全部学期" /></label>
        <label class="aa-filter-field"><span>点名类别</span><AppSelect v-model="sessionType" :options="typeOptions" /></label>
        <AppButton variant="ghost" @click="search">查询</AppButton>
        <AppButton v-if="canScan && sessionType !== 'ADMIN_SPECIAL'" variant="secondary" :loading="scanning" @click="scanAbsent">旷课预警扫描</AppButton>
      </div>
      <AppInlineAlert type="info" :title="panel === 'sessions' ? 'PC 与移动端共用正式考勤场次' : '点名必须属于正式课次和当前授课关系'" :description="panel === 'sessions' ? '普通任课教师可在 PC 继续逐生点名并提交；所有写入仍走与移动端相同的正式名单、任课关系和提交门禁。' : '特殊补录与正式课堂分口径统计；正式课堂提交后自动进入统计和授权预警。'" />

      <AppSectionCard v-if="selectedSessionId" title="课次名单与考勤记录">
        <AppButton variant="ghost" @click="closeSession">返回场次列表</AppButton>
        <LoadingState v-if="detailLoading" />
        <ErrorState v-else-if="detailError" :description="detailError" @retry="loadSession" />
        <template v-else-if="sessionDetail">
          <p class="aa-object">{{ sessionDetail.courseName || '课程未提供' }} · {{ sessionDetail.sessionDate }} · 第 {{ sessionDetail.slotNo ?? '—' }} 节<br>场次 {{ sessionDetail.sessionId }} · {{ sessionStatus(sessionDetail.status) }} · {{ sessionDetail.sourceLabel || '来源待确认' }}</p>
          <EmptyState v-if="!sessionDetail.items?.length" title="本场次未提供名单" />
          <DataTable v-else :columns="rosterColumns" :rows="visibleRoster" row-key="studentId" :pagination="{ page: rosterPage, pageSize: 20, total: sessionDetail.items.length }" @page-change="rosterPage = $event">
            <template #cell-status="{ row }">
              <span>{{ attendanceStatus(row.status) }}</span>
              <span v-if="sessionDetail.status === 'DRAFT'" class="aa-mark-actions">
                <button v-for="status in ['PRESENT','LATE','ABSENT','LEAVE']" :key="status" class="mp-link" :disabled="markingStudentId === String(row.studentId) || submittingSession" @click="markAttendance(row, status)">{{ attendanceStatus(status) }}</button>
              </span>
            </template>
          </DataTable>
          <div v-if="sessionDetail.status === 'DRAFT' && sessionDetail.items?.length" class="aa-submit-row">
            <span>未点名 {{ unmarkedCount }} 人<template v-if="unmarkedCount"> · 请全部点名后再提交</template></span>
            <AppButton variant="primary" :loading="submittingSession" :disabled="Boolean(markingStudentId) || unmarkedCount > 0" @click="submitAttendance">提交本场考勤</AppButton>
          </div>
          <div v-else-if="sessionDetail.status === 'SUBMITTED'" class="aa-submit-receipt">
            <div><strong>本场考勤已提交</strong><span>正式状态已回读；后续统计与预警继续使用同一考勤事实。</span></div>
            <AppButton variant="ghost" @click="$router.push('/admin/academic-affairs/teacher/today')">返回今日教学</AppButton>
            <AppButton @click="$router.push('/admin/academic-affairs/attendance-stats')">查看考勤统计</AppButton>
          </div>
        </template>
      </AppSectionCard>

      <div v-if="panel === 'stats'" class="aa-scope-note">
        当前汇总口径：<strong>{{ data.sourceScopeLabel || (sessionType === 'ADMIN_SPECIAL' ? '管理员特殊补录' : '正式课堂') }}</strong>。
        <span v-if="sessionType === 'ADMIN_SPECIAL'">特殊补录仅用于审计核对，不进入标准课堂旷课预警。</span>
        <template v-else>特殊补录不会混入默认课堂指标。</template>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <template v-if="panel === 'sessions'">
          <AppSectionCard title="考勤场次台账">
            <EmptyState v-if="!sessions.length" title="暂无考勤场次" description="请从“今日教学”选择正式课次开始点名；PC 与移动端会读取同一场次" />
            <DataTable v-else :columns="sessionColumns" :rows="sessions" row-key="sessionId" :pagination="{ page, pageSize, total: sessionTotal }" @page-change="turnPage">
              <template #cell-status="{ row }">{{ sessionStatus(row.status) }}</template>
              <template #cell-actions="{ row }"><button class="mp-link" @click="openSession(row)">查看课次名单</button></template>
            </DataTable>
          </AppSectionCard>
        </template>
        <template v-else>
          <div class="aa-metric-grid">
            <AppMetricCard :title="`${data.sourceScopeLabel || '正式课堂'}场次`" :value="data.sessionCount" unit="次" />
            <AppMetricCard title="涉及学生" :value="studentTotal" unit="人" />
            <AppMetricCard title="有旷课学生" :value="absentStudentCount" unit="人" />
          </div>

          <AppSectionCard :title="`${data.sourceScopeLabel || '正式课堂'}学生考勤汇总（按旷课次数降序）`">
            <EmptyState v-if="!data.students.length" title="暂无考勤统计" description="教师在 PC 或移动端提交正式课堂点名后，这里出现跨堂次汇总" />
            <DataTable v-else :columns="columns" :rows="visibleStudents" row-key="studentId" :row-class="rowClass" :pagination="{ page: studentPage, pageSize: 20, total: studentTotal }" @page-change="turnStudentPage">
              <template #cell-absent="{ row }"><span :class="{ 'aa-cell-danger': row.absent > 0 }">{{ row.absent }}</span></template>
              <template #cell-absentRate="{ row }">{{ pct(row.absentRate) }}%</template>
            </DataTable>
          </AppSectionCard>
        </template>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/** 课堂考勤统计（/admin/academic-affairs/attendance-stats）：汇总 + 场次查询 + 旷课预警扫描。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppMetricCard, AppSectionCard, AppSelect, AppClassPicker, AppTermCodePicker, AppInlineAlert } from '@/components/common'
import { academicAffairsApi, academicAffairsWarningApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'
import { currentUserFromToken } from '@/services/http/client'
import { matchPermission } from '@/config/navPlan'

export default {
  name: 'AaAttendanceStatsView',
  components: {
    ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState,
    AppButton, AppMetricCard, AppSectionCard, AppSelect, AppClassPicker, AppTermCodePicker, AppInlineAlert
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    const q = (this.$route && this.$route.query) || {}
    return {
      loading: true, error: '', scanning: false,
      panel: q.panel === 'sessions' ? 'sessions' : 'stats',
      classId: '', termCode: '', sessionType: '', currentTermName: '', initializingTerm: false,
      page: 1, pageSize: 20, sessionTotal: 0, studentPage: 1, loadSeq: 0, scanSeq: 0,
      sessionDetail: null, detailLoading: false, detailError: '', detailSeq: 0, rosterPage: 1,
      markingStudentId: '', submittingSession: false,
      rosterColumns: [{ key: 'realName', title: '学生' }, { key: 'studentNo', title: '学号' }, { key: 'status', title: '出勤状态' }],
      data: { sessionCount: 0, studentTotal: 0, absentStudentCount: 0, students: [], sourceScopeLabel: '正式课堂' },
      sessions: [],
      panelOptions: [
        { label: '学生汇总', value: 'stats' },
        { label: '场次查询', value: 'sessions' }
      ],
      typeOptions: [
        { label: '全部正式课堂', value: '' },
        { label: '常规', value: '常规' },
        { label: '实训', value: '实训' },
        { label: '晚自习', value: '晚自习' },
        { label: '其他', value: '其他' },
        { label: '管理员特殊补录', value: 'ADMIN_SPECIAL' }
      ],
      columns: [
        { key: 'realName', title: '学生' }, { key: 'studentNo', title: '学号' },
        { key: 'sessions', title: '总堂次', align: 'center' }, { key: 'present', title: '出勤', align: 'center' },
        { key: 'late', title: '迟到', align: 'center' }, { key: 'absent', title: '旷课', align: 'center' },
        { key: 'leave', title: '请假', align: 'center' }, { key: 'absentRate', title: '缺勤率', align: 'center' }
      ],
      sessionColumns: [
        { key: 'sessionId', title: '场次ID' }, { key: 'classId', title: '班级ID' },
        { key: 'courseName', title: '课程' }, { key: 'sessionDate', title: '日期' },
        { key: 'sessionTypeLabel', title: '类别' }, { key: 'sourceLabel', title: '来源' },
        { key: 'status', title: '状态' }, { key: 'absentCount', title: '旷课人数', align: 'center' },
        { key: 'actions', title: '操作' }
      ]
    }
  },
  computed: {
    pageTitle() { return '课堂考勤' },
    pageSubtitle() { return this.panel === 'sessions' ? '场次回到对应正式课次，核对课程、教师、应到人数与提交状态' : '从正式课次与授课关系核对考勤；提交后进入正式统计和授权预警' },
    identityKey() { return JSON.stringify([currentUserFromToken(), this.ctx]) },
    filterKey() { return JSON.stringify([this.classId, this.termCode, this.sessionType]) },
    isAcademicTeacher() { return String(this.ctx?.currentRole?.roleCode || '').toUpperCase() === 'ACADEMIC_TEACHER' },
    canScan() { return matchPermission(this.ctx.permissionPatterns, 'academicAffairs.warning.rule.manage') },
    selectedSessionId() { return String(this.$route.query.sessionId || '') },
    visibleRoster() { return (this.sessionDetail?.items || []).slice((this.rosterPage - 1) * 20, this.rosterPage * 20).map(this.normalizeStudent) },
    visibleStudents() { return (this.data.students || []).map(this.normalizeStudent) },
    studentTotal() { return Number.isFinite(Number(this.data.studentTotal)) ? Number(this.data.studentTotal) : (this.data.students || []).length },
    absentStudentCount() { return Number.isFinite(Number(this.data.absentStudentCount)) ? Number(this.data.absentStudentCount) : (this.data.students || []).filter((s) => s.absent > 0).length },
    unmarkedCount() { return (this.sessionDetail?.items || []).filter(row => row.status === 'UNMARKED').length }
  },
  watch: {
    async identityKey() {
      this.loadSeq++; this.detailSeq++; this.scanSeq++
      this.data = { students: [], sessionCount: 0 }; this.sessions = []; this.sessionDetail = null; this.scanning = false
      this.termCode = ''; this.currentTermName = ''
      this.closeSession()
      await this.initializeCurrentTerm()
      this.search()
    },
    filterKey() { if (!this.initializingTerm) { this.closeSession(); this.search() } },
    selectedSessionId() { this.loadSession() },
    '$route.query.panel'(v) {
      if (this.panel === (v === 'sessions' ? 'sessions' : 'stats')) return
      this.panel = v === 'sessions' ? 'sessions' : 'stats'
      this.load()
    }
  },
  async created() {
    await this.initializeCurrentTerm()
    this.load()
    if (this.selectedSessionId) this.loadSession()
  },
  beforeUnmount() { this.loadSeq++; this.detailSeq++; this.scanSeq++ },
  methods: {
    async initializeCurrentTerm() {
      if (!this.isAcademicTeacher || this.termCode || this.selectedSessionId) return
      this.initializingTerm = true
      try {
        const res = await academicAffairsApi.getCurrentTerm()
        if (res?.code === 0 && res.data?.yearCode && res.data?.termNo) {
          this.termCode = String(res.data.yearCode) + '-' + String(res.data.termNo)
          this.currentTermName = res.data.termName || this.termCode
        }
      } finally {
        this.initializingTerm = false
      }
    },
    sessionStatus(value) { return { DRAFT: '草稿', SUBMITTED: '已提交' }[value] || '状态待确认' },
    attendanceStatus(value) { return { UNMARKED: '未点名', PRESENT: '出勤', LATE: '迟到', ABSENT: '旷课', LEAVE: '请假' }[value] || '状态待确认' },
    normalizeStudent(row = {}) {
      const studentId = String(row.studentId || '').trim()
      return {
        ...row,
        realName: String(row.realName || row.studentName || '').trim() || (studentId ? `学生 #${studentId}` : '姓名未提供'),
        studentNo: String(row.studentNo || row.studentCode || '').trim() || '学号未提供'
      }
    },
    togglePanel() {
      this.panel = this.panel === 'sessions' ? 'stats' : 'sessions'
      this.onPanelChange()
    },
    search() { this.page = 1; this.studentPage = 1; this.load() },
    turnPage(page) { this.page = page; this.load() },
    turnStudentPage(page) { this.studentPage = page; this.load() },
    openSession(row) { this.$router.replace({ query: { ...this.$route.query, panel: 'sessions', sessionId: row.sessionId } }) },
    closeSession() {
      this.detailSeq++; this.sessionDetail = null; this.detailError = ''; this.detailLoading = false
      if (!this.selectedSessionId) return
      const query = { ...this.$route.query }; delete query.sessionId
      this.$router.replace({ query })
    },
    async loadSession() {
      const seq = ++this.detailSeq, id = this.selectedSessionId, identity = this.identityKey
      const current = () => seq === this.detailSeq && id === this.selectedSessionId && identity === this.identityKey
      this.sessionDetail = null; this.detailError = ''; this.rosterPage = 1; this.detailLoading = !!id
      if (!id) return
      try {
        const res = await academicAffairsApi.getAttendanceSession(id)
        if (!current()) return
        if (res.code !== 0) this.detailError = res.message || '课次名单加载失败'
        else if (String(res.data?.sessionId) !== id) this.detailError = '课次身份不一致，请重新选择'
        else this.sessionDetail = res.data
      } catch (error) { if (current()) this.detailError = error?.message || '课次名单加载失败' }
      finally { if (current()) this.detailLoading = false }
    },
    async markAttendance(row, status) {
      if (!this.sessionDetail || this.sessionDetail.status !== 'DRAFT' || this.markingStudentId || this.submittingSession) return
      const studentId = String(row.studentId || '')
      const sessionId = String(this.sessionDetail.sessionId || '')
      const identity = this.identityKey
      if (!studentId || !sessionId) return
      this.markingStudentId = studentId
      try {
        const res = await academicAffairsApi.markAttendanceSession(sessionId, Number(studentId), status)
        if (String(this.selectedSessionId) !== sessionId || this.identityKey !== identity) return
        if (res.code !== 0) { toast.error(res.message || '点名未保存'); return }
        const receipt = res.data || {}
        if (String(receipt.sessionId || '') !== sessionId) {
          this.detailError = '点名回执场次身份不一致，请刷新当前场次核对'
          return
        }
        if (Array.isArray(receipt.items)) {
          // PC 点名写接口返回刚提交后的完整正式名单。直接采用权威写回执，
          // 避免 POST 成功后再依赖一次 GET 才能刷新“未点名人数”。
          this.sessionDetail = { ...this.sessionDetail, ...receipt }
        } else {
          await this.loadSession()
        }
      } catch (error) {
        if (String(this.selectedSessionId) === sessionId && this.identityKey === identity) {
          toast.error(error?.message || '点名未保存，请刷新正式名单核对')
        }
      } finally {
        if (this.markingStudentId === studentId) this.markingStudentId = ''
      }
    },
    async submitAttendance() {
      if (!this.sessionDetail || this.sessionDetail.status !== 'DRAFT' || this.submittingSession || this.markingStudentId) return
      const unmarked = (this.sessionDetail.items || []).filter(row => row.status === 'UNMARKED').length
      if (unmarked) { toast.error(`还有 ${unmarked} 人未完成点名`); return }
      const sessionId = String(this.sessionDetail.sessionId || '')
      const identity = this.identityKey
      if (!sessionId) return
      this.submittingSession = true
      try {
        const res = await academicAffairsApi.submitAttendanceSession(sessionId)
        if (String(this.selectedSessionId) !== sessionId || this.identityKey !== identity) return
        if (res.code !== 0) { toast.error(res.message || '考勤提交失败'); return }
        const receipt = res.data || {}
        if (String(receipt.sessionId || '') !== sessionId) {
          this.detailError = '考勤提交回执场次身份不一致，请到场次台账核对'
          return
        }
        // 提交写回执先落 UI，防止“服务端已提交、补读失败、页面仍显示草稿”导致重复操作。
        this.sessionDetail = {
          ...this.sessionDetail,
          ...receipt,
          items: Array.isArray(receipt.items) ? receipt.items : (this.sessionDetail.items || [])
        }
        toast.success(receipt.warningScanOk === false ? (receipt.warningScanError || '考勤已提交，预警扫描待核对') : '本场考勤已提交')
        await this.load()
      } catch (error) {
        if (String(this.selectedSessionId) === sessionId && this.identityKey === identity) {
          toast.error(error?.message || '提交结果未确认，请刷新场次核对')
        }
      } finally {
        this.submittingSession = false
      }
    },
    pct(v) { return Math.round((v || 0) * 100) },
    rowClass(row) { return row.absent >= 3 ? 'aa-row-danger' : '' },
    onPanelChange() {
      const q = { ...(this.$route.query || {}), panel: this.panel === 'sessions' ? 'sessions' : undefined }
      if (!q.panel) delete q.panel
      this.$router.replace({ query: q }).catch(() => {})
      this.load()
    },
    filterParams() {
      const params = {}
      if (this.classId) params.classId = this.classId
      if (this.termCode) params.termCode = this.termCode
      if (this.sessionType) params.sessionType = this.sessionType
      return params
    },
    async load() {
      const seq = ++this.loadSeq, identity = this.identityKey
      const query = JSON.stringify([this.panel, this.filterKey, this.page, this.studentPage])
      const current = () => seq === this.loadSeq && identity === this.identityKey && query === JSON.stringify([this.panel, this.filterKey, this.page, this.studentPage])
      this.loading = true
      this.error = ''
      const params = this.filterParams()
      try {
      if (this.panel === 'sessions') {
        const res = await academicAffairsApi.getAttendanceSessions({ ...params, page: this.page, pageSize: this.pageSize })
        if (!current()) return
        if (res.code === 0) { this.sessions = res.data?.list || res.data?.items || []; this.sessionTotal = res.data?.total ?? 0 }
        else this.error = res.message
      } else {
        const res = await academicAffairsApi.getAttendanceStats({ ...params, page: this.studentPage, pageSize: 20 })
        if (!current()) return
        if (res.code === 0) this.data = { sessionCount: 0, studentTotal: 0, absentStudentCount: 0, students: [], sourceScopeLabel: '正式课堂', ...res.data }
        else this.error = res.message
      }
      } catch (error) { if (current()) this.error = error?.message || '考勤加载失败' }
      finally { if (current()) this.loading = false }
    },
    async scanAbsent() {
      if (this.scanning || !this.canScan || this.sessionType === 'ADMIN_SPECIAL') return
      const seq = ++this.scanSeq, identity = this.identityKey
      const current = () => seq === this.scanSeq && identity === this.identityKey
      this.scanning = true
      try {
      const res = await academicAffairsWarningApi.scan('attendance')
      if (!current()) return
      if (res.code === 0) {
        const d = res.data || {}
        const created = d.created ?? d.newCount
        const updated = d.updated ?? d.updatedCount
        if (!Number.isFinite(Number(created)) || !Number.isFinite(Number(updated))) {
          toast.error('扫描已返回，但未提供完整的新增/更新回执；请到预警记录核对。')
          return
        }
        toast.success(`旷课预警扫描完成：新增 ${created}，更新 ${updated}`)
      } else {
        toast.error(res.message || '扫描失败')
      }
      } catch (error) { if (current()) toast.error(error?.message || '扫描结果未确认，请查看预警记录') }
      finally { if (current()) this.scanning = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.aa-filter-field { display: grid; gap: 6px; min-width: 160px; font-size: 13px; }
.aa-object { padding: 14px 16px; border-left: 3px solid var(--primary-color, #2b5bb4); background: var(--fill-2, #f7f8fa); line-height: 1.8; }
.aa-filter__label { font-size: 13px; color: var(--text-700, #4e5969); }
.aa-scope-note { padding: 10px 12px; border-radius: 8px; background: var(--fill-2, #f7f8fa); color: var(--text-700, #4e5969); font-size: 13px; line-height: 1.6; }
.aa-metric-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
.aa-cell-danger { color: var(--danger-600, #f53f3f); font-weight: 600; }
.aa-mark-actions { display:inline-flex; gap:8px; margin-left:10px; flex-wrap:wrap; }
.aa-submit-row { display:flex; align-items:center; justify-content:flex-end; gap:14px; margin-top:12px; }
.aa-submit-receipt { display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-top:12px; padding:12px 14px; border:1px solid var(--success-200,#b7dfc2); border-radius:9px; background:var(--success-50,#f0f9f2); }
.aa-submit-receipt div { flex:1 1 280px; }
.aa-submit-receipt strong,.aa-submit-receipt span { display:block; }
.aa-submit-receipt span { margin-top:3px; color:var(--text-600,#64748b); font-size:12px; }
:deep(.aa-row-danger) { background: var(--danger-50, #fff1f0); }
</style>
