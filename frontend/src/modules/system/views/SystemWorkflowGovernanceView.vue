<template>
  <ModulePageShell
    title="流程安全与运行治理"
    subtitle="启用流程 · 无审批人 · 节点动作策略 · 版本变更策略 · 在途异常人工推进"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="[{ key: 'refresh', label: '刷新' }]" @action="load" />
    </template>

    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <section class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">首屏结论</span></header>
          <div class="mp-card__body wg-summary">
            <div class="wg-stat">
              <span class="wg-stat__num">{{ overview.enabledWorkflows }}/{{ overview.totalWorkflows }}</span>
              <span class="wg-stat__label">已启用流程</span>
            </div>
            <div class="wg-stat">
              <span class="wg-stat__num">{{ (overview.noApproverNodes || []).length }}</span>
              <span class="wg-stat__label">无审批人节点</span>
            </div>
            <div class="wg-stat">
              <span class="wg-stat__num">{{ overview.runningInstances }}</span>
              <span class="wg-stat__label">在途实例</span>
            </div>
            <div class="wg-stat">
              <span class="wg-stat__num">{{ overview.staleRunningInstances }}</span>
              <span class="wg-stat__label">超30天未动</span>
            </div>
            <div class="wg-stat">
              <span class="wg-stat__num">{{ overview.activeNodeActionPolicies }}</span>
              <span class="wg-stat__label">生效中节点策略</span>
            </div>
            <div class="wg-stat">
              <span class="wg-stat__num">{{ overview.activeVersionStrategies }}</span>
              <span class="wg-stat__label">生效中版本策略</span>
            </div>
          </div>
          <div v-if="(overview.noApproverNodes || []).length" class="mp-card__body">
            <p v-for="n in overview.noApproverNodes" :key="n.workflowCode + n.nodeCode" class="wg-warn">
              {{ n.workflowCode }} · {{ n.nodeCode }}：责任角色 {{ n.roleCode }} 不存在或没有启用成员
            </p>
          </div>
        </section>

        <section class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">节点动作与版本策略</span>
            <span class="mp-note">页面权限 ≠ 流程动作权限；激活须两人复核</span>
          </header>
          <div class="mp-card__body wg-new">
            <input v-model.trim="newWorkflowCode" class="wg-input" placeholder="流程编码，如 AFFAIRS_LEAVE" />
            <input v-model.trim="newNodeCode" class="wg-input" placeholder="节点编码（版本策略留空）" />
            <select v-model="newPolicyType" class="wg-input">
              <option value="NODE_ACTION">节点动作权限</option>
              <option value="VERSION_STRATEGY">版本变更策略</option>
            </select>
            <input v-if="newPolicyType === 'NODE_ACTION'" v-model.trim="newActionPermission"
                   class="wg-input" placeholder="动作权限码，如 systemAdmin.workflow.override" />
            <select v-else v-model="newVersionStrategy" class="wg-input">
              <option value="DYNAMIC">DYNAMIC（默认，在途实例读最新配置）</option>
              <option value="SNAPSHOT">SNAPSHOT（在途实例期间拒绝改动）</option>
              <option value="MIGRATE">MIGRATE（允许改动但留痕受影响实例）</option>
            </select>
            <button class="mp-link" @click="askSaveDraft">保存草稿</button>
          </div>
          <div class="mp-card__body">
            <EmptyState v-if="!policies.length" title="还没有策略" description="填写上方表单保存一条草稿" />
            <DataTable v-else :columns="policyColumns" :rows="policies" row-key="policyId">
              <template #cell-scope="{ row }">
                <div class="mp-cell-main">{{ row.workflowCode }}</div>
                <div class="mp-cell-sub">{{ row.nodeCode || '（流程级）' }} · {{ row.policyType }}</div>
              </template>
              <template #cell-rule="{ row }">
                <span v-if="row.policyType === 'NODE_ACTION'">{{ row.actionPermissionCode }}</span>
                <span v-else>{{ row.versionStrategy }}</span>
              </template>
              <template #cell-status="{ row }">
                <StatusTag :type="statusTone(row.status)" :label="row.status" dot />
              </template>
              <template #cell-ops="{ row }">
                <button v-if="row.status === 'DRAFT'" class="mp-link" @click="submit(row)">提交复核</button>
                <button v-if="row.status === 'PENDING_REVIEW'" class="mp-link" @click="askActivate(row)">激活</button>
                <button v-if="row.status === 'ACTIVE'" class="mp-link" @click="askRetire(row)">下线</button>
              </template>
            </DataTable>
          </div>
        </section>

        <section class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">人工推进（解卡异常任务）</span>
            <span class="mp-note">必须填写理由，全程留痕，不代替业务判断</span>
          </header>
          <div class="mp-card__body wg-new">
            <input v-model.trim="forceTaskId" class="wg-input" placeholder="审批任务 ID" />
            <select v-model="forceAction" class="wg-input">
              <option value="APPROVED">强制通过</option>
              <option value="REJECTED">强制驳回</option>
              <option value="CANCELLED">强制作废</option>
            </select>
            <button class="mp-link" @click="askForceAdvance">人工推进</button>
          </div>
        </section>
      </template>
    </div>

    <AppConfirmDialog
      v-model:visible="dialogOpen"
      :type="pendingAction === 'retire' ? 'warning' : 'info'"
      :title="dialogTitle"
      :message="dialogMessage"
      :confirm-text="dialogTitle"
      require-reason
      reason-label="原因"
      :submitting="submitting"
      @confirm="submitDialog"
    >
      <label v-if="pendingAction === 'activate'" class="wg-field">
        自复核确认（提交人与激活人相同时必填）
        <input v-model.trim="selfReviewAck" class="wg-input" placeholder='填写"自复核通过，已确认影响面"' />
      </label>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

