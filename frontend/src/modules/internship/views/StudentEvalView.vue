<template>
  <ModulePageShell title="学生与教师评价" subtitle="阅读学生自评，完善指导意见，再交由学校审核。"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppButton variant="ghost" @click="goEnterpriseEvals">企业评价</AppButton>
      <AppExportButton :export-fn="exportFn" :has-permission="canBtn('internship.eval.self.export')" @exported="onExported">导出鉴定台账</AppExportButton>
    </template>

    <div class="mp-stack">
      <ActionReceipt :receipt="lastReceipt" @close="lastReceipt = null" />

      <div class="bar">
        <AppSearchBox v-model="keyword" placeholder="按学生姓名搜索" @search="reload" />
        <AppQuickFilterChips v-model="statusFilter" :options="statusOptions" allow-clear @change="reload" />
        <label class="view-filter">办理范围<select v-model="viewFilter" @change="reload"><option value="">全部鉴定</option><option value="self">已提交自评</option><option value="advisor">待补指导意见</option><option value="enterprise">待补企业导师意见</option><option value="position">待补岗位评分</option></select></label>
      </div>
      <p v-if="viewFilter" class="mp-note">导出台账按当前姓名与审核状态筛选，包含该批次全部办理范围。</p>

      <DualPaneWorkspace aside-title="学生鉴定" :aside-count="total">
        <!-- 左栏：学生鉴定队列（紧凑列表，连续审核） -->
        <template #aside>
          <div v-if="loading" class="state">加载中…</div>
          <div v-else-if="error" class="state is-err">{{ error }} <button type="button" class="mp-link" @click="load">重试</button></div>
          <div v-else-if="!rows.length" class="state">当前筛选下暂无学生鉴定</div>
          <ul v-else class="lv-list">
            <li v-for="r in rows" :key="r.id">
              <button type="button" class="lv-item" :class="{ 'is-active': String(r.id) === selectedId }" @click="select(r.id)">
                <div class="lv-item__row">
                  <span class="lv-item__name">{{ r.studentName }}</span>
                  <AppStatusTag :type="reviewTone(r.reviewStatus)">{{ r.reviewStatusLabel }}</AppStatusTag>
                </div>
                <div class="lv-item__sub">{{ r.studentNo }}<template v-if="r.advisorName"> · {{ r.advisorName }}</template></div>
                <div class="lv-item__sub">{{ r.createdAt }} · 自评 {{ r.submitStatusLabel }}</div>
              </button>
            </li>
          </ul>
        </template>
        <template #aside-foot>
          <AppPagination :page="page" :page-size="pageSize" :total="total"
                        :show-size-changer="false" :disabled="loading" @change="onPageChange" />
        </template>

        <!-- 右栏：当前学生鉴定详情、教师意见与审核操作 -->
        <section class="mp-card lv-main">
          <template v-if="!selectedId">
            <EmptyState v-if="doneHint" title="已处理到当前列表末尾"
              description="可翻页或调整筛选，继续核对其他鉴定"><template #actions><AppButton variant="ghost" @click="load">刷新列表</AppButton></template></EmptyState>
            <EmptyState v-else title="选择一份学生鉴定"
              description="在此查看自评、填写意见与完成审核"><template #actions><AppButton variant="ghost" @click="load">刷新列表</AppButton></template></EmptyState>
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
                <AppStatusTag :type="detail.data.submitStatus === 'SUBMITTED' ? 'success' : 'default'">自评 {{ detail.data.submitStatusLabel }}</AppStatusTag>
                <AppStatusTag :type="reviewTone(detail.data.reviewStatus)">{{ detail.data.reviewStatusLabel }}</AppStatusTag>
              </div>

              <h2 class="sec-t">学生自评</h2>
              <AppDescriptionList :items="detailItems" :columns="1" />
              <h2 class="sec-t">企业与岗位反馈</h2>
              <AppDescriptionList :items="feedbackItems" :columns="2" />
              <div v-if="detail.data.attachment?.fileId" class="evidence">
                <AppButton variant="secondary" :loading="downloading" @click="downloadAtt">下载自评附件</AppButton>
                <span class="mp-note">{{ detail.data.attachment.fileName }}</span>
                <p v-if="attachmentError" class="local-error" role="alert">{{ attachmentError }}</p>
              </div>

              <template v-if="canComment || commentDirty">
                <h2 class="sec-t">指导教师意见</h2>
                <AppInlineAlert v-if="commentConflict.active" type="warning" title="评价已更新，暂不能保存原意见" description="填写内容已保留。核对最新自评后，可恢复最新已保存意见并重新填写。">
                  <AppButton variant="ghost" @click="restoreComment">恢复最新已保存意见</AppButton>
                </AppInlineAlert>
                <div class="cmt">
                  <fieldset class="cmt__fields" :disabled="cmtSubmitting || cd.submitting || !canComment">
                  <AppFormItem label="指导教师意见" required :error="commentError">
                    <AppTextarea v-model="cmtForm.advisorOpinion" :rows="3" :maxlength="1000" placeholder="结合学生自评填写鉴定意见，至少 5 字" />
                    <AppTemplateChips class="cmt__chips" :options="ADVISOR_EVAL_COMMENT" size="compact" @pick="onPickAdvisorChip" />
                  </AppFormItem>
                  <AppFormItem label="企业导师意见（可选，如实转录）">
                    <AppTextarea v-model="cmtForm.mentorOpinion" :rows="2" :maxlength="1000" placeholder="如实转录企业导师意见" />
                    <AppTemplateChips class="cmt__chips" :options="ENTERPRISE_EVAL_COMMENT" size="compact" @pick="onPickMentorChip" />
                  </AppFormItem>
                  </fieldset>
                  <div class="cmt__actions">
                    <span class="mp-note">{{ commentDirty ? '意见尚未保存' : '保存后交由学校审核' }}</span>
                    <AppButton v-if="commentDirty && !commentConflict.active" variant="ghost" :disabled="cmtSubmitting || cd.submitting" @click="restoreComment">恢复已保存意见</AppButton>
                    <AppPermissionButton code="internship.eval.advisor.manage" :allowed="canBtn('internship.eval.advisor.manage')" variant="primary" size="sm"
                      :loading="cmtSubmitting" :disabled="commentConflict.active || cd.submitting || !canComment" @click="submitComment">保存指导意见</AppPermissionButton>
                  </div>
                </div>
              </template>
              <template v-else><h2 class="sec-t">已保存的导师意见</h2><AppDescriptionList :items="opinionItems" :columns="1" /></template>
              <template v-if="detail.data.reviewStatus !== 'PENDING'">
                <h2 class="sec-t">学校审核结果</h2><AppDescriptionList :items="reviewItems" :columns="2" />
              </template>

              <div class="sec-t">审核留痕</div>
              <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无记录" />
            </div>

            <div v-if="canReview" class="lv-foot">
              <span class="mp-note lv-foot__hint">{{ commentDirty ? '请先保存或恢复未保存意见' : !detail.data.advisorOpinion ? '等待指导教师保存意见后可通过' : '指导意见已保存，可审核' }}</span>
              <AppPermissionButton code="internship.eval.self.review" :allowed="canBtn('internship.eval.self.review')" variant="secondary" :disabled="cmtSubmitting || cd.submitting || commentDirty"
                @click="openReview(detail.data, 'RETURN')">退回</AppPermissionButton>
              <AppPermissionButton code="internship.eval.self.review" :allowed="canBtn('internship.eval.self.review')" variant="primary" :disabled="cmtSubmitting || cd.submitting || commentDirty || !detail.data.advisorOpinion"
                @click="openReview(detail.data, 'APPROVE')">通过</AppPermissionButton>
            </div>
          </template>
        </section>
      </DualPaneWorkspace>
    </div>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      :reason-chips="cd.requireReason ? REJECT_STUDENT_EVAL : []"
      :reason-label="cd.requireReason ? '退回原因（至少 5 字）' : '审核意见'" :submitting="cd.submitting" :confirm-disabled="conflict.active" @confirm="onConfirm">
      <AppInlineAlert v-if="conflict.active" type="warning" title="鉴定已更新，本次审核已暂停" description="审核意见已保留。请取消后核对最新详情，再重新选择可用操作。">
        <p v-if="conflict.stale">最新详情无法读取，请关闭后重试。</p><AppDescriptionList v-else :items="conflict.latest" :columns="1" />
      </AppInlineAlert>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppDescriptionList,
  AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppTemplateChips, AppTextarea, AppFormItem, AppPagination, AppInlineAlert } from '@/components/common'
