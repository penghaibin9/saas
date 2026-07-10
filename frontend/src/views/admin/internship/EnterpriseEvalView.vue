<template>
  <ModulePageShell title="评价管理" subtitle="完成学生、企业和教师评价，并进行成绩核算、审核、发布和复核 · 企业评价 · 企业导师五维评价 · 学校审核 · 来源可追溯"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppButton variant="ghost" @click="$router.push('/admin/internship/student-evals')">学生自评与教师评价</AppButton>
      <AppButton variant="ghost" @click="$router.push('/admin/internship/scores')">综合成绩</AppButton>
      <AppPermissionButton code="internship.enterpriseEval.create" variant="primary" @click="openCreate">＋ 录入企业评价</AppPermissionButton>
      <AppExportButton :export-fn="exportFn" @exported="onExported">⬇ 导出 Excel 台账</AppExportButton>
    </template>

    <div class="mp-stack">
      <ModuleSummaryStrip :metrics="summaryMetrics" :note="summaryMetrics.length ? '' : '暂无统计口径'" />

      <div class="bar">
        <AppSearchBox v-model="keyword" placeholder="按学生姓名搜索" @search="reload" />
        <AppQuickFilterChips v-model="statusFilter" :options="statusOptions" allow-clear @change="reload" />
      </div>

      <DualPaneWorkspace aside-title="企业评价" :aside-count="total">
        <!-- 左栏：企业评价队列（紧凑列表，连续审核） -->
        <template #aside>
          <div v-if="loading" class="state">加载中…</div>
          <div v-else-if="error" class="state is-err">{{ error }} <button type="button" class="mp-link" @click="load">重试</button></div>
          <div v-else-if="!rows.length" class="state">当前筛选下暂无企业评价记录</div>
          <ul v-else class="lv-list">
            <li v-for="r in rows" :key="r.id">
              <button type="button" class="lv-item" :class="{ 'is-active': String(r.id) === selectedId }" @click="select(r.id)">
                <div class="lv-item__row">
                  <span class="lv-item__name">{{ r.studentName }}</span>
                  <AppStatusTag :type="reviewTone(r.reviewStatus)">{{ r.reviewStatusLabel }}</AppStatusTag>
                </div>
                <div class="lv-item__sub">{{ r.studentNo }}<template v-if="r.mentorName"> · 企业导师 {{ r.mentorName }}</template></div>
                <div class="lv-item__sub">
                  均分 {{ r.avgScore }} · {{ r.sourceLabel }}<template v-if="r.recommendHire"> · 建议录用</template>
                </div>
              </button>
            </li>
          </ul>
        </template>
        <template #aside-foot>
          <div class="lv-pager">
            <button type="button" class="mp-link" :disabled="page <= 1 || loading" @click="onPageChange(page - 1)">上一页</button>
            <span class="mp-note">第 {{ page }} / 共 {{ pageCount }} 页</span>
            <button type="button" class="mp-link" :disabled="page >= pageCount || loading" @click="onPageChange(page + 1)">下一页</button>
          </div>
        </template>

        <!-- 右栏：当前企业评价详情与审核操作 -->
        <section class="mp-card lv-main">
          <template v-if="!selectedId">
            <EmptyState v-if="doneHint" title="当前列表企业评价已全部处理"
              description="可翻页或切换筛选条件，继续审核其他企业评价" />
            <EmptyState v-else title="从左侧选择一条企业评价开始审核"
              description="点击列表项查看五维评分与评语，通过或退回后自动跳到下一条待审核" />
          </template>
          <div v-else-if="detail.loading" class="state lv-main__state">详情加载中…</div>
          <div v-else-if="detail.error" class="state is-err lv-main__state">
            {{ detail.error }} <button type="button" class="mp-link" @click="loadDetail(selectedId)">重试</button>
          </div>
          <template v-else-if="detail.data">
            <div class="lv-main__body">
              <div class="lv-head">
                <span class="lv-head__name">{{ detail.data.studentName }}</span>
                <span class="mp-note">{{ detail.data.studentNo }}</span>
                <AppStatusTag :type="reviewTone(detail.data.reviewStatus)">{{ detail.data.reviewStatusLabel }}</AppStatusTag>
              </div>

              <div class="sec-t">学生与企业岗位摘要</div>
              <AppDescriptionList :items="summaryItems" :columns="2" />

              <div class="sec-t">五维评分</div>
              <AppDescriptionList :items="scoreItems" :columns="3" />

              <div class="sec-t">评语与建议</div>
              <AppDescriptionList :items="commentItems" :columns="1" />

              <template v-if="detail.data.attachment">
                <div class="sec-t">评价扫描件</div>
                <AppFilePreview :files="attachmentFiles" @download="downloadAtt" />
              </template>

              <template v-if="hasReviewResult">
                <div class="sec-t">审核结果</div>
                <AppDescriptionList :items="reviewItems" :columns="2" />
              </template>

              <div class="sec-t">审核留痕</div>
              <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无记录" />
            </div>

            <div v-if="detail.data.reviewStatus === 'PENDING'" class="lv-foot">
              <AppPermissionButton code="internship.enterpriseEval.review" variant="ghost" :danger="true"
                @click="openReview(detail.data, 'RETURN')">退回</AppPermissionButton>
              <AppPermissionButton code="internship.enterpriseEval.review" variant="secondary"
                @click="openReview(detail.data, 'APPROVE')">通过</AppPermissionButton>
            </div>
          </template>
        </section>
      </DualPaneWorkspace>
    </div>

    <!-- 录入企业评价（保留 modal 形态：属独立编辑页范畴，下一轮迁移） -->
    <div v-if="createDlg.visible" class="modal" @click.self="createDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">录入企业评价</div>
        <div class="modal__body">
          <AppFormItem label="实习学生" required>
            <AppStudentPicker
              v-model="form.internshipId"
              :remote-search="searchInternStudents"
              placeholder="输入姓名或学号搜索实习学生"
              search-placeholder="按姓名 / 学号搜索"
              data-scope-hint="指导教师仅本人指导学生；管理员全校"
            />
          </AppFormItem>
          <AppFormItem label="企业导师姓名（来源可追溯）" required>
            <AppTextInput v-model="form.mentorName" placeholder="填写企业导师真实姓名" />
          </AppFormItem>
          <div class="scores">
            <AppFormItem v-for="s in scoreDefs" :key="s.key" :label="s.label" class="score">
              <AppNumberInput v-model="form[s.key]" :min="0" :max="100" />
            </AppFormItem>
          </div>
          <AppFormItem label="综合评语"><AppTextarea v-model="form.overallComment" :rows="2" placeholder="企业对学生的综合评语" /></AppFormItem>
          <label class="chk"><input v-model="form.recommendHire" type="checkbox" />建议录用</label>
          <AppFormItem label="评价扫描件（可选，企业签署）">
            <input type="file" class="file" @change="onFile" />
            <span v-if="form.fileId" class="att">已上传：{{ attachName }}</span>
            <span v-else-if="uploadingFile" class="att">上传中…</span>
          </AppFormItem>
          <p class="hint">五维评分均 0-100。学校录入的企业纸质评价来源标记为「学校录入」，请如实转录企业导师评价，勿代填虚构。</p>
        </div>
        <div class="modal__foot">
          <AppButton variant="ghost" @click="createDlg.visible = false">取消</AppButton>
          <AppButton variant="primary" :loading="createDlg.submitting" @click="submitCreate">提交</AppButton>
        </div>
      </div>
    </div>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      reason-label="审核意见" :submitting="cd.submitting" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppDescriptionList,
  AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppTextInput, AppNumberInput,
  AppTextarea, AppFormItem, AppFilePreview, AppStudentPicker } from '@/components/common'