export default {
  name: 'SystemWorkflowGovernanceView',
  components: {
    ModulePageShell, ModuleToolbar, DataTable, StatusTag,
    LoadingState, ErrorState, EmptyState, AppConfirmDialog
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      overview: {},
      policies: [],
      newWorkflowCode: '',
      newNodeCode: '',
      newPolicyType: 'NODE_ACTION',
      newActionPermission: '',
      newVersionStrategy: 'DYNAMIC',
      forceTaskId: '',
      forceAction: 'APPROVED',
      dialogOpen: false,
      submitting: false,
      pendingAction: '',
      pendingRow: null,
      selfReviewAck: '',
      policyColumns: [
        { key: 'scope', title: '流程 / 节点' },
        { key: 'rule', title: '规则' },
        { key: 'status', title: '状态' },
        { key: 'ops', title: '操作' }
      ]
    }
  },
  computed: {
    dialogTitle() {
      return { draft: '保存草稿', submit: '提交复核', activate: '激活策略',
        retire: '下线策略', force: '人工推进' }[this.pendingAction] || '确认'
    },
    dialogMessage() {
      if (this.pendingAction === 'draft') return '保存这条策略草稿，此时不生效。'
      if (this.pendingAction === 'activate') return '激活后立即生效；提交人与激活人相同时需要额外自复核确认。'
      if (this.pendingAction === 'retire') return '下线后该范围恢复为未激活状态（不受节点策略约束）。'
      if (this.pendingAction === 'force') return `将审批任务 ${this.forceTaskId} 强制推进为 ${this.forceAction}，不触发原审批的业务联动。`
      return ''
    }
  },
  created() { this.load() },
  methods: {
    statusTone(s) {
      return { DRAFT: 'default', PENDING_REVIEW: 'warning', ACTIVE: 'success', RETIRED: 'default' }[s] || 'default'
    },
    askSaveDraft() {
      if (!this.newWorkflowCode) return toast.error('请填写流程编码')
      if (this.newPolicyType === 'NODE_ACTION' && !this.newActionPermission) {
        return toast.error('节点动作策略必须填写动作权限码')
      }
      this.pendingAction = 'draft'
      this.pendingRow = null
      this.dialogOpen = true
    },
    submit(row) {
      this.pendingAction = 'submit'
      this.pendingRow = row
      this.dialogOpen = true
    },
    askActivate(row) {
      this.pendingAction = 'activate'
      this.pendingRow = row
      this.selfReviewAck = ''
      this.dialogOpen = true
    },
    askRetire(row) {
      this.pendingAction = 'retire'
      this.pendingRow = row
      this.dialogOpen = true
    },
    askForceAdvance() {
      if (!/^\d+$/.test(this.forceTaskId)) return toast.error('请填写任务 ID（纯数字）')
      this.pendingAction = 'force'
      this.pendingRow = null
      this.dialogOpen = true
    },
    async submitDialog({ reason }) {
      this.submitting = true
      let res
      if (this.pendingAction === 'draft') {
        res = await systemApi.saveWorkflowPolicyDraft(this.newWorkflowCode, {
          nodeCode: this.newPolicyType === 'NODE_ACTION' ? this.newNodeCode : '',
          policyType: this.newPolicyType,
          actionPermissionCode: this.newActionPermission,
          versionStrategy: this.newVersionStrategy,
          reason
        })
      } else if (this.pendingAction === 'submit') {
        res = await systemApi.submitWorkflowPolicy(this.pendingRow.policyId, {
          expectedVersion: this.pendingRow.version
        })
      } else if (this.pendingAction === 'activate') {
        res = await systemApi.activateWorkflowPolicy(this.pendingRow.policyId, {
          reason, selfReviewAck: this.selfReviewAck, expectedVersion: this.pendingRow.version
        })
      } else if (this.pendingAction === 'retire') {
        res = await systemApi.retireWorkflowPolicy(this.pendingRow.policyId, {
          reason, expectedVersion: this.pendingRow.version
        })
      } else {
        res = await systemApi.forceAdvanceWorkflowTask(this.forceTaskId, {
          action: this.forceAction, reason
        })
      }
      this.submitting = false
      if (res.code === 0) {
        toast.success('已完成')
        this.dialogOpen = false
        this.pendingRow = null
        if (this.pendingAction === 'draft') {
          this.newWorkflowCode = ''; this.newNodeCode = ''; this.newActionPermission = ''
        }
        if (this.pendingAction === 'force') this.forceTaskId = ''
        await this.load()
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const [overview, policies] = await Promise.all([
        systemApi.getWorkflowGovernanceOverview(),
        systemApi.listWorkflowPolicies()
      ])
      if (overview.code === 0) this.overview = overview.data || {}
      else this.error = overview.message
      if (policies.code === 0) this.policies = policies.data.list || []
      else if (!this.error) this.error = policies.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.wg-summary { display: flex; flex-wrap: wrap; gap: var(--space-4); }
.wg-stat {
  min-width: 130px;
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
}
.wg-stat__num { display: block; font-size: var(--font-size-xl); font-weight: var(--font-weight-semibold); }
.wg-stat__label { display: block; color: var(--text-secondary); font-size: var(--font-size-xs); }
.wg-warn { color: var(--color-danger); margin: 2px 0; }
.wg-new { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: center; }
.wg-input {
  padding: 6px 10px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-sm);
  min-width: 160px;
}
.wg-field { display: block; margin: var(--space-2) 0; }
</style>
