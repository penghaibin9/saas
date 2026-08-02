<template>
  <ModulePageShell
    title="教职工任职"
    subtitle="任职有起止时间，到期自动失效；下方保留旧归属投影用于对账"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />

      <template v-else>
        <section class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">正式任职</span>
            <span>
              <label class="sa-toggle">
                <input v-model="includeExpired" type="checkbox" @change="loadAssignments" />
                显示已过期/已撤销
              </label>
              <AppButton variant="primary" size="small" @click="openCreate">新增任职</AppButton>
            </span>
          </header>
          <div class="mp-card__body" style="padding-top: 0">
            <table class="mp-audit">
              <thead>
                <tr>
                  <th style="width: 120px">岗位</th>
                  <th>组织</th>
                  <th style="width: 110px">人员</th>
                  <th style="width: 175px">生效期间</th>
                  <th style="width: 110px">来源</th>
                  <th style="width: 100px">当前状态</th>
                  <th style="width: 80px">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in assignments" :key="row.assignmentId">
                  <td class="is-who">
                    {{ assignmentLabel(row.assignmentType) }}
                    <span v-if="row.isPrimary" class="sa-flag">主任职</span>
                  </td>
                  <td>{{ orgName(row.orgType, row.orgNodeId) }}</td>
                  <td>{{ row.userId }}</td>
                  <td>{{ fmt(row.effectiveAt) }} ~ {{ row.expiresAt ? fmt(row.expiresAt) : '长期' }}</td>
                  <td>{{ sourceLabel(row.sourceType) }}</td>
                  <td>
                    <StatusTag
                      :type="row.effectiveNow ? 'success' : 'default'"
                      :label="row.effectiveNow ? '生效中' : statusLabel(row.status)"
                      dot
                    />
                  </td>
                  <td>
                    <button v-if="row.effectiveNow" class="mp-link" @click="openRevoke(row)">撤销</button>
                    <span v-else class="mp-note">—</span>
                  </td>
                </tr>
              </tbody>
            </table>
            <EmptyState
              v-if="!assignments.length"
              title="暂无正式任职"
              description="点右上角新增；旧的辅导员/班主任/教学秘书字段已在升级时回填为投影任职"
            />
          </div>
        </section>

        <section class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">旧归属投影（只读对账）</span>
            <span class="mp-note">来自班级辅导员/班主任、学院教学秘书和教师范围字段，退役前保留</span>
          </header>
          <div class="mp-card__body" style="padding-top: 0">
            <DataTable v-if="legacyRows.length" :columns="legacyColumns" :rows="legacyRows" row-key="id">
              <template #cell-status="{ row }">
                <StatusTag :type="row.status === 'ACTIVE' ? 'success' : 'default'" :label="row.status || 'ACTIVE'" dot />
              </template>
            </DataTable>
            <EmptyState v-else title="暂无旧归属数据" description="" />
          </div>
        </section>
      </template>
    </div>

    <AppDrawer v-model:visible="form.open" title="新增任职">
      <label class="sa-label">人员 userId<span class="sa-required">*</span></label>
      <input v-model="form.userId" class="mp-input" placeholder="教职工账号 userId" />

      <label class="sa-label">组织<span class="sa-required">*</span></label>
      <select v-model="form.orgKey" class="mp-input">
        <option value="">请选择组织</option>
        <option v-for="opt in orgOptions" :key="opt.key" :value="opt.key">{{ opt.label }}</option>
      </select>

      <label class="sa-label">岗位<span class="sa-required">*</span></label>
      <select v-model="form.assignmentType" class="mp-input">
        <option v-for="opt in assignmentTypes" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
      </select>

      <div class="sa-row">
        <div>
          <label class="sa-label">生效时间</label>
          <input v-model="form.effectiveAt" type="datetime-local" class="mp-input" />
        </div>
        <div>
          <label class="sa-label">结束时间（留空=长期）</label>
          <input v-model="form.expiresAt" type="datetime-local" class="mp-input" />
        </div>
      </div>

      <label class="sa-check">
        <input v-model="form.isPrimary" type="checkbox" />
        设为主任职（同一人只保留一个主任职）
      </label>

      <label class="sa-label">任命原因</label>
      <textarea v-model="form.reason" class="mp-textarea" rows="2" placeholder="将写入任职记录" />

      <div v-if="form.error" class="mp-form-err">{{ form.error }}</div>
      <template #footer>
        <AppButton variant="ghost" @click="form.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="form.submitting" @click="submitCreate">确认任命</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer v-model:visible="revoke.open" title="撤销任职">
      <p class="sa-tip">撤销后立即失效，历史记录保留可查。</p>
      <label class="sa-label">撤销原因<span class="sa-required">*</span></label>
      <textarea v-model="revoke.reason" class="mp-textarea" rows="2" placeholder="至少 5 个字" />
      <div v-if="revoke.error" class="mp-form-err">{{ revoke.error }}</div>
      <template #footer>
        <AppButton variant="ghost" @click="revoke.open = false">取消</AppButton>
        <AppButton variant="primary" :loading="revoke.submitting" @click="submitRevoke">确认撤销</AppButton>
      </template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

const ASSIGNMENT_TYPES = [
  { value: 'COUNSELOR', label: '辅导员' },
  { value: 'HEAD_TEACHER', label: '班主任' },
  { value: 'SECRETARY', label: '教学秘书' },
  { value: 'LEADER', label: '负责人' },
  { value: 'OTHER', label: '其他岗位' }
]

