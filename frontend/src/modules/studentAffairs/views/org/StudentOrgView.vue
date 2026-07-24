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
      <div class="sa-toolbar">
        <div class="sa-grid sa-grid--metrics">
          <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
        </div>
        <AppPermissionButton :allowed="canBtn('studentAffairs.org.manage')" code="studentAffairs.org.manage" :loading="saving" @click="openForm">建组织</AppPermissionButton>
      </div>

      <AppSectionCard v-if="formVisible" title="新建学生组织">
        <div class="og-grid">
          <label class="og-field"><span>组织名称 *</span><AppTextInput v-model="form.orgName" /></label>
          <label class="og-field"><span>类型</span>
            <AppSelect v-model="form.orgType" :options="TYPE_OPTIONS" placeholder="" /></label>
          <label class="og-field"><span>级别</span>
            <AppSelect v-model="form.level" :options="LEVEL_OPTIONS" placeholder="" /></label>
          <label class="og-field"><span>指导老师</span><AppTextInput v-model="form.advisorName" /></label>
        </div>
        <p v-if="form.error" class="og-error">{{ form.error }}</p>
        <div class="og-actions">
          <button type="button" class="og-btn" @click="formVisible = false">取消</button>
          <AppPermissionButton :allowed="canBtn('studentAffairs.org.manage')" code="studentAffairs.org.manage" :loading="saving" @click="save">保存</AppPermissionButton>
        </div>
      </AppSectionCard>

      <div class="og-layout">
        <AppSectionCard title="组织列表" class="og-list">
          <ul class="og-orgs">
            <li v-for="o in items" :key="o.orgId" class="og-org" :class="{ 'is-active': sel && sel.orgId === o.orgId }" @click="select(o)">
              <div class="og-org__top"><span class="og-org__name">{{ o.orgName }}</span>
                <StatusTag :type="o.status==='ACTIVE' ? 'success' : 'default'" :label="o.status==='ACTIVE' ? '在运营' : '停用'" dot /></div>
              <div class="og-org__meta">{{ o.levelLabel }} · {{ o.orgTypeLabel }} · {{ o.advisorName || '无指导老师' }}</div>
            </li>
            <li v-if="!items.length" class="og-empty">暂无学生组织，点右上「建组织」</li>
          </ul>
        </AppSectionCard>

        <AppSectionCard :title="sel ? (sel.orgName + ' · 在任成员') : '组织详情'" class="og-detail">
          <p v-if="!sel" class="og-hint">从左侧选择一个组织查看/管理在任成员。</p>
          <template v-else>
            <div class="og-subhead">
              <h4>在任成员（{{ positions.length }}）</h4>
              <AppPermissionButton :allowed="canBtn('studentAffairs.org.manage')" v-if="sel.status==='ACTIVE'" code="studentAffairs.org.manage" size="sm" @click="openAppoint">任命</AppPermissionButton>
            </div>
            <div v-if="apForm.visible" class="og-inline">
              <AppStudentPicker v-model="apForm.studentId" placeholder="按姓名 / 学号搜索学生" />
              <AppTextInput v-model="apForm.position" placeholder="职务 如 主席/部长" />
              <AppTextInput v-model="apForm.termCode" placeholder="任期 如 2025-2026" />
              <AppPermissionButton :allowed="canBtn('studentAffairs.org.manage')" code="studentAffairs.org.manage" size="sm" @click="appoint">任命</AppPermissionButton>
            </div>
            <DataTable v-if="positions.length" :columns="positionColumns" :rows="positions" row-key="positionId">
              <template #cell-student="{ row }">{{ row.realName || ('#'+row.studentId) }}</template>
              <template #cell-position="{ row }">{{ row.position }}</template>
              <template #cell-term="{ row }">{{ row.termCode || '—' }}</template>
              <template #cell-actions="{ row }">
                <AppPermissionButton :allowed="canBtn('studentAffairs.org.manage')" code="studentAffairs.org.manage" size="sm" variant="secondary" danger @click="dismiss(row)">卸任</AppPermissionButton>
              </template>
            </DataTable>
            <p v-else class="sa-empty">暂无在任成员</p>
          </template>
        </AppSectionCard>
      </div>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import {
  AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSectionCard, AppSelect,
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
    AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSectionCard, AppSelect,
    StatusTag: AppStatusTag, AppStudentPicker, AppTextInput, DataTable
  },
  data() {
    return {
      positionColumns: POSITION_COLUMNS,
      loading: true, saving: false, errorMessage: '', items: [], TYPES,
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
      const res = await studentAffairsApi.getOrganizations({ pageSize: 300 })
      if (res.code === 0 && res.data) this.items = res.data.items || []
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
      const res = await studentAffairsApi.dismissOrgPosition(p.positionId)
      if (res.code === 0) { toast.success('已卸任'); this.select(this.sel) } else toast.error(res.message || '卸任失败')
    }
  }
}
</script>

<style scoped>
.sa-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); margin-bottom: var(--space-4); flex-wrap: wrap; }
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: var(--space-4); flex: 1; min-width: 300px; }
.og-grid { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: var(--space-3); margin-bottom: var(--space-3); }
.og-field { display: flex; flex-direction: column; gap: 4px; font-size: var(--font-size-sm); }
.og-input { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 7px 10px; }
.og-error { color: var(--danger-500,#dc2626); font-size: var(--font-size-sm); }
.og-actions { display: flex; gap: var(--space-3); justify-content: flex-end; }
.og-btn { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-md); padding: 7px 16px; cursor: pointer; }
.og-layout { display: grid; grid-template-columns: 340px 1fr; gap: var(--space-4); }
.og-orgs { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--space-2); }
.og-org { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: var(--space-3); cursor: pointer; }
.og-org.is-active { border-color: var(--color-primary); box-shadow: 0 0 0 2px rgba(37,99,235,0.12); }
.og-org__top { display: flex; justify-content: space-between; align-items: center; }
.og-org__name { font-weight: 600; }
.og-org__meta { font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 4px; }
.og-empty, .og-hint { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.og-subhead { display: flex; justify-content: space-between; align-items: center; margin: 0 0 var(--space-2); }
.og-subhead h4 { margin: 0; font-size: var(--font-size-md); }
.og-inline { display: flex; gap: var(--space-2); margin-bottom: var(--space-2); flex-wrap: wrap; }
.og-inline > * { flex: 1 1 180px; min-width: 180px; }
.og-inline > .app-perm-btn { flex: 0 0 auto; min-width: 0; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-3); text-align: center; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } .og-grid, .og-layout { grid-template-columns: 1fr; } }
@import '@/styles/module-page.css';
</style>
