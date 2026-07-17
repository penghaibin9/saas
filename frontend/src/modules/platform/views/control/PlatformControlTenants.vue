<template>
  <ModulePageShell title="租户学校管控" subtitle="开通 / 停用 / 试用 / 到期 / 套餐 / 容量，一站式托管" role-name="平台超级管理员" data-scope-name="全平台（跨租户）">
    <template #actions>
      <AppButton variant="primary" @click="openCreate">+ 开通新学校</AppButton>
    </template>
    <div v-if="pickerHint" class="pct__hint">{{ pickerHint }}（点击行进入该学校的配置页）</div>
    <ModuleToolbar :actions="[]" :hint="`共 ${rows.length} 所学校`">
      <template #left>
        <input v-model.trim="keyword" class="pct__input" placeholder="搜索学校名 / 编码" @keyup.enter="load" />
        <select v-model="status" class="pct__input pct__input--sel" @change="load">
          <option value="">全部状态</option>
          <option value="trial">试用</option>
          <option value="active">正式</option>
          <option value="expired">已到期</option>
          <option value="disabled">已停用</option>
        </select>
        <AppButton @click="load">查询</AppButton>
      </template>
    </ModuleToolbar>
    <LoadingState v-if="loading" text="正在加载租户列表…" />
    <template v-else>
      <DataTable :columns="columns" :rows="rows" row-key="tenantId" row-clickable @row-click="goDetail">
        <template #cell-tenantName="{ row }">
          <div class="pct__name">{{ row.tenantName }}</div>
          <div class="pct__code">{{ row.tenantCode }} · {{ row.environment === 'demo' ? '演示环境' : '生产环境' }}</div>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="statusType(row.status)" :label="statusLabel(row.status)" />
        </template>
        <template #cell-usage="{ row }">
          <span class="pct__usage">{{ row.studentCount }}/{{ row.maxStudents }} 生 · {{ row.userCount }}/{{ row.maxUsers }} 号</span>
        </template>
        <template #cell-expireAt="{ row }">{{ fmt(row.expireAt) }}</template>
        <template #cell-actions="{ row }">
          <div class="pct__ops">
            <AppButton v-if="row.status === 'disabled'" variant="ghost" @click="act(row, 'enable')">启用</AppButton>
            <AppButton v-else variant="danger" @click="act(row, 'disable')">停用</AppButton>
            <AppButton v-if="row.status === 'trial'" variant="ghost" @click="act(row, 'extend-trial', { days: 7 })">延试用7天</AppButton>
            <AppButton v-if="row.status !== 'active'" variant="ghost" @click="convert(row)">转正式</AppButton>
            <AppButton v-if="row.tenantCode === 'demo-school'" variant="warning" @click="act(row, 'reset-demo-data')">重置演示</AppButton>
            <AppButton v-if="row.tenantCode === 'sandbox-school'" variant="warning" @click="resetSandbox(row)">恢复演示数据</AppButton>
          </div>
        </template>
      </DataTable>
      <EmptyState v-if="!rows.length" text="没有符合条件的学校" />
    </template>

    <AppDrawer :visible="createVisible" title="开通新学校" @update:visible="createVisible = $event">
      <div v-if="createResult" class="pct__secret">
        <strong>学校已开通，请立即保存管理员凭据</strong>
        <p>学校编码：<code>{{ createResult.tenantCode }}</code></p>
        <p>管理员账号：<code>{{ createResult.loginName }}</code></p>
        <p>初始密码：<code>{{ createResult.initialPassword }}</code></p>
        <small>密码仅本次显示；管理员首次登录后必须修改。角色模板已经自动初始化。</small>
        <div class="pct__form-ops">
          <AppButton variant="primary" @click="copyCredential">复制凭据</AppButton>
          <AppButton @click="closeCreate">我已保存</AppButton>
        </div>
      </div>
      <div v-else class="pct__form">
        <label class="pct__field"><span>学校编码 *</span><input v-model.trim="form.tenantCode" class="pct__input" placeholder="如 gz-tech（唯一）" /></label>
        <label class="pct__field"><span>学校全称 *</span><input v-model.trim="form.tenantName" class="pct__input" placeholder="如 广州科技职业技术学院" /></label>
        <label class="pct__field"><span>初始套餐</span>
          <select v-model="form.packageCode" class="pct__input">
            <option value="trial">试用版（30 天）</option>
            <option value="basic">基础版</option>
            <option value="standard">标准版</option>
            <option value="professional">专业版</option>
            <option value="private">私有化版</option>
          </select>
        </label>
        <label class="pct__field"><span>环境</span>
          <select v-model="form.environment" class="pct__input">
            <option value="production">生产环境</option>
            <option value="demo">演示环境</option>
          </select>
        </label>
        <label class="pct__field"><span>省 / 市</span>
          <span class="pct__pair">
            <input v-model.trim="form.province" class="pct__input" placeholder="省" />
            <input v-model.trim="form.city" class="pct__input" placeholder="市" />
          </span>
        </label>
        <label class="pct__field"><span>联系人 / 电话</span>
          <span class="pct__pair">
            <input v-model.trim="form.contactName" class="pct__input" placeholder="姓名" />
            <input v-model.trim="form.contactPhone" class="pct__input" placeholder="手机号" />
          </span>
        </label>
        <label class="pct__field"><span>首位学校管理员账号 *</span><input v-model.trim="form.adminLoginName" class="pct__input" placeholder="如 admin（校内唯一）" /></label>
        <label class="pct__field"><span>首位学校管理员姓名 *</span><input v-model.trim="form.adminRealName" class="pct__input" placeholder="如 张老师" /></label>
        <div class="pct__form-ops">
          <AppButton variant="primary" :loading="saving" @click="submitCreate">开通</AppButton>
          <AppButton @click="createVisible = false">取消</AppButton>
        </div>
      </div>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
