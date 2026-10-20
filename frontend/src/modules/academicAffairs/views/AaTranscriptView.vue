<template>
  <ModulePageShell
    :title="pageTitle"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="aa-reg-search">
        <AppStudentPicker v-model="studentId" class="aa-input--grow" placeholder="按姓名/学号检索学生" :disabled="loading || exporting" @change="onStudentChange" />
      </div>

      <ErrorState v-if="error" :description="error" @retry="restoreRoute" />
      <template v-else-if="studentId">
        <LoadingState v-if="loading" />
        <template v-else-if="data">
          <div class="aa-transcript-summary">
            <span>已获学分 <strong>{{ data.earnedCredits ?? data.totalCredits ?? '待核对' }}</strong></span>
            <span>累计 GPA <strong>{{ data.gpa ?? '待核对' }}</strong></span>
            <span>挂科门次 <strong>{{ data.failCount ?? '待核对' }}</strong></span>
          </div>
          <AppSectionCard class="aa-transcript-paper" :title="`${name || '学生'} 的${exportMode ? '成绩导出' : '成绩单'}`">
            <template #header-extra>
              <button class="mp-btn" :disabled="!pagination.total || exporting" @click="exportPanel = !exportPanel">导出成绩单</button>
            </template>
            <div v-if="exportPanel" class="aa-export-bar">
              <input v-model.trim="exportPurpose" class="aa-input aa-input--grow" placeholder="导出用途（必填，≥5字，如：学院例会核对，将写入审计）" />
              <AppButton variant="primary" :loading="exporting" @click="doExport">确认导出 xlsx</AppButton>
            </div>
            <p v-if="!data.items.length" class="mp-note">当前学生暂无可展示的正式成绩。</p>
            <EmptyState v-if="!data.items.length && !data.note" title="暂无成绩记录" description="学生还没有已发布的课程成绩" />
            <div class="aa-table-scroll" role="region" aria-label="数据表格，可横向滚动" tabindex="0" v-else-if="data.items.length">
<table  class="aa-course-table">
              <thead><tr><th>课程 / 编码</th><th>学期</th><th>学分</th><th>成绩</th><th>结果</th><th>次数 / 来源 / 版本</th></tr></thead>
              <tbody>
                <tr v-for="g in data.items" :key="g.gradeId">
                  <td>{{ g.courseName || '待核对' }}<small class="aa-cell-note">{{ g.courseCode || '课程编码待核对' }}</small></td>
                  <td>{{ g.term || '—' }}</td>
                  <td>{{ g.credit ?? '待核对' }}</td>
                  <td>{{ g.score ?? '—' }}</td>
                  <td><AppStatusTag :type="passType(g.passStatus)">{{ passLabel(g.passStatus) }}</AppStatusTag></td>
                   <td>{{ g.attemptNo == null ? '次数待核对' : `第 ${g.attemptNo} 次` }}<small class="aa-cell-note">{{ sourceLabel(g.source) }} · {{ g.courseVersion == null ? '版本待核对' : `版本 ${g.courseVersion}` }}</small><small class="aa-cell-note">{{ identityLabel(g.academicIdentity) }}</small></td>
                </tr>
              </tbody>
            </table>
</div>
            <div v-if="pagination.total" class="aa-page-controls"><AppButton variant="ghost" :disabled="pagination.page <= 1 || loading" @click="changePage(pagination.page - 1)">上一页</AppButton><span>第 {{ pagination.page }} / {{ pageCount }} 页 · 共 {{ pagination.total }} 条</span><AppButton variant="ghost" :disabled="pagination.page >= pageCount || loading" @click="changePage(pagination.page + 1)">下一页</AppButton></div>
            <p class="mp-note">{{ identityCoverageNote }} 累计学分、GPA 与挂科门次来自服务器全成绩单汇总，不按当前页重算。</p>
          </AppSectionCard>
        </template>
      </template>
      <EmptyState v-else :title="exportMode ? '选择学生建立成绩导出作业' : '选择学生查看成绩单'" description="用上方选择器搜索学生" />
    </div>
  </ModulePageShell>
</template>

<script>
/** Page ID: AA-182 学生成绩单。GET /students/:id/transcript 服务端分页读侧。 */
import { ModulePageShell, LoadingState, EmptyState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppStatusTag, AppStudentPicker } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'
import { currentUserFromToken } from '@/services/http/client'
import { gradeError } from './parallel-c/grade-review'

