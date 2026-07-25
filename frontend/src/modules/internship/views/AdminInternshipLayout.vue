<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="岗位实习中心"
    :ctx="ctx"
    @menu-select="onMenuSelect"
  >
    <div v-if="serviceBanner" class="ix-svc-banner" role="alert">
      <span>{{ serviceBanner }}</span>
      <button type="button" class="mp-link" @click="reloadContext">重试</button>
    </div>
    <InternshipBatchStrip v-if="ctx && !permissionServiceBlocked" />
    <router-view v-if="ctx && !permissionServiceBlocked && !batchBlocked && batchReady" :ctx="ctx" />
    <ErrorState
      v-else-if="permissionServiceBlocked"
      title="权限服务加载失败"
      :description="serviceBanner"
      @retry="reloadContext"
    />
    <ErrorState
      v-else-if="batchBlocked"
      title="批次服务暂不可用"
      :description="batchStore.batchError || '批次列表加载失败，已保留上次选择；恢复前请勿按全历史数据操作'"
      @retry="reloadBatches"
    />
    <LoadingState v-else-if="!ctx || !batchReady" text="正在加载岗位实习中心…" />
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
    batchReady() {
      // 批次首轮已判定（成功/空/需显式选择/URL 无效）或加载失败已保留兜底，才允许子页渲染。
      // 关键：F5 硬刷新时子页读取 batchStore.selectedBatchId 拉数据，若在批次判定完成前抢跑，
      // 会用空 batchId 触发后端 400「必须指定实习批次 batchId」。此门确保子页拿到 URL/存储中的批次后再挂载。
      const s = this.batchStore
      return s.initialized || s.batchLoadFailed
    },
    serviceBanner() {
      if (!this.ctx) return ''
      if (this.ctx.permissionServiceError) return this.ctx.permissionServiceError
      if (this.ctx.moduleAccessHealthy === false) {
        return this.ctx.moduleAccessError || '模块授权计算失败'
      }
      if (this.batchStore.batchLoadFailed) return this.batchStore.batchError
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
