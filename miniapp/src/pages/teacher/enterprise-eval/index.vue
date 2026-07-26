<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="企业评价" subtitle="纸质材料代录 · 学校独立审核" show-back />

    <view class="ee__tabs">
      <view class="ee__tab" :class="{ 'is-on': tab === 'list' }" @click="tab = 'list'">评价台账<text v-if="tab === 'list'" class="ee__tab-u" /></view>
      <view v-if="canCreate" class="ee__tab" :class="{ 'is-on': tab === 'create' }" @click="openCreate">代录评价<text v-if="tab === 'create'" class="ee__tab-u" /></view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack">
        <view class="card ee__batch" v-if="batches.length">
          <text class="ee__label">实习批次</text>
          <picker class="ee__picker" mode="selector" :range="batchLabels" :value="batchIndex" @change="onBatch">
            <view class="ee__pick-val">{{ batchLabels[batchIndex] || '请选择批次' }}<text class="ee__arrow">▾</text></view>
          </picker>
        </view>
        <MobileInlineAlert type="info" description="企业评价采用企业盖章纸质材料代录：必须上传原始材料，录入人不得审核本人录入记录；只有审核通过后，企业评价分才进入成绩核算。" />

        <template v-if="tab === 'list'">
          <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次" description="当前身份的数据范围内没有可查看批次。" />
          <MobileGlobalState v-else-if="!list.length" state="empty" title="暂无企业评价" description="当前批次尚未录入企业评价。" />
          <view v-for="item in list" :key="item.id" class="card ee">
            <view class="row-between">
              <view class="flex-1"><text class="t-md t-bold">{{ item.studentName }}</text><text class="ee__sub">{{ item.studentNo }} · {{ item.positionName || '岗位待定' }}</text></view>
              <MobileStatusTag :label="item.reviewStatusLabel" :type="statusTone(item.reviewStatus)" />
            </view>
            <view class="ee__scores"><text>出勤 {{ item.attendanceScore }}</text><text>技能 {{ item.skillScore }}</text><text>态度 {{ item.attitudeScore }}</text><text>协作 {{ item.collaborationScore }}</text><text>安全 {{ item.safetyScore }}</text></view>
            <text class="ee__avg">五维均分 {{ item.avgScore }}</text>
            <view class="ee__source"><text>来源：{{ item.sourceLabel }}</text><text>录入：{{ item.recordedByName || '—' }}</text><text v-if="item.reviewedByName">审核：{{ item.reviewedByName }}</text></view>
            <view v-if="canReview && item.reviewStatus === 'PENDING'" class="ee__actions">
              <button class="btn btn-ghost flex-1" :disabled="submitting" @click="review(item, 'RETURN')">退回</button>
              <button class="btn btn-primary flex-1" :disabled="submitting || isOwnRecord(item)" @click="review(item, 'APPROVE')">{{ isOwnRecord(item) ? '录入人不可自审' : '审核通过' }}</button>
            </view>
          </view>
        </template>

        <template v-else-if="canCreate">
          <MobileGlobalState v-if="!students.length" state="empty" title="暂无可代录学生" description="当前批次没有本人指导或授权范围内学生，或学生已有企业评价。" />
          <view v-else class="card ee__form">
            <view class="ee__row"><text class="ee__label">实习学生 *</text><picker class="ee__picker" mode="selector" :range="studentLabels" :value="studentIndex" @change="(e) => studentIndex = Number(e.detail.value)"><view class="ee__pick-val">{{ studentLabels[studentIndex] || '请选择' }}<text class="ee__arrow">▾</text></view></picker></view>
            <view class="ee__row"><text class="ee__label">企业导师 *</text><input class="ee__input" v-model.trim="form.mentorName" placeholder="纸质评价表上的企业导师姓名" /></view>
            <view v-for="field in scoreFields" :key="field.key" class="ee__row"><text class="ee__label">{{ field.label }} *</text><input class="ee__input" type="number" v-model="form[field.key]" placeholder="0-100" /></view>
            <view class="ee__row"><text class="ee__label">综合评语</text><input class="ee__input" v-model.trim="form.overallComment" placeholder="按企业原始评价如实录入" /></view>
            <view class="ee__row"><text class="ee__label">建议录用</text><switch :checked="form.recommendHire" @change="(e) => form.recommendHire = e.detail.value" /></view>
            <view class="ee__file">
              <view><text class="ee__label">企业盖章材料 *</text><text class="ee__file-name">{{ sourceFileName || '支持图片、PDF、Word等文件' }}</text></view>
              <button class="btn btn-ghost" :disabled="uploading" @click="pickFile">{{ uploading ? '上传中…' : (form.sourceFileId ? '重新上传' : '选择并上传') }}</button>
            </view>
          </view>
          <MobileSafeAreaBar v-if="students.length"><button class="btn btn-primary flex-1" :disabled="submitting || uploading" @click="submit">{{ submitting ? '提交中…' : '提交代录，等待独立审核' }}</button></MobileSafeAreaBar>
        </template>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { useSessionStore } from '@/stores/session'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { teacherInternshipEnterpriseEvals, teacherInternshipEnterpriseEvalCreate, teacherInternshipEnterpriseEvalReview, teacherInternshipMyStudents } from '@/services/internshipApi'