import DualPaneWorkspace from './components/DualPaneWorkspace.vue'
import ActionReceipt from './components/ActionReceipt.vue'
import { studentEvalApi } from '@/modules/internship/api/student-eval.api'
import { downloadAttachment } from '@/modules/internship/api/guidance-visit.api'
import { emptyConflict, isConflict, captureConflict } from '@/modules/internship/composables/conflictGuard'
import { canCode } from '@/modules/internship/composables/permission'
import { toast } from '@/utils/toast'
import { ENTERPRISE_EVAL_COMMENT, REJECT_STUDENT_EVAL, ADVISOR_EVAL_COMMENT } from '@/modules/internship/constants/presetPrompts'
import { useInternshipBatchStore } from '@/stores/internshipBatch'

/* 右栏只渲染 /internship/student-evals/{id} 真实返回字段（见 internship_student_eval_service._row + _full + get_eval） */
const DETAIL = [
  { key: 'advisorName', label: '指导教师' },
  { key: 'selfSummary', label: '实习总结' }, { key: 'selfHarvest', label: '学习收获' },
  { key: 'selfProblem', label: '存在问题' }
]
const FEEDBACK = [
  { key: 'enterpriseRating', label: '对企业评分（1-5）' }, { key: 'enterpriseFeedback', label: '对企业评价' },
  { key: 'positionRating', label: '对岗位评分（1-5）' }, { key: 'positionFeedback', label: '对岗位评价' }
]
const OPINION = [
  { key: 'advisorOpinion', label: '指导教师意见' },
  { key: 'mentorOpinion', label: '企业导师意见' }
]
const STATUS_OPTIONS = [{ label: '待审核', value: 'PENDING' }, { label: '已通过', value: 'APPROVED' }, { label: '已退回', value: 'RETURNED' }]

