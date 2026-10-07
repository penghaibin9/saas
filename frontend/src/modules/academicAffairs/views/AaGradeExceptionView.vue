<template>
  <ModulePageShell
    title="成绩异常"
    subtitle="按缺考、缓考、免修、作弊标记核对原成绩任务；空分和零分不等同于异常"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/grade-fail')">挂科清单</AppButton>
    </template>

    <div class="mp-stack">
      <div class="aa-filter">
        <label class="aa-filter__item">学期<input v-model.trim="term" class="aa-input aa-input--sm" placeholder="学期码（空=全部）" @keyup.enter="search" /></label>
        <label class="aa-filter__item">
          异常类型
          <AppSelect v-model="exceptionFlag" :options="exceptionFlagOptions" placeholder="" @change="search" />
        </label>
        <AppButton @click="search">查询</AppButton>
      </div>

      <p class="mp-note">这里展示成绩任务的正式任课关系，只用于定位原任务；不代表当前审批责任人。</p>
      <ErrorState v-if="error" :description="error" @retry="restoreRoute" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="无成绩异常记录" description="当前范围内没有缺考、缓考、免修或作弊标记的学生" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="recordId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-exceptionFlag="{ row }">
          <AppStatusTag :type="exceptionFlagColor(row.exceptionFlag)">{{ EXCEPTION_FLAG_LABEL[row.exceptionFlag] || '异常类型待核对' }}</AppStatusTag>
        </template>
        <template #cell-taskStatus="{ row }">
          <AppStatusTag :type="taskStatusColor(row.taskStatus)">{{ TASK_STATUS_LABEL[row.taskStatus] || '任务状态待核对' }}</AppStatusTag>
        </template>
        <template #cell-teachingRelation="{ row }">
          <span>{{ teachingRelation(row) }}</span><small class="aa-cell-note">教学任务 {{ row.teachingTaskId || '未关联' }} · 班级 {{ row.classId || '未关联' }}</small>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" :disabled="!row.gradeTaskId" @click="goTask(row)">查看原任务</button>
          <button class="mp-link" :disabled="!row.studentId" @click="goTranscript(row)">成绩单</button>
        </template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
