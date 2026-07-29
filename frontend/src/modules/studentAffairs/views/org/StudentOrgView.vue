<template>
  <AppPageShell
    title="学生干部与组织"
    subtitle="校/院学生组织建制与任职管理；干部履历汇总组织任职与班级班干部，供推优评先只读引用。"
    role-name="团委 / 学工处"
    data-scope-name="按租户（团委全校）"
    watermark-purpose="学生干部与组织管理"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载学生组织..." @retry="load"
                    @back="$router.push('/admin/student-affairs/activity')">
      <section class="sa-summary-strip">
        <div class="sa-summary-strip__content">
          <span class="sa-summary-strip__eyebrow">组织与干部履历</span>
          <h2 class="sa-summary-strip__title">当前页共 {{ items.length }} 个组织；选择组织后维护在任成员、职务和任期</h2>
          <p class="sa-summary-strip__text">组织任职会进入学生干部履历，供推优评先只读引用。任命前应核对组织状态、学生身份、职务名称和任期；卸任后历史记录继续保留。</p>
        </div>
        <div class="sa-summary-strip__actions">
          <AppPermissionButton :allowed="canBtn('studentAffairs.org.manage')" code="studentAffairs.org.manage" :loading="saving" @click="openForm">新建组织</AppPermissionButton>
        </div>
      </section>

      <div class="sa-workflow-strip" aria-label="学生组织管理流程">
        <div class="sa-workflow-step" data-step="1"><strong>建立组织</strong><br>设置名称、类型、级别和指导老师</div>
        <div class="sa-workflow-step" data-step="2"><strong>选择组织</strong><br>查看当前组织状态与在任成员</div>
        <div class="sa-workflow-step" data-step="3"><strong>任命干部</strong><br>登记学生、职务和任期</div>
        <div class="sa-workflow-step" data-step="4"><strong>卸任留痕</strong><br>结束当前任职，历史履历继续保留</div>
      </div>

      <div class="sa-toolbar">
        <div class="sa-grid sa-grid--metrics">
          <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
        </div>
        <AppPermissionButton :allowed="canBtn('studentAffairs.org.manage')" code="studentAffairs.org.manage" :loading="saving" @click="openForm">建组织</AppPermissionButton>
      </div>

      <AppSectionCard v-if="formVisible" title="新建学生组织">
        <div class="og-form-note">先明确组织名称、类型与级别。指导老师可选填，组织建立后再在右侧维护在任成员。</div>
        <div class="og-grid">
          <label class="og-field og-field--wide"><span>组织名称 *</span><AppTextInput v-model="form.orgName" placeholder="如：校学生会 / 信息工程学院学生会" /></label>
          <label class="og-field"><span>类型</span><AppSelect v-model="form.orgType" :options="TYPE_OPTIONS" placeholder="" /></label>
          <label class="og-field"><span>级别</span><AppSelect v-model="form.level" :options="LEVEL_OPTIONS" placeholder="" /></label>
          <label class="og-field"><span>指导老师</span><AppTextInput v-model="form.advisorName" placeholder="选填" /></label>
        </div>
        <p v-if="form.error" class="og-error">{{ form.error }}</p>
        <div class="og-actions">
          <button type="button" class="og-btn" @click="formVisible = false">取消</button>
          <AppPermissionButton :allowed="canBtn('studentAffairs.org.manage')" code="studentAffairs.org.manage" :loading="saving" @click="save">保存组织</AppPermissionButton>
        </div>
      </AppSectionCard>

      <div class="og-layout">
        <AppSectionCard title="组织列表" class="og-list">
          <p class="og-section-hint">选择组织后，右侧展示在任成员和任命入口。</p>
          <ul class="og-orgs">
            <li v-for="o in items" :key="o.orgId" class="og-org" :class="{ 'is-active': sel && sel.orgId === o.orgId }" @click="select(o)">
              <div class="og-org__top"><span class="og-org__name">{{ o.orgName }}</span>
                <StatusTag :type="o.status==='ACTIVE' ? 'success' : 'default'" :label="o.status==='ACTIVE' ? '在运营' : '停用'" dot /></div>
              <div class="og-org__meta">{{ o.levelLabel }} · {{ o.orgTypeLabel }} · {{ o.advisorName || '无指导老师' }}</div>
            </li>
            <li v-if="!items.length" class="og-empty">暂无学生组织，点击“新建组织”建立第一条组织建制。</li>
          </ul>
          <AppPagination v-model:page="pagination.page" v-model:pageSize="pagination.pageSize"
                         :total="pagination.total" @change="load" />
        </AppSectionCard>

        <AppSectionCard :title="sel ? (sel.orgName + ' · 在任成员') : '组织详情'" class="og-detail">
          <p v-if="!sel" class="og-hint">从左侧选择一个组织，查看当前成员、职务与任期，并进行任命或卸任。</p>
          <template v-else>
            <div class="og-selected-summary">
              <div><span>当前组织</span><strong>{{ sel.orgName }}</strong><small>{{ sel.levelLabel }} · {{ sel.orgTypeLabel }} · {{ sel.advisorName || '无指导老师' }}</small></div>
              <StatusTag :type="sel.status==='ACTIVE' ? 'success' : 'default'" :label="sel.status==='ACTIVE' ? '在运营' : '停用'" dot />
            </div>
            <div class="og-subhead">
              <div><h4>在任成员（{{ positions.length }}）</h4><small>任命记录进入学生干部履历</small></div>
              <AppPermissionButton :allowed="canBtn('studentAffairs.org.manage')" v-if="sel.status==='ACTIVE'" code="studentAffairs.org.manage" size="sm" @click="openAppoint">任命成员</AppPermissionButton>
            </div>
            <div v-if="apForm.visible" class="og-inline sa-inline-workspace">
              <div class="og-inline__title">登记新任职</div>
              <AppStudentPicker v-model="apForm.studentId" placeholder="按姓名 / 学号搜索学生" />
              <AppTextInput v-model="apForm.position" placeholder="职务，如：主席 / 部长" />
              <AppTextInput v-model="apForm.termCode" placeholder="任期，如：2025-2026" />
              <AppPermissionButton :allowed="canBtn('studentAffairs.org.manage')" code="studentAffairs.org.manage" size="sm" @click="appoint">确认任命</AppPermissionButton>
            </div>
            <DataTable v-if="positions.length" :columns="positionColumns" :rows="positions" row-key="positionId">
              <template #cell-student="{ row }"><span class="mp-cell-main">{{ row.realName || ('#'+row.studentId) }}</span></template>
              <template #cell-position="{ row }"><strong>{{ row.position }}</strong></template>
              <template #cell-term="{ row }">{{ row.termCode || '—' }}</template>
              <template #cell-actions="{ row }">
                <AppPermissionButton :allowed="canBtn('studentAffairs.org.manage')" code="studentAffairs.org.manage" size="sm" variant="secondary" danger @click="dismiss(row)">卸任</AppPermissionButton>
              </template>
            </DataTable>
            <p v-else class="sa-empty">该组织暂无在任成员。组织处于运营状态时，可点击“任命成员”建立干部任职。</p>
          </template>
        </AppSectionCard>
      </div>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import {
  AppGlobalState, AppMetricCard, AppPageShell, AppPagination, AppPermissionButton, AppSectionCard, AppSelect,
  AppStatusTag, AppStudentPicker, AppTextInput
} from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'
import { canCode } from '@/modules/studentAffairs/composables/permission'

