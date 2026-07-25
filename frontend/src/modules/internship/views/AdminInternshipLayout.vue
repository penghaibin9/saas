<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="岗位实习中心"
    :ctx="ctx"
    @menu-select="onMenuSelect"
  >
    <!-- 仅「模块授权计算失败」用横幅；权限/批次硬阻断由下方 ErrorState 独占，避免重复提示 -->
    <div v-if="serviceBanner" class="ix-svc-banner" role="alert">
      <span>{{ serviceBanner }}</span>
      <button type="button" class="mp-link" @click="reloadContext">重试</button>
    </div>
    <InternshipBatchStrip v-if="ctx && !permissionServiceBlocked && !batchBlocked" />
    <router-view v-if="ctx && !permissionServiceBlocked && !batchBlocked" :ctx="ctx" />
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
    <LoadingState v-else-if="!ctx" text="正在加载岗位实习中心…" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminInternshipLayout — /admin/internship 父布局。
 * 侧栏二级/三级菜单由 BasePortalLayout + navPlan.js（getVisibleNavPlan）渲染，禁止在此硬编码业务菜单。
 * 品牌名 / 角色 / 数据范围来自 internshipApi.getContext()；ctx 下发给子路由避免重复拉取。
 * 批次条：统一写入 URL query.batchId，子页不得静默猜批次。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState, ErrorState } from '@/components/business'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { internshipPickerAdapters } from '@/modules/internship/pickerAdapters'
import InternshipBatchStrip from './_shared/InternshipBatchStrip.vue'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import router from '@/router'

export default {
  name: 'AdminInternshipLayout',
  components: { BasePortalLayout, LoadingState, ErrorState, InternshipBatchStrip },
  provide() {
    return { appPickerAdapters: internshipPickerAdapters }
  },
  data() {
    return { ctx: null }
  },
  computed: {
    brandTitle() {
      if (!this.ctx) return '管理端'
      return this.ctx.tenantBrandConfig.schoolName + ' · 管理端'
    },
    batchStore() {
      return useInternshipBatchStore()
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
  methods: {
    async reloadContext() {
      const res = await internshipApi.getContext()
      if (res.code === 0) this.ctx = res.data
      if (this.permissionServiceBlocked) return
      await this.reloadBatches()
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
      const batchQ = this.batchStore.withBatchQuery({})
      const raw = String(item.path)
      const qIdx = raw.indexOf('?')
      if (qIdx < 0) {
        router.push({ path: raw, query: batchQ }).catch(() => {})
        return
      }
      const path = raw.slice(0, qIdx) || '/'
      const search = new URLSearchParams(raw.slice(qIdx + 1))
      const query = { ...Object.fromEntries(search.entries()), ...batchQ }
      router.push({ path, query }).catch(() => {})
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
