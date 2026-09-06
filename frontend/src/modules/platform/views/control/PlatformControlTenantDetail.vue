<template>
  <ModulePageShell :title="tenant ? tenant.tenantName : '租户配置'" :subtitle="tenant ? tenant.tenantCode + ' · ' + pkgLabel : ''" role-name="平台超级管理员" data-scope-name="全平台（跨租户）">
    <template #actions>
      <AppButton variant="ghost" @click="$router.push('/admin/platform/tenants')">← 返回列表</AppButton>
    </template>
    <LoadingState v-if="loading" text="正在加载租户配置…" />
    <template v-else-if="tenant">
      <div class="ptd__tabs">
        <button v-for="t in tabs" :key="t.key" type="button" class="ptd__tab" :class="{ 'is-active': tab === t.key }" @click="switchTab(t.key)">
          {{ t.label }}
        </button>
      </div>

      <div v-if="tab === 'info'" class="ptd__cols">
        <AppCard class="ptd__panel">
          <AppSectionHeader title="运营状态" />
          <ul class="ptd__kv">
            <li><span>状态</span><StatusTag :type="statusType" :label="statusLabel" /></li>
            <li><span>套餐</span><b>{{ tenant.packageName }}</b></li>
            <li><span>到期时间</span><b>{{ fmt(tenant.expireAt) }}</b></li>
            <li><span>环境</span><b>{{ tenant.environment === 'demo' ? '演示环境' : '生产环境' }}</b></li>
            <li><span>联系人</span><b>{{ (tenant.contactName || '—') + ' ' + (tenant.contactPhone || '') }}</b></li>
            <li><span>地区</span><b>{{ (tenant.province || '—') + ' ' + (tenant.city || '') }}</b></li>
          </ul>
          <div class="ptd__ops">
            <AppButton v-if="tenant.status === 'disabled'" variant="primary" @click="act('enable')">启用</AppButton>
            <AppButton v-else variant="danger" @click="act('disable')">停用</AppButton>
            <AppButton variant="ghost" @click="act('extend-trial', { days: 30 })">延期 30 天</AppButton>
            <AppButton variant="warning" @click="act('expire')">标记到期（只读）</AppButton>
          </div>
        </AppCard>
        <AppCard class="ptd__panel">
          <AppSectionHeader title="容量与用量" />
          <ul class="ptd__kv">
            <li><span>学生数</span><b>{{ tenant.studentCount }} / {{ tenant.maxStudents }}</b></li>
            <li><span>账号数</span><b>{{ tenant.userCount }} / {{ tenant.maxUsers }}</b></li>
            <li><span>商业存储上限</span><b>{{ formatBytes(tenant360.storage?.commercialStorageLimitBytes) }}</b></li>
            <li><span>学校治理配额</span><b>{{ formatBytes(tenant360.storage?.schoolGovernanceQuotaBytes) }}</b></li>
            <li><span>真实占用（文件+预留）</span><b>{{ formatBytes(tenant360.storage?.actualOccupancyBytes) }}</b></li>
            <li v-if="tenant360.effectiveState?.mismatch"><span>状态一致性</span><b class="ptd__danger">租户主状态与租户元数据不一致</b></li>
          </ul>
          <p class="ptd__authority-note">商业套餐与商业额度由已支付订单或受控特批决定；本页不再提供普通直改入口。</p>
        </AppCard>
      </div>

      <AppCard v-else-if="tab === 'features'" class="ptd__panel">
        <AppSectionHeader title="商业授权（只读对账）" />
        <p class="ptd__authority-note">{{ featuresAuthorityHint }}</p>
        <div class="ptd__switches">
          <label v-for="k in featureKeys" :key="k" class="ptd__switch">
            <input :checked="Boolean(features[k])" type="checkbox" disabled />
            <span>{{ featureLabels[k] || '待命名功能' }}</span>
          </label>
        </div>
      </AppCard>

      <AppCard v-else-if="tab === 'studentPortal'" class="ptd__panel">
        <AppSectionHeader title="学生电脑门户配置（保存后写审计；关闭的模块或功能，学生端菜单隐藏且后端拒绝访问）" />
        <StudentPortalConfigPanel :tenant-id="tid" />
      </AppCard>

      <div v-else-if="tab === 'rules'" class="ptd__rules">
        <AppCard v-for="(kv, group) in rules" :key="group" class="ptd__panel">
          <AppSectionHeader :title="ruleGroupLabels[group] || '其他规则'" />
          <div class="ptd__rule-grid">
            <label v-for="(v, k) in kv" :key="k" class="ptd__field ptd__field--rule">
              <span>{{ ruleLabels[k] || '待命名规则项' }}</span>
              <input v-if="typeof v === 'boolean'" v-model="kv[k]" type="checkbox" class="ptd__check" />
              <input v-else-if="typeof v === 'number'" v-model.number="kv[k]" type="number" class="ptd__input ptd__input--sm" />
              <input v-else v-model="kv[k]" class="ptd__input" />
            </label>
          </div>
        </AppCard>
        <div class="ptd__ops"><AppButton variant="primary" :loading="saving" @click="saveRules">保存全部规则（版本 {{ rulesVersion }}）</AppButton></div>
      </div>

      <AppCard v-else-if="tab === 'workflows'" class="ptd__panel">
        <AppSectionHeader title="审批流运行定义（只读）" />
        <p class="ptd__authority-note">WorkflowDefinition 是唯一运行真值；历史 WORKFLOWS JSON 仅用于漂移对账，请在学校系统管理的流程治理工作区修改正式定义。</p>
        <DataTable :columns="wfColumns" :rows="workflowRows" row-key="workflowCode">
          <template #cell-enabled="{ row }"><input :checked="Boolean(row.enabled)" type="checkbox" disabled /></template>
          <template #cell-needApproval="{ row }"><input :checked="Boolean(row.needApproval)" type="checkbox" disabled /></template>
          <template #cell-approverRoleCodes="{ row }"><span class="ptd__roles">{{ roleLabels(row.approverRoleCodes) }}</span></template>
          <template #cell-timeoutHours="{ row }"><span>{{ row.timeoutHours || '—' }}</span></template>
        </DataTable>
      </AppCard>

      <AppCard v-else-if="tab === 'brand'" class="ptd__panel">
        <AppSectionHeader title="品牌与展示（学校端顶栏 / 水印 / 主色 / 试用咨询电话）" />
        <div class="ptd__brand">
          <label v-for="f in brandFields" :key="f.key" class="ptd__field">
            <span>{{ f.label }}</span>
            <input v-model="brand[f.key]" class="ptd__input" :placeholder="f.ph || ''" />
          </label>
        </div>
        <div class="ptd__ops"><AppButton variant="primary" :loading="saving" @click="saveBrand">保存品牌配置（版本 {{ brandVersion }}）</AppButton></div>
      </AppCard>

      <AppCard v-else-if="tab === 'users'" class="ptd__panel">
        <AppSectionHeader title="学校账号（创建管理员 / 停用 / 重置密码）" />
        <div class="ptd__user-create">
          <input v-model.trim="newUser.loginName" class="ptd__input" placeholder="登录名" />
          <input v-model.trim="newUser.realName" class="ptd__input" placeholder="姓名" />
          <AppButton variant="primary" @click="createUser">创建学校管理员</AppButton>
        </div>
        <div v-if="oneTimeSecret" class="ptd__secret">
          <span>{{ oneTimeSecret }}（仅本次显示，请立即转交；刷新或切换学校后不可再查看）</span>
          <AppButton variant="ghost" @click="oneTimeSecret = ''">我已记录</AppButton>
        </div>
        <DataTable :columns="userColumns" :rows="users" row-key="userId">
          <template #cell-status="{ row }"><StatusTag :type="row.status === 'ACTIVE' ? 'success' : 'default'" :label="row.status === 'ACTIVE' ? '启用' : '停用'" /></template>
          <template #cell-userType="{ row }">{{ platformRoleLabel(row.userType) }}</template>
          <template #cell-lastLoginAt="{ row }">{{ fmt(row.lastLoginAt) || '从未登录' }}</template>
          <template #cell-actions="{ row }">
            <div class="ptd__ops ptd__ops--row">
              <AppButton v-if="row.status !== 'ACTIVE'" variant="ghost" @click="userAct(row, 'enable')">启用</AppButton>
              <AppButton v-else variant="danger" @click="userAct(row, 'disable')">停用</AppButton>
              <AppButton variant="warning" @click="userAct(row, 'reset-password')">重置密码</AppButton>
            </div>
          </template>
        </DataTable>
        <EmptyState v-if="!users.length" text="该学校暂无账号" compact />
      </AppCard>

      <TenantOffboardingPanel v-else-if="tab === 'offboarding'" :tenant-id="tid" :tenant="tenant" :tenant360="tenant360" @changed="load" />
    </template>
    <ErrorState v-else :text="error || '租户不存在'" @retry="load" />
  </ModulePageShell>