const SOURCE_LABEL = { MANUAL: '手工任命', PROJECTED: '旧字段回填', IMPORT: '批量导入' }
const STATUS_LABEL = { ACTIVE: '未到生效期', EXPIRED: '已过期', REVOKED: '已撤销' }

export default {
  name: 'SystemStaffAffiliationView',
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppButton, AppDrawer
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      includeExpired: false,
      assignments: [],
      legacyRows: [],
      orgOptions: [],
      orgNameMap: {},
      assignmentTypes: ASSIGNMENT_TYPES,
      legacyColumns: [
        { key: 'roleLabel', title: '岗位' },
        { key: 'orgName', title: '组织' },
        { key: 'orgType', title: '组织类型' },
        { key: 'staffName', title: '人员' },
        { key: 'staffKey', title: '人员标识' },
        { key: 'status', title: '状态' }
      ],
      form: {
        open: false, userId: '', orgKey: '', assignmentType: 'COUNSELOR',
        effectiveAt: '', expiresAt: '', isPrimary: false, reason: '', error: '', submitting: false
      },
      revoke: { open: false, id: '', expectedVersion: 0, reason: '', error: '', submitting: false }
    }
  },
  created() { this.load() },
  methods: {
    fmt(v) { return v ? String(v).replace('T', ' ').slice(0, 16) : '—' },
    assignmentLabel(t) { return (ASSIGNMENT_TYPES.find((x) => x.value === t) || {}).label || t },
    sourceLabel(s) { return SOURCE_LABEL[s] || s },
    statusLabel(s) { return STATUS_LABEL[s] || s },
    orgName(type, id) { return this.orgNameMap[`${type}:${id}`] || `${type}:${id}` },

    async load() {
      this.loading = true
      this.error = ''
      const [tree, legacy] = await Promise.all([
        systemApi.getDepartmentTree(),
        systemApi.listStaffAffiliations()
      ])
      if (tree.code === 0) this.buildOrgOptions(tree.data || [])
      if (legacy.code === 0) this.legacyRows = (legacy.data || {}).list || []
      await this.loadAssignments()
      this.loading = false
    },

    buildOrgOptions(tree) {
      const options = []
      const map = {}
      const walk = (nodes, prefix) => {
        (nodes || []).forEach((node) => {
          const label = prefix ? `${prefix} / ${node.name}` : node.name
          const key = `${node.type}:${node.id}`
          options.push({ key, label: `${label}（${node.typeLabel}）` })
          map[key] = label
          walk(node.children, label)
        })
      }
      walk(tree, '')
      this.orgOptions = options
      this.orgNameMap = map
    },

    async loadAssignments() {
      const res = await systemApi.listStaffAssignments({ includeExpired: this.includeExpired })
      if (res.code === 0) this.assignments = (res.data || {}).items || []
      else this.error = res.message
    },

    openCreate() {
      this.form = {
        open: true, userId: '', orgKey: '', assignmentType: 'COUNSELOR',
        effectiveAt: '', expiresAt: '', isPrimary: false, reason: '', error: '', submitting: false
      }
    },

    async submitCreate() {
      if (!this.form.userId) { this.form.error = '请填写人员 userId'; return }
      if (!this.form.orgKey) { this.form.error = '请选择组织'; return }
      const [orgType, orgNodeId] = this.form.orgKey.split(':')
      this.form.submitting = true
      this.form.error = ''
      const res = await systemApi.createStaffAssignment({
        userId: Number(this.form.userId),
        orgType,
        orgNodeId: Number(orgNodeId),
        assignmentType: this.form.assignmentType,
        effectiveAt: this.form.effectiveAt ? new Date(this.form.effectiveAt).toISOString() : null,
        expiresAt: this.form.expiresAt ? new Date(this.form.expiresAt).toISOString() : null,
        isPrimary: this.form.isPrimary,
        reason: this.form.reason
      })
      this.form.submitting = false
      if (res.code === 0) {
        toast.success('任职已生效')
        this.form.open = false
        this.loadAssignments()
      } else {
        this.form.error = res.message
      }
    },

    openRevoke(row) {
      this.revoke = {
        open: true, id: row.assignmentId, expectedVersion: row.version,
        reason: '', error: '', submitting: false
      }
    },

    async submitRevoke() {
      if (!this.revoke.reason || this.revoke.reason.trim().length < 5) {
        this.revoke.error = '撤销原因不少于 5 个字'
        return
      }
      this.revoke.submitting = true
      const res = await systemApi.revokeStaffAssignment(this.revoke.id, {
        reason: this.revoke.reason.trim(),
        expectedVersion: this.revoke.expectedVersion
      })
      this.revoke.submitting = false
      if (res.code === 0) {
        toast.success('任职已撤销')
        this.revoke.open = false
        this.loadAssignments()
      } else {
        this.revoke.error = res.message
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.sa-toggle { margin-right: var(--space-3); font-size: var(--font-size-sm); }
.sa-flag {
  margin-left: var(--space-1); padding: 0 var(--space-1); border-radius: var(--radius-sm);
  background: var(--fill-secondary); font-size: var(--font-size-xs); color: var(--text-secondary); font-weight: normal;
}
.sa-label { display: block; margin-top: var(--space-3); margin-bottom: var(--space-1); font-size: var(--font-size-sm); }
.sa-required { color: var(--danger-600); }
.sa-row { display: flex; gap: var(--space-3); }
.sa-row > div { flex: 1; min-width: 0; }
.sa-check { display: block; margin-top: var(--space-3); font-size: var(--font-size-sm); }
.sa-tip { margin: 0 0 var(--space-2); font-size: var(--font-size-sm); color: var(--text-secondary); }
</style>