const TYPES = { STUDENT_UNION: '学生会', SOCIETY_FEDERATION: '社团联合会', SELF_GOV: '自律委员会', OTHER: '其他组织' }
const TYPE_OPTIONS = Object.entries(TYPES).map(([value, label]) => ({ value, label }))
const LEVEL_OPTIONS = [{ value: 'SCHOOL', label: '校级' }, { value: 'COLLEGE', label: '院级' }]
const POSITION_COLUMNS = [
  { key: 'student', title: '学生' },
  { key: 'position', title: '职务' },
  { key: 'term', title: '任期' },
  { key: 'actions', title: '操作', align: 'right', width: '100px' }
]

export default {
  name: 'StudentOrgView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppGlobalState, AppMetricCard, AppPageShell, AppPagination, AppPermissionButton, AppSectionCard, AppSelect,
    StatusTag: AppStatusTag, AppStudentPicker, AppTextInput, DataTable
  },
  data() {
    return {
      positionColumns: POSITION_COLUMNS,
      loading: true, saving: false, errorMessage: '', items: [], TYPES,
      pagination: { page: 1, pageSize: 20, total: 0 },
      formVisible: false, form: { orgName: '', orgType: 'STUDENT_UNION', level: 'SCHOOL', advisorName: '', error: '' },
      sel: null, positions: [], apForm: { visible: false, studentId: null, position: '', termCode: '' }
    }
  },
  computed: {
    TYPE_OPTIONS: () => TYPE_OPTIONS,
    LEVEL_OPTIONS: () => LEVEL_OPTIONS,
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const school = this.items.filter((o) => o.level === 'SCHOOL').length
      const college = this.items.filter((o) => o.level === 'COLLEGE').length
      return [
        { key: 't', label: '组织总数', value: this.items.length, accent: 'primary' },
        { key: 's', label: '校级', value: school, accent: 'success' },
        { key: 'c', label: '院级', value: college, accent: 'info' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    async load() {
      this.loading = true; this.errorMessage = ''
      const res = await studentAffairsApi.getOrganizations({
        page: this.pagination.page, pageSize: this.pagination.pageSize
      })
      if (res.code === 0 && res.data) {
        this.items = res.data.items || []
        this.pagination.total = Number(res.data.total || 0)
      }
      else this.errorMessage = res.message || '学生组织加载失败'
      this.loading = false
    },
    openForm() { this.form = { orgName: '', orgType: 'STUDENT_UNION', level: 'SCHOOL', advisorName: '', error: '' }; this.formVisible = true },
    async save() {
      const m = this.form
      const orgName = (m.orgName || '').trim()
      if (!orgName) { m.error = '组织名称必填'; return }
      m.error = ''; this.saving = true
      const res = await studentAffairsApi.createOrganization({ orgName, orgType: m.orgType, level: m.level, advisorName: (m.advisorName || '').trim() || undefined })
      this.saving = false
      if (res.code === 0) { toast.success('已创建'); this.formVisible = false; this.load() } else m.error = res.message || '创建失败'
    },
    async select(o) {
      this.sel = o; this.positions = []; this.apForm.visible = false
      const res = await studentAffairsApi.getOrgPositions(o.orgId)
      if (res.code === 0 && res.data) this.positions = res.data.items || []
    },
    openAppoint() { this.apForm = { visible: true, studentId: '', position: '', termCode: '' } },
    async appoint() {
      const f = this.apForm
      const position = (f.position || '').trim()
      if (!f.studentId || !position) { toast.error('学生与职务必填'); return }
      const res = await studentAffairsApi.appointOrgPosition(this.sel.orgId, { studentId: Number(f.studentId), position, termCode: (f.termCode || '').trim() || undefined })
      if (res.code === 0) { toast.success('已任命'); this.apForm.visible = false; this.select(this.sel) } else toast.error(res.message || '任命失败')
    },
    async dismiss(p) {
      const res = await studentAffairsApi.dismissOrgPosition(p.positionId, p.version)
      if (res.code === 0) { toast.success('已卸任'); this.select(this.sel) } else toast.error(res.message || '卸任失败')
    }
  }
}
</script>

<style scoped>
.sa-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); margin-bottom: var(--space-4); flex-wrap: wrap; }
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: var(--space-3); flex: 1; min-width: 300px; }
.og-form-note { margin-bottom: var(--space-4); padding: 10px 12px; border: 1px solid var(--primary-100); border-radius: var(--radius-md); background: var(--primary-50); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.6; }
.og-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-3); margin-bottom: var(--space-3); }
.og-field { display: flex; flex-direction: column; gap: 4px; min-width: 0; font-size: var(--font-size-sm); }
.og-field--wide { grid-column: span 3; }
.og-error { margin: 0; padding: 9px 11px; border-radius: var(--radius-md); background: var(--danger-50); color: var(--danger-700, #b91c1c); font-size: var(--font-size-sm); }
.og-actions { display: flex; gap: var(--space-3); justify-content: flex-end; padding-top: var(--space-3); border-top: 1px solid var(--border-light); }
.og-btn { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-md); padding: 7px 16px; cursor: pointer; }
.og-layout { display: grid; grid-template-columns: minmax(280px, 340px) minmax(0, 1fr); gap: var(--space-4); align-items: start; }
.og-section-hint { margin: 0 0 var(--space-3); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.6; }
.og-orgs { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--space-2); }
.og-org { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: var(--space-3); cursor: pointer; transition: border-color .12s, background .12s; }
.og-org:hover { border-color: var(--primary-200); background: var(--primary-50); }
.og-org.is-active { border-color: var(--color-primary); background: var(--primary-50); box-shadow: inset 3px 0 0 var(--color-primary); }
.og-org__top { display: flex; justify-content: space-between; align-items: center; gap: var(--space-2); }
.og-org__name { font-weight: 600; }
.og-org__meta { font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 4px; line-height: 1.5; }
.og-empty, .og-hint { color: var(--text-tertiary); padding: var(--space-5); text-align: center; line-height: 1.65; }
.og-selected-summary { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-4); padding: var(--space-3); border: 1px solid var(--primary-100); border-radius: var(--radius-md); background: var(--primary-50); }
.og-selected-summary > div { display: grid; gap: 3px; }
.og-selected-summary span, .og-selected-summary small { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.og-selected-summary strong { color: var(--text-primary); }
.og-subhead { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-3); margin: 0 0 var(--space-3); padding-bottom: var(--space-3); border-bottom: 1px solid var(--border-light); }
.og-subhead > div { display: grid; gap: 2px; }
.og-subhead h4 { margin: 0; font-size: var(--font-size-md); }
.og-subhead small { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.og-inline { display: grid; grid-template-columns: minmax(160px, 1fr) minmax(140px, .8fr) minmax(140px, .8fr) auto; gap: var(--space-2); margin-bottom: var(--space-3); align-items: end; }
.og-inline__title { grid-column: 1 / -1; color: var(--text-primary); font-size: var(--font-size-sm); font-weight: 700; }
@media (max-width: 960px) { .sa-grid--metrics, .og-grid, .og-layout { grid-template-columns: 1fr; } .og-field--wide { grid-column: span 1; } .og-inline { grid-template-columns: 1fr; } }
@media (max-width: 640px) { .og-actions { align-items: stretch; flex-direction: column-reverse; } .og-actions > * { width: 100%; } .og-selected-summary, .og-subhead { flex-direction: column; } }
@import '@/styles/module-page.css';
</style>
