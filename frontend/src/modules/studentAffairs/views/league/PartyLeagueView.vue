<template>
  <AppPageShell
    title="党团建设"
    subtitle="党/团员发展阶段台账（申请人→积极分子→发展对象→预备党员→正式党员）。材料脱敏、仅记引用。"
    role-name="党委 / 团委 / 组织委员"
    data-scope-name="按数据范围（辅导员限本班）"
    watermark-purpose="党团发展台账（敏感）"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载发展台账..." @retry="load"
                    @back="$router.push('/admin/student-affairs/activity')">
      <div class="sa-toolbar">
        <div class="sa-grid sa-grid--metrics">
          <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
        </div>
        <AppPermissionButton :allowed="canBtn('studentAffairs.league.manage')" code="studentAffairs.league.manage" :loading="saving" @click="openForm">建发展档案</AppPermissionButton>
      </div>

      <AppSectionCard v-if="formVisible" title="建党团发展台账">
        <div class="lg-grid">
          <div class="lg-field"><span>学生 *</span><AppStudentPicker v-model="form.studentId" placeholder="按姓名 / 学号搜索学生" /></div>
          <label class="lg-field"><span>类型</span>
            <AppSelect v-model="form.devType" :options="DEV_TYPE_OPTIONS" placeholder="" /></label>
          <label class="lg-field"><span>党/团支部</span><AppTextInput v-model="form.branchName" /></label>
        </div>
        <p v-if="form.error" class="lg-error">{{ form.error }}</p>
        <div class="lg-actions">
          <button type="button" class="lg-btn" @click="formVisible = false">取消</button>
          <AppPermissionButton :allowed="canBtn('studentAffairs.league.manage')" code="studentAffairs.league.manage" :loading="saving" @click="save">建档</AppPermissionButton>
        </div>
      </AppSectionCard>

      <div class="lg-layout">
        <AppSectionCard title="发展台账" class="lg-list">
          <div class="lg-filters">
            <button v-for="f in stageFilters" :key="f.key" type="button" class="lg-chip"
                    :class="{ 'is-on': activeStage === f.key }" @click="setStage(f.key)">{{ f.label }}</button>
          </div>
          <ul class="lg-devs">
            <li v-for="d in items" :key="d.devId" class="lg-dev" :class="{ 'is-active': sel && sel.devId === d.devId }" @click="select(d)">
              <div class="lg-dev__top"><span class="lg-dev__name">{{ d.realName || ('学生#'+d.studentId) }}</span>
                <StatusTag :type="statusType(d.status)" :label="d.statusLabel" dot /></div>
              <div class="lg-dev__meta">{{ d.devTypeLabel }} · {{ d.currentStageLabel }} · {{ d.branchName || '未填支部' }}</div>
            </li>
            <li v-if="!items.length" class="lg-empty">暂无发展台账</li>
          </ul>
        </AppSectionCard>

        <AppSectionCard :title="sel ? (sel.realName + ' · 发展阶段时间线') : '阶段详情'" class="lg-detail">
          <p v-if="!sel" class="lg-hint">从左侧选择一条发展台账查看阶段时间线并推进。</p>
          <template v-else>
            <div class="lg-subhead">
              <div>当前阶段：<b>{{ sel.currentStageLabel }}</b> · <StatusTag :type="statusType(sel.status)" :label="sel.statusLabel" dot /></div>
              <div v-if="sel.status==='ONGOING'" class="lg-adv">
                <AppSelect v-model="advStage" class="lg-advpick" :options="nextStageOptions" placeholder="推进到…" />
                <AppPermissionButton :allowed="canBtn('studentAffairs.league.manage')" code="studentAffairs.league.manage" size="sm" :disabled="!advStage" @click="advance">推进</AppPermissionButton>
                <AppPermissionButton :allowed="canBtn('studentAffairs.league.manage')" code="studentAffairs.league.manage" size="sm" variant="secondary" danger @click="terminate">终止</AppPermissionButton>
              </div>
            </div>
            <ol class="lg-timeline">
              <li v-for="st in stages" :key="st.stageId">
                <span class="lg-tl__stage">{{ st.toStageLabel }}</span>
                <span class="lg-tl__meta">{{ (st.occurredAt||'').slice(0,10) }} · {{ st.operator || '—' }}
                  <em v-if="st.hasMaterial" class="lg-tl__mat">📎 含材料</em></span>
                <span v-if="st.remark" class="lg-tl__remark">{{ st.remark }}</span>
              </li>
              <li v-if="!stages.length" class="lg-empty">暂无阶段记录</li>
            </ol>

            <div class="lg-attach">
              <div class="lg-attach__head">
                <span>发展材料附件（授权下载留痕）</span>
                <label class="lg-upload">
                  <input type="file" class="lg-file" :disabled="uploading" @change="uploadMaterial" />
                  <span>{{ uploading ? '上传中…' : '＋ 上传材料' }}</span>
                </label>
              </div>
              <ul class="lg-attach__list">
                <li v-for="a in attachments" :key="a.attachmentId">
                  <span class="lg-att__name">📎 {{ a.fileName || ('附件#' + a.attachmentId) }}</span>
                  <span class="lg-att__meta">{{ (a.uploadedAt || '').slice(0, 10) }}</span>
                  <AppPermissionButton :allowed="canBtn('studentAffairs.league.view')" code="studentAffairs.league.view" size="sm" variant="secondary"
                                       @click="downloadMaterial(a)">下载</AppPermissionButton>
                </li>
                <li v-if="!attachments.length" class="lg-empty">暂无材料附件</li>
              </ul>
            </div>
          </template>
        </AppSectionCard>
      </div>
    </AppGlobalState>

    <!-- 终止发展：无党团发展口径词条，不套用其他场景模板 -->
    <AppConfirmDialog
      v-model:visible="terDlg.visible" title="终止发展流程" type="danger" confirm-text="确认终止"
      require-reason :reason-min-length="5" reason-label="终止原因（≥5 字）"
      description="终止后该生发展流程置为已终止，原因记入档案。"
      :submitting="saving" @confirm="submitTerminate"
    />
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSectionCard,
  AppSelect, AppStatusTag, AppStudentPicker, AppTextInput
} from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'
import { canCode } from '@/modules/studentAffairs/composables/permission'


