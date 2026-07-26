<template>
  <ModulePageShell :title="head.className || '班级画像'" :subtitle="subtitle"
    :role-name="roleName" :data-scope-name="scopeHint">
    <template #actions>
      <AppButton variant="ghost" size="sm" @click="goBack">← 返回班级列表</AppButton>
    </template>

    <div v-if="loadErr" class="mp-stack">
      <ErrorState :description="loadErr" @retry="loadProfile" />
    </div>
    <div v-else class="mp-stack">
      <section class="mp-card hd">
        <div class="hd-main">
          <span class="hd-name">{{ head.className }}</span>
          <span class="mp-note">{{ head.collegeName }} · {{ head.majorName }} · {{ head.grade }}级</span>
        </div>
        <div class="hd-teacher">
          <span>辅导员：<b>{{ head.counselorName || '—' }}</b></span>
          <span>班主任：<b>{{ head.headTeacherName || '—' }}</b></span>
        </div>
      </section>

      <div class="metrics">
        <AppMetricCard v-for="m in metrics" :key="m.key" :title="m.label" :value="m.value" :unit="m.unit"
          :accent="metricAccent(m)" />
      </div>

      <div class="tabs">
        <button v-for="t in tabs" :key="t.key" type="button" class="tab" :class="{ 'is-active': tab === t.key }"
          @click="switchTab(t.key)">{{ t.label }}</button>
      </div>

      <!-- 学生名单 -->
      <template v-if="tab === 'students'">
        <LoadingState v-if="stu.loading" />
        <EmptyState v-else-if="!stu.rows.length" title="暂无学生" description="该班级暂无在籍学生" />
        <DataTable v-else :columns="stuColumns" :rows="stu.rows" row-key="studentId"
          :pagination="stu.pagination" @page-change="onStuPage">
          <template #cell-realName="{ row }">
            <div class="mp-cell-main">{{ row.realName }}</div>
            <div class="mp-cell-sub">{{ row.studentNo }}</div>
          </template>
        </DataTable>
      </template>

      <!-- 班级材料 -->
      <template v-else-if="tab === 'materials'">
        <div class="bar">
          <AppButton variant="secondary" size="sm" @click="openMaterialForm">＋ 新增材料</AppButton>
        </div>
        <LoadingState v-if="mat.loading" />
        <EmptyState v-else-if="!mat.rows.length" title="暂无班级材料" description="上传班会记录、主题活动、评优、考勤台账等材料" />
        <DataTable v-else :columns="matColumns" :rows="mat.rows" row-key="id" :pagination="mat.pagination" @page-change="onMatPage">
          <template #cell-title="{ row }">
            <div class="mp-cell-main">{{ row.title }}</div>
            <div class="mp-cell-sub">{{ row.materialTypeLabel }}<template v-if="row.uploader"> · {{ row.uploader }}</template></div>
          </template>
          <template #cell-file="{ row }">
            <button v-if="row.fileId" type="button" class="mp-link" @click="download(row)">{{ row.fileName || '下载附件' }}</button>
            <span v-else class="mp-note">无附件</span>
          </template>
          <template #cell-actions="{ row }">
            <AppPermissionButton :allowed="canBtn('studentAffairs.class.create')" code="studentAffairs.class.create" variant="danger" size="sm" @click="voidMaterial(row)">作废</AppPermissionButton>
          </template>
        </DataTable>
      </template>

      <!-- 班干部 -->
      <template v-else>
        <div class="bar">
          <AppButton variant="secondary" size="sm" @click="openCadreForm">＋ 任命班干部</AppButton>
        </div>
        <LoadingState v-if="cadre.loading" />
        <EmptyState v-else-if="!cadre.rows.length" title="暂无班干部" description="任命班长、团支书、学习委员等" />
        <ul v-else class="cadre-list">
          <li v-for="c in cadre.rows" :key="c.cadreId">
            <span class="cadre-pos">{{ positionLabel(c.position) }}</span>
            <span>{{ cadreName(c) }}</span>
            <AppPermissionButton :allowed="canBtn('studentAffairs.class.cadre.manage')" code="studentAffairs.class.cadre.manage" variant="danger" size="sm" @click="removeCadre(c)">免去</AppPermissionButton>
          </li>
        </ul>
      </template>
    </div>

    <AppConfirmDialog v-model:visible="confirm.visible" :title="confirm.title" :content="confirm.content"
      :danger="confirm.danger" :confirm-text="confirm.confirmText" :submitting="confirm.submitting" @confirm="onConfirm" />

    <!-- 表单弹窗（新增材料 / 任命班干部） -->
    <AppDrawer :visible="fm.visible" :title="fm.title" @update:visible="closeForm">
      <div class="fm-body">
        <template v-if="fm.kind === 'material'">
          <div class="fm-item">
            <label class="fm-label">材料类型<i>*</i></label>
            <AppSelect v-model="fm.values.materialType" :options="materialTypeOptions" placeholder="请选择类型" />
          </div>
          <div class="fm-item">
            <label class="fm-label">材料标题<i>*</i></label>
            <AppQuickPhrases scene-key="sa.class.material" @pick="onPickMaterialTitle" />
            <AppTextInput ref="matTitleTa" v-model="fm.values.title" placeholder="如：第3周主题班会记录" :maxlength="200" />
          </div>
          <div class="fm-item">
            <label class="fm-label">材料日期</label>
            <AppDatePicker v-model="fm.values.materialAt" />
          </div>
          <div class="fm-item">
            <label class="fm-label">附件（可选，走文件中心）</label>
            <input type="file" @change="onFilePick" />
            <span v-if="fm.uploading" class="mp-note">上传中…</span>
            <span v-else-if="fm.values.fileName" class="mp-note">已上传：{{ fm.values.fileName }}</span>
          </div>
          <div class="fm-item">
            <label class="fm-label">备注</label>
            <AppQuickPhrases scene-key="sa.class.material" @pick="onPickMaterialRemark" />
            <AppTextarea ref="matRemarkTa" v-model="fm.values.remark" placeholder="选填" :rows="2" :maxlength="500" show-count />
          </div>
        </template>
        <template v-else>
          <div class="fm-item">
            <label class="fm-label">职务<i>*</i></label>
            <AppSelect v-model="fm.values.position" :options="positionOptions" placeholder="请选择职务" />
          </div>
          <div class="fm-item">
            <label class="fm-label">学生<i>*</i></label>
            <AppStudentPicker v-model="fm.values.studentId" :options="studentOptions" placeholder="从本班学生选择" />
          </div>
        </template>
        <p v-if="fm.err" class="fm-err">{{ fm.err }}</p>
      </div>
      <template #footer>
        <AppButton variant="ghost" @click="closeForm">取消</AppButton>
        <AppButton variant="primary" :loading="fm.submitting" :disabled="fm.uploading" @click="submitForm">确定</AppButton>
      </template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