</template>

<script>
import { AppButton, AppCard, AppSectionHeader } from '@/components/ui'
import { DataTable, EmptyState, ErrorState, LoadingState, ModulePageShell, StatusTag } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { platformControlHardeningApi } from '@/modules/platform/api/platformControlHardening.api'
import StudentPortalConfigPanel from '@/modules/platform/components/StudentPortalConfigPanel.vue'
import TenantOffboardingPanel from '@/modules/platform/components/TenantOffboardingPanel.vue'
import {
  PLATFORM_FEATURE_LABELS,
  PLATFORM_RULE_GROUP_LABELS,
  PLATFORM_RULE_LABELS,
  platformRoleLabel,
  platformStatusLabel
} from '@/modules/platform/constants/platform-display.constants'
import { toast } from '@/utils/toast'

const STATUS = { trial: ['warning', '试用中'], active: ['success', '正式'], expired: ['danger', '已到期'], disabled: ['default', '已停用'] }

export default {
  name: 'PlatformControlTenantDetail',
  components: { AppButton, AppCard, AppSectionHeader, DataTable, EmptyState, ErrorState, LoadingState, ModulePageShell, StatusTag, StudentPortalConfigPanel, TenantOffboardingPanel },
  data() {
    return {
      loading: true,
      saving: false,
      error: '',
      tenant: null,
      tenant360: {},
      requestEpoch: 0,
      tabRequestEpoch: 0,
      tab: 'info',
      tabs: [
        { key: 'info', label: '运营与容量' }, { key: 'features', label: '商业授权' },
        { key: 'rules', label: '规则中心' }, { key: 'workflows', label: '审批流' },
        { key: 'brand', label: '品牌' }, { key: 'users', label: '账号' },
        { key: 'studentPortal', label: '学生电脑门户' }, { key: 'offboarding', label: '退租与数据销毁' }
      ],
      quota: { maxStudents: 0, maxUsers: 0, storageLimitMb: 0 },
      features: {}, featureKeys: [], featureLabels: PLATFORM_FEATURE_LABELS, featuresMeta: {},
      rules: null, rulesVersion: 0, ruleGroupLabels: PLATFORM_RULE_GROUP_LABELS, ruleLabels: PLATFORM_RULE_LABELS,
      workflowRows: [], workflowMeta: {},
      wfColumns: [
        { key: 'workflowName', title: '审批流', width: '180px' }, { key: 'enabled', title: '启用', width: '60px', align: 'center' },
        { key: 'needApproval', title: '需审批', width: '70px', align: 'center' }, { key: 'approverRoleCodes', title: '审批角色', width: '200px' },
        { key: 'timeoutHours', title: '时限(小时)', width: '110px' }
      ],
      brand: {}, brandVersion: 0,
      brandFields: [
        { key: 'platformName', label: '平台名称（顶栏）' }, { key: 'topBarName', label: '顶栏主标题' },
        { key: 'watermarkText', label: '页面水印文案' }, { key: 'primaryColor', label: '品牌主色', ph: '#2563EB' },
        { key: 'contactPhone', label: '试用/续费咨询电话', ph: '13549666867' }, { key: 'copyrightText', label: '版权文案' }
      ],
      users: [],
      userColumns: [
        { key: 'loginName', title: '登录名', width: '140px' }, { key: 'realName', title: '姓名', width: '110px' },
        { key: 'userType', title: '类型', width: '130px' }, { key: 'status', title: '状态', width: '80px' },
        { key: 'lastLoginAt', title: '最近登录', width: '150px' }, { key: 'actions', title: '操作', width: '220px' }
      ],
      newUser: { loginName: '', realName: '' },
      oneTimeSecret: ''
    }
  },
  computed: {
    tid() { return this.$route.params.tenantId || this.$route.params.id },
    pkgLabel() { return this.tenant ? this.tenant.packageName + ' · 到期 ' + this.fmt(this.tenant.expireAt) : '' },
    statusType() { return (STATUS[this.tenant?.status] || ['default'])[0] },
    statusLabel() { return (STATUS[this.tenant?.status] || ['default', '状态待确认'])[1] },
    featuresAuthorityHint() {
      if (this.featuresMeta.legacyOverrideReadOnly) return '检测到历史授权覆盖：当前仅允许只读对账，不能继续从此页面直接改商业授权。'
      if (this.featuresMeta.authoritySource === 'PAID_ORDER') return '商业授权来自已支付订单；学校启停由学校系统管理单独控制。'
      return '商业授权来自套餐/订单权威；此处只展示，不作为学校功能开关写入口。'
    }
  },
  watch: {
    tid(newTenantId, oldTenantId) {
      if (String(newTenantId || '') === String(oldTenantId || '')) return
      this.resetTenantState()
      const requestedTab = this.$route.query.tab
      this.tab = requestedTab && this.tabs.some((item) => item.key === requestedTab) ? requestedTab : 'info'
      this.load()
    }
  },
  created() {
    const requestedTab = this.$route.query.tab
    if (requestedTab && this.tabs.some((item) => item.key === requestedTab)) this.tab = requestedTab
    this.load()
  },
  methods: {
    fmt(v) { return v ? String(v).replace('T', ' ').slice(0, 16) : '' },
    formatBytes(value) { return value == null ? '未配置' : `${(Number(value || 0) / 1024 / 1024 / 1024).toFixed(2)} 吉字节` },
    platformRoleLabel,
    roleLabels(values) { return (values || []).map((value) => platformRoleLabel(value)).join(' / ') || '—' },
    clearTenantPayload() {
      this.error = ''
      this.tenant = null
      this.tenant360 = {}
      this.saving = false
      this.quota = { maxStudents: 0, maxUsers: 0, storageLimitMb: 0 }
      this.features = {}; this.featureKeys = []; this.featuresMeta = {}
      this.rules = null; this.rulesVersion = 0
      this.workflowRows = []; this.workflowMeta = {}
      this.brand = {}; this.brandVersion = 0
      this.users = []
      this.newUser = { loginName: '', realName: '' }
      this.oneTimeSecret = ''
    },
    resetTenantState() {
      this.requestEpoch += 1
      this.tabRequestEpoch += 1
      this.clearTenantPayload()
      this.loading = true
    },
    async load() {
      const tenantId = String(this.tid || '')
      const epoch = ++this.requestEpoch
      this.tabRequestEpoch += 1
      this.clearTenantPayload()
      this.loading = true
      const res = await platformControlApi.getTenant(tenantId)
      if (epoch !== this.requestEpoch || tenantId !== String(this.tid || '')) return
      this.loading = false
      if (res.code !== 0) {
        this.error = res.message || '租户配置加载失败'
        return
      }
      this.tenant = res.data
      this.tenant360 = res.data.tenant360 || {}
      this.quota = { maxStudents: res.data.maxStudents, maxUsers: res.data.maxUsers, storageLimitMb: res.data.storageLimitMb }
      await this.loadTab(this.tab)
    },
    switchTab(key) {
      this.tab = key
      this.$router.replace({ query: { ...this.$route.query, tab: key } })
      this.loadTab(key)
    },
    async loadTab(key) {
      const tenantId = String(this.tid || '')
      const epoch = ++this.tabRequestEpoch
      const stillCurrent = () => epoch === this.tabRequestEpoch && tenantId === String(this.tid || '')
      if (key === 'features' && !this.featureKeys.length) {
        const res = await platformControlApi.getFeatures(tenantId)
        if (!stillCurrent()) return
        if (res.code === 0) {
          this.features = res.data.features || {}
          this.featureKeys = Object.keys(this.features)
          this.featuresMeta = res.data || {}
        } else toast.error(res.message)
      } else if (key === 'rules' && !this.rules) {
        const res = await platformControlApi.getRules(tenantId)
        if (!stillCurrent()) return
        if (res.code === 0) { this.rules = res.data.rules || {}; this.rulesVersion = Number(res.data.overrideVersion || 0) }
        else toast.error(res.message)
      } else if (key === 'workflows' && !this.workflowRows.length) {
        const res = await platformControlApi.getWorkflows(tenantId)
        if (!stillCurrent()) return
        if (res.code === 0) { this.workflowRows = Object.values(res.data.workflows || {}); this.workflowMeta = res.data || {} }
        else toast.error(res.message)
      } else if (key === 'brand' && !Object.keys(this.brand).length) {
        const res = await platformControlApi.getBrand(tenantId)
        if (!stillCurrent()) return
        if (res.code === 0) { this.brand = res.data.brand || {}; this.brandVersion = Number(res.data.overrideVersion || 0) }
        else toast.error(res.message)
      } else if (key === 'users') {
        const res = await platformControlApi.listUsers(tenantId)
        if (!stillCurrent()) return
        if (res.code === 0) this.users = res.data.list || []
        else toast.error(res.message)
      }
    },
    async governedTransition(action, payload = {}) {
      const reason = window.prompt('请输入本次变更原因（至少 5 个字符）')
      if (!reason || reason.trim().length < 5) return
      const expectedVersion = Number(this.tenant360.version || this.tenant.version || 0)
      const body = { ...payload, reason: reason.trim(), expectedVersion }
      const preview = await platformControlApi.previewTenantTransition(this.tid, action, body)
      if (preview.code !== 0) return toast.error(preview.message)
      const warnings = (preview.data.warnings || []).join('；')
      const fromStatus = platformStatusLabel(preview.data.fromStatus)
      const toStatus = platformStatusLabel(preview.data.toStatus)
      if (!window.confirm(`${fromStatus} → ${toStatus}${warnings ? `\n${warnings}` : ''}\n确认执行？`)) return
      const res = await platformControlApi.applyTenantTransition(this.tid, action, body)
      if (res.code === 0) {
        if (res.data?.cacheRecoveryRequired) toast.warning(res.data.warning || '业务已生效，但权限缓存待恢复')
        else toast.success('变更已生效')
        await this.load()
      } else toast.error(res.message)
    },
    async act(action, body = {}) { return this.governedTransition(action, body) },
    async saveRules() {
      const reason = window.prompt('请输入规则变更原因（至少 5 个字符）')
      if (!reason || reason.trim().length < 5) return
      this.saving = true
      const res = await platformControlHardeningApi.putRules(this.tid, this.rules, this.rulesVersion, reason.trim())
      this.saving = false
      if (res.code === 0) {
        this.rules = res.data.rules || this.rules
        this.rulesVersion = Number(res.data.overrideVersion || this.rulesVersion)
        toast.success('规则已保存')
      } else if (res.bizCode === 'DATA_CONFLICT') {
        toast.error('规则已被其他人修改，请刷新后重试')
      } else toast.error(res.message)
    },
    async saveBrand() {
      const reason = window.prompt('请输入品牌变更原因（至少 5 个字符）')
      if (!reason || reason.trim().length < 5) return
      this.saving = true
      const res = await platformControlHardeningApi.putBrand(this.tid, { ...this.brand }, this.brandVersion, reason.trim())
      this.saving = false
      if (res.code === 0) {
        this.brand = res.data.brand || this.brand
        this.brandVersion = Number(res.data.overrideVersion || this.brandVersion)
        toast.success('品牌配置已保存')
      } else if (res.bizCode === 'DATA_CONFLICT') {
        toast.error('品牌配置已被其他人修改，请刷新后重试')
      } else toast.error(res.message)
    },
    async createUser() {
      if (!this.newUser.loginName || !this.newUser.realName) return toast.error('登录名与姓名必填')
      const res = await platformControlApi.createUser(this.tid, { ...this.newUser })
      if (res.code === 0) {
        this.oneTimeSecret = '账号 ' + res.data.loginName + ' 初始密码：' + res.data.initialPassword
        this.newUser = { loginName: '', realName: '' }
        this.loadTab('users')
      } else toast.error(res.message)
    },
    async userAct(row, action) {
      const res = await platformControlApi.userAction(row.userId, action)
      if (res.code === 0) {
        if (action === 'reset-password' && res.data.newPassword) this.oneTimeSecret = '账号 ' + row.loginName + ' 新密码：' + res.data.newPassword
        else toast.success('操作成功')
        this.loadTab('users')
      } else toast.error(res.message)
    }
  }
}
</script>

