<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="教务中心"
    :ctx="ctx"
    @menu-select="onMenuSelect"
  >
    <template v-if="ctx">
      <div v-if="isArchiveArea && canManageArchive" class="aa-ops-strip">
        <div>
          <strong>{{ isSemesterPilot ? '真实学期验收' : '生产验收工具' }}</strong>
          <span>{{ isSemesterPilot ? '只读取真实学校正式事实并冻结六阶段证据，不生成业务数据。' : '真实学校完整学期上线时，可进入隐藏验收工作区。' }}</span>
        </div>
        <button v-if="!isSemesterPilot" type="button" @click="openSemesterPilot">真实学期验收</button>
        <button v-else type="button" @click="closeSemesterPilot">返回教务归档</button>
      </div>
      <AaSemesterPilotView v-if="isSemesterPilot && canManageArchive" />
      <template v-if="!(isSemesterPilot && canManageArchive)">
        <router-view v-if="ctx" :ctx="ctx" />
      </template>
    </template>
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
 * W5：真实学期验收使用归档页隐藏 query 工作区，不新增 navPlan 菜单，不扩大普通 archive.view 权限。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { ErrorState, LoadingState } from '@/components/business'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { academicAffairsPickerAdapters } from '@/modules/academicAffairs/pickerAdapters'
import AaSemesterPilotView from '@/modules/academicAffairs/views/AaSemesterPilotView.vue'
import { matchPermission } from '@/config/navPlan'
import router from '@/router'

export default {
  name: 'AdminAcademicAffairsLayout',
  components: { BasePortalLayout, ErrorState, LoadingState, AaSemesterPilotView },
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
    },
    isArchiveArea() {
      return String(this.$route.path || '').startsWith('/admin/academic-affairs/archive')
    },
    isSemesterPilot() {
      return this.isArchiveArea && this.$route.query?.ops === 'semester-pilot'
    },
    canManageArchive() {
      const patterns = this.ctx?.permissionPatterns
      return Array.isArray(patterns) && matchPermission(patterns, 'academicAffairs.archive.manage')
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
        if (import.meta.env && import.meta.env.PROD && !Array.isArray(res.data.permissionPatterns)) {
          throw new Error('权限上下文读取失败。为保护学校数据，教务菜单已停止加载，请重新登录后再试。')
        }
        this.ctx = res.data
      } catch (err) {
        this.error = (err && err.message) || '请检查网络或重新登录后再试'
      }
    },
    openSemesterPilot() {
      router.push({ path: '/admin/academic-affairs/archive', query: { ...this.$route.query, ops: 'semester-pilot' } }).catch(() => {})
    },
    closeSemesterPilot() {
      const query = { ...this.$route.query }
      delete query.ops
      router.push({ path: '/admin/academic-affairs/archive', query }).catch(() => {})
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

<style scoped>
.aa-ops-strip { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin: 0 0 14px; padding: 10px 12px; border: 1px solid var(--border-light, #e5e7eb); border-radius: 10px; background: var(--bg-section, #f8fafc); }
.aa-ops-strip > div { min-width: 0; display: grid; gap: 3px; }
.aa-ops-strip strong { color: var(--text-primary, #0f172a); font-size: 13px; }
.aa-ops-strip span { color: var(--text-tertiary, #64748b); font-size: 12px; }
.aa-ops-strip button { flex: 0 0 auto; border: 1px solid var(--primary-300, #93c5fd); border-radius: 8px; background: var(--bg-card, #fff); color: var(--primary-700, #1d4ed8); padding: 7px 10px; cursor: pointer; }
@media (max-width: 720px) { .aa-ops-strip { align-items: stretch; flex-direction: column; } .aa-ops-strip button { align-self: flex-start; } }
</style>