/**
 * 班级画像独立页（/admin/campus-service/classes/:classId）。
 * 聚合指标 + 学生名单(脱敏) + 班级材料(附件走文件中心) + 班干部任免。真实对接 /student-affairs/classes/*。
 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppMetricCard, AppConfirmDialog, AppPermissionButton, AppSelect, AppStudentPicker, AppTextInput, AppTextarea, AppDatePicker, AppQuickPhrases } from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { classApi } from '@/modules/studentAffairs/api/class.api'
import { requestUpload, requestBlob } from '@/services/http/client'
import { toast } from '@/utils/toast'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { canCode } from '@/modules/studentAffairs/composables/permission'


const MATERIAL_TYPES = [
  { label: '班会记录', value: 'CLASS_MEETING' }, { label: '主题活动', value: 'THEME_ACTIVITY' },
  { label: '评优材料', value: 'EVALUATION' }, { label: '考勤台账', value: 'ATTENDANCE' },
  { label: '班级总结', value: 'SUMMARY' }, { label: '其他', value: 'OTHER' }
]
const POSITIONS = [
  { label: '班长', value: 'MONITOR' }, { label: '副班长', value: 'VICE_MONITOR' },
  { label: '团支书', value: 'LEAGUE_SECRETARY' }, { label: '学习委员', value: 'STUDY' },
  { label: '生活委员', value: 'LIFE' }, { label: '体育委员', value: 'SPORTS' },
  { label: '心理委员', value: 'PSYCHOLOGY' }, { label: '组织委员', value: 'ORGANIZATION' },
  { label: '宣传委员', value: 'PUBLICITY' }, { label: '其他', value: 'OTHER' }
]
const STU_COLUMNS = [
  { key: 'realName', title: '学生' }, { key: 'gender', title: '性别' },
  { key: 'studentStatus', title: '学籍状态' }, { key: 'phoneMasked', title: '联系方式' }
]
const MAT_COLUMNS = [
  { key: 'title', title: '材料' }, { key: 'materialAt', title: '日期' },
  { key: 'file', title: '附件' }, { key: 'actions', title: '操作' }
]

export default {
  name: 'ClassProfileView',
  components: {
    ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppMetricCard, AppConfirmDialog,
    AppPermissionButton, AppSelect, AppStudentPicker, AppTextInput, AppTextarea, AppDatePicker, AppButton, AppDrawer, AppQuickPhrases
  },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      loadErr: '', head: {}, metrics: [],
      tab: 'students',
      tabs: [{ key: 'students', label: '学生名单' }, { key: 'materials', label: '班级材料' }, { key: 'cadres', label: '班干部' }],
      stu: { loading: false, rows: [], pagination: { page: 1, pageSize: 10, total: 0 } },
      mat: { loading: false, rows: [], pagination: { page: 1, pageSize: 10, total: 0 } },
      cadre: { loading: false, rows: [] },
      materialTypeOptions: MATERIAL_TYPES, positionOptions: POSITIONS,
      stuColumns: STU_COLUMNS, matColumns: MAT_COLUMNS,
      confirm: { visible: false, title: '', content: '', danger: false, confirmText: '确认', submitting: false, submit: null },
      fm: { visible: false, kind: '', title: '', submitting: false, uploading: false, err: '', values: {} }
    }
  },
  computed: {
    classId() { return this.$route.params.classId },
    roleName() { return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || '辅导员 / 学院学工 / 学工处' },
    scopeHint() { return (this.ctx && this.ctx.dataScope && (this.ctx.dataScope.scopeName || this.ctx.dataScope.name)) || '按数据范围裁剪' },
    subtitle() { return this.head.className ? `${this.head.collegeName || ''} · ${this.head.majorName || ''}` : '班级 360 画像' },
    studentOptions() { return this.stu.rows.map((s) => ({ label: `${s.realName}（${s.studentNo}）`, value: s.studentId })) }
  },
  created() { this.loadProfile(); this.loadStudents() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    goBack() { this.$router.push('/admin/campus-service/classes') },
    metricAccent(m) {
      if ((m.key === 'riskOpen' || m.key === 'overdueLeave' || m.key === 'discipline') && m.value) return 'risk'
      if (m.key === 'currentLeave' && m.value) return 'warning'
      return 'primary'
    },
    positionLabel(v) { return (POSITIONS.find((o) => o.value === v) || {}).label || v },
    studentName(sid) {
      const s = this.stu.rows.find((x) => String(x.studentId) === String(sid))
      return s ? `${s.realName}（${s.studentNo}）` : `学生#${sid}`
    },
    /** 班干部显示名：优先用后端直接返回的 studentName/studentNo（不依赖是否已加载学生名单 tab），
     *  缺失时回退到本地学生表查找，再回退到 学生#id。 */
    cadreName(c) {
      if (c.studentName) return c.studentNo ? `${c.studentName}（${c.studentNo}）` : c.studentName
      return this.studentName(c.studentId)
    },
    async loadProfile() {
      this.loadErr = ''
      const res = await classApi.profile(this.classId)
      if (res.code !== 0) { this.loadErr = res.message || '加载失败'; return }
      this.head = res.data
      this.metrics = res.data.metrics || []
    },
    switchTab(k) {
      this.tab = k
      if (k === 'students' && !this.stu.rows.length) this.loadStudents()
      if (k === 'materials' && !this.mat.rows.length) this.loadMaterials()
      if (k === 'cadres' && !this.cadre.rows.length) this.loadCadres()
    },
    async loadStudents() {
      this.stu.loading = true
      const res = await classApi.students(this.classId, { page: this.stu.pagination.page, pageSize: this.stu.pagination.pageSize })
      this.stu.loading = false
      if (res.code !== 0) return toast.error(res.message || '学生加载失败')
      this.stu.rows = res.data.list; this.stu.pagination.total = res.data.total
    },
    onStuPage(p) { this.stu.pagination.page = p; this.loadStudents() },
    async loadMaterials() {
      this.mat.loading = true
      const res = await classApi.materials(this.classId, { page: this.mat.pagination.page, pageSize: this.mat.pagination.pageSize })
      this.mat.loading = false
      if (res.code !== 0) return toast.error(res.message || '材料加载失败')
      this.mat.rows = res.data.list; this.mat.pagination.total = res.data.total
    },
    onMatPage(p) { this.mat.pagination.page = p; this.loadMaterials() },
    async loadCadres() {
      this.cadre.loading = true
      if (!this.stu.rows.length) await this.loadStudents()
      const res = await classApi.cadres(this.classId)
      this.cadre.loading = false
      if (res.code !== 0) return toast.error(res.message || '班干部加载失败')
      this.cadre.rows = (res.data && res.data.items) || []
    },
    openMaterialForm() {
      this.fm = { visible: true, kind: 'material', title: '新增班级材料', submitting: false, uploading: false, err: '',
        values: { materialType: '', title: '', materialAt: '', remark: '', fileId: '', fileName: '' } }
    },
    openCadreForm() {
      if (!this.stu.rows.length) this.loadStudents()
      this.fm = { visible: true, kind: 'cadre', title: '任命班干部', submitting: false, uploading: false, err: '',
        values: { position: '', studentId: '' } }
    },
    closeForm() { this.fm.visible = false },
    onPickMaterialTitle(text) {
      const el = this.$refs.matTitleTa && this.$refs.matTitleTa.$refs && this.$refs.matTitleTa.$refs.input
      if (!el) return
      const { value, selStart, selEnd } = insertAtCursor(el, this.fm.values.title, text)
      this.fm.values.title = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    onPickMaterialRemark(text) {
      const el = this.$refs.matRemarkTa && this.$refs.matRemarkTa.$refs && this.$refs.matRemarkTa.$refs.el
      if (!el) return
      const { value, selStart, selEnd } = insertAtCursor(el, this.fm.values.remark, text)
      this.fm.values.remark = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    async onFilePick(e) {
      const file = e.target.files && e.target.files[0]
      if (!file) return
      this.fm.uploading = true; this.fm.err = ''
      try {
        const d = await requestUpload('/files/upload', file)
        this.fm.values.fileId = d.fileId; this.fm.values.fileName = d.fileName || file.name
      } catch (err) {
        this.fm.err = '附件上传失败：' + (err.message || '')
      } finally {
        this.fm.uploading = false
      }
    },
    async submitForm() {
      this.fm.err = ''
      const v = this.fm.values
      if (this.fm.kind === 'material') {
        if (!v.materialType) { this.fm.err = '请选择材料类型'; return }
        if (!v.title || !v.title.trim()) { this.fm.err = '请填写材料标题'; return }
        this.fm.submitting = true
        const res = await classApi.addMaterial(this.classId, {
          materialType: v.materialType, title: v.title.trim(), materialAt: v.materialAt || null,
          remark: v.remark || null, fileId: v.fileId || null, fileName: v.fileName || null
        })
        this.fm.submitting = false
        if (res.code !== 0) { this.fm.err = res.message || '新增失败'; return }
        this.fm.visible = false; toast.success('已新增材料')
        this.mat.pagination.page = 1; this.loadMaterials(); this.loadProfile()
      } else {
        if (!v.position) { this.fm.err = '请选择职务'; return }
        if (!v.studentId) { this.fm.err = '请选择学生'; return }
        this.fm.submitting = true
        const res = await classApi.addCadre(this.classId, { studentId: v.studentId, position: v.position })
        this.fm.submitting = false
        if (res.code !== 0) { this.fm.err = res.message || '任命失败'; return }
        this.fm.visible = false; toast.success('已任命')
        this.loadCadres(); this.loadProfile()
      }
    },
    voidMaterial(row) {
      this.confirm = { visible: true, title: '作废材料', content: `确认作废「${row.title}」？作废后不可恢复（逻辑删除，留审计）。`,
        danger: true, confirmText: '确认作废', submitting: false,
        submit: async () => {
          const res = await classApi.voidMaterial(row.id)
          if (res.code !== 0) { toast.error(res.message || '作废失败'); return false }
          toast.success('已作废'); this.loadMaterials(); this.loadProfile(); return true
        } }
    },
    removeCadre(c) {
      this.confirm = { visible: true, title: '免去班干部', content: `确认免去「${this.cadreName(c)}」的${this.positionLabel(c.position)}职务？`,
        danger: true, confirmText: '确认免去', submitting: false,
        submit: async () => {
          const res = await classApi.removeCadre(c.cadreId)
          if (res.code !== 0) { toast.error(res.message || '免去失败'); return false }
          toast.success('已免去'); this.loadCadres(); this.loadProfile(); return true
        } }
    },
    async onConfirm() {
      this.confirm.submitting = true
      const okDone = await this.confirm.submit()
      this.confirm.submitting = false
      if (okDone !== false) this.confirm.visible = false
    },
    async download(row) {
      try {
        const blob = await requestBlob(`/files/download/${row.fileId}`)
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url; a.download = row.fileName || '附件'
        document.body.appendChild(a); a.click(); a.remove()
        URL.revokeObjectURL(url)
      } catch (e) { toast.error('下载失败：' + (e.message || '')) }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.hd { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); flex-wrap: wrap; padding: var(--space-4); }
.hd-name { font-size: var(--font-size-lg, 18px); font-weight: var(--font-weight-semibold); margin-right: var(--space-2); }
.hd-teacher { display: flex; gap: var(--space-4); font-size: var(--font-size-sm); color: var(--text-secondary); }
.metrics { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: var(--space-3); }
.tabs { display: flex; gap: var(--space-1); border-bottom: 1px solid var(--border-base); }
.tab { font: inherit; cursor: pointer; background: transparent; border: none; padding: var(--space-2) var(--space-4); color: var(--text-secondary); border-bottom: 2px solid transparent; }
.tab.is-active { color: var(--primary-600); border-bottom-color: var(--primary-600); font-weight: var(--font-weight-medium); }
.bar { display: flex; justify-content: flex-end; }
.cadre-list { list-style: none; margin: 0; padding: 0; }
.cadre-list li { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-2) 0; border-bottom: 1px solid var(--border-light); font-size: var(--font-size-sm); }
.cadre-pos { min-width: 72px; font-weight: var(--font-weight-medium); }
.lav-danger { color: var(--danger-600); }
.fm-body { display: flex; flex-direction: column; gap: var(--space-3); }
.fm-item { display: flex; flex-direction: column; gap: 6px; }
.fm-label { font-size: var(--font-size-sm); color: var(--text-secondary); }
.fm-label i { color: var(--danger-600); font-style: normal; margin-left: 2px; }
.fm-err { color: var(--danger-600); font-size: var(--font-size-sm); margin: 0; }
</style>
