<template>
  <div class="wf-page">
    <AppSectionHeader title="流程模板管理" subtitle="各业务模块审批流的模板、版本与节点定义（本期不含可视化设计器）" />

    <div class="wf-page__filters">
      <select v-model="filters.moduleCode" @change="load">
        <option value="">全部模块</option>
        <option v-for="(label, code) in moduleOptions" :key="code" :value="code">{{ label }}</option>
      </select>
      <select v-model="filters.status" @change="load">
        <option value="">全部状态</option>
        <option v-for="(label, code) in statusOptions" :key="code" :value="code">{{ label }}</option>
      </select>
      <input v-model.trim="filters.keyword" placeholder="搜索模板名称 / 编码" @keyup.enter="load" />
      <AppButton variant="secondary" @click="load">查询</AppButton>
    </div>

    <WorkflowStateBlock :loading="loading" :error="error" :empty="!list.length" :view-state="viewState" @retry="load">
      <div class="wf-processes__list">
        <ProcessTemplateCard v-for="t in list" :key="t.templateId" :template="t" @view="openDetail">
          <template #actions>
            <AppButton
              v-if="t.status !== 'ENABLED'"
              variant="primary"
              :disabled="readonly || !canToggle"
              :loading="togglingId === t.templateId"
              @click="toggle(t, 'ENABLED')"
            >启用</AppButton>
            <AppButton
              v-else
              variant="warning"
              :disabled="readonly || !canToggle"
              :loading="togglingId === t.templateId"
              @click="toggle(t, 'DISABLED')"
            >停用</AppButton>
            <AppButton variant="ghost" @click="openDetail(t)">详情</AppButton>
          </template>
        </ProcessTemplateCard>
      </div>
    </WorkflowStateBlock>

    <AppDrawer :visible="detailVisible" :title="detail ? detail.templateName : '模板详情'" @update:visible="detailVisible = $event">
      <div v-if="detail" class="wf-processes__detail">
        <dl class="wf-processes__kv">
          <dt>编码</dt><dd>{{ detail.templateCode }}</dd>
          <dt>模块</dt><dd>{{ moduleLabel(detail.moduleCode) }}</dd>
          <dt>业务类型</dt><dd>{{ detail.businessType }}</dd>
          <dt>版本</dt><dd>v{{ detail.version }}</dd>
          <dt>状态</dt><dd><AppBadge :type="statusType(detail.status)">{{ statusText(detail.status) }}</AppBadge></dd>
          <dt>发布时间</dt><dd>{{ detail.publishedAt || '未发布' }}</dd>
          <dt>维护人</dt><dd>{{ detail.updatedBy }} · {{ detail.updatedAt }}</dd>
        </dl>
        <h4 class="wf-processes__sub">节点定义（{{ detail.nodes.length }}）</h4>
        <div v-for="n in detail.nodes" :key="n.nodeId" class="wf-processes__node">
          <div class="wf-processes__node-head">
            <span class="wf-processes__node-name">{{ n.nodeName }}</span>
            <AppBadge type="neutral">{{ nodeTypeLabel(n.nodeType) }}</AppBadge>
          </div>
          <div class="wf-processes__node-meta">
            <span v-if="n.candidateRoles.length">候选角色：{{ n.candidateRoles.map(roleLabel).join('、') }}</span>
            <span>退回 {{ n.allowReject ? '✓' : '✗' }}</span>
            <span>撤回 {{ n.allowWithdraw ? '✓' : '✗' }}</span>
            <span>转办 {{ n.allowTransfer ? '✓' : '✗' }}</span>
            <span v-if="n.requireComment">意见必填≥{{ n.commentMinLength }}字</span>
            <span v-if="n.nextNodeIds.length">→ {{ n.nextNodeIds.join(', ') }}</span>
          </div>
        </div>
      </div>
    </AppDrawer>
  </div>
</template>