import { searchInternStudents } from './components/entityPickerAdapters'
import DualPaneWorkspace from './components/DualPaneWorkspace.vue'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import { enterpriseEvalApi } from '@/modules/internship/api/enterprise-eval.api'
import { toast } from '@/utils/toast'

const SCORES = [
  { key: 'attendanceScore', label: '出勤' }, { key: 'skillScore', label: '技能' },
  { key: 'attitudeScore', label: '态度' }, { key: 'collaborationScore', label: '协作' }, { key: 'safetyScore', label: '安全纪律' }
]
const STATUS_OPTIONS = [{ label: '待审核', value: 'PENDING' }, { label: '已通过', value: 'APPROVED' }, { label: '已退回', value: 'RETURNED' }]
/* 右栏只渲染 /internship/enterprise-evals/{id} 真实返回字段（见 internship_enterprise_eval_service._row + get_eval） */
const SUMMARY_FIELDS = [
  { key: 'studentName', label: '学生' }, { key: 'studentNo', label: '学号' },
  { key: 'advisorName', label: '指导教师' }, { key: 'mentorName', label: '企业导师' },
  { key: 'positionName', label: '岗位' }, { key: 'sourceLabel', label: '来源' },
  { key: 'createdAt', label: '录入时间' }
]
const SCORE_FIELDS = [
  { key: 'attendanceScore', label: '出勤' }, { key: 'skillScore', label: '技能' },
  { key: 'attitudeScore', label: '态度' }, { key: 'collaborationScore', label: '协作' },
  { key: 'safetyScore', label: '安全纪律' }, { key: 'avgScore', label: '均分' }
]
const COMMENT_FIELDS = [
  { key: 'overallComment', label: '综合评语' }, { key: 'recommendHire', label: '建议录用', bool: true }
]
const REVIEW_FIELDS = [
  { key: 'reviewStatusLabel', label: '审核状态' }, { key: 'reviewComment', label: '审核意见' }
]

