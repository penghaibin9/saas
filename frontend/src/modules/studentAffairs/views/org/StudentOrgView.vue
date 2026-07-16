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
        <AppPermissionButton code="studentAffairs.org.manage" :loading="saving" @click="openForm">建组织</AppPermissionButton>
      </div>

      <AppSectionCard v-if="formVisible" title="新建学生组织">
        <div class="og-grid">
          <label class="og-field"><span>组织名称 *</span><input v-model.trim="form.orgName" class="og-input" /></label>
          <label class="og-field"><span>类型</span>
            <select v-model="form.orgType" class="og-input">
              <option v-for="(l,k) in TYPES" :key="k" :value="k">{{ l }}</option>
            </select></label>
          <label class="og-field"><span>级别</span>
            <select v-model="form.level" class="og-input"><option value="SCHOOL">校级</option><option value="COLLEGE">院级</option></select></label>
          <label class="og-field"><span>指导老师</span><input v-model.trim="form.advisorName" class="og-input" /></label>
        </div>
        <p v-if="form.error" class="og-error">{{ form.error }}</p>
        <div class="og-actions">
          <button type="button" class="og-btn" @click="formVisible = false">取消</button>
          <AppPermissionButton code="studentAffairs.org.manage" :loading="saving" @click="save">保存</AppPermissionButton>
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
          <AppPagination v-model:page="pagination.page" v-model:pageSize="pagination.pageSize"
                         :total="pagination.total" @change="load" />
        </AppSectionCard>

        <AppSectionCard :title="sel ? (sel.orgName + ' · 在任成员') : '组织详情'" class="og-detail">
          <p v-if="!sel" class="og-hint">从左侧选择一个组织查看/管理在任成员。</p>
          <template v-else>
            <div class="og-subhead">
              <h4>在任成员（{{ positions.length }}）</h4>
              <AppPermissionButton v-if="sel.status==='ACTIVE'" code="studentAffairs.org.manage" size="sm" @click="openAppoint">任命</AppPermissionButton>
            </div>
            <div v-if="apForm.visible" class="og-inline">
              <input v-model.number="apForm.studentId" type="number" class="og-input" placeholder="学生主档ID" />
              <input v-model.trim="apForm.position" class="og-input" placeholder="职务 如 主席/部长" />
              <input v-model.trim="apForm.termCode" class="og-input" placeholder="任期 如 2025-2026" />
              <button type="button" class="og-btn" @click="appoint">任命</button>
            </div>
            <table class="sa-table">
              <thead><tr><th>学生</th><th>职务</th><th>任期</th><th>操作</th></tr></thead>
              <tbody>
                <tr v-for="p in positions" :key="p.positionId">
                  <td>{{ p.realName || ('#'+p.studentId) }}</td><td>{{ p.position }}</td><td>{{ p.termCode || '—' }}</td>
                  <td><AppPermissionButton code="studentAffairs.org.manage" size="sm" variant="secondary" danger @click="dismiss(p)">卸任</AppPermissionButton></td>
                </tr>
                <tr v-if="!positions.length"><td colspan="4" class="sa-empty">暂无在任成员</td></tr>
              </tbody>
            </table>
          </template>
        </AppSectionCard>
      </div>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppMetricCard, AppPageShell, AppPagination, AppPermissionButton, AppSectionCard, AppStatusTag } from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

const TYPES = { STUDENT_UNION: '学生会', SOCIETY_FEDERATION: '社团联合会', SELF_GOV: '自律委员会', OTHER: '其他组织' }

export default {
  name: 'StudentOrgView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppPagination, AppPermissionButton, AppSectionCard, StatusTag: AppStatusTag },
  data() {
    return {
      loading: true, saving: false, errorMessage: '', items: [], TYPES, total: 0, byLevel: {},
      pagination: { page: 1, pageSize: 20, total: 0 },
      formVisible: false, form: { orgName: '', orgType: 'STUDENT_UNION', level: 'SCHOOL', advisorName: '', error: '' },
      sel: null, positions: [], apForm: { visible: false, studentId: null, position: '', termCode: '' }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      return [
        { key: 't', label: '组织总数', value: this.total, accent: 'primary' },
        { key: 's', label: '校级', value: this.byLevel.SCHOOL || 0, accent: 'success' },
        { key: 'c', label: '院级', value: this.byLevel.COLLEGE || 0, accent: 'info' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      // 指标基于全量聚合（不分页）；列表按真实分页取（后端 /student-affairs/organizations 已支持 page/pageSize）
      const [all, filtered] = await Promise.all([
        studentAffairsApi.getOrganizations({ pageSize: 500 }),
        studentAffairsApi.getOrganizations({ page: this.pagination.page, pageSize: this.pagination.pageSize })
      ])
      if (all.code === 0 && all.data) {
        const allItems = all.data.items || []
        this.total = all.data.total != null ? all.data.total : allItems.length
        this.byLevel = allItems.reduce((m, x) => { m[x.level] = (m[x.level] || 0) + 1; return m }, {})
      } else {
        this.errorMessage = all.message || '学生组织加载失败'
      }
      if (filtered.code === 0 && filtered.data) {
        this.items = filtered.data.items || []
        this.pagination.total = filtered.data.total != null ? filtered.data.total : this.items.length
      } else if (!this.errorMessage) {
        this.errorMessage = filtered.message || '学生组织加载失败'
      }
      this.loading = false
    },
    openForm() { this.form = { orgName: '', orgType: 'STUDENT_UNION', level: 'SCHOOL', advisorName: '', error: '' }; this.formVisible = true },
    async save() {
      const m = this.form
      if (!m.orgName) { m.error = '组织名称必填'; return }
      m.error = ''; this.saving = true
      const res = await studentAffairsApi.createOrganization({ orgName: m.orgName, orgType: m.orgType, level: m.level, advisorName: m.advisorName || undefined })
      this.saving = false
      if (res.code === 0) { toast.success('已创建'); this.formVisible = false; this.load() } else m.error = res.message || '创建失败'
    },
    async select(o) {
      this.sel = o; this.positions = []; this.apForm.visible = false
      const res = await studentAffairsApi.getOrgPositions(o.orgId)
      if (res.code === 0 && res.data) this.positions = res.data.items || []
    },
    openAppoint() { this.apForm = { visible: true, studentId: null, position: '', termCode: '' } },
    async appoint() {
      const f = this.apForm
      if (!f.studentId || !f.position) { toast.error('学生ID与职务必填'); return }
      const res = await studentAffairsApi.appointOrgPosition(this.sel.orgId, { studentId: Number(f.studentId), position: f.position, termCode: f.termCode || undefined })
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
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-2) var(--space-3); text-align: left; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-3); text-align: center; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } .og-grid, .og-layout { grid-template-columns: 1fr; } }
</style>
