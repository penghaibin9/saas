<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="企业评价" subtitle="纸质材料代录 · 独立审核 · 退回重交" show-back />

    <view class="ee__tabs">
      <view class="ee__tab" :class="{ 'is-on': tab === 'list' }" @click="showList">评价台账<text v-if="list.length" class="ee__tab-badge">{{ list.length }}</text><text v-if="tab === 'list'" class="ee__tab-u" /></view>
      <view v-if="canCreate" class="ee__tab" :class="{ 'is-on': tab === 'form' }" @click="openCreate">{{ editingEval ? '修改重交' : '代录评价' }}<text v-if="tab === 'form'" class="ee__tab-u" /></view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack">
        <view class="card ee__batch" v-if="batches.length">
          <view class="ee__batch-copy">
            <text class="ee__eyebrow">当前评价批次</text>
            <text class="ee__batch-name">{{ batches[batchIndex]?.name || '请选择批次' }}</text>
          </view>
          <picker class="ee__picker" mode="selector" :disabled="!!editingEval || submitting" :range="batchLabels" :value="batchIndex" @change="onBatch">
            <view class="ee__pick-val">切换批次 <text v-if="!editingEval" class="ee__arrow">▾</text></view>
          </picker>
        </view>

        <view v-if="tab === 'list' && batches.length" class="card ee__summary">
          <view class="ee__summary-main">
            <text class="ee__summary-label">本批次企业评价</text>
            <view class="ee__summary-value"><text>{{ list.length }}</text><text>份</text></view>
            <text class="ee__summary-note">{{ summaryConclusion }}</text>
          </view>
          <view class="ee__summary-metrics">
            <view class="ee__metric"><text>{{ pendingCount }}</text><text>待审核</text></view>
            <view class="ee__metric is-danger"><text>{{ returnedCount }}</text><text>已退回</text></view>
            <view class="ee__metric is-success"><text>{{ approvedCount }}</text><text>已通过</text></view>
          </view>
        </view>

        <MobileInlineAlert type="info" description="企业评价必须依据企业盖章原始材料如实代录；录入人不能审核本人记录，审核通过后才进入成绩核算。" />

        <template v-if="tab === 'list'">
          <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次" description="当前身份的数据范围内没有可查看批次。" />
          <MobileGlobalState v-else-if="!list.length" state="empty" title="当前批次没有企业评价" description="可由有权限的教师依据企业盖章材料进行代录。" />
          <view v-for="item in list" :key="item.id" class="card ee">
            <view class="row-between ee__head">
              <view class="flex-1 ee__identity"><text class="t-md t-bold">{{ item.studentName }}</text><text class="ee__sub">{{ item.studentNo }} · {{ item.positionName || '岗位待定' }}</text></view>
              <MobileStatusTag :label="item.reviewStatusLabel" :type="statusTone(item.reviewStatus)" />
            </view>

            <view class="ee__score-overview">
              <view class="ee__avg-block"><text class="ee__avg-value">{{ item.avgScore }}</text><text class="ee__avg-label">五维均分</text></view>
              <view class="ee__scores">
                <text>出勤 {{ item.attendanceScore }}</text><text>技能 {{ item.skillScore }}</text><text>态度 {{ item.attitudeScore }}</text><text>协作 {{ item.collaborationScore }}</text><text>安全 {{ item.safetyScore }}</text>
              </view>
            </view>

            <view v-if="item.reviewComment" class="ee__return">
              <text class="ee__return-title">审核意见</text>
              <text class="ee__return-text">{{ item.reviewComment }}</text>
            </view>

            <view class="ee__source">
              <view><text>材料来源</text><text>{{ item.sourceLabel || '—' }}</text></view>
              <view><text>录入人</text><text>{{ item.recordedByName || '—' }}</text></view>
              <view><text>审核人</text><text>{{ item.reviewedByName || '待审核' }}</text></view>
            </view>

            <view class="ee__next" :class="{ 'is-danger': item.reviewStatus === 'RETURNED' }">
              <text class="ee__next-label">下一步</text>
              <text class="ee__next-text">{{ nextStepText(item) }}</text>
            </view>

            <view v-if="item.reviewStatus === 'RETURNED' && canEditReturned(item)" class="ee__actions">
              <button class="btn btn-primary flex-1" :disabled="submitting" @click="editReturned(item)">修改并重新上传材料</button>
            </view>
            <view v-else-if="canReview && item.reviewStatus === 'PENDING'" class="ee__actions">
              <button class="ee__reject flex-1" :disabled="submitting || isOwnRecord(item)" @click="review(item, 'RETURN')">{{ isOwnRecord(item) ? '录入人不可自审' : '退回修改' }}</button>
              <button class="ee__approve flex-1" :disabled="submitting || isOwnRecord(item)" @click="review(item, 'APPROVE')">{{ isOwnRecord(item) ? '录入人不可自审' : '审核通过' }}</button>
            </view>
          </view>
        </template>

        <template v-else-if="canCreate">
          <MobileInlineAlert v-if="editingEval" type="warning" :title="`正在修改：${editingEval.studentName}`" :description="editingEval.reviewComment || '评价已退回，请按审核意见修改，并重新上传企业盖章材料。'" />
          <MobileGlobalState v-if="!editingEval && !students.length" state="empty" title="暂无可代录学生" description="当前批次没有本人指导或授权范围内学生，或学生已有企业评价。" />
          <template v-else>
            <view class="card ee__form-section">
              <view class="ee__section-head"><text class="ee__step">1</text><view><text class="ee__section-title">评价对象</text><text class="ee__section-hint">核对学生和企业导师信息</text></view></view>
              <view class="ee__row"><text class="ee__label">实习学生 <text class="ee__required">*</text></text><template v-if="editingEval"><text class="ee__readonly">{{ editingEval.studentName }}（{{ editingEval.studentNo }}）</text></template><picker v-else class="ee__picker" mode="selector" :range="studentLabels" :value="studentIndex" @change="(e) => studentIndex = Number(e.detail.value)"><view class="ee__field-value">{{ studentLabels[studentIndex] || '请选择' }}<text class="ee__arrow">▾</text></view></picker></view>
              <view class="ee__row"><text class="ee__label">企业导师 <text class="ee__required">*</text></text><input class="ee__input" v-model.trim="form.mentorName" placeholder="纸质评价表上的企业导师姓名" /></view>
            </view>

            <view class="card ee__form-section">
              <view class="ee__section-head"><text class="ee__step">2</text><view><text class="ee__section-title">五维评分</text><text class="ee__section-hint">按原始评价表录入0-100整数</text></view></view>
              <view class="ee__score-form">
                <view v-for="field in scoreFields" :key="field.key" class="ee__score-field"><text>{{ field.label }}</text><input type="number" v-model="form[field.key]" placeholder="0-100" /></view>
              </view>
              <view class="ee__row"><text class="ee__label">综合评语</text><input class="ee__input" v-model.trim="form.overallComment" placeholder="按企业原始评价如实录入" /></view>
              <view class="ee__row"><view class="ee__switch-copy"><text class="ee__switch-title">建议录用</text><text class="ee__switch-hint">与企业原始评价保持一致</text></view><switch :checked="form.recommendHire" @change="(e) => form.recommendHire = e.detail.value" /></view>
            </view>

            <view class="card ee__form-section">
              <view class="ee__section-head"><text class="ee__step">3</text><view><text class="ee__section-title">原始材料</text><text class="ee__section-hint">必须上传企业盖章文件，退回重交需重新上传</text></view></view>
              <view class="ee__file"><view class="ee__file-copy"><text class="ee__label">企业盖章材料 <text class="ee__required">*</text></text><text class="ee__file-name">{{ sourceFileName || (editingEval ? '退回重交必须上传新的企业材料' : '支持图片、PDF、Word等文件') }}</text></view><button class="btn btn-ghost" :disabled="uploading" @click="pickFile">{{ uploading ? '上传中…' : (form.sourceFileId ? '重新上传' : '选择并上传') }}</button></view>
            </view>
          </template>
          <MobileSafeAreaBar v-if="editingEval || students.length"><button class="btn btn-primary flex-1" :disabled="submitting || uploading" @click="submit">{{ submitting ? '提交中…' : (editingEval ? '修改重交，等待再次审核' : '提交代录，等待独立审核') }}</button></MobileSafeAreaBar>
        </template>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { useSessionStore } from '@/stores/session'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { teacherInternshipEnterpriseEvals, teacherInternshipEnterpriseEvalCreate, teacherInternshipEnterpriseEvalResubmit, teacherInternshipEnterpriseEvalReview, teacherInternshipMyStudents } from '@/services/internshipApi'