<style scoped>
.ptd__tabs{display:flex;gap:var(--space-1);flex-wrap:wrap}.ptd__tab{height:34px;padding:0 14px;border:1px solid var(--card-b);border-radius:9px;background:rgba(255,255,255,.75);color:var(--t2);font-size:13px;font-family:inherit;cursor:pointer}.ptd__tab.is-active{background:var(--btn-p-bg);border-color:transparent;color:#fff;font-weight:var(--font-weight-semibold)}.ptd__cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:var(--space-3)}.ptd__panel{padding:var(--space-4)}.ptd__kv{list-style:none;margin:var(--space-2) 0 0;padding:0;display:flex;flex-direction:column;gap:var(--space-2)}.ptd__kv li{display:flex;align-items:center;justify-content:space-between;font-size:var(--font-size-sm);color:var(--text-secondary)}.ptd__kv b{color:var(--t1)}.ptd__danger{color:var(--danger-600,#b42318)!important}.ptd__ops{display:flex;gap:var(--space-2);flex-wrap:wrap;margin-top:var(--space-3)}.ptd__ops--row{margin-top:0}.ptd__field{display:flex;flex-direction:column;gap:var(--space-1);font-size:var(--font-size-sm);color:var(--text-secondary)}.ptd__field--rule{flex-direction:row;align-items:center;justify-content:space-between;gap:var(--space-2)}.ptd__input{height:34px;padding:0 10px;border:1px solid var(--card-b);border-radius:9px;background:rgba(255,255,255,.85);color:var(--t1);font-size:13px;font-family:inherit;min-width:0}.ptd__input:focus{outline:none;border-color:var(--glow)}.ptd__input--sm{width:90px}.ptd__check{width:16px;height:16px}.ptd__switches{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:var(--space-2);margin-top:var(--space-3)}.ptd__switch{display:flex;align-items:center;gap:var(--space-2);font-size:var(--font-size-sm);color:var(--t2)}.ptd__rules{display:flex;flex-direction:column;gap:var(--space-3)}.ptd__rule-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:var(--space-2) var(--space-4);margin-top:var(--space-3)}.ptd__roles{font-size:12px;color:var(--text-secondary)}.ptd__brand{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:var(--space-3);margin-top:var(--space-3)}.ptd__user-create{display:flex;gap:var(--space-2);flex-wrap:wrap;margin:var(--space-3) 0}.ptd__secret{display:flex;align-items:center;justify-content:space-between;gap:var(--space-2);padding:var(--space-2) var(--space-3);border-radius:9px;background:var(--warn-l);color:var(--warning-700);font-size:var(--font-size-sm);margin-bottom:var(--space-3)}.ptd__authority-note{margin:var(--space-3) 0 0;padding:var(--space-2) var(--space-3);border-radius:9px;background:var(--color-primary-soft);color:var(--text-secondary);font-size:var(--font-size-sm);line-height:1.6}
</style>
