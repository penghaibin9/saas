<template>
  <ModulePageShell
    title="成绩认定 · 课程替代"
    :subtitle="'转专业/转学学生用原修课程成绩替代现计划课程；审核通过即写入成绩台账（source=RECOGNIZED）并刷新学分绩点'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="primary" @click="openCreate">代录认定申请</AppButton>
    </template>

    <div class="aarn-bar">
      <button v-for="s in statusTabs" :key="s.key"
              :class="['aarn-chip', { 'is-active': statusFilter === s.key }]"
              @click="statusFilter = s.key; load()">{{ s.label }}</button>
    </div>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <EmptyState v-else-if="!rows.length" title="暂无认定申请" description="学生自助提交或教务代录后在此审核" />
    <DataTable v-else :columns="columns" :rows="rows" row-key="recognitionId">
      <template #cell-student="{ row }">{{ row.studentName }}（{{ row.studentNo }}）</template>
      <template #cell-map="{ row }">
        <div class="mp-cell-main">{{ row.sourceCourseName }} → {{ row.targetCourseName }}</div>
        <div class="mp-cell-sub">
          {{ row.sourceScore }} 分 · {{ row.sourceCredit != null ? row.sourceCredit + ' 学分' : '学分未填' }} · {{ row.sourceOrigin || '来源未注明' }}
          <span v-if="row.attachmentFileIds && row.attachmentFileIds.length">· 📎 {{ row.attachmentFileIds.length }} 附件</span>
        </div>
      </template>
      <template #cell-review="{ row }">
        <template v-if="row.reviewedBy">
          <div class="mp-cell-main">{{ row.reviewedBy }}</div>
          <div class="mp-cell-sub">{{ (row.reviewedAt || '').replace('T', ' ').slice(0, 16) }}</div>
        </template>
        <span v-else class="mp-cell-sub">—</span>
      </template>
      <template #cell-status="{ row }">
        <StatusTag :type="row.status === 'APPROVED' ? 'success' : row.status === 'REJECTED' ? 'danger' : 'primary'"
                   :label="{ SUBMITTED: '待审核', APPROVED: '已通过', REJECTED: '已驳回' }[row.status] || row.status" dot />
      </template>
      <template #cell-ops="{ row }">
        <button v-if="row.status === 'SUBMITTED'" class="mp-link" @click="approve(row)">通过</button>
        <button v-if="row.status === 'SUBMITTED'" class="mp-link is-danger" @click="openReject(row)">驳回</button>
        <span v-if="row.status === 'REJECTED'" class="mp-cell-sub">{{ row.reviewReason }}</span>
      </template>
    </DataTable>

    <AppDrawer :visible="createVisible" title="代录成绩认定申请" @close="createVisible = false">
      <div class="aarn-form">
        <AppFormItem label="学生" required><AppStudentPicker v-model="form.studentId" :disabled="saving" @change="onStudentChange" /></AppFormItem>
        <AppFormItem label="原课程名称" required><AppTextInput v-model="form.sourceCourseName" placeholder="如 高等数学A" :disabled="saving" /></AppFormItem>
        <AppFormItem label="原成绩（≥60）" required><AppNumberInput v-model="form.sourceScore" :min="0" :max="100" :disabled="saving" /></AppFormItem>
        <AppFormItem label="原学分"><AppNumberInput v-model="form.sourceCredit" :min="0" :max="30" :disabled="saving" /></AppFormItem>
        <AppFormItem label="来源说明"><AppTextInput v-model="form.sourceOrigin" placeholder="原专业/原学校/证书折算等" :disabled="saving" /></AppFormItem>
        <AppFormItem label="替代目标课程" required>
          <AppCoursePicker v-model="form.targetCourseId" placeholder="从课程库选择被替代的校内课程" :disabled="saving" @change="onTargetChange" />
        </AppFormItem>
        <AppFormItem label="佐证附件">
          <div class="aarn-upload">
            <input ref="fileInput" type="file" class="aarn-file" :disabled="saving || uploading" @change="onPickFile" />
            <span v-if="uploading" class="aarn-uploading">上传中…</span>
            <div v-if="form.attachments.length" class="aarn-files">
              <span v-for="(f, i) in form.attachments" :key="f.fileId" class="aarn-file-chip">
                {{ f.fileName }}<button type="button" class="aarn-file-x" @click="form.attachments.splice(i, 1)">✕</button>
              </span>
            </div>
          </div>
        </AppFormItem>
        <AppFormItem label="申请理由"><AppTextarea v-model="form.reason" placeholder="选填" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="createVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitCreate">提交</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="rejectVisible" :title="'驳回 · ' + (rejectRow ? rejectRow.studentName : '')" @close="rejectVisible = false">
      <div class="aarn-form">
        <AppFormItem label="驳回原因（≥5字）" required><AppTextarea v-model="rejectReason" placeholder="如：原课程学时/大纲不满足替代要求" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="rejectError" type="danger" :description="rejectError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="rejectVisible = false">取消</AppButton>
        <AppButton variant="danger" :loading="saving" @click="submitReject">驳回</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="confirmVisible" :title="confirmTitle" :message="confirmMessage" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
