<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="毕业设计中心"
    :ctx="layoutCtx"
    @menu-select="onMenuSelect"
  >
    <AppInlineAlert
      v-if="ctx && contextError"
      type="danger"
      title="权限上下文加载失败"
      :description="contextError"
      class="gd-scope-alert"
    />
    <AppInlineAlert
      v-else-if="ctx && !permissionReady"
      type="warning"
      title="权限尚未就绪"
      description="真实权限未加载成功前，写操作暂不可用。请检查网络后重试，或联系管理员确认角色授权。"
      class="gd-scope-alert"
    />
    <AppInlineAlert
      v-else-if="ctx && ctx.scopeHint"
      type="warning"
      title="数据范围未就绪"
      :description="ctx.scopeHint"
      class="gd-scope-alert"
    />

    <div v-if="ctx" class="gd-batch-context" aria-label="当前毕业设计批次">
      <GraduationBatchStrip class="gd-batch-bar" />
    </div>

    <div
      v-if="canRenderBusiness"
      class="gd-business-view"
      :class="{ 'gd-student-readonly': isStudentList && !canManageStudents }"
    >
      <AppInlineAlert
        v-if="isStudentList && !canManageStudents"
        type="info"
        title="当前为只读名单视图"
        description="你可以查看本数据范围内的毕设学生、进度和材料状态；建档、导师分配、选题、资格认定、分组、答辩组分配与归档仅对具有学生管理权限的角色开放。"
        class="gd-scope-alert"
      />
      <AppInlineAlert
        v-if="isReminderWorkspace"
        type="info"
        title="催交会发送真实站内消息"
        description="点击催交后，系统会向该学生创建真实站内消息并写入催办留痕；请勿因旧页面缓存而重复电话或微信催办。"
        class="gd-scope-alert"
      />
      <GraduationExtensionAdminPanel v-if="isExtensionWorkspace" :ctx="businessCtx" />
      <router-view v-else :key="businessViewKey" :ctx="businessCtx" />
    </div>
    <LoadingState v-else-if="loading" text="正在加载毕业设计中心…" />
    <EmptyState
      v-else-if="!scopeReady && ctx"
      title="数据范围未配置"
      description="当前角色需要学院/专业数据范围后才能查看业务列表。请先在系统管理完成组织范围配置，或切换到已授权角色。"
    />
    <EmptyState
      v-else
      title="无法进入毕业设计中心"
      description="权限上下文不可用。请刷新页面重试；若持续失败，请联系学校管理员。"
    />
  </BasePortalLayout>
</template>

<script>
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState, EmptyState } from '@/components/business'
import { AppInlineAlert } from '@/components/common'
import { matchPermission } from '@/config/navPlan'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { graduationPickerAdapters } from '@/modules/graduation/pickerAdapters'
import '@/modules/graduation/styles/graduation-workspaces.css'
import { useGraduationBatchStore } from '@/stores/graduationBatch'
import GraduationBatchStrip from './_shared/GraduationBatchStrip.vue'
import GraduationExtensionAdminPanel from './GraduationExtensionAdminPanel.vue'
import router from '@/router'