function emptyForm() {
  return { internshipId: '', mentorName: '', attendanceScore: null, skillScore: null,
    attitudeScore: null, collaborationScore: null, safetyScore: null, overallComment: '', recommendHire: false, fileId: '' }
}

export default {
  name: 'EnterpriseEvalView',
  components: { ModulePageShell, EmptyState, DualPaneWorkspace, ModuleSummaryStrip, AppButton,
    AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppDescriptionList,
    AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppTextInput, AppNumberInput, AppTextarea,
    AppFormItem, AppFilePreview, AppStudentPicker },
  data() {
    return {
      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',
      keyword: '', statusFilter: 'PENDING', statusOptions: STATUS_OPTIONS, scoreDefs: SCORES,
      selectedId: '', doneHint: false,
      detail: { loading: false, error: '', data: null },
      form: emptyForm(), attachName: '', uploadingFile: false,
      createDlg: { visible: false, submitting: false },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false, submitting: false },
      pending: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    pageCount() { return Math.max(1, Math.ceil(this.total / this.pageSize)) },
    summaryMetrics() {
      // 仅在列表真实加载成功后展示服务端 total；loading / error 一律不展示
      if (this.loading || this.error) return []
      const cur = this.statusOptions.find((o) => o.value === this.statusFilter)
      return [{ label: '企业评价 · ' + (cur ? cur.label : '全部'), value: this.total,
        tone: this.statusFilter === 'PENDING' && this.total ? 'warn' : undefined }]
    },
    summaryItems() { const d = this.detail.data || {}; return SUMMARY_FIELDS.map((f) => ({ label: f.label, value: d[f.key] })) },
    scoreItems() { const d = this.detail.data || {}; return SCORE_FIELDS.map((f) => ({ label: f.label, value: d[f.key] })) },
    commentItems() { const d = this.detail.data || {}; return COMMENT_FIELDS.map((f) => ({ label: f.label, value: f.bool ? (d[f.key] ? '是' : '否') : d[f.key] })) },
    reviewItems() { const d = this.detail.data || {}; return REVIEW_FIELDS.map((f) => ({ label: f.label, value: d[f.key] })) },
    hasReviewResult() { const d = this.detail.data || {}; return !!d.reviewStatus && d.reviewStatus !== 'PENDING' },
    attachmentFiles() { const a = this.detail.data?.attachment; return a ? [{ id: a.fileId, name: a.fileName, sensitive: true }] : [] },
    auditRecords() {
      return (this.detail.data?.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actor: t.operator, reason: t.detail && (t.detail.comment || ''), at: t.occurredAt
      }))
    }
  },
  watch: {
    '$route.query.id': {
      immediate: true,
      handler(id) {
        const sid = (id || '').toString()
        if (sid === this.selectedId) return
        this.selectedId = sid
        if (sid) { this.doneHint = false; this.loadDetail(sid) } else { this.detail = { loading: false, error: '', data: null } }
      }
    }
  },
  created() { this.load() },
  methods: {
    reviewTone(s) { return s === 'APPROVED' ? 'success' : s === 'RETURNED' ? 'danger' : 'warning' },
    exportFn() { return enterpriseEvalApi.exportEvals({ keyword: this.keyword, reviewStatus: this.statusFilter }) },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条（水印 + 导出留痕）`) },
    reload() { this.page = 1; this.load() },
    onPageChange(p) {
      if (p < 1 || p > this.pageCount || p === this.page) return
      this.page = p; this.load()
    },
    async load() {
      this.loading = true; this.error = ''
      const params = { page: this.page, pageSize: this.pageSize, keyword: this.keyword }
      if (this.statusFilter) params.reviewStatus = this.statusFilter
      const res = await enterpriseEvalApi.getEvals(params)
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
      // 处理完当前页最后一条后翻页越界（如筛选=待审核时该页清空）：自动回到最后一个有效页
      const pc = Math.max(1, Math.ceil(this.total / this.pageSize))
      if (!this.rows.length && this.total > 0 && this.page > pc) { this.page = pc; return this.load() }
    },
    select(id) {
      const sid = String(id)
      this.doneHint = false
      if (String(this.$route.query.id || '') === sid) {
        if (this.selectedId !== sid) { this.selectedId = sid; this.loadDetail(sid) }
        return
      }
      this.$router.replace({ query: { ...this.$route.query, id: sid } })
    },
    clearSelection() {
      const query = { ...this.$route.query }
      delete query.id
      this.$router.replace({ query })
    },
    async loadDetail(id) {
      this.detail = { loading: true, error: '', data: null }
      const res = await enterpriseEvalApi.getDetail(id)
      if (String(this.selectedId) !== String(id)) return
      this.detail.loading = false
      if (res.code !== 0) { this.detail.error = res.message || '详情加载失败'; return }
      this.detail.data = res.data
    },
    // 选择器远程搜索（岗位实习模块适配层，后端裁定关键字与数据范围）
    searchInternStudents,
    openCreate() {
      // 学生候选改为选择器内按关键字远程搜索，不再一次性预载 200 条
      this.form = emptyForm(); this.attachName = ''; this.createDlg.visible = true
    },
    async onFile(e) {
      const file = e.target.files && e.target.files[0]
      if (!file) return
      this.uploadingFile = true
      const res = await enterpriseEvalApi.uploadAttachment(file)
      this.uploadingFile = false
      if (res.code !== 0) return toast.error(res.message || '上传失败')
      this.form.fileId = res.data.fileId; this.attachName = res.data.fileName || file.name
    },
    async submitCreate() {
      if (!this.form.internshipId) return toast.error('请选择实习学生')
      if (!this.form.mentorName.trim()) return toast.error('请填写企业导师姓名')
      for (const s of SCORES) {
        const v = this.form[s.key]
        if (v === null || v === '' || v < 0 || v > 100) return toast.error(`${s.label}评分须为 0-100`)
      }
      this.createDlg.submitting = true
      const res = await enterpriseEvalApi.create(this.form)
      this.createDlg.submitting = false
      if (res.code !== 0) return toast.error(res.message || '提交失败')
      this.createDlg.visible = false; toast.success('已录入并写审计'); this.load()
    },
    async downloadAtt() {
      const a = this.detail.data?.attachment
      if (!a) return
      try { await enterpriseEvalApi.downloadAttachment(a.fileId, a.fileName) } catch (e) { toast.error('下载失败：' + (e.message || '')) }
    },
    openReview(r, action) {
      const ap = action === 'APPROVE'
      this.pending = { id: r.id, action }
      this.cd = { visible: true, title: ap ? '企业评价 · 通过' : '企业评价 · 退回',
        content: `${ap ? '通过' : '退回'}「${r.studentName}」的企业评价，意见将写入审计。`,
        danger: !ap, confirmText: ap ? '通过' : '退回', requireReason: !ap, submitting: false }
    },
    async onConfirm({ reason }) {
      this.cd.submitting = true
      const res = await enterpriseEvalApi.review(this.pending.id, { action: this.pending.action, comment: reason || '' })
      this.cd.submitting = false
      if (res.code !== 0) return toast.error(res.message || '操作失败')
      this.cd.visible = false; toast.success('审核完成，已写审计')
      await this.advanceAfterReview(this.pending.id)
    },
    /** 审核成功后：刷新当前页并自动选中下一条待审核；无下一条则清空选中并提示已处理完 */
    async advanceAfterReview(oldId) {
      const oldIndex = Math.max(0, this.rows.findIndex((r) => String(r.id) === String(oldId)))
      await this.load()
      let after = null, before = null
      this.rows.forEach((r, i) => {
        if (r.reviewStatus !== 'PENDING' || String(r.id) === String(oldId)) return
        if (i >= oldIndex) { if (!after) after = r } else if (!before) before = r
      })
      const next = after || before
      if (next) { this.select(next.id); return }
      this.clearSelection()
      this.doneHint = true
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.bar { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.state { padding: var(--space-6); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); border: 1px dashed var(--border-base); border-radius: var(--radius-base); margin: var(--space-3); }
.state.is-err { color: var(--danger-600); }
.sec-t { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); margin: var(--space-4) 0 var(--space-2); }
.hint { margin: var(--space-2) 0 0; font-size: var(--font-size-xs); color: var(--text-tertiary); }

/* 左栏紧凑列表 */
.lv-list { list-style: none; margin: 0; padding: var(--space-2); display: flex; flex-direction: column; gap: var(--space-1); }
.lv-item { display: block; width: 100%; text-align: left; font: inherit; cursor: pointer; background: transparent; border: 1px solid transparent; border-radius: var(--radius-md, 8px); padding: var(--space-2) var(--space-3); transition: background 0.12s ease, border-color 0.12s ease; }
.lv-item:hover { background: var(--primary-50, #eff6ff); }
.lv-item.is-active { background: var(--primary-50, #eff6ff); border-color: var(--primary-600, #2563eb); }
.lv-item__row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
.lv-item__name { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary); }
.lv-item__sub { margin-top: 2px; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.lv-pager { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }

/* 右栏详情与固定操作区 */
.lv-main { display: flex; flex-direction: column; min-height: 320px; }
.lv-main__body { flex: 1; padding: var(--space-4); min-width: 0; }
.lv-main__state { margin: var(--space-4); }
.lv-head { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.lv-head__name { font-size: var(--font-size-md, 15px); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.lv-foot { position: sticky; bottom: 0; display: flex; justify-content: flex-end; gap: var(--space-2); padding: var(--space-3) var(--space-4); border-top: 1px solid var(--border-light); background: var(--bg-card, #fff); border-radius: 0 0 var(--r, 12px) var(--r, 12px); }

/* 录入企业评价 modal（保留形态，下一轮迁独立编辑页） */
.scores { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.score { width: calc(20% - var(--space-2)); min-width: 90px; }
.chk { display: flex; align-items: center; gap: var(--space-1); font-size: var(--font-size-sm); color: var(--text-secondary); margin-bottom: var(--space-3); }
.file { font-size: var(--font-size-xs); }
.att { font-size: var(--font-size-xs); color: var(--success-700); margin-left: var(--space-2); }
.modal { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center; justify-content: center; z-index: var(--z-modal, 1000); padding: var(--space-4); }
.modal__card { background: var(--bg-card); border-radius: var(--radius-lg); width: min(600px, 100%); max-height: 88vh; display: flex; flex-direction: column; box-shadow: var(--shadow-lg); }
.modal__head { padding: var(--space-4); font-weight: var(--font-weight-semibold); border-bottom: 1px solid var(--border-light); }
.modal__body { padding: var(--space-4); overflow-y: auto; }
.modal__foot { padding: var(--space-3) var(--space-4); border-top: 1px solid var(--border-light); display: flex; justify-content: flex-end; gap: var(--space-2); }

</style>