import { chooseSingleFile, uploadBusinessFile } from '@/services/fileApi'
import { createSubmitLock, normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const submitLock = createSubmitLock(1500)
const ADMIN_ROLES = ['SCHOOL_ADMIN', 'COLLEGE_ADMIN', 'INTERNSHIP_ADMIN', 'INTERN_ADMIN', 'COLLEGE_INTERNSHIP_ADMIN']
const EMPTY_FORM = () => ({ mentorName: '', attendanceScore: '', skillScore: '', attitudeScore: '', collaborationScore: '', safetyScore: '', overallComment: '', recommendHire: false, sourceFileId: '' })

export default {
  data() {
    return {
      tab: 'list', state: 'loading', submitting: false, uploading: false,
      list: [], students: [], studentIndex: 0, batches: [], batchId: '', batchIndex: 0,
      sourceFileName: '', editingEval: null,
      page: 1, hasMore: false, loadingMore: false,
      scoreFields: [{ key: 'attendanceScore', label: '出勤' }, { key: 'skillScore', label: '技能' }, { key: 'attitudeScore', label: '态度' }, { key: 'collaborationScore', label: '协作' }, { key: 'safetyScore', label: '安全纪律' }],
      form: EMPTY_FORM()
    }
  },
  computed: {
    context() { return useInternshipContextStore() },
    roleCode() { return this.context.roleCode || '' },
    isAdminRole() { return ADMIN_ROLES.includes(this.roleCode) },
    canCreate() { return this.context.can('internship.eval.enterprise.manage') },
    canReview() { return this.isAdminRole && this.context.can('internship.eval.enterprise.review') },
    batchLabels() { return this.batches.map((b) => `${b.name} · ${b.status} · ${b.studentCount}人`) },
    studentLabels() { return this.students.map((s) => `${s.name}（${s.studentNo}）· ${s.enterpriseName || '企业待定'}`) },
    currentUserId() { return String(useSessionStore().identity?.userId || '') },
    pendingCount() { return this.list.filter((item) => item.reviewStatus === 'PENDING').length },
    returnedCount() { return this.list.filter((item) => item.reviewStatus === 'RETURNED').length },
    approvedCount() { return this.list.filter((item) => item.reviewStatus === 'APPROVED').length },
    summaryConclusion() {
      if (!this.list.length) return '当前批次尚未录入企业评价。'
      if (this.returnedCount) return `有 ${this.returnedCount} 份评价被退回，优先通知原录入人修改重交。`
      if (this.pendingCount) return `${this.pendingCount} 份评价等待独立审核。`
      return '当前已录入评价均完成审核。'
    }
  },
  onLoad() { this.load() },
  onReachBottom() { if (this.tab === 'list') this.loadMore() },
  onPullDownRefresh() { this.load(() => uni.stopPullDownRefresh()) },
  methods: {
    statusTone(status) { return status === 'APPROVED' ? 'success' : status === 'RETURNED' ? 'danger' : 'warning' },
    isOwnRecord(item) { return !!this.currentUserId && String(item.recordedByUserId || '') === this.currentUserId },
    canEditReturned(item) { return this.canCreate && (this.isOwnRecord(item) || this.isAdminRole) },
    nextStepText(item) {
      if (item.reviewStatus === 'RETURNED') return this.canEditReturned(item) ? '按审核意见修改评分并重新上传企业盖章材料。' : '等待原录入人或管理员修改重交。'
      if (item.reviewStatus === 'PENDING') return this.isOwnRecord(item) ? '等待其他授权人员独立审核。' : '核对原始材料与五维评分后完成审核。'
      return '评价已审核通过，将作为成绩核算的企业评价分来源。'
    },
    showList() { this.tab = 'list'; this.editingEval = null; this.form = EMPTY_FORM(); this.sourceFileName = '' },
    async load(done) {
      this.state = 'loading'
      this.page = 1
      this.hasMore = false
      try {
        this.context.restore(); await this.context.load(true)
        this.batches = this.context.batches || []; this.batchId = this.context.selectedBatchId || ''
        this.batchIndex = Math.max(0, this.batches.findIndex((b) => String(b.id) === String(this.batchId)))
        await Promise.all([this.loadList(), this.canCreate ? this.loadStudents() : Promise.resolve()])
        this.state = 'ready'
      } catch (e) { this.state = 'error'; toast((e && e.message) || '企业评价数据加载失败') }
      finally { done && done() }
    },
    async loadList() {
      if (!this.batchId) { this.list = []; return }
      this.page = 1
      const data = await teacherInternshipEnterpriseEvals(this.batchId, 1, 20)
      this.list = data?.items || data?.list || []
      this.hasMore = !!data?.hasMore
    },
    async loadMore() {
      if (!this.batchId || !this.hasMore || this.loadingMore || this.state !== 'ready') return
      const selectedBatch = this.batchId
      this.loadingMore = true
      try {
        const nextPage = this.page + 1
        const data = await teacherInternshipEnterpriseEvals(selectedBatch, nextPage, 20)
        if (selectedBatch !== this.batchId) return
        this.list = [...this.list, ...(data?.items || [])]
        this.page = nextPage
        this.hasMore = !!data?.hasMore
      } finally { this.loadingMore = false }
    },
    async loadStudents() {
      if (!this.batchId) { this.students = []; return }
      const data = await teacherInternshipMyStudents(this.batchId)
      const existingIds = new Set((this.list || []).map((x) => String(x.internId || x.internshipId)))
      this.students = (data?.list || []).filter((x) => !existingIds.has(String(x.id))); this.studentIndex = 0
    },
    async onBatch(e) {
      this.batchIndex = Number(e.detail.value); const batch = this.batches[this.batchIndex]
      this.context.selectBatch(batch?.id); this.batchId = this.context.selectedBatchId; this.editingEval = null; this.form = EMPTY_FORM(); this.state = 'loading'
      this.list = []
      try { await Promise.all([this.loadList(), this.canCreate ? this.loadStudents() : Promise.resolve()]); this.state = 'ready' }
      catch (err) { this.state = 'error'; toast(err?.message || '批次数据加载失败') }
    },
    async openCreate() { this.editingEval = null; this.form = EMPTY_FORM(); this.sourceFileName = ''; this.tab = 'form'; if (this.canCreate && !this.students.length) { try { await this.loadStudents() } catch (e) { toast(e?.message || '学生名单加载失败') } } },
    editReturned(item) {
      if (!this.canEditReturned(item)) return
      this.editingEval = item
      this.form = {
        mentorName: item.mentorName || '', attendanceScore: String(item.attendanceScore ?? ''),
        skillScore: String(item.skillScore ?? ''), attitudeScore: String(item.attitudeScore ?? ''),
        collaborationScore: String(item.collaborationScore ?? ''), safetyScore: String(item.safetyScore ?? ''),
        overallComment: item.overallComment || '', recommendHire: !!item.recommendHire, sourceFileId: ''
      }
      this.sourceFileName = ''; this.tab = 'form'
    },
    async pickFile() {
      if (this.uploading) return
      try {
        const file = await chooseSingleFile(); if (!file) return
        if (Number(file.size || 0) > 20 * 1024 * 1024) return toast('文件不能超过20MB')
        this.uploading = true
        const result = await uploadBusinessFile(file, { bizType: 'INTERNSHIP_ENTERPRISE_EVAL', bizId: this.editingEval?.id || '' })
        this.form.sourceFileId = result.fileId; this.sourceFileName = result.fileName || file.name || '已上传材料'; toast('评价材料上传成功')
      } catch (e) { toast(normalizeError(e).text || '文件上传失败') } finally { this.uploading = false }
    },
    submit() {
      if (this.submitting) return
      const student = this.editingEval ? null : this.students[this.studentIndex]
      if (!this.editingEval && !student) return toast('请选择实习学生')
      if (!this.form.mentorName) return toast('请填写企业导师姓名')
      for (const field of this.scoreFields) { const value = Number(this.form[field.key]); if (!Number.isInteger(value) || value < 0 || value > 100) return toast(`${field.label}评分必须是0-100整数`) }
      if (!this.form.sourceFileId) return toast(this.editingEval ? '退回重交必须上传新的企业盖章材料' : '请上传企业盖章评价材料')
      const body = { sourceType: 'SCHOOL_RECORDED', ...this.form }
      this.scoreFields.forEach((field) => { body[field.key] = Number(this.form[field.key]) })
      if (this.editingEval) body.expectedVersion = this.editingEval.version
      else body.internshipId = student.id
      this.submitting = true
      const action = this.editingEval
        ? () => teacherInternshipEnterpriseEvalResubmit(this.editingEval.id, this.batchId, body)
        : () => teacherInternshipEnterpriseEvalCreate(this.batchId, body)
      submitLock.run(action).then(() => {
        toast(this.editingEval ? '企业评价已修改重交' : '企业评价已代录，等待独立审核')
        this.showList(); return this.load()
      }).catch((e) => { if (e?.code !== 'LOCKED') toast(normalizeError(e).text) }).finally(() => { this.submitting = false })
    },
    review(item, action) {
      if (!this.canReview || this.submitting || this.state !== 'ready' || this.isOwnRecord(item)) return
      uni.showModal({ title: action === 'APPROVE' ? '审核通过' : '退回评价', editable: true, placeholderText: action === 'RETURN' ? '请输入退回原因（至少5字）' : '可填写审核意见', success: (res) => {
        if (!res.confirm) return
        const comment = String(res.content || '').trim(); if (action === 'RETURN' && comment.length < 5) return toast('退回原因至少5字')
        this.submitting = true
        teacherInternshipEnterpriseEvalReview(item.id, this.batchId, { action, comment, expectedVersion: item.version }).then(() => { toast('审核完成'); return this.loadList() }).catch((e) => toast(normalizeError(e).text)).finally(() => { this.submitting = false })
      } })
    }
  }
}
</script>

<style scoped>
.ee__tabs{display:flex;gap:var(--space-6);padding:var(--space-3) var(--page-padding-mobile) 0;background:var(--bg-card)}.ee__tab{position:relative;padding-bottom:var(--space-3);color:var(--text-tertiary)}.ee__tab.is-on{color:var(--text-primary);font-weight:var(--font-weight-semibold)}.ee__tab-u{position:absolute;left:50%;bottom:0;transform:translateX(-50%);width:22px;height:3px;border-radius:2px;background:var(--teacher-600)}.ee__tab-badge{margin-left:5px;padding:1px 6px;border-radius:var(--radius-full);background:var(--danger-500);color:#fff;font-size:10px}.ee__batch{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-3)}.ee__batch-copy{min-width:0;display:flex;flex-direction:column;gap:3px}.ee__eyebrow{font-size:var(--font-size-xs);color:var(--text-tertiary)}.ee__batch-name{font-size:var(--font-size-md);font-weight:600;color:var(--text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ee__picker{flex-shrink:0}.ee__pick-val{color:var(--teacher-700);font-size:var(--font-size-sm);white-space:nowrap}.ee__arrow{margin-left:4px;color:var(--text-tertiary)}.ee__summary{display:flex;align-items:stretch;gap:var(--space-3);padding:var(--space-3)}.ee__summary-main{flex:1;min-width:0}.ee__summary-label{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary)}.ee__summary-value{display:flex;align-items:baseline;gap:4px;margin-top:4px}.ee__summary-value text:first-child{font-size:34px;line-height:1;font-weight:700;color:var(--teacher-700)}.ee__summary-value text:last-child{font-size:var(--font-size-sm);color:var(--text-secondary)}.ee__summary-note{display:block;margin-top:8px;font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.ee__summary-metrics{width:50%;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));background:var(--gray-50);border-radius:var(--radius-md);overflow:hidden}.ee__metric{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;padding:10px 3px;border-left:1px solid var(--border-light);text-align:center}.ee__metric:first-child{border-left:0}.ee__metric text:first-child{font-size:var(--font-size-lg);font-weight:700;color:var(--warning-700)}.ee__metric.is-danger text:first-child{color:var(--danger-600)}.ee__metric.is-success text:first-child{color:var(--success-700)}.ee__metric text:last-child{font-size:10px;color:var(--text-tertiary)}.ee{display:flex;flex-direction:column;gap:var(--space-3);padding:var(--space-3)}.ee__head{align-items:flex-start}.ee__identity{min-width:0}.ee__sub{display:block;margin-top:3px;color:var(--text-tertiary);font-size:var(--font-size-xs);word-break:break-word}.ee__score-overview{display:flex;align-items:center;gap:var(--space-3);padding:var(--space-2);background:var(--gray-50);border-radius:var(--radius-md)}.ee__avg-block{width:76px;flex-shrink:0;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:8px;border-right:1px solid var(--border-light)}.ee__avg-value{font-size:28px;line-height:1;font-weight:700;color:var(--teacher-700)}.ee__avg-label{margin-top:5px;font-size:10px;color:var(--text-tertiary)}.ee__scores{flex:1;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px 12px;font-size:var(--font-size-xs);color:var(--text-secondary)}.ee__return{padding:var(--space-2) var(--space-3);border:1px solid var(--danger-200,#fecaca);border-radius:var(--radius-md);background:var(--danger-50)}.ee__return-title{display:block;font-size:var(--font-size-xs);font-weight:600;color:var(--danger-700)}.ee__return-text{display:block;margin-top:4px;font-size:var(--font-size-xs);line-height:1.5;color:var(--danger-700);word-break:break-word}.ee__source{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;padding:var(--space-2);background:var(--gray-50);border-radius:var(--radius-md)}.ee__source>view{min-width:0;display:flex;flex-direction:column;gap:3px}.ee__source text:first-child{font-size:10px;color:var(--text-tertiary)}.ee__source text:last-child{font-size:var(--font-size-xs);font-weight:600;color:var(--text-primary);word-break:break-word}.ee__next{display:flex;gap:10px;padding:10px 12px;border-radius:var(--radius-md);background:var(--teacher-50,#eff6ff)}.ee__next.is-danger{background:var(--warning-50,#fff7ed)}.ee__next-label{flex-shrink:0;font-size:var(--font-size-xs);font-weight:600;color:var(--text-secondary)}.ee__next-text{font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.ee__actions{display:flex;gap:var(--space-2)}.ee__reject,.ee__approve{min-height:var(--touch-target-min);border-radius:var(--radius-md);font-size:var(--font-size-md)}.ee__reject{border:1px solid var(--danger-500);background:var(--bg-card);color:var(--danger-600)}.ee__approve{border:none;background:var(--teacher-600);color:#fff}.ee__reject::after,.ee__approve::after{border:none}.ee__form-section{display:flex;flex-direction:column;padding:var(--space-3)}.ee__section-head{display:flex;align-items:center;gap:10px;padding-bottom:var(--space-2);border-bottom:1px solid var(--border-light)}.ee__step{display:flex;align-items:center;justify-content:center;width:26px;height:26px;flex-shrink:0;border-radius:50%;background:var(--teacher-600);color:#fff;font-size:var(--font-size-sm);font-weight:700}.ee__section-title{display:block;font-size:var(--font-size-sm);font-weight:600;color:var(--text-primary)}.ee__section-hint{display:block;margin-top:2px;font-size:var(--font-size-xs);color:var(--text-tertiary)}.ee__row{display:flex;align-items:center;min-height:52px;border-bottom:1px solid var(--border-light);gap:var(--space-3)}.ee__label{width:104px;flex-shrink:0;color:var(--text-secondary);font-size:var(--font-size-sm)}.ee__required{color:var(--danger-600)}.ee__field-value,.ee__input,.ee__readonly{min-width:0;flex:1;text-align:right;color:var(--text-primary);font-size:var(--font-size-sm)}.ee__score-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;padding:var(--space-3) 0}.ee__score-field{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:10px 12px;border:1px solid var(--border-light);border-radius:var(--radius-md);background:var(--gray-50)}.ee__score-field text{font-size:var(--font-size-sm);color:var(--text-secondary)}.ee__score-field input{width:70px;text-align:right;font-size:var(--font-size-md);color:var(--text-primary)}.ee__switch-copy{min-width:0;flex:1}.ee__switch-title{display:block;font-size:var(--font-size-sm);color:var(--text-primary)}.ee__switch-hint{display:block;margin-top:2px;font-size:var(--font-size-xs);color:var(--text-tertiary)}.ee__file{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding-top:var(--space-3)}.ee__file-copy{min-width:0}.ee__file-name{display:block;margin-top:4px;color:var(--text-tertiary);font-size:var(--font-size-xs);line-height:1.45;word-break:break-word}@media(max-width:360px){.ee__summary{flex-direction:column}.ee__summary-metrics{width:100%}.ee__score-overview{align-items:flex-start}.ee__source{grid-template-columns:1fr}.ee__score-form{grid-template-columns:1fr}.ee__batch{align-items:flex-start}}
</style>
