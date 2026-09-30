<template>
  <BasePortalLayout
    class="internship-portal"
    :inert="leaveVisible || undefined"
    :title="brandTitle"
    subtitle="岗位实习中心"
    workspace
    hide-global-workbench
    :workspace-navigate="resolveWorkspaceDestination"
    :ctx="ctx"
    @menu-select="onMenuSelect"
  >
    <!-- 仅「模块授权计算失败」用横幅；权限/批次硬阻断由下方 ErrorState 独占，避免重复提示 -->
    <div v-if="serviceBanner" class="ix-svc-banner" role="alert">
      <span>{{ serviceBanner }}</span>
      <button type="button" class="mp-link" @click="reloadContext">重试</button>
    </div>
    <InternshipBatchStrip v-if="ctx && !hasBusinessHeader && !permissionServiceBlocked && !batchBlocked" />
    <!-- 子页只能在统一批次 Authority 完成首轮解析后挂载；否则 immediate watcher 会先发无 batchId 请求。 -->
    <div class="ix-content"><ErrorState
      v-if="contextError"
      title="岗位实习中心暂未加载成功"
      :description="contextError"
      @retry="reloadContext"
    /><router-view
      v-else-if="ctx && !permissionServiceBlocked && !batchBlocked && batchContextReady"
      :key="batchStore.selectedBatchId || 'no-batch'"
      :ctx="ctx"
    />
    <ErrorState
      v-else-if="permissionServiceBlocked"
      title="权限服务加载失败"
      :description="ctx.permissionServiceError || '权限服务加载失败'"
      @retry="reloadContext"
    />
    <ErrorState
      v-else-if="batchBlocked"
      title="批次服务暂不可用"
      :description="batchStore.batchError || '批次列表加载失败，已保留上次选择；恢复前请勿按全历史数据操作'"
      @retry="reloadBatches"
    />
    <LoadingState
      v-else-if="ctx && !batchContextReady"
      text="正在加载当前实习批次…"
    />
    <LoadingState v-else-if="!ctx" text="正在加载岗位实习中心…" /></div>
    <Teleport to="body"><div ref="leaveDialogHost" @keydown.esc.stop.prevent="settleLeave(false)" @keydown.tab="containLeaveFocus">
      <AppConfirmDialog :visible="leaveVisible" title="离开当前表单？" :message="leaveMessage"
        type="warning" confirm-text="放弃修改并离开" cancel-text="继续编辑"
        @confirm="settleLeave(true)" @cancel="settleLeave(false)" />
    </div></Teleport>
  </BasePortalLayout>
</template>

