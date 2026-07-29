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
      <section class="sa-summary-strip">
        <div class="sa-summary-strip__content">
          <span class="sa-summary-strip__eyebrow">党团发展工作台</span>
          <h2 class="sa-summary-strip__title">发展中 {{ statusCounts === null ? '—' : (statusCounts.ONGOING || 0) }} 人，已完成 {{ statusCounts === null ? '—' : (statusCounts.COMPLETED || 0) }} 人</h2>
          <p class="sa-summary-strip__text">发展流程必须逐级推进，不允许跳过阶段。选择学生后核对当前阶段、历史时间线和材料，再执行下一阶段或终止。</p>
        </div>
        <div class="sa-summary-strip__actions">
          <AppPermissionButton :allowed="canBtn('studentAffairs.league.manage')" code="studentAffairs.league.manage" :loading="saving" @click="openForm">建立发展档案</AppPermissionButton>
        </div>
      </section>

      <div class="sa-workflow-strip" aria-label="党员发展流程">
        <div class="sa-workflow-step" data-step="1"><strong>建立档案</strong><br>选择学生、类型与党团支部</div>
        <div class="sa-workflow-step" data-step="2"><strong>逐级推进</strong><br>按申请人、积极分子等顺序推进</div>
        <div class="sa-workflow-step" data-step="3"><strong>材料留痕</strong><br>上传阶段材料并执行授权下载</div>
        <div class="sa-workflow-step" data-step="4"><strong>完成 / 终止</strong><br>转正或终止均保留原因和历史</div>
      </div>

      <div class="sa-toolbar">
        <div class="sa-grid sa-grid--metrics">
          <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
        </div>
        <AppPermissionButton :allowed="canBtn('studentAffairs.league.manage')" code="studentAffairs.league.manage" :loading="saving" @click="openForm">建发展档案</AppPermissionButton>
      </div>

      <AppSectionCard v-if="formVisible" title="建立党团发展档案">
        <div class="lg-form-note">建立档案后默认进入首个发展阶段。党团支部可选填，但建议完整登记，便于后续材料和组织关系追溯。</div>
        <div class="lg-grid">
          <div class="lg-field"><span>学生 *</span><AppStudentPicker v-model="form.studentId" placeholder="按姓名 / 学号搜索学生" /></div>
          <label class="lg-field"><span>类型</span><AppSelect v-model="form.devType" :options="DEV_TYPE_OPTIONS" placeholder="" /></label>
          <label class="lg-field"><span>党/团支部</span><AppTextInput v-model="form.branchName" placeholder="选填，如：信息工程学院学生第一党支部" /></label>
        </div>
        <p v-if="form.error" class="lg-error">{{ form.error }}</p>
        <div class="lg-actions">
          <button type="button" class="lg-btn" @click="formVisible = false">取消</button>
          <AppPermissionButton :allowed="canBtn('studentAffairs.league.manage')" code="studentAffairs.league.manage" :loading="saving" @click="save">确认建档</AppPermissionButton>
        </div>
      </AppSectionCard>

      <div class="lg-layout">
        <AppSectionCard title="发展台账" class="lg-list">
          <p class="lg-section-hint">按类型、状态和阶段筛选。选择学生后，右侧展示完整阶段时间线和材料。</p>
          <div class="lg-filters sa-filter-bar">
            <AppSelect v-model="activeType" :options="devTypeFilters" placeholder="全部类型" @change="setType" />
            <AppSelect v-model="activeStatus" :options="statusFilters" placeholder="全部状态" @change="setStatus" />
            <button v-for="f in stageFilters" :key="f.key" type="button" class="lg-chip"
                    :class="{ 'is-on': activeStage === f.key }" @click="setStage(f.key)">{{ f.label }}</button>
          </div>
          <ul class="lg-devs">
            <li v-for="d in items" :key="d.devId" class="lg-dev" :class="{ 'is-active': sel && sel.devId === d.devId }" @click="select(d)">
              <div class="lg-dev__top"><span class="lg-dev__name">{{ d.realName || ('学生#'+d.studentId) }}</span>
                <StatusTag :type="statusType(d.status)" :label="d.statusLabel" dot /></div>
              <div class="lg-dev__meta">{{ d.devTypeLabel }} · {{ d.currentStageLabel }} · {{ d.branchName || '未填支部' }}</div>
            </li>
            <li v-if="!items.length" class="lg-empty">当前筛选下暂无发展档案。可清除筛选，或点击“建立发展档案”。</li>
          </ul>
          <AppPagination v-model:page="pagination.page" v-model:pageSize="pagination.pageSize"
                         :total="pagination.total" @change="load" />
        </AppSectionCard>

        <AppSectionCard :title="sel ? (sel.realName + ' · 发展阶段时间线') : '阶段详情'" class="lg-detail">
          <p v-if="!sel" class="lg-hint">从左侧选择一条发展档案，查看当前阶段、历史材料和下一步可执行动作。</p>
          <template v-else>
            <div class="lg-selected-summary">
              <div><span>当前发展档案</span><strong>{{ sel.realName || ('学生#' + sel.studentId) }}</strong><small>{{ sel.devTypeLabel }} · {{ sel.branchName || '未填支部' }}</small></div>
              <div><span>当前阶段</span><strong>{{ sel.currentStageLabel }}</strong><StatusTag :type="statusType(sel.status)" :label="sel.statusLabel" dot /></div>
            </div>
            <div class="lg-subhead">
              <div><strong>阶段时间线</strong><small>只能推进到后端允许的下一阶段</small></div>
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
              <li v-if="!stages.length" class="lg-empty">暂无阶段记录。</li>
            </ol>

            <div class="lg-attach">
              <div class="lg-attach__head">
                <div><span>发展材料附件</span><small>上传和下载均按权限控制，授权下载留痕</small></div>
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
                <li v-if="!attachments.length" class="lg-empty">当前阶段暂无材料附件。</li>
              </ul>
            </div>
          </template>
        </AppSectionCard>
      </div>
    </AppGlobalState>

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
  AppConfirmDialog, AppGlobalState, AppMetricCard, AppPageShell, AppPagination, AppPermissionButton, AppSectionCard,
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
    AppConfirmDialog, AppGlobalState, AppMetricCard, AppPageShell, AppPagination, AppPermissionButton, AppSectionCard,
    AppSelect, StatusTag: AppStatusTag, AppStudentPicker, AppTextInput
  },
  data() {
    return {
      loading: true, saving: false, errorMessage: '', items: [], statusCounts: null, activeStage: '', stageFilters: STAGE_FILTERS,
      activeType: '', activeStatus: '',
      devTypeFilters: [{ value: '', label: '全部类型' }, ...DEV_TYPE_OPTIONS],
      statusFilters: [{ value: '', label: '全部状态' }, { value: 'ONGOING', label: '发展中' },
        { value: 'COMPLETED', label: '已完成' }, { value: 'TERMINATED', label: '已终止' }],
      pagination: { page: 1, pageSize: 20, total: 0 },
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
      return i >= 0 && i + 1 < STAGES.length ? [STAGES[i + 1]] : []
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
      const res = await studentAffairsApi.getLeagueDev({
        stage: this.activeStage, devType: this.activeType, status: this.activeStatus,
        page: this.pagination.page, pageSize: this.pagination.pageSize
      })
      if (res.code === 0 && res.data) {
        this.items = res.data.items || []
        this.pagination.total = Number(res.data.total || 0)
        this.statusCounts = res.data.statusCounts || null
      }
      else this.errorMessage = res.message || '发展台账加载失败'
      this.loading = false
    },
    setStage(k) { if (this.activeStage === k) return; this.activeStage = k; this.pagination.page = 1; this.load() },
    setType() { this.pagination.page = 1; this.load() },
    setStatus() { this.pagination.page = 1; this.load() },
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
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: var(--space-3); flex: 1; min-width: 300px; }
.lg-form-note { margin-bottom: var(--space-4); padding: 10px 12px; border: 1px solid var(--primary-100); border-radius: var(--radius-md); background: var(--primary-50); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.6; }
.lg-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-3); margin-bottom: var(--space-3); }
.lg-field { display: flex; flex-direction: column; gap: 4px; min-width: 0; font-size: var(--font-size-sm); }
.lg-error { margin: 0; padding: 9px 11px; border-radius: var(--radius-md); background: var(--danger-50); color: var(--danger-700, #b91c1c); font-size: var(--font-size-sm); }
.lg-actions { display: flex; gap: var(--space-3); justify-content: flex-end; padding-top: var(--space-3); border-top: 1px solid var(--border-light); }
.lg-btn { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-md); padding: 7px 16px; cursor: pointer; }
.lg-layout { display: grid; grid-template-columns: minmax(300px, 360px) minmax(0, 1fr); gap: var(--space-4); align-items: start; }
.lg-section-hint { margin: 0 0 var(--space-3); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.6; }
.lg-advpick { width: 170px; }
.lg-filters { display: flex; gap: 6px; margin-bottom: var(--space-3); flex-wrap: wrap; }
.lg-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 4px 10px; font-size: var(--font-size-xs); cursor: pointer; }
.lg-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.lg-devs { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--space-2); }
.lg-dev { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: var(--space-3); cursor: pointer; transition: border-color .12s, background .12s; }
.lg-dev:hover { border-color: var(--primary-200); background: var(--primary-50); }
.lg-dev.is-active { border-color: var(--color-primary); background: var(--primary-50); box-shadow: inset 3px 0 0 var(--color-primary); }
.lg-dev__top { display: flex; justify-content: space-between; align-items: center; gap: var(--space-2); }
.lg-dev__name { font-weight: 600; }
.lg-dev__meta { font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 4px; line-height: 1.5; }
.lg-empty, .lg-hint { color: var(--text-tertiary); padding: var(--space-4); text-align: center; line-height: 1.65; }
.lg-selected-summary { display: grid; grid-template-columns: minmax(0, 1fr) minmax(160px, .55fr); gap: var(--space-3); margin-bottom: var(--space-4); padding: var(--space-3); border: 1px solid var(--primary-100); border-radius: var(--radius-md); background: var(--primary-50); }
.lg-selected-summary > div { display: grid; gap: 3px; }
.lg-selected-summary span, .lg-selected-summary small { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.lg-selected-summary strong { color: var(--text-primary); }
.lg-subhead { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: var(--space-3); flex-wrap: wrap; gap: var(--space-3); padding-bottom: var(--space-3); border-bottom: 1px solid var(--border-light); }
.lg-subhead > div:first-child { display: grid; gap: 2px; }
.lg-subhead small { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.lg-adv { display: flex; gap: var(--space-2); align-items: center; flex-wrap: wrap; }
.lg-timeline { list-style: none; margin: 0; padding: 0; border-left: 2px solid var(--border-light); }
.lg-timeline li { padding: 0 0 var(--space-3) var(--space-4); position: relative; }
.lg-timeline li::before { content: ''; position: absolute; left: -5px; top: 4px; width: 8px; height: 8px; border-radius: 50%; background: var(--color-primary); }
.lg-tl__stage { font-weight: 600; }
.lg-tl__meta { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); }
.lg-tl__mat { color: var(--color-primary); font-style: normal; margin-left: 6px; }
.lg-tl__remark { display: block; margin-top: 2px; font-size: var(--font-size-sm); color: var(--text-tertiary); overflow-wrap: anywhere; }
.lg-attach { margin-top: var(--space-4); border-top: 1px solid var(--border-light); padding-top: var(--space-3); }
.lg-attach__head { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-3); font-size: var(--font-size-sm); font-weight: 600; margin-bottom: var(--space-2); }
.lg-attach__head > div { display: grid; gap: 2px; }
.lg-attach__head small { color: var(--text-tertiary); font-size: var(--font-size-xs); font-weight: 400; }
.lg-upload { position: relative; overflow: hidden; border: 1px solid var(--color-primary); color: var(--color-primary); border-radius: var(--radius-md); padding: 5px 12px; cursor: pointer; font-weight: 500; }
.lg-file { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.lg-attach__list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.lg-attach__list li { display: flex; align-items: center; gap: var(--space-3); padding: 8px 10px; border: 1px solid var(--border-light); border-radius: var(--radius-md); }
.lg-att__name { flex: 1; min-width: 0; overflow-wrap: anywhere; }
.lg-att__meta { font-size: var(--font-size-xs); color: var(--text-tertiary); white-space: nowrap; }
@media (max-width: 960px) { .sa-grid--metrics, .lg-grid, .lg-layout { grid-template-columns: 1fr; } }
@media (max-width: 640px) { .lg-actions { align-items: stretch; flex-direction: column-reverse; } .lg-actions > * { width: 100%; } .lg-selected-summary { grid-template-columns: 1fr; } .lg-advpick { width: 100%; } .lg-attach__head { flex-direction: column; } }
</style>