import { AppButton, AppDrawer } from '@/components/ui'
import { DataTable, EmptyState, LoadingState, ModulePageShell, ModuleToolbar, StatusTag } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { toast } from '@/utils/toast'

const STATUS = {
  trial: ['warning', '试用中'],
  active: ['success', '正式'],
  expired: ['danger', '已到期'],
  disabled: ['default', '已停用']
}

export default {
  name: 'PlatformControlTenants',
  components: { AppButton, AppDrawer, DataTable, EmptyState, LoadingState, ModulePageShell, ModuleToolbar, StatusTag },
  props: {
    targetTab: { type: String, default: '' }
  },
  data() {
    return {
      loading: true,
      saving: false,
      rows: [],
      keyword: '',
      status: '',
      createVisible: false,
      createResult: null,
      form: this.blankForm(),
      columns: [
        { key: 'tenantName', title: '学校', width: '240px' },
        { key: 'status', title: '状态', width: '90px' },
        { key: 'packageName', title: '套餐', width: '90px' },
        { key: 'usage', title: '用量（学生/账号）', width: '170px' },
        { key: 'expireAt', title: '到期时间', width: '120px' },
        { key: 'actions', title: '操作', width: '300px' }
      ]
    }
  },
  computed: {
    pickerHint() {
      const map = {
        features: '功能开关按学校配置',
        rules: '规则中心按学校配置',
        workflows: '审批流按学校配置',
        brands: '品牌按学校配置',
        users: '账号按学校管理'
      }
      return map[this.targetTab] || ''
    }
  },
  created() {
    this.load()
    if (this.$route.meta && this.$route.meta.openCreate) this.createVisible = true
  },
  methods: {
    blankForm() {
      return { tenantCode: '', tenantName: '', packageCode: 'trial', environment: 'production', province: '', city: '', contactName: '', contactPhone: '', adminLoginName: 'admin', adminRealName: '' }
    },
    async load() {
      this.loading = true
      const res = await platformControlApi.listTenants({ keyword: this.keyword, status: this.status })
      this.loading = false
      if (res.code === 0) {
        this.rows = res.data.list || []
      } else {
        toast.error(res.message)
      }
    },
    statusType(s) {
      return (STATUS[s] || ['default', s])[0]
    },
    statusLabel(s) {
      return (STATUS[s] || ['default', s])[1]
    },
    fmt(v) {
      return v ? String(v).replace('T', ' ').slice(0, 10) : '—'
    },
    goDetail(row) {
      const tab = this.targetTab || 'info'
      this.$router.push(`/admin/platform/tenants/${row.tenantId}?tab=${tab}`)
    },
    openCreate() {
      this.form = this.blankForm()
      this.createResult = null
      this.createVisible = true
    },
    async submitCreate() {
      if (!this.form.tenantCode || !this.form.tenantName || !this.form.adminLoginName || !this.form.adminRealName) {
        toast.error('学校编码、全称和首位管理员信息必填')
        return
      }
      this.saving = true
      const res = await platformControlApi.createTenant({ ...this.form })
      this.saving = false
      if (res.code === 0) {
        toast.success(`已开通「${this.form.tenantName}」`)
        const admin = res.data.schoolAdmin || {}
        this.createResult = {
          tenantCode: res.data.tenantCode,
          loginName: admin.loginName,
          initialPassword: admin.initialPassword
        }
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async copyCredential() {
      const value = `学校编码：${this.createResult.tenantCode}\n管理员账号：${this.createResult.loginName}\n初始密码：${this.createResult.initialPassword}`
      try {
        if (!navigator.clipboard) throw new Error('clipboard unavailable')
        await navigator.clipboard.writeText(value)
        toast.success('管理员凭据已复制')
      } catch {
        toast.info('浏览器未允许复制，请手动保存页面上的凭据')
      }
    },
    closeCreate() {
      this.createVisible = false
      this.createResult = null
    },
    async act(row, action, body = {}) {
      const res = await platformControlApi.tenantAction(row.tenantId, action, body)
      if (res.code === 0) {
        toast.success(res.message === 'ok' ? '操作成功' : res.message)
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async resetSandbox(row) {
      const confirmed = window.confirm(`确认恢复「${row.tenantName}」的演示数据？\n\n现场新增数据会被清理，预置流程数据、账号和权限会恢复。其他学校不受影响。`)
      if (!confirmed) return
      const res = await platformControlApi.resetSandboxData(row.tenantId)
      if (res.code === 0) {
        toast.success(res.message || '演示数据已恢复')
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async convert(row) {
      const res = await platformControlApi.tenantAction(row.tenantId, 'convert-to-paid', { packageCode: 'standard' })
      if (res.code === 0) {
        toast.success(`「${row.tenantName}」已转正式（标准版）`)
        this.load()
      } else {
        toast.error(res.message)
      }
    }
  }
}
</script>

<style scoped>
.pct__hint {
  padding: var(--space-2) var(--space-3);
  border-radius: 9px;
  background: var(--pri-bg);
  color: var(--pri);
  font-size: var(--font-size-sm);
}
.pct__secret {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-4);
  border: 1px solid var(--warning-300, #f5c26b);
  border-radius: 12px;
  background: var(--warning-50, #fff8e8);
}
.pct__secret p { margin: 0; }
.pct__secret code { user-select: all; font-weight: 700; }
.pct__input {
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
.pct__input:focus {
  outline: none;
  border-color: var(--glow);
}
.pct__input--sel {
  width: 110px;
}
.pct__name {
  font-weight: var(--font-weight-medium);
  color: var(--t1);
}
.pct__code {
  font-size: 12px;
  color: var(--text-tertiary);
}
.pct__usage {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.pct__ops {
  display: flex;
  gap: var(--space-1);
  flex-wrap: wrap;
}
.pct__form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.pct__field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.pct__field .pct__input {
  width: 100%;
}
.pct__pair {
  display: flex;
  gap: var(--space-2);
}
.pct__form-ops {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-2);
}
</style>