<script>
import { provideBusinessHeader } from '@/components/business/businessHeader'
/**
 * AdminInternshipLayout — /admin/internship 父布局。
 * 侧栏二级/三级菜单由 BasePortalLayout + navPlan.js（getVisibleNavPlan）渲染，禁止在此硬编码业务菜单。
 * 品牌名 / 角色 / 数据范围来自 internshipApi.getContext()；ctx 下发给子路由避免重复拉取。
 * 批次条：统一写入 URL query.batchId，子页不得静默猜批次。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState, ErrorState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { internshipPickerAdapters } from '@/modules/internship/pickerAdapters'
import InternshipBatchStrip from './_shared/InternshipBatchStrip.vue'
import { withInternshipBatch } from '../navigation.js'
import { useInternshipBatchStore } from '@/stores/internshipBatch'

export default {
  setup() { return { hasBusinessHeader: provideBusinessHeader(InternshipBatchStrip) } },
  name: 'AdminInternshipLayout',
  components: { BasePortalLayout, LoadingState, ErrorState, InternshipBatchStrip, AppConfirmDialog },
  provide() {
    return { appPickerAdapters: internshipPickerAdapters }
  },
  data() {
    return { ctx: null, contextError: '', contextLoading: false, contextTicket: 0, leaveVisible: false, leaveMessage: '' }
  },
  computed: {
    brandTitle() {
      if (!this.ctx) return '管理端'
      return (this.ctx.tenantBrandConfig?.schoolName || '岗位实习') + ' · 管理端'
    },
    batchStore() {
      return useInternshipBatchStore()
    },
    batchContextReady() {
      return this.batchStore.initialized && !this.batchStore.batchLoading
    },
    permissionServiceBlocked() {
      return !!(this.ctx && this.ctx.permissionServiceError)
    },
    batchBlocked() {
      return !!(this.ctx && this.batchStore.batchLoadFailed && !this.batchStore.hasBatch)
    },
    serviceBanner() {
      if (!this.ctx) return ''
      // 硬阻断场景由 ErrorState 展示；批次软失败由批次条内联提示
      if (this.permissionServiceBlocked || this.batchBlocked) return ''
      if (this.ctx.moduleAccessHealthy === false) {
        return this.ctx.moduleAccessError || '模块授权计算失败'
      }
      return ''
    }
  },
  watch: {
    '$route.query.batchId': {
      immediate: true,
      handler(id) {
        if (!this.ctx || this.permissionServiceBlocked) return
        this.batchStore.ensureLoaded({ batchIdFromUrl: id || '', force: !!id })
      }
    }
  },
  async created() {
    await this.reloadContext()
  },
  mounted() {
    this.removeLeaveConfirmation = window.__SAAS_DIRTY_FORM_GUARD__?.registerConfirmation?.(this.requestLeave)
  },
  beforeUnmount() {
    this.contextTicket++
    this.removeLeaveConfirmation?.()
    this.settleLeave(false)
  },
  methods: {
    requestLeave(message) {
      this.leaveResolver?.(false)
      this.leaveMessage = message
      this.leaveVisible = true
      this.leaveFocus = document.activeElement
      this.$nextTick(() => {
        const host = this.$refs.leaveDialogHost
        host?.querySelector('[role="dialog"]')?.setAttribute('aria-label', '离开当前表单？')
        host?.querySelector('button')?.focus()
      })
      return new Promise(resolve => { this.leaveResolver = resolve })
    },
    settleLeave(accepted) {
      this.leaveVisible = false
      const resolve = this.leaveResolver
      this.leaveResolver = null
      resolve?.(accepted === true)
      if (!accepted) this.$nextTick(() => { if (this.leaveFocus?.isConnected) this.leaveFocus.focus() })
    },
    containLeaveFocus(event) {
      if (!this.leaveVisible) return
      const buttons = [...this.$refs.leaveDialogHost.querySelectorAll('button:not(:disabled)')]
      const first = buttons[0], last = buttons[buttons.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    },
    resolveWorkspaceDestination(path) {
      return withInternshipBatch(path, this.batchStore.selectedBatchId)
    },
    async reloadContext() {
      if (this.contextLoading) return
      const ticket = ++this.contextTicket
      this.contextLoading = true
      this.contextError = ''
      try {
        const res = await internshipApi.getContext()
        if (ticket !== this.contextTicket) return
        if (res?.code !== 0 || !res.data) throw new Error(res?.message || '当前身份信息加载失败，请重试')
        if (!Array.isArray(res.data.permissionPatterns) && !res.data.permissionServiceError) {
          throw new Error('当前身份信息未能完整加载，请重试；如登录已失效，请重新登录')
        }
        this.ctx = res.data
        if (this.permissionServiceBlocked) return
        await this.reloadBatches()
      } catch (error) {
        if (ticket !== this.contextTicket) return
        this.ctx = null
        this.contextError = error.message || '岗位实习中心加载失败，请重试'
      } finally {
        if (ticket === this.contextTicket) this.contextLoading = false
      }
    },
    async reloadBatches() {
      await this.batchStore.ensureLoaded({
        batchIdFromUrl: this.$route.query.batchId || '',
        force: true
      })
      if (this.batchStore.selectedBatchId && !this.$route.query.batchId) {
        this.$router.replace({
          query: { ...this.$route.query, batchId: this.batchStore.selectedBatchId }
        }).catch(() => {})
      }
    },
    onMenuSelect(item) {
      if (!item?.path) return
      this.$router.push(withInternshipBatch(item.path, this.batchStore.selectedBatchId)).catch(() => {})
    }
  }
}
</script>

<style scoped>
.ix-svc-banner {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  align-items: center;
  padding: 8px 16px;
  background: #fef2f2;
  color: #991b1b;
  border-bottom: 1px solid #fecaca;
  font-size: 13px;
}
</style>
