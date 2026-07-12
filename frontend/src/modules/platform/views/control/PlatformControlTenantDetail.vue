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
            <AppButton variant="ghost" @click="changePkg">变更套餐</AppButton>
            <AppButton variant="warning" @click="act('expire')">标记到期（只读）</AppButton>
          </div>
        </AppCard>
        <AppCard class="ptd__panel">
          <AppSectionHeader title="容量与用量" />
          <ul class="ptd__kv">
            <li><span>学生数</span><b>{{ tenant.studentCount }} / {{ tenant.maxStudents }}</b></li>
            <li><span>账号数</span><b>{{ tenant.userCount }} / {{ tenant.maxUsers }}</b></li>
            <li><span>存储</span><b>{{ tenant.usedStorageMb }} / {{ tenant.storageLimitMb }} MB</b></li>
          </ul>
          <div class="ptd__quota">
            <label class="ptd__field"><span>学生上限</span><input v-model.number="quota.maxStudents" type="number" class="ptd__input" /></label>
            <label class="ptd__field"><span>账号上限</span><input v-model.number="quota.maxUsers" type="number" class="ptd__input" /></label>
            <label class="ptd__field"><span>存储上限(MB)</span><input v-model.number="quota.storageLimitMb" type="number" class="ptd__input" /></label>
            <AppButton variant="primary" @click="saveQuota">保存容量</AppButton>
          </div>
        </AppCard>
      </div>

      <AppCard v-else-if="tab === 'features'" class="ptd__panel">
        <AppSectionHeader title="功能开关（保存后业务端即刻生效：关闭的功能接口返回 403）" />
        <div class="ptd__switches">
          <label v-for="k in featureKeys" :key="k" class="ptd__switch">
            <input v-model="features[k]" type="checkbox" />
            <span>{{ featureLabels[k] || k }}</span>
          </label>
        </div>
        <div class="ptd__ops"><AppButton variant="primary" :loading="saving" @click="saveFeatures">保存功能开关</AppButton></div>
      </AppCard>

      <AppCard v-else-if="tab === 'studentPortal'" class="ptd__panel">
        <AppSectionHeader title="学生 PC 门户配置（保存后写审计；关闭的模块/功能，学生端菜单隐藏且后端 403）" />
        <StudentPortalConfigPanel :tenant-id="tid" />
      </AppCard>

      <div v-else-if="tab === 'rules'" class="ptd__rules">
        <AppCard v-for="(kv, group) in rules" :key="group" class="ptd__panel">
          <AppSectionHeader :title="ruleGroupLabels[group] || group" />
          <div class="ptd__rule-grid">
            <label v-for="(v, k) in kv" :key="k" class="ptd__field ptd__field--rule">
              <span :title="k">{{ ruleLabels[k] || k }}</span>
              <input v-if="typeof v === 'boolean'" v-model="kv[k]" type="checkbox" class="ptd__check" />
              <input v-else-if="typeof v === 'number'" v-model.number="kv[k]" type="number" class="ptd__input ptd__input--sm" />
              <input v-else v-model="kv[k]" class="ptd__input" />
            </label>
          </div>
        </AppCard>
        <div class="ptd__ops"><AppButton variant="primary" :loading="saving" @click="saveRules">保存全部规则（即刻生效）</AppButton></div>
      </div>

      <AppCard v-else-if="tab === 'workflows'" class="ptd__panel">
        <AppSectionHeader title="审批流配置（是否需要审批 / 审批角色 / 时限）" />
        <DataTable :columns="wfColumns" :rows="workflowRows" row-key="workflowCode">
          <template #cell-enabled="{ row }">
            <input v-model="row.enabled" type="checkbox" @change="saveWorkflow(row)" />
          </template>
          <template #cell-needApproval="{ row }">
            <input v-model="row.needApproval" type="checkbox" @change="saveWorkflow(row)" />
          </template>
          <template #cell-approverRoleCodes="{ row }">
            <span class="ptd__roles">{{ (row.approverRoleCodes || []).join(' / ') || '—' }}</span>
          </template>
          <template #cell-timeoutHours="{ row }">
            <input v-model.number="row.timeoutHours" type="number" class="ptd__input ptd__input--sm" @change="saveWorkflow(row)" />
          </template>
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
        <div class="ptd__ops"><AppButton variant="primary" :loading="saving" @click="saveBrand">保存品牌配置</AppButton></div>
      </AppCard>

      <AppCard v-else-if="tab === 'users'" class="ptd__panel">
        <AppSectionHeader title="学校账号（创建管理员 / 停用 / 重置密码）" />
        <div class="ptd__user-create">
          <input v-model.trim="newUser.loginName" class="ptd__input" placeholder="登录名" />
          <input v-model.trim="newUser.realName" class="ptd__input" placeholder="姓名" />
          <AppButton variant="primary" @click="createUser">创建学校管理员</AppButton>
        </div>
        <div v-if="oneTimeSecret" class="ptd__secret">
          <span>{{ oneTimeSecret }}（仅本次显示，请立即转交；刷新后不可再查看）</span>
          <AppButton variant="ghost" @click="oneTimeSecret = ''">我已记录</AppButton>
        </div>
        <DataTable :columns="userColumns" :rows="users" row-key="userId">
          <template #cell-status="{ row }">
            <StatusTag :type="row.status === 'ACTIVE' ? 'success' : 'default'" :label="row.status === 'ACTIVE' ? '启用' : '停用'" />
          </template>
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
    </template>
    <ErrorState v-else :text="error || '租户不存在'" @retry="load" />
  </ModulePageShell>
