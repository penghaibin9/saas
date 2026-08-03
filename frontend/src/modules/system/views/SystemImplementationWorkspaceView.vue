<template>
  <ModulePageShell
    title="实施项目工作区"
    subtitle="项目阶段 · 未确认政策 · 未安装对象 · 上线阻断 · 验收证据"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onAction" />
    </template>

    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!project" title="本校还没有实施项目"
                  description="到「首次开局向导」创建实施项目后回到本页统一推进" />
      <template v-else>
        <section class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">{{ project.projectName }}</span>
            <StatusTag :type="stageTone" :label="stageLabel" dot />
          </header>
          <div class="mp-card__body iw-conclusions">
            <div class="iw-item">
              <span class="iw-item__num">{{ blockingChecks.length }}</span>
              <span class="iw-item__label">上线阻断</span>
            </div>
            <div class="iw-item">
              <span class="iw-item__num">{{ pendingPolicyCount }}</span>
              <span class="iw-item__label">未确认流程政策</span>
            </div>
            <div class="iw-item">
              <span class="iw-item__num">{{ notInstalledCount }}</span>
              <span class="iw-item__label">未安装对象</span>
            </div>
            <div class="iw-item">
              <span class="iw-item__num">{{ blockedModules.length }}</span>
              <span class="iw-item__label">未授权模块</span>
            </div>
            <div class="iw-item">
              <span class="iw-item__num">{{ project.acceptanceDigest ? '已封板' : '未验收' }}</span>
              <span class="iw-item__label">验收证据</span>
            </div>
          </div>
        </section>

        <section v-if="preview" class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">应用前确认</span>
            <span class="mp-note">快照哈希 {{ shortHash }}</span>
          </header>
          <div class="mp-card__body">
            <p v-if="blockedModules.length" class="iw-blocked">
              以下模块未获得平台商业授权，无法安装启用：{{ blockedModules.join('、') }}
            </p>
            <ul class="iw-list">
              <li>幂等键：{{ idempotencyKey || '（先预览生成）' }}</li>
              <li>本次将新建审批流程 {{ (preview.impact && preview.impact.workflows.toCreate.length) || 0 }} 个，
                已存在跳过 {{ (preview.impact && preview.impact.workflows.alreadyInstalled.length) || 0 }} 个</li>
              <li>本次将新建角色工作台 {{ (preview.impact && preview.impact.workbenches.toCreate.length) || 0 }} 个，
                已存在跳过 {{ (preview.impact && preview.impact.workbenches.alreadyInstalled.length) || 0 }} 个</li>
              <li>涉及模块：{{ (preview.impact && preview.impact.selectedModules.join('、')) || '—' }}</li>
              <li v-if="preview.missingSections && preview.missingSections.length">
                缺失配置段：{{ preview.missingSections.join('、') }}
              </li>
            </ul>
            <p class="mp-note">{{ (preview.impact && preview.impact.note) || '' }}</p>
          </div>
        </section>

        <section v-if="checks.length" class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">上线检查</span></header>
          <div class="mp-card__body">
            <DataTable :columns="checkColumns" :rows="checks" row-key="code">
              <template #cell-result="{ row }">
                <StatusTag :type="row.result === 'PASS' ? 'success' : 'danger'" :label="row.result" dot />
              </template>
              <template #cell-severity="{ row }">
                <StatusTag :type="row.severity === 'BLOCKER' ? 'danger' : 'warning'" :label="row.severity" dot />
              </template>
            </DataTable>
          </div>
        </section>

        <section class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">分步作业入口</span></header>
          <div class="mp-card__body iw-links">
            <router-link v-for="link in stepLinks" :key="link.path" class="mp-link" :to="link.path">
              {{ link.label }}
            </router-link>
          </div>
        </section>
      </template>
    </div>

    <AppConfirmDialog
      v-model:visible="confirmOpen"
      type="warning"
      :title="pendingAction === 'apply' ? '应用预设快照？' : '验收封板？'"
      :message="confirmMessage"
      :confirm-text="pendingAction === 'apply' ? '确认应用' : '确认验收'"
      require-reason
      :reason-label="pendingAction === 'apply' ? '应用原因' : '验收意见'"
      :submitting="submitting"
      @confirm="submit"
    />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { implementationApi } from '@/modules/system/api/implementation.api'
import { toast } from '@/utils/toast'

const STAGE_LABELS = {
  DRAFT: '草稿', CONFIGURING: '配置中', PREVIEW_READY: '预览就绪', APPLIED: '已应用',
  VERIFYING: '检查中', READY_FOR_ACCEPTANCE: '可验收', ACCEPTED: '已验收封板'
}