import { chooseSingleFile, uploadBusinessFile } from '@/services/fileApi'
import { createSubmitLock, normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const submitLock = createSubmitLock(1500)
const ADMIN_ROLES = ['SCHOOL_ADMIN', 'COLLEGE_ADMIN', 'INTERNSHIP_ADMIN', 'INTERN_ADMIN', 'COLLEGE_INTERNSHIP_ADMIN']

export default {
  data() {
    return {
      tab: 'list', state: 'loading', submitting: false, uploading: false,
      list: [], students: [], studentIndex: 0, batches: [], batchId: '', batchIndex: 0,
      sourceFileName: '',
      scoreFields: [{ key: 'attendanceScore', label: '出勤' }, { key: 'skillScore', label: '技能' }, { key: 'attitudeScore', label: '态度' }, { key: 'collaborationScore', label: '协作' }, { key: 'safetyScore', label: '安全纪律' }],
      form: { mentorName: '', attendanceScore: '', skillScore: '', attitudeScore: '', collaborationScore: '', safetyScore: '', overallComment: '', recommendHire: false, sourceFileId: '' }
    }
  },
  computed: {
    context() { return useInternshipContextStore() },
    roleCode() { return this.context.roleCode || '' },
    canCreate() { return this.context.can('internship.eval.enterprise.manage') },
    canReview() { return ADMIN_ROLES.includes(this.roleCode) && this.context.can('internship.eval.enterprise.review') },
    batchLabels() { return this.batches.map((b) => `${b.name} · ${b.status} · ${b.studentCount}人`) },
    studentLabels() { return this.students.map((s) => `${s.name}（${s.studentNo}）· ${s.enterpriseName || '企业待定'}`) },
    currentUserId() { return String(useSessionStore().user?.userId || '') }
  },
  onLoad() { this.load() },
  onPullDownRefresh() { this.load(() => uni.stopPullDownRefresh()) },
  methods: {
    statusTone(status) { return status === 'APPROVED' ? 'success' : status === 'RETURNED' ? 'danger' : 'warning' },
    isOwnRecord(item) { return !!this.currentUserId && String(item.recordedByUserId || '') === this.currentUserId },
    async load(done) {
      this.state = 'loading'
      try {
        this.context.restore(); await this.context.load(true)
        this.batches = this.context.batches || []; this.batchId = this.context.selectedBatchId || ''
        this.batchIndex = Math.max(0, this.batches.findIndex((b) => String(b.id) === String(this.batchId)))
        await Promise.all([this.loadList(), this.canCreate ? this.loadStudents() : Promise.resolve()])
        this.state = 'ready'
      } catch (e) { this.state = 'error'; toast((e && e.message) || '企业评价数据加载失败') }
      finally { done && done() }
    },
    async loadList() { if (!this.batchId) { this.list = []; return }; const data = await teacherInternshipEnterpriseEvals(this.batchId); this.list = data?.list || [] },
    async loadStudents() {
      if (!this.batchId) { this.students = []; return }
      const data = await teacherInternshipMyStudents(this.batchId)
      const existingIds = new Set((this.list || []).map((x) => String(x.internId || x.internshipId)))
      this.students = (data?.list || []).filter((x) => !existingIds.has(String(x.id))); this.studentIndex = 0
    },
    async onBatch(e) {
      this.batchIndex = Number(e.detail.value); const batch = this.batches[this.batchIndex]
      this.context.selectBatch(batch?.id); this.batchId = this.context.selectedBatchId; this.state = 'loading'
      try { await Promise.all([this.loadList(), this.canCreate ? this.loadStudents() : Promise.resolve()]); this.state = 'ready' }
      catch (err) { this.state = 'error'; toast(err?.message || '批次数据加载失败') }
    },
    async openCreate() { this.tab = 'create'; if (this.canCreate && !this.students.length) { try { await this.loadStudents() } catch (e) { toast(e?.message || '学生名单加载失败') } } },
    async pickFile() {
      if (this.uploading) return
      try {
        const file = await chooseSingleFile(); if (!file) return
        if (Number(file.size || 0) > 20 * 1024 * 1024) { toast('文件不能超过20MB'); return }
        this.uploading = true
        const result = await uploadBusinessFile(file, { bizType: 'INTERNSHIP_ENTERPRISE_EVAL' })
        this.form.sourceFileId = result.fileId; this.sourceFileName = result.fileName || file.name || '已上传材料'; toast('评价材料上传成功')
      } catch (e) { toast(normalizeError(e).text || '文件上传失败') } finally { this.uploading = false }
    },
    submit() {
      if (this.submitting) return
      const student = this.students[this.studentIndex]
      if (!student) return toast('请选择实习学生')
      if (!this.form.mentorName) return toast('请填写企业导师姓名')
      for (const field of this.scoreFields) { const value = Number(this.form[field.key]); if (!Number.isInteger(value) || value < 0 || value > 100) return toast(`${field.label}评分必须是0-100整数`) }
      if (!this.form.sourceFileId) return toast('请上传企业盖章评价材料')
      const body = { internshipId: student.id, batchId: this.batchId, sourceType: 'SCHOOL_RECORDED', ...this.form }
      this.scoreFields.forEach((field) => { body[field.key] = Number(this.form[field.key]) })
      this.submitting = true
      submitLock.run(() => teacherInternshipEnterpriseEvalCreate(body)).then(() => {
        toast('企业评价已代录，等待独立审核')
        this.form = { mentorName: '', attendanceScore: '', skillScore: '', attitudeScore: '', collaborationScore: '', safetyScore: '', overallComment: '', recommendHire: false, sourceFileId: '' }
        this.sourceFileName = ''; this.tab = 'list'; return this.load()
      }).catch((e) => { if (e?.code !== 'LOCKED') toast(normalizeError(e).text) }).finally(() => { this.submitting = false })
    },
    review(item, action) {
      if (!this.canReview || this.submitting || this.isOwnRecord(item)) return
      uni.showModal({ title: action === 'APPROVE' ? '审核通过' : '退回评价', editable: true, placeholderText: action === 'RETURN' ? '请输入退回原因（至少5字）' : '可填写审核意见', success: (res) => {
        if (!res.confirm) return
        const comment = String(res.content || '').trim(); if (action === 'RETURN' && comment.length < 5) return toast('退回原因至少5字')
        this.submitting = true
        teacherInternshipEnterpriseEvalReview(item.id, { action, comment, expectedVersion: item.version }).then(() => { toast('审核完成'); return this.loadList() }).catch((e) => toast(normalizeError(e).text)).finally(() => { this.submitting = false })
      } })
    }
  }
}
</script>

<style scoped>
.ee__tabs{display:flex;gap:var(--space-6);padding:var(--space-3) var(--page-padding-mobile) 0;background:var(--bg-card)}.ee__tab{position:relative;padding-bottom:var(--space-3);color:var(--text-tertiary)}.ee__tab.is-on{color:var(--text-primary);font-weight:var(--font-weight-semibold)}.ee__tab-u{position:absolute;left:50%;bottom:0;transform:translateX(-50%);width:22px;height:3px;border-radius:2px;background:var(--teacher-600)}.ee__batch,.ee__row,.ee__file{display:flex;align-items:center;min-height:50px;border-bottom:1px solid var(--border-light)}.ee__label{width:110px;flex-shrink:0;color:var(--text-secondary);font-size:var(--font-size-sm)}.ee__picker,.ee__input{flex:1}.ee__pick-val,.ee__input{text-align:right;color:var(--text-primary);font-size:var(--font-size-sm)}.ee__arrow{margin-left:4px;color:var(--text-tertiary)}.ee{display:flex;flex-direction:column;gap:var(--space-2)}.ee__sub{display:block;margin-top:3px;color:var(--text-tertiary);font-size:var(--font-size-xs)}.ee__scores{display:flex;flex-wrap:wrap;gap:6px 12px;padding:var(--space-2);background:var(--gray-50);border-radius:var(--radius-md);font-size:var(--font-size-xs)}.ee__avg{color:var(--teacher-700);font-weight:var(--font-weight-semibold)}.ee__source{display:flex;flex-wrap:wrap;gap:8px 14px;color:var(--text-tertiary);font-size:var(--font-size-xs)}.ee__actions{display:flex;gap:var(--space-2)}.ee__form{display:flex;flex-direction:column}.ee__file{justify-content:space-between;gap:var(--space-2);padding:var(--space-2) 0}.ee__file-name{display:block;margin-top:4px;color:var(--text-tertiary);font-size:var(--font-size-xs)}
</style>