export default {
  name: 'StudentEvalView',
  props: { ctx: { type: Object, default: () => ({}) } },
  components: { ModulePageShell, EmptyState, DualPaneWorkspace, AppButton,
    AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppDescriptionList,
    AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppTemplateChips, AppTextarea, AppFormItem, AppPagination,
    ActionReceipt, AppInlineAlert },
  data() {
    return {
      ENTERPRISE_EVAL_COMMENT, REJECT_STUDENT_EVAL, ADVISOR_EVAL_COMMENT,
      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '', listSequence: 0,
      keyword: '', statusFilter: 'PENDING', statusOptions: STATUS_OPTIONS, viewFilter: '',
      selectedId: '', doneHint: false,
      detail: { loading: false, error: '', data: null },
      cmtForm: { advisorOpinion: '', mentorOpinion: '' }, cmtSubmitting: false,
      cmtVersion: null, commentDrafts: {}, commentError: '', commentConflict: emptyConflict(),
      downloading: false, attachmentError: '', conflict: emptyConflict(),
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false, submitting: false },
      pending: null,
      lastReceipt: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    commentDirty() { const d = this.detail.data; return !!d && (this.cmtForm.advisorOpinion !== (d.advisorOpinion || '') || this.cmtForm.mentorOpinion !== (d.mentorOpinion || '')) },
    feedbackItems() { return FEEDBACK.map(f => ({ label: f.label, value: this.detail.data?.[f.key] })) },
    opinionItems() { return OPINION.map(f => ({ label: f.label, value: this.detail.data?.[f.key] })) },
    reviewItems() { const d = this.detail.data || {}; return [{ label: '审核结果', value: d.reviewStatusLabel }, { label: '审核人', value: d.reviewedByName }, { label: '审核时间', value: d.reviewedAt }, { label: '审核意见', value: d.reviewComment }] },
    detailItems() {
      const d = this.detail.data || {}
      return DETAIL.map((f) => ({
        label: f.label,
        value: d[f.key] != null && d[f.key] !== '' ? d[f.key] : '—'
      }))
    },
    canComment() {
      const d = this.detail.data || {}
      return d.submitStatus === 'SUBMITTED' && d.reviewStatus === 'PENDING' && this.canBtn('internship.eval.advisor.manage')
    },
    canReview() {
      const d = this.detail.data || {}
      return d.submitStatus === 'SUBMITTED' && d.reviewStatus === 'PENDING'
    },
    auditRecords() {
      return (this.detail.data?.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actor: t.operator, reason: t.detail && (t.detail.comment || ''), at: t.occurredAt
      }))
    }
  },
  watch: {
    ctx: { deep: true, handler() { this.resetDetail(false); this.commentDrafts = {}; this.lastReceipt = null; this.clearSelection(); this.load() } },
    '$route.query': {
      deep: true,
      immediate: true,
      handler(query, previous) {
        if (!previous || ['view', 'reviewStatus', 'keyword', 'page', 'batchId'].some(key => Object.hasOwn(query, key) !== Object.hasOwn(previous, key) || String(query[key] ?? '') !== String(previous[key] ?? ''))) this.applyQuery()
        const sid = String(query.id || '')
        if (sid === this.selectedId) return
        this.resetDetail()
        this.selectedId = sid
        if (sid) { this.doneHint = false; this.loadDetail(sid) } else { this.detail = { loading: false, error: '', data: null } }
      }
    },
    'batchStore.selectedBatchId'() {
      this.resetDetail(false); this.commentDrafts = {}; this.lastReceipt = null
      this.page = 1
      this.clearSelection()
      this.load()
    }
  },
  beforeUnmount() { this.listSequence++; this.resetDetail(false); this.commentDrafts = {} },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    applyQuery() {
      const view = String(this.$route.query.view || '').toLowerCase()
      this.viewFilter = ['self', 'enterprise', 'position', 'advisor'].includes(view) ? view : ''
      this.statusFilter = this.$route.query.reviewStatus != null ? String(this.$route.query.reviewStatus) : 'PENDING'
      this.keyword = String(this.$route.query.keyword || '')
      this.page = Math.max(1, Number.parseInt(this.$route.query.page, 10) || 1)
      this.doneHint = false; this.load()
    },
    syncQuery() {
      const query = this.batchStore.withBatchQuery({ ...this.$route.query, view: this.viewFilter, keyword: this.keyword, reviewStatus: this.statusFilter, page: String(this.page) })
      if (Object.keys(query).every(key => Object.hasOwn(this.$route.query, key) && String(query[key]) === String(this.$route.query[key]))) this.load()
      else this.$router.replace({ query })
    },
    onPickMentorChip(text) {
      if (!text || this.cmtSubmitting || this.cd.submitting) return
      const cur = (this.cmtForm.mentorOpinion || '').trim()
      this.cmtForm.mentorOpinion = cur ? cur + '；' + text : text
    },
    onPickAdvisorChip(text) {
      if (!text || this.cmtSubmitting || this.cd.submitting) return
      const cur = (this.cmtForm.advisorOpinion || '').trim()
      this.cmtForm.advisorOpinion = cur ? cur + '；' + text : text
    },
    reviewTone(s) { return s === 'APPROVED' ? 'success' : s === 'RETURNED' ? 'danger' : 'warning' },
    goEnterpriseEvals() { this.$router.push({ path: '/admin/internship/enterprise-evals', query: this.batchStore.withBatchQuery() }) },
    exportFn() {
      if (!this.batchStore.selectedBatchId) return Promise.resolve({ code: 1, message: '请先选择批次' })
      return studentEvalApi.exportEvals({ keyword: this.keyword, reviewStatus: this.statusFilter, batchId: this.batchStore.selectedBatchId })
    },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条（水印 + 导出留痕）`) },
    reload() { this.page = 1; this.doneHint = false; this.syncQuery() },
    onPageChange({ page }) { this.page = page; this.syncQuery() },
    async load() {
      const sequence = ++this.listSequence, batchId = this.batchStore.selectedBatchId
      this.rows = []; this.total = 0
      if (!this.batchStore.selectedBatchId) {
        this.loading = false; this.error = '请先选择批次'; this.rows = []; this.total = 0
        return
      }
      this.loading = true; this.error = ''
      const params = { page: this.page, pageSize: this.pageSize, keyword: this.keyword, batchId: this.batchStore.selectedBatchId }
      if (this.statusFilter) params.reviewStatus = this.statusFilter
      if (this.viewFilter) params.view = this.viewFilter
      const res = await studentEvalApi.getEvals(params)
      if (sequence !== this.listSequence || batchId !== this.batchStore.selectedBatchId) return
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
      // 处理完当前页最后一条后翻页越界（如筛选=待审核时该页清空）：自动回到最后一个有效页
      const pc = Math.max(1, Math.ceil(this.total / this.pageSize))
      if (!this.rows.length && this.total > 0 && this.page > pc) { this.page = pc; this.syncQuery(); return false }
      return true
    },
    select(id) {
      if (id == null || id === '') return
      const sid = String(id)
      this.doneHint = false
      if (this.selectedId === sid) return
      this.resetDetail(); this.selectedId = sid; this.loadDetail(sid)
      this.$router.replace({ query: this.batchStore.withBatchQuery({ ...this.$route.query, id: sid, page: String(this.page) }) })
    },
    rememberComment() {
      if (this.detail.data && this.commentDirty) this.commentDrafts[String(this.detail.data.id)] = { form: { ...this.cmtForm }, version: this.cmtVersion }
    },
    resetDetail(preserveDraft = true) {
      if (preserveDraft) this.rememberComment()
      this.detail = { loading: false, error: '', data: null }
      this.cmtForm = { advisorOpinion: '', mentorOpinion: '' }; this.cmtVersion = null; this.cmtSubmitting = false
      this.commentError = ''; this.commentConflict = emptyConflict()
      this.pending = null; this.cd = { ...this.cd, visible: false, submitting: false }; this.conflict = emptyConflict()
      this.downloading = false; this.attachmentError = ''
    },
    restoreComment() {
      if (!this.detail.data || this.detail.loading || this.detail.error || this.cmtSubmitting || this.cd.submitting) return
      const d = this.detail.data
      delete this.commentDrafts[String(d.id)]
      this.cmtForm = { advisorOpinion: d.advisorOpinion || '', mentorOpinion: d.mentorOpinion || '' }
      this.cmtVersion = d.version; this.commentConflict = emptyConflict(); this.commentError = ''
    },
    clearSelection() {
      this.resetDetail(); this.selectedId = ''
      const query = { ...this.$route.query, page: String(this.page) }
      delete query.id
      this.$router.replace({ query: this.batchStore.withBatchQuery(query) })
    },
    async loadDetail(id) {
      if (!id || !this.batchStore.selectedBatchId) return
      const batchId = this.batchStore.selectedBatchId
      this.rememberComment()
      this.detail = { loading: true, error: '', data: null }
      const workspace = this.detail
      this.downloading = false; this.attachmentError = ''
      const res = await studentEvalApi.getDetail(id)
      if (workspace !== this.detail || batchId !== this.batchStore.selectedBatchId || String(this.selectedId) !== String(id)) return
      this.detail.loading = false
      if (res.code !== 0) { this.detail.error = res.message || '详情加载失败'; return }
      if (res.data.batchId && String(res.data.batchId) !== String(batchId)) { this.detail.error = '该鉴定不属于当前批次，请从当前列表重新选择'; return }
      this.detail.data = res.data
      // 意见表单从接口真实返回值带出，便于在已有意见上续写
      const draft = this.commentDrafts[String(id)]
      this.cmtForm = draft ? { ...draft.form } : { advisorOpinion: res.data.advisorOpinion || '', mentorOpinion: res.data.mentorOpinion || '' }
      this.cmtVersion = draft ? draft.version : res.data.version
      if (draft && String(draft.version) !== String(res.data.version)) this.commentConflict = { ...emptyConflict(), active: true }
    },
    async downloadAtt() {
      const workspace = this.detail, a = workspace.data?.attachment
      if (!a?.fileId || this.downloading || workspace.loading || workspace.error) return
      this.downloading = true; this.attachmentError = ''
      try { await downloadAttachment(String(a.fileId), a.fileName) }
      catch (e) { if (this.detail === workspace) this.attachmentError = e.message || '附件下载失败' }
      finally { if (this.detail === workspace) this.downloading = false }
    },
    async submitComment() {
      if (!this.canComment || this.cmtSubmitting || this.cd.submitting || this.commentConflict.active || this.detail.loading || this.detail.error) return
      if (this.cmtForm.advisorOpinion.trim().length < 5) { this.commentError = '指导教师意见至少填写 5 字'; return }
      const workspace = this.detail, form = this.cmtForm, batchId = this.batchStore.selectedBatchId
      this.commentError = ''
      this.cmtSubmitting = true
      const res = await studentEvalApi.advisorComment(workspace.data.id, {
        ...form, expectedVersion: this.cmtVersion
      })
      if (workspace !== this.detail || form !== this.cmtForm || batchId !== this.batchStore.selectedBatchId) return
      this.cmtSubmitting = false
      if (res.code !== 0) {
        this.commentError = res.message || '保存失败，填写内容已保留'
        if (isConflict(res)) { this.commentConflict = { ...emptyConflict(), active: true }; this.rememberComment(); await this.loadDetail(this.selectedId) }
        return
      }
      delete this.commentDrafts[String(workspace.data.id)]
      workspace.data = { ...workspace.data, ...res.data, mentorOpinion: form.mentorOpinion.trim() }
      this.cmtForm = { advisorOpinion: workspace.data.advisorOpinion, mentorOpinion: workspace.data.mentorOpinion }; this.cmtVersion = res.data.version
      this.lastReceipt = { actionLabel: '导师评价已保存', objectLabel: this.detail.data.studentName,
        id: res.data.id, version: res.data.version, statusLabel: '待学校审核',
        auditText: '导师意见与学生自评版本已关联', nextStep: '由学校管理员按新版本完成审核' }
      toast.success('已保存意见')
      await Promise.all([this.loadDetail(this.selectedId), this.load()])
    },
    openReview(r, action) {
      if (!this.canReview || !this.canBtn('internship.eval.self.review') || this.cmtSubmitting || this.cd.submitting || this.commentDirty || this.detail.loading || this.detail.error || !r || String(r.id) !== this.selectedId || !['APPROVE', 'RETURN'].includes(action)) return
      if (action === 'APPROVE' && !r.advisorOpinion?.trim()) return
      this.conflict = emptyConflict()
      const ap = action === 'APPROVE'
      this.pending = { id: r.id, action, version: r.version, studentName: r.studentName }
      this.cd = { visible: true, title: ap ? '鉴定 · 通过' : '鉴定 · 退回',
        content: `${ap ? '通过' : '退回'}「${r.studentName}」的实习鉴定，意见将写入审计。`,
        danger: !ap, confirmText: ap ? '通过' : '退回', requireReason: !ap, submitting: false }
    },
    async onConfirm({ reason }) {
      const pending = this.pending
      if (!pending || this.cd.submitting || this.cmtSubmitting || this.conflict.active || !this.canReview || !this.canBtn('internship.eval.self.review') || this.commentDirty || this.detail.loading || this.detail.error || String(pending.id) !== this.selectedId) return
      if (pending.action === 'APPROVE' && !this.detail.data.advisorOpinion?.trim()) return
      if (pending.action === 'RETURN' && String(reason || '').trim().length < 5) return toast.error('退回原因至少填写 5 字')
      const dialog = this.cd, batchId = this.batchStore.selectedBatchId
      dialog.submitting = true
      const res = await studentEvalApi.review(pending.id, { action: pending.action, comment: reason || '', expectedVersion: pending.version })
      if (this.cd === dialog) dialog.submitting = false
      if (this.cd !== dialog || this.pending !== pending || batchId !== this.batchStore.selectedBatchId || String(pending.id) !== this.selectedId) return
      if (res.code !== 0) {
        if (isConflict(res)) {
          this.conflict = { ...emptyConflict(), active: true, kept: reason || '' }
          const conflict = await captureConflict({ res, kept: reason || '', refresh: async () => { await this.loadDetail(pending.id); if (this.detail.error || !this.detail.data) throw new Error('回读失败') }, latest: () => this.reviewItems })
          if (this.pending === pending && this.cd === dialog) this.conflict = conflict
          return
        }
        return toast.error(res.message || '操作失败')
      }
      this.detail.data = { ...this.detail.data, ...res.data }
      this.lastReceipt = { actionLabel: pending.action === 'APPROVE' ? '学生鉴定已通过' : '学生鉴定已退回',
        objectLabel: pending.studentName, id: res.data.id, version: res.data.version,
        statusLabel: res.data.reviewStatusLabel || res.data.reviewStatus,
        auditText: '审核结果已保存', nextStep: pending.action === 'APPROVE' ? '可继续核对综合成绩' : '等待学生按意见修改重交' }
      this.cd.visible = false; toast.success('审核完成，已写审计')
      await this.advanceAfterReview(pending.id)
    },
    /** 审核成功后：刷新当前页并自动选中下一条待审核（已提交自评）；无下一条则清空选中并提示已处理完 */
    async advanceAfterReview(oldId) {
      const batchId = this.batchStore.selectedBatchId, route = this.$route.fullPath
      const oldIndex = Math.max(0, this.rows.findIndex((r) => String(r.id) === String(oldId)))
      const loaded = await this.load()
      if (!loaded || this.error || batchId !== this.batchStore.selectedBatchId || route !== this.$route.fullPath || String(oldId) !== this.selectedId) return
      let after = null, before = null
      this.rows.forEach((r, i) => {
        if (r.submitStatus !== 'SUBMITTED' || r.reviewStatus !== 'PENDING' || String(r.id) === String(oldId)) return
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
.view-filter { display: flex; align-items: center; gap: 8px; font-size: var(--font-size-xs); color: var(--text-secondary); }
.view-filter select { border: 1px solid var(--border-light); border-radius: 8px; padding: 7px 10px; font: inherit; color: var(--text-primary); background: var(--bg-card, #fff); }
.state { padding: var(--space-6); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); border: 1px dashed var(--border-base); border-radius: var(--radius-base); margin: var(--space-3); }
.state.is-err { color: var(--danger-600); }
.sec-t { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); margin: var(--space-4) 0 var(--space-2); }

/* 左栏紧凑列表 */
.lv-list { list-style: none; margin: 0; padding: var(--space-2); display: flex; flex-direction: column; gap: var(--space-1); }
.lv-item { display: block; width: 100%; text-align: left; font: inherit; cursor: pointer; background: transparent; border: 1px solid transparent; border-radius: var(--radius-md, 8px); padding: var(--space-2) var(--space-3); transition: background 0.12s ease, border-color 0.12s ease; }
.lv-item:hover { background: var(--primary-50, #eff6ff); }
.lv-item.is-active { background: var(--primary-50, #eff6ff); border-color: var(--primary-600, #2563eb); }
.lv-item__row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
.lv-item__name { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary); }
.lv-item__sub { margin-top: 2px; font-size: var(--font-size-xs); color: var(--text-tertiary); }

/* 右栏详情与固定操作区 */
.lv-main { display: flex; flex-direction: column; min-height: 320px; }
.lv-main__body { flex: 1; padding: var(--space-4); min-width: 0; }
.lv-main__state { margin: var(--space-4); }
.lv-head { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.lv-head__name { font-size: var(--font-size-md, 15px); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.lv-foot { position: sticky; bottom: 0; display: flex; justify-content: flex-end; gap: var(--space-2); padding: var(--space-3) var(--space-4); border-top: 1px solid var(--border-light); background: var(--bg-card, #fff); border-radius: 0 0 var(--r, 12px) var(--r, 12px); }

/* 右栏内联意见表单 */
.cmt { border: 1px solid var(--border-light); border-radius: var(--radius-md, 8px); padding: var(--space-3); }
.cmt__actions { display: flex; justify-content: flex-end; }
.cmt__chips { margin-top: var(--space-2); }
.cmt__fields { margin: 0; padding: 0; min-width: 0; border: 0; }
.cmt__actions { align-items: center; gap: 10px; flex-wrap: wrap; }
.cmt__actions > .mp-note { margin-right: auto; }
.lv-foot { align-items: center; flex-wrap: wrap; }
.lv-foot__hint { margin-right: auto; }
.lv-item:focus-visible { outline: 2px solid var(--primary-600); outline-offset: 2px; }
.lv-item__sub { overflow-wrap: anywhere; }
.evidence { margin-top: 16px; }
.local-error { color: var(--danger-600); font-size: var(--font-size-sm); }
@media (max-width: 600px) { .lv-foot__hint { width: 100%; } }
@media (max-height: 700px) { .lv-foot { position: static; } }

</style>
