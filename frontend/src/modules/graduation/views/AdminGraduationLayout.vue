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
      description="真实权限未加载成功前，写操作已禁用。请检查网络后重试，或联系管理员确认角色授权。"
      class="gd-scope-alert"
    />
    <AppInlineAlert
      v-else-if="ctx && ctx.scopeHint"
      type="warning"
      title="数据范围未就绪"
      :description="ctx.scopeHint"
      class="gd-scope-alert"
    />
    <GraduationBatchStrip v-if="ctx" class="gd-batch-bar" />
    <router-view v-if="canRenderBusiness" :ctx="businessCtx" />
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
/**
 * AdminGraduationLayout — /admin/graduation 父布局。
 * 侧栏由 BasePortalLayout + navPlan（graduationWorkspaces 8 工作区）驱动，禁止本文件硬编码业务菜单。
 * 统一提供批次上下文（Pinia）与权限 fail-safe（permissionReady / scopeReady）。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState, EmptyState } from '@/components/business'
import { AppInlineAlert } from '@/components/common'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { graduationPickerAdapters } from '@/modules/graduation/pickerAdapters'
import { useGraduationBatchStore } from '@/stores/graduationBatch'
import GraduationBatchStrip from './_shared/GraduationBatchStrip.vue'
import router from '@/router'

export default {
  name: 'AdminGraduationLayout',
  components: { BasePortalLayout, LoadingState, EmptyState, AppInlineAlert, GraduationBatchStrip },
  provide() {
    return { appPickerAdapters: graduationPickerAdapters }
  },
  data() {
    return {
      loading: true,
      ctx: null,
      contextError: '',
      permissionReady: false,
      scopeReady: false
    }
  },
  computed: {
    brandTitle() {
      if (!this.ctx) return '管理端'
      return (this.ctx.tenantBrandConfig?.schoolName || '管理端') + ' · 管理端'
    },
    layoutCtx() {
      // 布局壳可用静态壳；写权限与业务加载由 permissionReady / scopeReady 门禁
      return this.ctx
    },
    canRenderBusiness() {
      return !!(this.ctx && this.permissionReady && this.scopeReady)
    },
    businessCtx() {
      if (!this.ctx) return null
      return {
        ...this.ctx,
        permissionReady: this.permissionReady,
        scopeReady: this.scopeReady,
        writeEnabled: this.permissionReady && !this.ctx.readonlyTenant,
        contextError: this.contextError
      }
    }
  },
  watch: {
    '$route.query.batchId': {
      immediate: true,
      handler(id) {
        const store = useGraduationBatchStore()
        store.ensureLoaded({ batchIdFromUrl: id || '', force: !store.initialized })
      }
    }
  },
  async created() {
    await this.loadContext()
  },
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
          permissionActions: {},
          permissionPatterns: null
        }
        this.permissionReady = false
        this.scopeReady = false
        this.contextError = res.message || '权限上下文加载失败'
        return
      }
      this.ctx = res.data
      this.permissionReady = !!res.data.permissionReady
      // 需要组织范围但未配置 → 不加载业务列表
      const needsScope = !!res.data.roleNeedsOrgScope
      const configured = res.data.scopeConfigured !== false
      this.scopeReady = !(needsScope && !configured)
      if (!this.permissionReady) {
        this.contextError = res.data.permissionError || '真实权限未加载成功，写操作已禁用'
      }
      const store = useGraduationBatchStore()
      await store.ensureLoaded({
        batchIdFromUrl: this.$route.query.batchId || '',
        force: true
      })
      this.syncBatchToUrl()
    },
    syncBatchToUrl() {
      const store = useGraduationBatchStore()
      const cur = this.$route.query.batchId ? String(this.$route.query.batchId) : ''
      const next = store.selectedBatchId || ''
      if (next && next !== cur) {
        router.replace({ query: { ...this.$route.query, batchId: next } }).catch(() => {})
      }
    },
    onMenuSelect(item) {
      if (item?.path && item.path !== this.$route.fullPath.split('#')[0]) {
        const store = useGraduationBatchStore()
        const path = item.path
        const hasQuery = path.includes('?')
        const batchQ = store.selectedBatchId ? `batchId=${encodeURIComponent(store.selectedBatchId)}` : ''
        let target = path
        if (batchQ && !/[?&]batchId=/.test(path)) {
          target = hasQuery ? `${path}&${batchQ}` : `${path}?${batchQ}`
        }
        router.push(target).catch(() => {})
      }
    }
  }
}
</script>

<style scoped>
.gd-scope-alert {
  margin: 0 0 var(--space-4);
}
.gd-batch-bar {
  margin: 0 0 var(--space-3);
}
</style>