/** Page ID: AA-185 成绩异常。GET /grade-views/exception-list。
 * 汇总各录入任务中正式 exception_flag 的学生（跨任务读侧下钻，零写入）。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppSelect } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { currentUserFromToken } from '@/services/http/client'
import { gradeError } from './parallel-c/grade-review'
import { EXCEPTION_FLAG_LABEL, exceptionFlagColor } from '@/modules/academicAffairs/constants/grade-graduation'

const TASK_STATUS_LABEL = {
  NOT_STARTED: '未开始', INPUTTING: '录入中', SUBMITTED: '已提交',
  COLLEGE_REVIEW: '学院审核中', ACADEMIC_REVIEW: '教务终审中', PUBLISHED: '已发布',
  RETURNED: '已退回', ARCHIVED: '已归档'
}

export default {
  name: 'AaGradeExceptionView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppStatusTag, AppSelect },
  props: { ctx: { type: Object, required: true } },
  inject: { academicFlow: { default: null } },
  data() {
    return {
      alive: true, readSeq: 0, loading: true, error: '', rows: [], term: '', exceptionFlag: '',
      pagination: { page: 1, pageSize: 50, total: 0 },
      EXCEPTION_FLAG_LABEL, TASK_STATUS_LABEL,
      columns: [
        { key: 'studentName', title: '学生' },
        { key: 'studentNo', title: '学号' },
        { key: 'courseName', title: '课程' },
        { key: 'term', title: '学期' },
        { key: 'exceptionFlag', title: '异常类型' },
        { key: 'taskStatus', title: '任务状态' },
        { key: 'teachingRelation', title: '正式任课关系', width: '240px' },
        { key: 'actions', title: '操作', width: '180px' }
      ]
    }
  },
  computed: {
    identityKey() { const u = currentUserFromToken() || {}; return JSON.stringify([u.tenantId, u.userId, u.activeContextId, u.currentRoleCode, this.ctx.currentRole, this.ctx.dataScope, this.ctx.ctxKey, this.ctx.permissionVersion, this.ctx.dataScopeVersion, this.ctx.permissionPatterns]) },
    routeKey() { return this.$route?.fullPath || '' },

    exceptionFlagOptions() {
      return [{ value: '', label: '全部' }, ...Object.entries(EXCEPTION_FLAG_LABEL).map(([value, label]) => ({ value, label }))]
    }
  },
  created() { this.restoreRoute() },
  watch: { identityKey() { this.invalidate(); this.restoreRoute() }, routeKey() { this.invalidate(); this.restoreRoute() } },
  beforeUnmount() { this.alive = false; this.readSeq++ },
  methods: {
    exceptionFlagColor,
    taskStatusColor(s) {
      if (s === 'PUBLISHED') return 'success'
      if (s === 'RETURNED') return 'danger'
      if (['SUBMITTED', 'COLLEGE_REVIEW', 'ACADEMIC_REVIEW'].includes(s)) return 'processing'
      return 'default'
    },
    teachingRelation(row) {
      if (row.teacherAuthorityReady !== true) return row.teacherKey ? `任课关系未核对 · 任务登记 ${row.teacherKey}` : '任课关系未核对'
      const names = Array.isArray(row.teacherNames) ? row.teacherNames : [], keys = Array.isArray(row.teacherKeys) ? row.teacherKeys : []
      if (names.length) return names.join('、')
      if (keys.length) return keys.join('、')
      return '任课关系未配置'
    },
    exactId(value) { const id = String(value ?? '').trim(); return /^[1-9]\d*$/.test(id) ? id : '' },
    invalidate() { this.readSeq++; this.loading = false; this.error = ''; this.rows = []; this.pagination = { page: 1, pageSize: 50, total: 0 } },
    forbidden(err) { return /403|NO_DATA_SCOPE|FORBIDDEN|NO_PERMISSION/.test([err?.code, err?.bizCode].join(' ')) },
    async navigate(patch) { const query = { ...this.$route.query, ...patch }; Object.keys(query).forEach(key => { if (query[key] == null || query[key] === '') delete query[key] }); const before = this.routeKey; try { await this.$router.replace({ path: this.$route.path, query }) } catch { /* duplicate navigation */ } if (before === this.routeKey) this.restoreRoute() },
    restoreRoute() {
      const query = this.$route?.query || {}
      const allowed = new Set(this.exceptionFlagOptions.map(item => item.value))
      if ((query.term != null && (typeof query.term !== 'string' || query.term.length > 64 || Array.from(query.term).some(char => char.codePointAt(0) < 32 || char.codePointAt(0) === 127))) || (query.type != null && typeof query.type !== 'string') || !allowed.has(query.type || '') || (query.page != null && typeof query.page !== 'string') || (query.pageSize != null && typeof query.pageSize !== 'string')) { this.error = '筛选或分页参数无效，请重新选择。'; return }
      this.term = query.term || ''; this.exceptionFlag = query.type || ''
      const page = Number(query.page || ''), pageSize = Number(query.pageSize || '')
      this.pagination.page = Number.isInteger(page) && page > 0 && page <= 100000 ? page : 1
      this.pagination.pageSize = Number.isInteger(pageSize) && pageSize > 0 && pageSize <= 200 ? pageSize : 50
      this.load()
    },
    goTask(row) {
      const taskId = this.exactId(row?.gradeTaskId); if (!taskId) { this.error = '原成绩任务标识无效，无法下钻。'; return }
      const returnToken = this.academicFlow?.captureReturn?.()
      this.$router.push({ path: '/admin/academic-affairs/grade-entry', query: { taskId, ...(returnToken ? { returnToken } : {}) } })
    },
    goTranscript(row) {
      this.$router.push({ path: '/admin/academic-affairs/transcript', query: { studentId: row.studentId, name: row.studentName } })
    },
    onPageChange(p) { this.navigate({ term: this.term || undefined, type: this.exceptionFlag || undefined, page: String(p), pageSize: String(this.pagination.pageSize) }) },
    search() { this.navigate({ term: this.term || undefined, type: this.exceptionFlag || undefined, page: '1', pageSize: String(this.pagination.pageSize) }) },
    normalizeRows(value) {
      if (!Array.isArray(value)) throw { code: 'EXCEPTION_PAGE_INVALID', message: '异常分页结构无效' }
      const records = new Set()
      return value.map(row => {
        const recordId = this.exactId(row?.recordId), gradeTaskId = this.exactId(row?.gradeTaskId)
        if (!recordId || !gradeTaskId || records.has(recordId) || (this.term && row.term !== this.term) || (this.exceptionFlag && row.exceptionFlag !== this.exceptionFlag)) throw { code: 'EXCEPTION_OBJECT_MISMATCH', message: '异常记录与当前任务或筛选条件不一致' }
        for (const key of ['classId', 'teachingTaskId']) if (row[key] != null && row[key] !== '' && !this.exactId(row[key])) throw { code: 'EXCEPTION_RELATION_MISMATCH', message: '异常记录的教学关系标识无效' }
        if (typeof row.teacherAuthorityReady !== 'boolean') throw { code: 'EXCEPTION_RELATION_MISMATCH', message: '正式任课关系核验状态缺失' }
        for (const key of ['teacherKeys', 'teacherNames']) if (!Array.isArray(row[key]) || row[key].some(value => typeof value !== 'string') || new Set(row[key]).size !== row[key].length) throw { code: 'EXCEPTION_RELATION_MISMATCH', message: '异常记录的任课关系结构无效' }
        records.add(recordId); return { ...row, recordId, gradeTaskId }
      })
    },
    async load() {
      const seq = ++this.readSeq, identity = this.identityKey, route = this.routeKey, page = this.pagination.page, pageSize = this.pagination.pageSize, term = this.term, exceptionFlag = this.exceptionFlag
      const valid = () => this.alive && seq === this.readSeq && identity === this.identityKey && route === this.routeKey && page === this.pagination.page && pageSize === this.pagination.pageSize && term === this.term && exceptionFlag === this.exceptionFlag
      this.loading = true; this.error = ''; this.rows = []; this.pagination.total = 0
      try {
        const res = await academicAffairsApi.getExceptionList({ term: term || undefined, exceptionFlag: exceptionFlag || undefined, page, pageSize })
        if (!valid()) return
        if (res.code !== 0) throw res
        if ((res.data?.page != null && Number(res.data.page) !== page) || (res.data?.pageSize != null && Number(res.data.pageSize) !== pageSize)) throw { code: 'EXCEPTION_PAGE_MISMATCH', message: '异常响应页码与当前页面不一致' }
        this.rows = this.normalizeRows(res.data?.list)
        const total = res.data?.total; if (!Number.isSafeInteger(total) || total < this.rows.length) throw { code: 'EXCEPTION_TOTAL_INVALID', message: '异常总数与当前页不一致' }; this.pagination.total = total
      } catch (err) { if (valid()) { this.rows = []; this.pagination.total = 0; if (this.forbidden(err)) { this.term = ''; this.exceptionFlag = ''; this.loading = false } this.error = gradeError(err, '记录读取失败，请重试。') } }
      finally { if (valid()) this.loading = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; gap: 16px; align-items: center; }
.aa-filter__item { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-input { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; }
.aa-input--sm { width: 200px; }
.aa-select { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; }
.aa-cell-note { display: block; margin-top: 4px; color: var(--text-500, #646a73); font-size: 12px; }
</style>
