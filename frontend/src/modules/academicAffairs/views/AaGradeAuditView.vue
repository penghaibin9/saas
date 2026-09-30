<template>
  <ModulePageShell
    title="成绩操作审计"
    subtitle="按时间核对成绩操作；可见范围由当前身份与服务端权限决定"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="aa-filter-row">
        <AppSelect v-model="bizType" :options="bizTypeOptions" placeholder="" @change="onFilterChange" />
      </div>

      <ErrorState v-if="error" :description="error" @retry="restoreRoute" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无匹配的操作记录" description="成绩相关操作发生后会记入这里" />
      <template v-else>
        <ol class="aa-audit-timeline" aria-label="成绩操作时间线">
          <li v-for="row in rows" :key="row.id" class="aa-audit-event">
            <time>{{ formatTime(row.occurredAt) }}</time>
            <div><strong>{{ actionLabel(row.action) }}</strong><p>{{ bizTypeLabel(row.bizType) }} · {{ row.operator || '操作人待核对' }} · {{ row.roleName || '角色待核对' }}</p>
              <details><summary>查看操作证据</summary><p>业务对象：{{ row.bizId || '未记录' }}</p><p>{{ row.detail || '暂无操作说明' }}</p><div class="aa-audit-values"><article><strong>变更前</strong><small>{{ evidenceKind(row.beforeValue) }}</small><pre>{{ evidenceText(row.beforeValue) }}</pre></article><article><strong>变更后</strong><small>{{ evidenceKind(row.afterValue) }}</small><pre>{{ evidenceText(row.afterValue) }}</pre></article></div><p class="mp-note">这里只展示正式审计表保存的原始值；无法解析的历史文本不会标为已结构核验。当前接口没有正式请求标识，页面不生成替代值。</p></details>
            </div>
          </li>
        </ol>
        <div class="aa-audit-pages"><button class="mp-btn" :disabled="pagination.page <= 1" @click="onPageChange(pagination.page - 1)">上一页</button><span>第 {{ pagination.page }} 页 · 共 {{ pagination.total }} 条</span><button class="mp-btn" :disabled="pagination.page * pagination.pageSize >= pagination.total" @click="onPageChange(pagination.page + 1)">下一页</button></div>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * Page ID: AA-196 成绩操作审计。
 * 只读，复用 GET /grade-views/audit（新增，读 t_affairs_audit_trail，biz_type=AA_GRADE_*，
 * 数据来自成绩模块既有 _audit() 写入，非新表）。数据范围由后端裁定：
 * ACADEMIC_ADMIN/SCHOOL_ADMIN/COLLEGE_ADMIN 查全量，ACADEMIC_TEACHER 仅本人操作，其余角色 403。
 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSelect } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { currentUserFromToken } from '@/services/http/client'
import { gradeError } from './parallel-c/grade-review'

const BIZ_TYPE_LABEL = {
  AA_GRADE_TASK: '成绩任务', AA_GRADE_RECORD: '成绩明细/更正', AA_GRADE_TRANSCRIPT: '成绩单导出'
}
const ACTION_LABEL = {
  CREATE: '创建任务', ENTER: '录入成绩', IMPORT: '批量导入', SUBMIT: '提交学院审核',
  COLLEGE_RETURN: '学院退回', COLLEGE_APPROVE: '学院通过', PUBLISH: '教务发布',
  ACADEMIC_RETURN: '教务退回', ARCHIVE: '学期归档',
  CHANGE_APPLY: '发起更正申请', CHANGE_STEP: '更正流转', CHANGE_APPROVE: '更正终审通过', CHANGE_REJECT: '更正驳回',
  EXPORT: '导出成绩单', EXPORT_QUERY_COPY: '导出成绩查询件'
}

