<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="教务中心"
    :ctx="ctx"
    @menu-select="onMenuSelect"
  >
    <router-view v-if="ctx" :ctx="ctx" />
    <ErrorState
      v-else-if="error"
      title="教务中心加载失败"
      :description="error"
      @retry="loadContext"
      @back="goWorkbench"
    />
    <LoadingState v-else text="正在加载教务中心…" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminAcademicAffairsLayout — /admin/academic-affairs 父布局（13B 教务中心）。
 * 侧栏二级/三级菜单由 BasePortalLayout + navPlan.js（getVisibleNavPlan）渲染，禁止在此硬编码业务菜单。
 * 品牌名 / 角色 / 数据范围来自 academicAffairsApi.getContext()；ctx 下发给子路由避免重复拉取。
 * 上下文加载失败必须显式展示错误与重试，禁止永久停留 Loading，也禁止注入空权限上下文扩大菜单。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { ErrorState, LoadingState } from '@/components/business'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { academicAffairsPickerAdapters } from '@/modules/academicAffairs/pickerAdapters'
import router from '@/router'

export default {
  name: 'AdminAcademicAffairsLayout',
  components: { BasePortalLayout, ErrorState, LoadingState },
  provide() {
    return { appPickerAdapters: academicAffairsPickerAdapters }
  },
  data() {
    return { ctx: null, error: '' }
  },
  computed: {
    brandTitle() {
      if (!this.ctx) return '管理端'
      const school = this.ctx.tenantBrandConfig && this.ctx.tenantBrandConfig.schoolName
      return `${school || '学校'} · 管理端`
    }
  },
  created() {
    this.loadContext()
  },
  methods: {
    async loadContext() {
      this.error = ''
      this.ctx = null
      try {
        const res = await academicAffairsApi.getContext()
        if (!res || res.code !== 0 || !res.data) {
          throw new Error((res && res.message) || '无法读取当前角色、权限和数据范围')
        }
        this.ctx = res.data
      } catch (err) {
        this.error = (err && err.message) || '请检查网络或重新登录后再试'
      }
    },
    goWorkbench() {
      router.push('/').catch(() => {})
    },
    onMenuSelect(item) {
      if (item?.path && item.path !== this.$route.fullPath.split('#')[0]) {
        router.push(item.path).catch(() => {})
      }
    }
  }
}
</script>