export default {
  name: 'AdminGraduationLayout',
  components: {
    BasePortalLayout, LoadingState, EmptyState, AppInlineAlert,
    GraduationBatchStrip, GraduationExtensionAdminPanel
  },
  provide() { return { appPickerAdapters: graduationPickerAdapters } },
  data() {
    return { loading: true, ctx: null, contextError: '', permissionReady: false, scopeReady: false }
  },
  computed: {
    brandTitle() {
      if (!this.ctx) return '管理端'
      return (this.ctx.tenantBrandConfig?.schoolName || '管理端') + ' · 管理端'
    },
    layoutCtx() { return this.ctx },
    canRenderBusiness() { return !!(this.ctx && this.permissionReady && this.scopeReady) },
    isStudentList() { return this.$route.name === 'graduation-students' },
    isReminderWorkspace() { return ['graduation-proposals', 'graduation-finals'].includes(this.$route.name) },
    isExtensionWorkspace() {
      return this.$route.name === 'graduation-dashboard' && ['excellent', 'delay'].includes(String(this.$route.query.extension || ''))
    },
    canManageStudents() {
      const patterns = this.ctx?.permissionPatterns
      return Array.isArray(patterns) && matchPermission(patterns, 'graduationDesign.student.manage')
    },
    businessViewKey() {
      return `${this.$route.name || this.$route.path}|${this.$route.meta?.defaultPanel || ''}`
    },
    businessCtx() {
      if (!this.ctx) return null
      const studentListWrite = !this.isStudentList || this.canManageStudents
      return {
        ...this.ctx,
        permissionReady: this.permissionReady,
        scopeReady: this.scopeReady,
        writeEnabled: this.permissionReady && !this.ctx.readonlyTenant && studentListWrite,
        contextError: this.contextError
      }
    }
  },
  watch: {
    '$route.query.batchId': {
      immediate: true,
      async handler(id) {
        const store = useGraduationBatchStore()
        await store.ensureLoaded({ batchIdFromUrl: id || '', force: !store.initialized })
        // BasePortalLayout owns generic leaf navigation and may complete its
        // path-only push after this module has emitted a batch-aware target.
        // Graduation owns the selected batch, so repair only a missing query
        // from the store; never replace an explicit batchId from the URL.
        if (!id && this.$route.path.startsWith('/admin/graduation')) {
          await this.syncBatchToUrl()
        }
      }
    },
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        if (panel === 'grad-qual') {
          router.replace({ query: { ...this.$route.query, panel: 'roster' } }).catch(() => {})
        }
      }
    }
  },
  async created() { await this.loadContext() },
  methods: {
    async loadContext() {
      this.loading = true
      this.contextError = ''
      const res = await graduationApi.getContext()
      this.loading = false
      if (res.code !== 0 || !res.data) {
        this.ctx = {
          tenantBrandConfig: { schoolName: '管理端' },
          currentRole: { roleName: '未识别' },
          dataScope: { scopeName: '未知' },
          permissionActions: {}, permissionPatterns: null
        }
        this.permissionReady = false
        this.scopeReady = false
        this.contextError = res.message || '权限上下文加载失败'
        return
      }
      this.ctx = res.data
      this.permissionReady = !!res.data.permissionReady
      const needsScope = !!res.data.roleNeedsOrgScope
      const configured = res.data.scopeConfigured !== false
      this.scopeReady = !(needsScope && !configured)
      if (!this.permissionReady) this.contextError = res.data.permissionError || '真实权限未加载成功，写操作已禁用'
      const store = useGraduationBatchStore()
      await store.ensureLoaded({ batchIdFromUrl: this.$route.query.batchId || '', force: true })
      await this.syncBatchToUrl()
    },
    async syncBatchToUrl() {
      const store = useGraduationBatchStore()
      const cur = this.$route.query.batchId ? String(this.$route.query.batchId) : ''
      const next = store.selectedBatchId || ''
      if (next && next !== cur) {
        await router.replace({ query: { ...this.$route.query, batchId: next } }).catch(() => {})
      }
    },
    onMenuSelect(item) {
      if (item?.path && item.path !== this.$route.fullPath.split('#')[0]) {
        const store = useGraduationBatchStore()
        const path = item.path
        const batchQ = store.selectedBatchId ? `batchId=${encodeURIComponent(store.selectedBatchId)}` : ''
        let target = path
        if (batchQ && !/[?&]batchId=/.test(path)) target = path.includes('?') ? `${path}&${batchQ}` : `${path}?${batchQ}`
        router.push(target).catch(() => {})
      }
    }
  }
}
</script>