export default {
  name: 'SystemImplementationWorkspaceView',
  components: {
    ModulePageShell, ModuleToolbar, DataTable, StatusTag,
    LoadingState, ErrorState, EmptyState, AppConfirmDialog
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      project: null,
      preview: null,
      idempotencyKey: '',
      checks: [],
      runtime: null,
      confirmOpen: false,
      submitting: false,
      pendingAction: '',
      checkColumns: [
        { key: 'name', title: '检查项' },
        { key: 'result', title: '结果' },
        { key: 'severity', title: '级别' },
        { key: 'ownerRole', title: '责任角色' }
      ],
      stepLinks: [
        { label: '首次开局向导', path: '/admin/system/implementation/wizard' },
        { label: '预设方案', path: '/admin/system/implementation/presets' },
        { label: '数据导入与智能匹配', path: '/admin/system/implementation/data-mapping' },
        { label: '已安装配置', path: '/admin/system/implementation/installed' },
        { label: '变更与升级', path: '/admin/system/implementation/changes' },
        { label: '上线检查与验收', path: '/admin/system/implementation/acceptance' }
      ]
    }
  },
  computed: {
    stageLabel() {
      return STAGE_LABELS[this.project?.status] || this.project?.status || '—'
    },
    stageTone() {
      if (this.project?.status === 'ACCEPTED') return 'success'
      if (this.project?.status === 'VERIFYING') return 'warning'
      return 'default'
    },
    blockingChecks() {
      return this.checks.filter((c) => c.result !== 'PASS' && c.severity === 'BLOCKER')
    },
    blockedModules() {
      return (this.preview && this.preview.entitlement && this.preview.entitlement.blockedModules) || []
    },
    pendingPolicyCount() {
      return (this.runtime && this.runtime.pendingPolicyConfirmation) || 0
    },
    notInstalledCount() {
      if (!this.preview || !this.preview.impact) return 0
      return this.preview.impact.workflows.toCreate.length + this.preview.impact.workbenches.toCreate.length
    },
    shortHash() {
      return this.idempotencyKey ? `${this.idempotencyKey.slice(0, 12)}…` : '—'
    },
    toolbarActions() {
      const actions = [{ key: 'refresh', label: '刷新' }]
      if (!this.project) return actions
      if (['DRAFT', 'CONFIGURING', 'PREVIEW_READY'].includes(this.project.status)) {
        actions.unshift({ key: 'preview', label: '生成预览' })
      }
      if (this.project.status === 'PREVIEW_READY') {
        actions.unshift({ key: 'apply', label: '应用快照', variant: 'primary' })
      }
      if (['APPLIED', 'VERIFYING', 'READY_FOR_ACCEPTANCE'].includes(this.project.status)) {
        actions.unshift({ key: 'checks', label: '运行上线检查' })
      }
      if (this.project.status === 'READY_FOR_ACCEPTANCE') {
        actions.unshift({ key: 'accept', label: '验收封板', variant: 'primary' })
      }
      return actions
    },
    confirmMessage() {
      if (this.pendingAction === 'apply') {
        return `将按快照 ${this.shortHash} 安装预设；已存在的对象只跳过不覆盖，重复提交不会装第二遍。`
      }
      return '验收后配置封板，只能通过新建变更项目调整。'
    }
  },
  created() { this.load() },
  methods: {
    onAction(key) {
      if (key === 'refresh') return this.load()
      if (key === 'preview') return this.doPreview()
      if (key === 'checks') return this.doChecks()
      if (key === 'apply' || key === 'accept') {
        this.pendingAction = key
        this.confirmOpen = true
      }
    },
    async doPreview() {
      const res = await this.call(() => implementationApi.preview(this.project.id))
      if (!res) return
      this.preview = res.preview
      this.idempotencyKey = res.idempotencyKey || res.previewHash || ''
      this.project = res.project || this.project
      if (this.preview.blocked) toast.error('预览存在阻断项，请先处理后再应用')
      else toast.success('预览已生成')
    },
    async doChecks() {
      const res = await this.call(() => implementationApi.runChecks(this.project.id))
      if (!res) return
      this.checks = res.checks || []
      await this.load()
    },
    async submit({ reason }) {
      this.submitting = true
      const res = this.pendingAction === 'apply'
        ? await this.call(() => implementationApi.apply(this.project.id, {
          confirmText: '确认应用', reason, idempotencyKey: this.idempotencyKey
        }))
        : await this.call(() => implementationApi.accept(this.project.id, {
          confirmText: '确认验收', comment: reason
        }))
      this.submitting = false
      if (!res) return
      if (this.pendingAction === 'apply' && res.idempotent) {
        toast.success(`该快照已应用过，沿用安装版本 ${res.installationNo || ''}`)
      } else {
        toast.success('已完成')
      }
      this.confirmOpen = false
      await this.load()
    },
    async call(fn) {
      try {
        return await fn()
      } catch (e) {
        toast.error(e?.message || '操作失败')
        return null
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        this.project = await implementationApi.current()
        if (this.project) {
          this.checks = (this.project.checks || []).map((c) => ({ ...c }))
          try {
            this.runtime = await implementationApi.runtimePresets(this.project.id)
          } catch (e) {
            this.runtime = null
          }
        }
      } catch (e) {
        this.error = e?.message || '实施项目加载失败'
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.iw-conclusions { display: flex; flex-wrap: wrap; gap: var(--space-4); }
.iw-item {
  min-width: 120px;
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
}
.iw-item__num { display: block; font-size: var(--font-size-xl); font-weight: var(--font-weight-semibold); }
.iw-item__label { display: block; color: var(--text-secondary); font-size: var(--font-size-xs); }
.iw-blocked { color: var(--color-danger); font-weight: var(--font-weight-medium); }
.iw-list { margin: var(--space-2) 0; padding-left: var(--space-4); }
.iw-links { display: flex; flex-wrap: wrap; gap: var(--space-4); }
</style>