/** 成绩认定/课程替代（/admin/academic-affairs/grade-recognition）：代录+审核；通过写 RECOGNIZED 成绩并刷新台账。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppNumberInput, AppTextarea, AppFormItem, AppConfirmDialog, AppInlineAlert, AppCoursePicker, AppStudentPicker } from '@/components/common'
import { academicAffairsApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { requestUpload } from '@/services/http/client'
import { toast } from '@/utils/toast'

export default {
  name: 'AaGradeRecognitionView',
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppTextInput, AppNumberInput, AppTextarea, AppFormItem,
    AppConfirmDialog, AppInlineAlert, AppCoursePicker, AppStudentPicker
  },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      loading: true, error: '', rows: [], statusFilter: 'SUBMITTED',
      statusTabs: [
        { key: 'SUBMITTED', label: '待审核' }, { key: 'APPROVED', label: '已通过' },
        { key: 'REJECTED', label: '已驳回' }, { key: '', label: '全部' }
      ],
      columns: [
        { key: 'student', title: '学生' }, { key: 'map', title: '课程替代（原→目标）' },
        { key: 'review', title: '审核信息' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }
      ],
      createVisible: false, formError: '', uploading: false,
      form: { studentId: '', studentNo: '', sourceCourseName: '', sourceScore: 60, sourceCredit: null, sourceOrigin: '', targetCourseId: '', targetCourseName: '', attachments: [], reason: '' },
      rejectVisible: false, rejectRow: null, rejectReason: '', rejectError: '',
      saving: false, confirmVisible: false, confirmTitle: '', confirmMessage: '', pendingAction: null
    }
  },
  async created() {
    const c = await api.getContext()
    if (c.code === 0) this.ctx = c.data
    this.load()
  },
  methods: {
    async load() {
      this.loading = true; this.error = ''
      const res = await api.listRecognitions(this.statusFilter ? { status: this.statusFilter, pageSize: 100 } : { pageSize: 100 })
      if (res.code === 0) this.rows = res.data.list
      else this.error = res.message
      this.loading = false
    },
    openCreate() {
      this.form = { studentId: '', studentNo: '', sourceCourseName: '', sourceScore: 60, sourceCredit: null, sourceOrigin: '', targetCourseId: '', targetCourseName: '', attachments: [], reason: '' }
      this.formError = ''; this.createVisible = true
    },
    onStudentChange(v, items) {
      const item = items?.[0]
      this.form.studentNo = item?.raw?.studentNo || item?.studentNo || ''
    },
    onTargetChange(v, items) {
      const item = items?.[0]
      this.form.targetCourseName = item?.raw?.courseName || item?.name || ''
    },
    async onPickFile(e) {
      const file = e.target.files && e.target.files[0]
      if (!file) return
      this.uploading = true
      try {
        const meta = await requestUpload('/files', file)
        this.form.attachments.push({ fileId: String(meta.fileId), fileName: meta.fileName || file.name })
      } catch (err) {
        toast.error((err && err.message) || '上传失败')
      } finally {
        this.uploading = false
        if (this.$refs.fileInput) this.$refs.fileInput.value = ''
      }
    },
    async submitCreate() {
      if (!this.form.studentNo || !this.form.sourceCourseName || !this.form.targetCourseId) {
        this.formError = '学号、原课程、目标课程（从课程库选择）必填'; return
      }
      this.saving = true
      const body = {
        studentNo: this.form.studentNo, sourceCourseName: this.form.sourceCourseName,
        sourceScore: this.form.sourceScore, sourceCredit: this.form.sourceCredit || undefined,
        sourceOrigin: this.form.sourceOrigin || undefined,
        targetCourseId: this.form.targetCourseId,
        attachmentFileIds: this.form.attachments.map((f) => f.fileId),
        reason: this.form.reason || undefined
      }
      const res = await api.submitRecognition(body)
      this.saving = false
      if (res.code === 0) { toast.success('已提交'); this.createVisible = false; this.load() } else this.formError = res.message
    },
    approve(row) {
      this.confirmTitle = '通过认定'
      this.confirmMessage = `确认通过「${row.studentName}」的认定？将以 ${row.sourceScore} 分写入课程「${row.targetCourseName}」并立即刷新学分绩点。`
      this.pendingAction = async () => {
        const res = await api.reviewRecognition(row.recognitionId, 'APPROVE')
        if (res.code === 0) { toast.success('已通过并写入台账'); this.load() } else toast.error(res.message)
      }
      this.confirmVisible = true
    },
    openReject(row) { this.rejectRow = row; this.rejectReason = ''; this.rejectError = ''; this.rejectVisible = true },
    async submitReject() {
      if (!this.rejectReason || this.rejectReason.trim().length < 5) { this.rejectError = '原因至少5字'; return }
      this.saving = true
      const res = await api.reviewRecognition(this.rejectRow.recognitionId, 'REJECT', this.rejectReason.trim())
      this.saving = false
      if (res.code === 0) { toast.success('已驳回'); this.rejectVisible = false; this.load() } else this.rejectError = res.message
    },
    onConfirm() { const a = this.pendingAction; this.pendingAction = null; if (a) a() }
  }
}
</script>

<style scoped>
.aarn-bar { display: flex; gap: 8px; margin-bottom: 12px; }
.aarn-chip { padding: 4px 14px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 14px; background: none; cursor: pointer; font-size: 13px; color: var(--text-secondary, #64748b); }
.aarn-chip.is-active { color: var(--primary-color, #2563eb); border-color: var(--primary-color, #2563eb); background: var(--primary-light, #eff6ff); }
.aarn-form { display: flex; flex-direction: column; gap: 12px; }
.aarn-upload { display: flex; flex-direction: column; gap: 8px; }
.aarn-file { font-size: 13px; }
.aarn-uploading { font-size: 12px; color: var(--primary-color, #2563eb); }
.aarn-files { display: flex; flex-wrap: wrap; gap: 6px; }
.aarn-file-chip { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; background: var(--fill-light, #f1f5f9); border-radius: 6px; font-size: 12px; }
.aarn-file-x { border: none; background: none; cursor: pointer; color: var(--text-tertiary, #94a3b8); font-size: 12px; }
</style>