export default {
  name: 'AaTranscriptView',
  components: { ModulePageShell, LoadingState, EmptyState, ErrorState, AppButton, AppSectionCard, AppStatusTag, AppStudentPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      studentId: '', name: '', loading: false, error: '', data: null, alive: true, readSeq: 0, exportSeq: 0,
      pagination: { page: 1, pageSize: 30, total: 0 }, exportPanel: false, exportPurpose: '', exporting: false
    }
  },
  computed: {
    exportMode() { return this.$route?.query?.action === 'export' },
    pageTitle() { return this.exportMode ? '成绩导出' : '学生成绩单' },
    pageSubtitle() { return this.exportMode ? '查询件与正式证明分开，导出用途写入审计' : '查询正式生效成绩，按课程核对修读次数、来源与版本' },
    identityKey() { const u = currentUserFromToken() || {}; return JSON.stringify([u.tenantId, u.userId, u.activeContextId, u.currentRoleCode, this.ctx.currentRole, this.ctx.dataScope, this.ctx.ctxKey, this.ctx.permissionVersion, this.ctx.dataScopeVersion, this.ctx.permissionPatterns]) },
    routeKey() { return this.$route?.fullPath || '' },
    pageCount() { return Math.max(1, Math.ceil(this.pagination.total / this.pagination.pageSize)) },
    identityCoverageNote() { return this.data?.historicalIdentityComplete ? '本页历史学籍身份均已解析；该结论只覆盖当前页。' : '本页存在未解析的历史学籍身份，不对其它页作推断。' }
  },
  watch: {
    identityKey() { this.invalidate(); this.restoreRoute() },
    routeKey() { this.invalidate(); this.restoreRoute() }
  },
  created() { this.restoreRoute() },
  beforeUnmount() { this.alive = false; this.invalidate() },
  methods: {
    passLabel(status) { return status === 'PASSED' ? '及格' : ['FAIL', 'FAILED'].includes(status) ? '不及格' : '结果待核对' },
    passType(status) { return status === 'PASSED' ? 'success' : ['FAIL', 'FAILED'].includes(status) ? 'danger' : 'info' },
    sourceLabel(source) { return ({ NORMAL: '正常修读', REGULAR: '正常修读', PUBLISH: '正常发布', MAKEUP: '补考', RETAKE: '重修', CHANGE: '成绩更正', RECHECK: '复查更正', RECOGNITION: '成绩认定', EXEMPTION: '免修', LEGACY: '历史记录' })[source] || '来源待核对' },
    identityLabel(identity) { if (identity?.status === 'RESOLVED') return `当期学籍已解析${identity.grade ? ` · ${identity.grade}` : ''}${identity.studentStatus ? ` · ${identity.studentStatus}` : ''}`; return `当期学籍未解析${identity?.reason ? ` · ${identity.reason}` : ''}` },
    invalidate() { this.readSeq++; this.exportSeq++; this.data = null; this.error = ''; this.loading = false; this.exporting = false; this.exportPurpose = ''; this.exportPanel = false; this.pagination = { page: 1, pageSize: 30, total: 0 } },
    forbidden(err) { return /403|NO_DATA_SCOPE|FORBIDDEN|NO_PERMISSION/.test([err?.code, err?.bizCode].join(' ')) },
    routeStudentId(value) { return typeof value === 'string' && /^[1-9]\d*$/.test(value) ? value : '' },
    async navigate(query) { const before = this.routeKey; try { await this.$router.replace({ path: this.$route.path, query }) } catch { /* duplicate navigation */ } if (before === this.routeKey) this.restoreRoute() },
    restoreRoute() {
      const query = this.$route?.query || {}, rawId = query.studentId
      if (rawId != null && !this.routeStudentId(rawId)) { this.studentId = ''; this.name = ''; this.data = null; this.error = '学生参数无效，请从学生选择器重新进入。'; return }
      if (query.name != null && (typeof query.name !== 'string' || query.name.length > 100 || Array.from(query.name).some(char => char.codePointAt(0) < 32 || char.codePointAt(0) === 127))) { this.studentId = ''; this.name = ''; this.data = null; this.error = '学生名称参数无效，请从学生选择器重新进入。'; return }

      this.studentId = this.routeStudentId(rawId); this.name = query.name || ''
      if ((query.page != null && typeof query.page !== 'string') || (query.pageSize != null && typeof query.pageSize !== 'string')) { this.studentId = ''; this.name = ''; this.data = null; this.error = '成绩单分页参数无效，请重新进入。'; return }
      const page = Number(query.page || ''), pageSize = Number(query.pageSize || '')
      this.pagination.page = Number.isInteger(page) && page > 0 && page <= 100000 ? page : 1
      this.pagination.pageSize = Number.isInteger(pageSize) && pageSize > 0 && pageSize <= 200 ? pageSize : 30
      this.exportPanel = query.action === 'export'
      if (this.studentId) this.load()
    },
    onStudentChange(value, items) {
      const id = this.routeStudentId(String(value || ''))
      const item = items?.[0], student = item?.raw || item || {}
      const name = String(student.realName || student.studentName || item?.label || '').slice(0, 100)
      this.navigate(id ? { studentId: id, name, page: '1', pageSize: String(this.pagination.pageSize) } : {})
    },
    changePage(page) { if (!this.loading && page >= 1 && page <= this.pageCount) this.navigate({ ...this.$route.query, page: String(page), pageSize: String(this.pagination.pageSize) }) },
    normalizeTranscript(payload, studentId, page, pageSize) {
      if (!payload || String(payload.studentId) !== String(studentId) || Number(payload.page) !== page || Number(payload.pageSize) !== pageSize || payload.identityCoverage !== 'PAGE') throw { code: 'TRANSCRIPT_OBJECT_MISMATCH', message: '成绩单响应与当前学生或页码不一致' }
      if (!Array.isArray(payload.items) || !Number.isSafeInteger(payload.total) || payload.total < payload.items.length || payload.items.length > pageSize || typeof payload.historicalIdentityComplete !== 'boolean') throw { code: 'TRANSCRIPT_PAGE_INVALID', message: '成绩单分页结构无效' }
      const ids = new Set()
      const items = payload.items.map(item => { const id = String(item?.gradeId || ''); if (!/^[1-9]\d*$/.test(id) || ids.has(id) || !item.academicIdentity || String(item.academicIdentity.termCode || '') !== String(item.term || '')) throw { code: 'TRANSCRIPT_ITEM_MISMATCH', message: '成绩单条目或历史身份与当前对象不一致' }; ids.add(id); return { ...item } })
      return { ...payload, items, total: Number(payload.total) }
    },
    async load() {
      if (!this.studentId) { this.invalidate(); return }
      const seq = ++this.readSeq, identity = this.identityKey, route = this.routeKey, studentId = this.studentId, page = this.pagination.page, pageSize = this.pagination.pageSize
      const valid = () => this.alive && seq === this.readSeq && identity === this.identityKey && route === this.routeKey && studentId === this.studentId && page === this.pagination.page && pageSize === this.pagination.pageSize
      this.loading = true; this.error = ''; this.data = null; this.pagination.total = 0
      try {
        const res = await academicAffairsApi.getTranscript(studentId, { page, pageSize })
        if (!valid()) return
        if (res.code !== 0) throw res
        this.data = this.normalizeTranscript(res.data, studentId, page, pageSize); this.pagination.total = this.data.total
      } catch (err) { if (valid()) { if (this.forbidden(err)) { this.data = null; this.studentId = ''; this.name = ''; this.pagination.total = 0; this.loading = false } this.error = gradeError(err, '成绩单读取失败，请重试。') } }
      finally { if (valid()) this.loading = false }
    },
    async doExport() {
      if (this.exporting || this.loading || !this.pagination.total) return
      if (this.exportPurpose.trim().length < 5) { toast.error('导出用途必填且不少于 5 个字'); return }
      const seq = ++this.exportSeq, identity = this.identityKey, studentId = this.studentId, name = this.name
      const route = this.routeKey, valid = () => this.alive && seq === this.exportSeq && identity === this.identityKey && route === this.routeKey && studentId === this.studentId
      this.exporting = true
      try {
        const res = await academicAffairsApi.exportTranscript(studentId, this.exportPurpose.trim())
        if (!valid()) return
        if (res.code !== 0) throw res
        const href = URL.createObjectURL(res.data), a = document.createElement('a')
        a.href = href; a.download = `${name || '学生'}-成绩单-${Date.now()}.xlsx`
        document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(href)
        toast.success('导出成功，已写入审计'); this.exportPanel = false; this.exportPurpose = ''
      } catch (err) {
        if (!valid()) return
        if (this.forbidden(err)) { const message = gradeError(err); this.invalidate(); this.studentId = ''; this.name = ''; this.error = message }
        else toast.error(gradeError(err, '导出结果未取得，请核对后重试。'))
      } finally { if (valid()) this.exporting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-reg-search { display: flex; gap: 12px; align-items: center; }
.aa-input { height: 34px; padding: 0 12px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 14px; box-sizing: border-box; }
.aa-input--grow { flex: 1; }
.aa-cand-list { list-style: none; margin: 0; padding: 0; border: 1px solid var(--border-100, #f0f1f2); border-radius: 6px; }
.aa-cand-item { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; border-bottom: 1px solid var(--border-100, #f0f1f2); font-size: 13px; }
.aa-cand-item:last-child { border-bottom: none; }
.aa-transcript-summary { display: flex; justify-content: center; gap: 32px; color: var(--text-500); }
.aa-transcript-paper { width: min(100%, 900px); margin: 0 auto; box-sizing: border-box; }
.aa-cell-note { display: block; margin-top: 4px; color: var(--text-500); font-size: 12px; }
.aa-page-controls { display: flex; justify-content: center; align-items: center; gap: 12px; margin-top: 16px; }
.aa-export-bar { display: flex; gap: 12px; align-items: center; margin-bottom: 14px; padding: 10px 12px; background: var(--fill-50, #f7f8fa); border-radius: 6px; }
.aa-course-table { width: 100%; border-collapse: collapse; }
.aa-course-table th, .aa-course-table td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border-100, #f0f1f2); font-size: 14px; }
.aa-course-table th { color: var(--text-500, #646a73); font-weight: 500; font-size: 13px; }
</style>