const STAGES = [
  { key: 'APPLICANT', label: '入党申请人' }, { key: 'ACTIVIST', label: '入党积极分子' },
  { key: 'DEVELOPMENT_TARGET', label: '发展对象' }, { key: 'PROBATIONARY', label: '预备党员' },
  { key: 'FULL_MEMBER', label: '正式党员' }
]
const STAGE_FILTERS = [{ key: '', label: '全部' }].concat(STAGES)
const DEV_TYPE_OPTIONS = [{ value: 'PARTY', label: '党员发展' }, { value: 'LEAGUE', label: '团员发展' }]

export default {
  name: 'PartyLeagueView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppConfirmDialog, AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSectionCard,
    AppSelect, StatusTag: AppStatusTag, AppStudentPicker, AppTextInput
  },
  data() {
    return {
      loading: true, saving: false, errorMessage: '', items: [], statusCounts: null, activeStage: '', stageFilters: STAGE_FILTERS,
      formVisible: false, form: { studentId: null, devType: 'PARTY', branchName: '', error: '' },
      sel: null, stages: [], advStage: '', attachments: [], uploading: false,
      terDlg: { visible: false }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      return [
        { key: 't', label: '发展档案', value: this.statusCounts === null ? '—' : (this.statusCounts.ALL || 0), accent: 'primary' },
        { key: 'o', label: '发展中', value: this.statusCounts === null ? '—' : (this.statusCounts.ONGOING || 0), accent: 'warning' },
        { key: 'c', label: '已转正', value: this.statusCounts === null ? '—' : (this.statusCounts.COMPLETED || 0), accent: 'success' }
      ]
    },
    nextStages() {
      if (!this.sel) return []
      const i = STAGES.findIndex((s) => s.key === this.sel.currentStage)
      return STAGES.slice(i + 1)
    },
    DEV_TYPE_OPTIONS: () => DEV_TYPE_OPTIONS,
    nextStageOptions() {
      return this.nextStages.map((s) => ({ value: s.key, label: s.label }))
    }
  },
  mounted() { this.load() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    async load() {
      this.loading = true; this.errorMessage = ''
      // 待服务端全量统计：工作台仅加载 API 单页上限。
      const res = await studentAffairsApi.getLeagueDev({ stage: this.activeStage, pageSize: 200 })
      if (res.code === 0 && res.data) {
        this.items = res.data.items || []
        this.statusCounts = res.data.statusCounts || null
      }
      else this.errorMessage = res.message || '发展台账加载失败'
      this.loading = false
    },
    setStage(k) { if (this.activeStage === k) return; this.activeStage = k; this.load() },
    openForm() { this.form = { studentId: '', devType: 'PARTY', branchName: '', error: '' }; this.formVisible = true },
    async save() {
      const m = this.form
      if (!m.studentId) { m.error = '请选择学生'; return }
      m.error = ''; this.saving = true
      const res = await studentAffairsApi.createLeagueDev({ studentId: Number(m.studentId), devType: m.devType, branchName: (m.branchName || '').trim() || undefined })
      this.saving = false
      if (res.code === 0) { toast.success('已建档'); this.formVisible = false; this.load() } else m.error = res.message || '建档失败'
    },
    async select(d) {
      this.sel = d; this.stages = []; this.advStage = ''; this.attachments = []
      const res = await studentAffairsApi.getLeagueStages(d.devId)
      if (res.code === 0 && res.data) this.stages = res.data.items || []
      this.loadAttachments()
    },
    async loadAttachments() {
      if (!this.sel) return
      const res = await studentAffairsApi.listAttachments('LEAGUE', this.sel.devId)
      if (res.code === 0 && res.data) this.attachments = res.data.items || []
    },
    async uploadMaterial(ev) {
      const file = ev.target.files && ev.target.files[0]
      ev.target.value = ''
      if (!file || !this.sel) return
      this.uploading = true
      const up = await studentAffairsApi.uploadAttachmentFile(file)
      if (up.code !== 0) { this.uploading = false; toast.error(up.message || '上传失败'); return }
      const res = await studentAffairsApi.linkAttachment({ bizType: 'LEAGUE', bizId: this.sel.devId, fileId: up.data.fileId })
      this.uploading = false
      if (res.code === 0) { toast.success('材料已上传'); this.loadAttachments() } else toast.error(res.message || '关联失败')
    },
    async downloadMaterial(a) {
      const res = await studentAffairsApi.downloadAttachment(a.attachmentId, a.fileName || '党团材料')
      if (res.code !== 0) toast.error(res.message || '无权下载或文件不存在')
    },
    async advance() {
      if (!this.advStage) return
      const res = await studentAffairsApi.advanceLeagueStage(this.sel.devId, { toStage: this.advStage, version: this.sel.version })
      if (res.code === 0) { toast.success('已推进'); this.sel = res.data; this.advStage = ''; this.select(res.data); this.load() } else toast.error(res.message || '推进失败')
    },
    terminate() { this.terDlg.visible = true },
    async submitTerminate({ reason }) {
      const res = await studentAffairsApi.terminateLeagueDev(this.sel.devId, reason.trim(), this.sel.version)
      if (res.code === 0) {
        this.terDlg.visible = false
        toast.success('已终止')
        this.sel = res.data
        this.load()
      } else toast.error(res.message || '终止失败')
    },
    statusType(s) { return ({ ONGOING: 'warning', COMPLETED: 'success', TERMINATED: 'default' })[s] || 'default' }
  }
}
</script>