export default {
  name: 'AaGradeAuditView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppSelect },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      bizType: '',
      bizTypeOptions: [
        { value: '', label: '全部对象' },
        { value: 'AA_GRADE_TASK', label: '成绩任务（录入/提交/审核/发布/退回/归档）' },
        { value: 'AA_GRADE_RECORD', label: '成绩明细更正' },
        { value: 'AA_GRADE_TRANSCRIPT', label: '成绩单导出' }
      ],
      alive: true, readSeq: 0, loading: true, error: '', rows: [],
      pagination: { page: 1, pageSize: 20, total: 0 },

    }
  },
  computed: {
    identityKey() { const u = currentUserFromToken() || {}; return JSON.stringify([u.tenantId, u.userId, u.activeContextId, u.currentRoleCode, this.ctx.currentRole, this.ctx.dataScope, this.ctx.ctxKey, this.ctx.permissionVersion, this.ctx.dataScopeVersion, this.ctx.permissionPatterns]) },
    routeKey() { return this.$route?.fullPath || '' }
  },
  created() { this.restoreRoute() },
  watch: { identityKey() { this.invalidate(); this.restoreRoute() }, routeKey() { this.invalidate(); this.restoreRoute() } },
  beforeUnmount() { this.alive = false; this.readSeq++ },
  methods: {
    bizTypeLabel(v) { return BIZ_TYPE_LABEL[v] || (v ? '待确认' : '—') },
    actionLabel(v) { return ACTION_LABEL[v] || (v ? '待确认' : '—') },
    formatTime(v) { return v ? String(v).replace('T', ' ').slice(0, 19) : '—' },
    evidenceValue(value) { if (value == null || value === '') return { text: '未记录', kind: '原审计值为空' }; const text = typeof value === 'string' ? value : JSON.stringify(value); try { return { text: JSON.stringify(JSON.parse(text), null, 2), kind: 'JSON 文本（仅格式化展示）' } } catch { return { text, kind: '历史原文（未结构核验）' } } },
    evidenceText(value) { return this.evidenceValue(value).text },
    evidenceKind(value) { return this.evidenceValue(value).kind },
    invalidate() { this.readSeq++; this.loading = false; this.rows = []; this.error = ''; this.pagination = { page: 1, pageSize: 20, total: 0 } },
    forbidden(err) { return /403|NO_DATA_SCOPE|FORBIDDEN|NO_PERMISSION/.test([err?.code, err?.bizCode].join(' ')) },
    async navigate(patch) { const query = { ...this.$route.query, ...patch }; Object.keys(query).forEach(key => { if (query[key] == null || query[key] === '') delete query[key] }); const before = this.routeKey; try { await this.$router.replace({ path: this.$route.path, query }) } catch { /* duplicate navigation */ } if (before === this.routeKey) this.restoreRoute() },
    restoreRoute() {
      const query = this.$route?.query || {}, rawType = query.type
      const allowed = new Set(this.bizTypeOptions.map(item => item.value))
      if ((rawType != null && typeof rawType !== 'string') || !allowed.has(rawType || '') || (query.page != null && typeof query.page !== 'string') || (query.pageSize != null && typeof query.pageSize !== 'string')) { this.error = '审计筛选或分页参数无效，请重新选择。'; return }
      this.bizType = rawType || ''
      const page = Number(query.page || ''), pageSize = Number(query.pageSize || '')
      this.pagination.page = Number.isInteger(page) && page > 0 && page <= 100000 ? page : 1
      this.pagination.pageSize = Number.isInteger(pageSize) && pageSize > 0 && pageSize <= 200 ? pageSize : 20
      this.load()
    },
    onFilterChange() { this.navigate({ type: this.bizType || undefined, page: '1', pageSize: String(this.pagination.pageSize) }) },
    onPageChange(p) { this.navigate({ type: this.bizType || undefined, page: String(p), pageSize: String(this.pagination.pageSize) }) },
    normalizeRows(value) {
      if (!Array.isArray(value)) throw { code: 'AUDIT_PAGE_INVALID', message: '审计分页结构无效' }
      const ids = new Set()
      return value.map(row => { const id = String(row?.id || ''); if (!/^[1-9]\d*$/.test(id) || ids.has(id) || (this.bizType && row.bizType !== this.bizType)) throw { code: 'AUDIT_OBJECT_MISMATCH', message: '审计记录与当前筛选对象不一致' }; ids.add(id); return { ...row } })
    },
    async load() {
      const seq = ++this.readSeq, identity = this.identityKey, route = this.routeKey, page = this.pagination.page, pageSize = this.pagination.pageSize, bizType = this.bizType
      const valid = () => this.alive && seq === this.readSeq && identity === this.identityKey && route === this.routeKey && page === this.pagination.page && pageSize === this.pagination.pageSize && bizType === this.bizType
      this.loading = true; this.error = ''; this.rows = []; this.pagination.total = 0
      try {
        const res = await academicAffairsApi.getGradeAudit({ bizType: bizType || undefined, page, pageSize })
        if (!valid()) return
        if (res.code !== 0) throw res
        if ((res.data?.page != null && Number(res.data.page) !== page) || (res.data?.pageSize != null && Number(res.data.pageSize) !== pageSize)) throw { code: 'AUDIT_PAGE_MISMATCH', message: '审计响应页码与当前页面不一致' }
        this.rows = this.normalizeRows(res.data?.list)
        const total = res.data?.total; if (!Number.isSafeInteger(total) || total < this.rows.length) throw { code: 'AUDIT_TOTAL_INVALID', message: '审计总数与当前页不一致' }; this.pagination.total = total
      } catch (err) { if (valid()) { this.rows = []; this.pagination.total = 0; if (this.forbidden(err)) { this.bizType = ''; this.loading = false } this.error = gradeError(err, '记录读取失败，请重试。') } }
      finally { if (valid()) this.loading = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-audit-timeline { list-style: none; margin: 0; padding: 0; }
.aa-audit-event { display: grid; grid-template-columns: 170px 1fr; gap: 24px; padding: 20px; border-bottom: 1px solid var(--border-200); background: var(--bg-white); }
.aa-audit-event time, .aa-audit-event p { font-size: 13px; color: var(--text-500); }
.aa-audit-event summary { cursor: pointer; color: var(--primary-600); }
.aa-audit-values { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 12px; }
.aa-audit-values article { min-width: 0; padding: 12px; border: 1px solid var(--border-200); border-radius: 8px; }
.aa-audit-values small { display: block; margin-top: 4px; color: var(--text-500); }
.aa-audit-values pre { max-height: 240px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; font: 12px/1.6 ui-monospace, SFMono-Regular, Consolas, monospace; }
.aa-audit-pages { display: flex; justify-content: center; gap: 16px; align-items: center; }
.aa-filter-row { margin-bottom: 12px; }
.aa-input {
  height: 34px;
  padding: 0 12px;
  border: 1px solid var(--border-300, #d0d3d9);
  border-radius: 6px;
  background: var(--bg-white, #fff);
  color: var(--text-900, #1f2329);
  font-size: 14px;
}
@media (max-width: 760px) { .aa-audit-event { grid-template-columns: 1fr; gap: 8px; } .aa-audit-values { grid-template-columns: 1fr; } }
</style>