<style scoped>
.gd-scope-alert { margin: 0 0 var(--space-3); }
.gd-batch-context {
  display: flex;
  justify-content: flex-end;
  min-width: 0;
  margin: 0 0 var(--space-2);
}
.gd-batch-bar {
  width: fit-content;
  max-width: 100%;
  min-height: 38px;
  padding: 4px 9px;
  border-color: var(--primary-100, #dbeafe);
  border-radius: var(--radius-lg, 10px);
  background: linear-gradient(100deg, var(--primary-50, #eff6ff), var(--card, #fff));
  box-shadow: 0 8px 24px -24px rgba(37, 99, 235, .65);
}
.gd-batch-bar :deep(.gbs__label) {
  color: var(--primary-700, #1d4ed8);
  font-size: var(--font-size-xs, 12px);
  font-weight: 700;
}
.gd-batch-bar :deep(.gbs__select) {
  min-width: 210px;
  max-width: min(420px, 48vw);
  min-height: 28px;
  padding-top: 2px;
  padding-bottom: 2px;
  border-color: var(--primary-200, #bfdbfe);
}
.gd-batch-bar :deep(.gbs__meta),
.gd-batch-bar :deep(.gbs__text) { font-size: var(--font-size-xs, 12px); }
.gd-student-readonly :deep(.mp-link + .mp-link) { display: none !important; }

.gd-business-view { min-width: 0; }
.gd-business-view :deep(.mp-stack) { gap: var(--space-3); }
.gd-business-view :deep(.mp-card) {
  border-color: var(--border-light, #e2e8f0);
  box-shadow: none;
}
.gd-business-view :deep(.mp-card__head) {
  min-height: 46px;
  padding: var(--space-3) var(--space-4);
}
.gd-business-view :deep(.mp-card__body) { padding: var(--space-4); }
.gd-business-view :deep(.mp-tabs) {
  display: flex;
  align-items: center;
  gap: 4px;
  max-width: 100%;
  padding: 4px;
  overflow-x: auto;
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: var(--radius-md, 8px);
  background: var(--gray-50, #f8fafc);
  scrollbar-width: thin;
}
.gd-business-view :deep(.mp-tab) {
  flex: 0 0 auto;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 6px;
  white-space: nowrap;
}
.gd-business-view :deep(.mp-tab.is-active) {
  background: var(--card, #fff);
  box-shadow: 0 1px 2px rgba(15, 23, 42, .08);
}
.gd-business-view :deep(.gd-actions),
.gd-business-view :deep(.ie-actions),
.gd-business-view :deep(.mp-toolbar) {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.gd-business-view :deep(.mp-note) {
  max-width: 100%;
  color: var(--text-tertiary, #64748b);
  line-height: 1.55;
}
.gd-business-view :deep(.mp-cell-main),
.gd-business-view :deep(.mp-cell-sub) { overflow-wrap: anywhere; }
.gd-business-view :deep(table) {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
}
.gd-business-view :deep(th) {
  position: sticky;
  top: 0;
  z-index: 2;
  background: var(--gray-50, #f8fafc);
  color: var(--text-secondary, #475569);
  font-weight: 600;
  white-space: nowrap;
}
.gd-business-view :deep(th),
.gd-business-view :deep(td) {
  padding-top: 10px;
  padding-bottom: 10px;
  vertical-align: top;
}
.gd-business-view :deep(.mp-link),
.gd-business-view :deep(.mp-btn) { white-space: nowrap; }
.gd-business-view :deep(textarea),
.gd-business-view :deep(input),
.gd-business-view :deep(select) { max-width: 100%; }
.gd-business-view :deep(.mp-pagination),
.gd-business-view :deep(.pagination) {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--space-2);
}

@media (max-width: 900px) {
  .gd-batch-context { justify-content: flex-start; }
  .gd-batch-bar { width: 100%; }
  .gd-batch-bar :deep(.gbs__select) { min-width: min(210px, 100%); max-width: 100%; }
  .gd-business-view :deep(.mp-card__head),
  .gd-business-view :deep(.mp-card__body) {
    padding-left: var(--space-3);
    padding-right: var(--space-3);
  }
  .gd-business-view :deep(.mp-grid-2) { grid-template-columns: 1fr; }
}
</style>
