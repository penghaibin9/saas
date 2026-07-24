<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="岗位实习中心"
    :ctx="ctx"
    @menu-select="onMenuSelect"
  >
    <InternshipBatchStrip v-if="ctx" />
    <router-view v-if="ctx" :ctx="ctx" />
    <LoadingState v-else text="正在加载岗位实习中心…" />
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
import { LoadingState } from '@/components/business'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { internshipPickerAdapters } from '@/modules/internship/pickerAdapters'
import InternshipBatchStrip from './_shared/InternshipBatchStrip.vue'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import router from '@/router'

export default {
  name: 'AdminInternshipLayout',
  components: { BasePortalLayout, LoadingState, InternshipBatchStrip },
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
    }
  },
  watch: {
    '$route.query.batchId': {
      immediate: true,
      handler(id) {
        if (!this.ctx) return
        this.batchStore.ensureLoaded({ batchIdFromUrl: id || '', force: !!id })
      }
    }
  },
  async created() {
    const res = await internshipApi.getContext()
    if (res.code === 0) this.ctx = res.data
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
  methods: {
    onMenuSelect(item) {
      if (!item?.path) return
      const q = this.batchStore.withBatchQuery({})
      if (item.path.includes('?')) {
        router.push(item.path).catch(() => {})
      } else {
        router.push({ path: item.path, query: q }).catch(() => {})
      }
    }
  }
}
</script>