<script>
/** 页面 2：/admin/workflow/processes 流程模板管理 */
import { AppButton, AppBadge, AppDrawer, AppSectionHeader } from '@/components/ui'
import WorkflowStateBlock from '@/modules/workflow/components/WorkflowStateBlock.vue'
import ProcessTemplateCard from '@/modules/workflow/components/ProcessTemplateCard.vue'
import { workflowProvider, canClickButton, getModuleLabel, getProcessStatusText, getProcessStatusType, getNodeTypeLabel, MODULE_LABELS, PROCESS_STATUS_LABELS, ROLE_LABELS } from '@/modules/workflow'
import { toast } from '@/utils/toast'

export default {
  name: 'WorkflowProcessesView',
  components: { AppButton, AppBadge, AppDrawer, AppSectionHeader, WorkflowStateBlock, ProcessTemplateCard },
  data() {
    return {
      loading: false,
      error: '',
      list: [],
      filters: { moduleCode: '', status: '', keyword: '' },
      detailVisible: false,
      detail: null,
      togglingId: ''
    }
  },
  computed: {
    moduleOptions: () => MODULE_LABELS,
    statusOptions: () => PROCESS_STATUS_LABELS,
    viewState() {
      return workflowProvider.getLicenseViewState()
    },
    readonly() {
      return this.viewState === 'READONLY'
    },
    canToggle() {
      return canClickButton('workflow.process.toggle')
    }
  },
  watch: {
    '$route.query.lv'() {
      this.load()
    }
  },
  created() {
    this.load()
  },
  methods: {
    moduleLabel: getModuleLabel,
    statusText: getProcessStatusText,
    statusType: getProcessStatusType,
    nodeTypeLabel: getNodeTypeLabel,
    roleLabel(code) {
      return ROLE_LABELS[code] || code
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        const res = await workflowProvider.getProcessTemplates(this.filters)
        if (res.code === 0) this.list = res.data.list
        else this.error = res.message
      } catch (e) {
        this.error = e.message || '加载失败'
      } finally {
        this.loading = false
      }
    },
    async openDetail(t) {
      const res = await workflowProvider.getProcessTemplateDetail(t.templateId)
      if (res.code === 0) {
        this.detail = res.data
        this.detailVisible = true
      } else {
        toast.warning(res.message)
      }
    },
    async toggle(t, status) {
      this.togglingId = t.templateId
      try {
        const res = await workflowProvider.updateProcessTemplateStatus(t.templateId, status)
        if (res.code === 0) {
          toast.success(status === 'ENABLED' ? `已启用「${t.templateName}」` : `已停用「${t.templateName}」`)
          await this.load()
        } else {
          toast.warning(res.message)
        }
      } finally {
        this.togglingId = ''
      }
    }
  }
}
</script>

<style scoped>
@import './workflow-page.css';
.wf-processes__list { display: flex; flex-direction: column; gap: var(--space-4); }
.wf-processes__detail { display: flex; flex-direction: column; gap: var(--space-3); }
.wf-processes__kv { display: grid; grid-template-columns: auto 1fr; gap: var(--space-2) var(--space-4); margin: 0; font-size: var(--font-size-sm); }
.wf-processes__kv dt { color: var(--text-tertiary); }
.wf-processes__kv dd { margin: 0; color: var(--text-primary); }
.wf-processes__sub { margin: var(--space-2) 0 0; font-size: var(--font-size-base); font-weight: var(--font-weight-medium); color: var(--text-primary); }
.wf-processes__node { border: 1px solid var(--border-light); border-radius: var(--radius-base); padding: var(--space-2) var(--space-3); }
.wf-processes__node-head { display: flex; align-items: center; gap: var(--space-2); }
.wf-processes__node-name { font-size: var(--font-size-base); color: var(--text-primary); font-weight: var(--font-weight-medium); }
.wf-processes__node-meta { display: flex; flex-wrap: wrap; gap: var(--space-3); margin-top: var(--space-1); font-size: var(--font-size-xs); color: var(--text-secondary); }
</style>