<style scoped>
.sa-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); margin-bottom: var(--space-4); flex-wrap: wrap; }
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: var(--space-4); flex: 1; min-width: 300px; }
.lg-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: var(--space-3); margin-bottom: var(--space-3); }
.lg-field { display: flex; flex-direction: column; gap: 4px; font-size: var(--font-size-sm); }
.lg-input { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 7px 10px; }
.lg-error { color: var(--danger-500,#dc2626); font-size: var(--font-size-sm); }
.lg-actions { display: flex; gap: var(--space-3); justify-content: flex-end; }
.lg-btn { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-md); padding: 7px 16px; cursor: pointer; }
.lg-layout { display: grid; grid-template-columns: 360px 1fr; gap: var(--space-4); }
.lg-advpick { width: 170px; }
.lg-filters { display: flex; gap: 6px; margin-bottom: var(--space-3); flex-wrap: wrap; }
.lg-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 3px 10px; font-size: var(--font-size-xs); cursor: pointer; }
.lg-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.lg-devs { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--space-2); }
.lg-dev { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: var(--space-3); cursor: pointer; }
.lg-dev.is-active { border-color: var(--color-primary); box-shadow: 0 0 0 2px rgba(37,99,235,0.12); }
.lg-dev__top { display: flex; justify-content: space-between; align-items: center; }
.lg-dev__name { font-weight: 600; }
.lg-dev__meta { font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 4px; }
.lg-empty, .lg-hint { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.lg-subhead { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-3); flex-wrap: wrap; gap: var(--space-2); }
.lg-adv { display: flex; gap: var(--space-2); align-items: center; }
.lg-timeline { list-style: none; margin: 0; padding: 0; border-left: 2px solid var(--border-light); }
.lg-timeline li { padding: 0 0 var(--space-3) var(--space-4); position: relative; }
.lg-timeline li::before { content: ''; position: absolute; left: -5px; top: 4px; width: 8px; height: 8px; border-radius: 50%; background: var(--color-primary); }
.lg-tl__stage { font-weight: 600; }
.lg-tl__meta { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); }
.lg-tl__mat { color: var(--color-primary); font-style: normal; margin-left: 6px; }
.lg-attach { margin-top: var(--space-4); border-top: 1px dashed var(--border-light); padding-top: var(--space-3); }
.lg-attach__head { display: flex; justify-content: space-between; align-items: center; font-size: var(--font-size-sm); font-weight: 600; margin-bottom: var(--space-2); }
.lg-upload { position: relative; overflow: hidden; border: 1px solid var(--color-primary); color: var(--color-primary); border-radius: var(--radius-md); padding: 4px 12px; cursor: pointer; font-weight: 500; }
.lg-file { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.lg-attach__list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.lg-attach__list li { display: flex; align-items: center; gap: var(--space-3); }
.lg-att__name { flex: 1; }
.lg-att__meta { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.lg-tl__remark { display: block; font-size: var(--font-size-sm); color: var(--text-tertiary); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } .lg-grid, .lg-layout { grid-template-columns: 1fr; } }
</style>
