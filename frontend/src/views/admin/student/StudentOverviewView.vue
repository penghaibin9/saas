<template>
  <div class="sp-page">
    <AppSectionHeader index="01" title="学生主档与身份中心" subtitle="全系统统一学生数据底座：主档、身份、学籍、监护人、数据范围与审计" />
    <StudentStateBlock :loading="loading" :error="error" :empty="!overview" :no-permission="noPermission" @retry="load">
      <template v-if="overview">
        <div class="sp-grid">
          <AppCard class="sp-metric" hoverable @click="go('/admin/student/list')">
            <span class="sp-metric__label">学生总数</span>
            <span class="sp-metric__value">{{ overview.totalCount }}</span>
            <span class="sp-metric__hint">点击进入学生列表</span>
          </AppCard>
          <AppCard class="sp-metric">
            <span class="sp-metric__label">在校学生</span>
            <span class="sp-metric__value">{{ overview.activeCount }}</span>
          </AppCard>
          <AppCard class="sp-metric" hoverable @click="go('/admin/student/identity')">
            <span class="sp-metric__label">待身份核验</span>
            <span class="sp-metric__value">{{ overview.pendingVerifyCount }}</span>
            <span class="sp-metric__hint">进入身份认证管理</span>
          </AppCard>
          <AppCard class="sp-metric">
            <span class="sp-metric__label">资料缺失</span>
            <span class="sp-metric__value">{{ overview.dataMissingCount }}</span>
          </AppCard>
          <AppCard class="sp-metric">
            <span class="sp-metric__label">学业预警</span>
            <span class="sp-metric__value">{{ overview.academicWarningCount }}</span>
          </AppCard>
          <AppCard class="sp-metric">
            <span class="sp-metric__label">账号未绑定</span>
            <span class="sp-metric__value">{{ overview.accountUnboundCount }}</span>
          </AppCard>
        </div>

        <div class="sp-cols">
          <AppCard class="sp-card">
            <AppSectionHeader title="最近状态变更" compact />
            <StudentTimeline :items="overview.recentStatusChanges" />
          </AppCard>
          <AppCard class="sp-card">
            <AppSectionHeader title="最近身份核验" compact />
            <StudentTimeline :items="overview.recentVerifies" />
          </AppCard>
        </div>

        <AppCard class="sp-card">
          <AppSectionHeader title="高频入口" compact />
          <div class="sp-actions-row">
            <AppButton variant="secondary" @click="go('/admin/student/list')">学生列表</AppButton>
            <AppButton variant="secondary" @click="go('/admin/student/identity')">身份认证</AppButton>
            <AppButton variant="secondary" @click="go('/admin/student/status')">状态管理</AppButton>
            <AppButton variant="secondary" @click="go('/admin/student/import-export')">导入导出</AppButton>
          </div>
        </AppCard>
      </template>
    </StudentStateBlock>
  </div>
</template>

<script>
/** 页面 2：/admin/student 学生主档概览 */
import { AppCard, AppButton, AppSectionHeader } from '@/components/ui'
import StudentStateBlock from '@/modules/student/components/StudentStateBlock.vue'
import StudentTimeline from '@/modules/student/components/StudentTimeline.vue'
import { studentProvider, hasStudentPermission, STUDENT_PERMISSION } from '@/modules/student'

export default {
  name: 'StudentOverviewView',
  components: { AppCard, AppButton, AppSectionHeader, StudentStateBlock, StudentTimeline },
  data() {
    return { loading: false, error: '', overview: null }
  },
  computed: {
    noPermission() {
      return !hasStudentPermission(STUDENT_PERMISSION.PROFILE_VIEW)
    }
  },
  created() {
    if (!this.noPermission) this.load()
  },
  methods: {
    go(path) {
      this.$router.push(path)
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        const res = await studentProvider.getStudentOverview()
        if (res.code === 0) this.overview = res.data
        else this.error = res.message
      } catch (e) {
        this.error = e.message || '加载失败'
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
@import './student-page.css';
</style>