</template>

<script>
import { AppButton, AppCard, AppSectionHeader } from '@/components/ui'
import { DataTable, EmptyState, ErrorState, LoadingState, ModulePageShell, StatusTag } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import StudentPortalConfigPanel from '@/modules/platform/components/StudentPortalConfigPanel.vue'
import { toast } from '@/utils/toast'

const STATUS = { trial: ['warning', '试用中'], active: ['success', '正式'], expired: ['danger', '已到期'], disabled: ['default', '已停用'] }

export default {
  name: 'PlatformControlTenantDetail',
  components: { AppButton, AppCard, AppSectionHeader, DataTable, EmptyState, ErrorState, LoadingState, ModulePageShell, StatusTag, StudentPortalConfigPanel },
  data() {
    return {
      loading: true,
      saving: false,
      error: '',
      tenant: null,
      tab: 'info',
      tabs: [
        { key: 'info', label: '运营与容量' },
        { key: 'features', label: '功能开关' },
        { key: 'rules', label: '规则中心' },
        { key: 'workflows', label: '审批流' },
        { key: 'brand', label: '品牌' },
        { key: 'users', label: '账号' },
        { key: 'studentPortal', label: '学生PC门户' }
      ],
      quota: { maxStudents: 0, maxUsers: 0, storageLimitMb: 0 },
      features: {},
      featureKeys: [],
      featureLabels: {
        studentProfile: '学生主档', student360: '学生360', orientation: '数字迎新', campusService: '在校服务',
        approval: '审批中心', todoMessage: '待办与消息', fileUpload: '文件上传', studentImport: '学生导入',
        studentExport: '学生导出', auditLog: '审计日志', graduation: '毕业设计', internship: '岗位实习',
        employment: '就业服务', riskWarning: '风险预警', miniapp: '小程序端', customBrand: '自定义品牌',
        workflowConfig: '流程配置', dataExport: '数据导出', apiAccess: 'API 访问'
      },
      rules: null,
      ruleGroupLabels: {
        student: '学生档案规则', approval: '审批规则', import: '导入规则', export: '导出规则',
        file: '文件规则', risk: '风险预警规则', message: '消息提醒规则', security: '安全规则', trial: '试用与到期规则'
      },
      ruleLabels: {
        rejectReasonRequired: '驳回必填原因', rejectReasonMinLength: '驳回原因最少字数',
        exportNeedPurpose: '导出必填用途', exportPurposeMinLength: '导出用途最少字数',
        importMaxRows: '单次导入最大行数', uploadMaxSizeMb: '上传大小上限(MB)',
        exportWatermarkEnabled: '导出水印', exportPhoneMasked: '导出手机号脱敏', exportIdCardMasked: '导出身份证脱敏',
        loginFailMaxTimes: '登录失败锁定次数', loginFailLockMinutes: '锁定分钟数'
      },
      workflowRows: [],
      wfColumns: [
        { key: 'workflowName', title: '审批流', width: '180px' },
        { key: 'enabled', title: '启用', width: '60px', align: 'center' },
        { key: 'needApproval', title: '需审批', width: '70px', align: 'center' },
        { key: 'approverRoleCodes', title: '审批角色', width: '200px' },
        { key: 'timeoutHours', title: '时限(小时)', width: '110px' }
      ],
      brand: {},
      brandFields: [
        { key: 'platformName', label: '平台名称（顶栏）' },
        { key: 'topBarName', label: '顶栏主标题' },
        { key: 'watermarkText', label: '页面水印文案' },
        { key: 'primaryColor', label: '品牌主色', ph: '#2563EB' },
        { key: 'contactPhone', label: '试用/续费咨询电话', ph: '13549666867' },
        { key: 'copyrightText', label: '版权文案' }
      ],
      users: [],
      userColumns: [
        { key: 'loginName', title: '登录名', width: '140px' },
        { key: 'realName', title: '姓名', width: '110px' },
        { key: 'userType', title: '类型', width: '130px' },
        { key: 'status', title: '状态', width: '80px' },
        { key: 'lastLoginAt', title: '最近登录', width: '150px' },
        { key: 'actions', title: '操作', width: '220px' }
      ],
      newUser: { loginName: '', realName: '' },
      oneTimeSecret: ''
    }
  },
  computed: {
    tid() {
      return this.$route.params.tenantId || this.$route.params.id
    },
    pkgLabel() {
      return this.tenant ? this.tenant.packageName + ' · 到期 ' + this.fmt(this.tenant.expireAt) : ''
    },
    statusType() {
      return (STATUS[this.tenant.status] || ['default'])[0]
    },
    statusLabel() {
      return (STATUS[this.tenant.status] || ['default', this.tenant.status])[1]
    }
  },
  created() {
    const t = this.$route.query.tab
    if (t && this.tabs.some((x) => x.key === t)) this.tab = t
    this.load()
  },
  methods: {
    fmt(v) {
      return v ? String(v).replace('T', ' ').slice(0, 16) : ''
    },
    async load() {
      this.loading = true
      const res = await platformControlApi.getTenant(this.tid)
      this.loading = false
      if (res.code !== 0) {
        this.error = res.message
        return
      }
      this.tenant = res.data
      this.quota = {
        maxStudents: res.data.maxStudents,
        maxUsers: res.data.maxUsers,
        storageLimitMb: res.data.storageLimitMb
      }
      this.loadTab(this.tab)
    },
    switchTab(key) {
      this.tab = key
      this.$router.replace({ query: { ...this.$route.query, tab: key } })
      this.loadTab(key)
    },
    async loadTab(key) {
      if (key === 'features' && !this.featureKeys.length) {
        const res = await platformControlApi.getFeatures(this.tid)
        if (res.code === 0) {
          this.features = res.data.features
          this.featureKeys = res.data.featureKeys || Object.keys(res.data.features)
        } else {
          toast.error(res.message)
        }
      } else if (key === 'rules' && !this.rules) {
        const res = await platformControlApi.getRules(this.tid)
        if (res.code === 0) this.rules = res.data.rules
        else toast.error(res.message)
      } else if (key === 'workflows' && !this.workflowRows.length) {
        const res = await platformControlApi.getWorkflows(this.tid)
        if (res.code === 0) this.workflowRows = Object.values(res.data.workflows)
        else toast.error(res.message)
      } else if (key === 'brand' && !Object.keys(this.brand).length) {
        const res = await platformControlApi.getBrand(this.tid)
        if (res.code === 0) this.brand = res.data.brand
        else toast.error(res.message)
      } else if (key === 'users') {
        const res = await platformControlApi.listUsers(this.tid)
        if (res.code === 0) this.users = res.data.list
        else toast.error(res.message)
      }
    },
    async act(action, body = {}) {
      const res = await platformControlApi.tenantAction(this.tid, action, body)
      if (res.code === 0) {
        toast.success(res.message === 'ok' ? '操作成功' : res.message)
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async changePkg() {
      const codes = ['trial', 'basic', 'standard', 'professional', 'private']
      const cur = codes.indexOf(this.tenant.packageCode)
      const next = codes[(cur + 1) % codes.length]
      const res = await platformControlApi.tenantAction(this.tid, 'change-package', { packageCode: next })
      if (res.code === 0) {
        toast.success(res.message)
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async saveQuota() {
      const res = await platformControlApi.tenantAction(this.tid, 'quota', { ...this.quota })
      if (res.code === 0) {
        toast.success('容量已更新')
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async saveFeatures() {
      this.saving = true
      const res = await platformControlApi.putFeatures(this.tid, { ...this.features })
      this.saving = false
      if (res.code === 0) toast.success('功能开关已保存，业务端即刻生效')
      else toast.error(res.message)
    },
    async saveRules() {
      this.saving = true
      const res = await platformControlApi.putRules(this.tid, this.rules)
      this.saving = false
      if (res.code === 0) toast.success('规则已保存，后端校验即刻按新规则执行')
      else toast.error(res.message)
    },
    async saveWorkflow(row) {
      const res = await platformControlApi.putWorkflow(this.tid, row.workflowCode, {
        enabled: row.enabled,
        needApproval: row.needApproval,
        timeoutHours: row.timeoutHours
      })
      if (res.code === 0) toast.success('「' + row.workflowName + '」已更新')
      else toast.error(res.message)
    },
    async saveBrand() {
      this.saving = true
      const res = await platformControlApi.putBrand(this.tid, { ...this.brand })
      this.saving = false
      if (res.code === 0) toast.success('品牌配置已保存')
      else toast.error(res.message)
    },
    async createUser() {
      if (!this.newUser.loginName || !this.newUser.realName) {
        toast.error('登录名与姓名必填')
        return
      }
      const res = await platformControlApi.createUser(this.tid, { ...this.newUser })
      if (res.code === 0) {
        this.oneTimeSecret = '账号 ' + res.data.loginName + ' 初始密码：' + res.data.initialPassword
        this.newUser = { loginName: '', realName: '' }
        this.loadTab('users')
      } else {
        toast.error(res.message)
      }
    },
    async userAct(row, action) {
      const res = await platformControlApi.userAction(row.userId, action)
      if (res.code === 0) {
        if (action === 'reset-password' && res.data.newPassword) {
          this.oneTimeSecret = '账号 ' + row.loginName + ' 新密码：' + res.data.newPassword
        } else {
          toast.success('操作成功')
        }
        this.loadTab('users')
      } else {
        toast.error(res.message)
      }
    }
  }
}
</script>

<style scoped>
.ptd__tabs {
  display: flex;
  gap: var(--space-1);
  flex-wrap: wrap;
}
.ptd__tab {
  height: 34px;
  padding: 0 14px;
  border: 1px solid var(--card-b);
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.75);
  color: var(--t2);
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
}
.ptd__tab.is-active {
  background: var(--btn-p-bg);
  border-color: transparent;
  color: #fff;
  font-weight: var(--font-weight-semibold);
}
.ptd__cols {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: var(--space-3);
}
.ptd__panel {
  padding: var(--space-4);
}
.ptd__kv {
  list-style: none;
  margin: var(--space-2) 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.ptd__kv li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.ptd__kv b {
  color: var(--t1);
}
.ptd__ops {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-top: var(--space-3);
}
.ptd__ops--row {
  margin-top: 0;
}
.ptd__quota {
  display: flex;
  align-items: flex-end;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-top: var(--space-3);
}
.ptd__field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.ptd__field--rule {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}
.ptd__input {
  height: 34px;
  padding: 0 10px;
  border: 1px solid var(--card-b);
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.85);
  color: var(--t1);
  font-size: 13px;
  font-family: inherit;
  min-width: 0;
}
.ptd__input:focus {
  outline: none;
  border-color: var(--glow);
}
.ptd__input--sm {
  width: 90px;
}
.ptd__check {
  width: 16px;
  height: 16px;
}
.ptd__switches {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: var(--space-2);
  margin-top: var(--space-3);
}
.ptd__switch {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--t2);
}
.ptd__rules {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.ptd__rule-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: var(--space-2) var(--space-4);
  margin-top: var(--space-3);
}
.ptd__roles {
  font-size: 12px;
  color: var(--text-secondary);
}
.ptd__brand {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: var(--space-3);
  margin-top: var(--space-3);
}
.ptd__user-create {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin: var(--space-3) 0;
}
.ptd__secret {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-radius: 9px;
  background: var(--warn-l);
  color: var(--warning-700);
  font-size: var(--font-size-sm);
  margin-bottom: var(--space-3);
}
</style>
