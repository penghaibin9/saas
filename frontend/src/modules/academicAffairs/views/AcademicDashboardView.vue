<template>
  <ModulePageShell
    title="学业过程中心"
    :subtitle="hero.termName + '（' + hero.termRange + '）'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.name"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-stack">
      <ModuleHero
        :title="ctx.tenantBrandConfig.schoolName + ' · 学业过程总览'"
        :subtitle="'指标按当前数据范围实时计算 · 更新于 ' + hero.updateTime"
        :chips="heroChips"
        :stats="hero.kpis"
        :flow="hero.flow"
      />

      <div class="mp-grid-2">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">今日待办</span>
            <button class="mp-link" @click="$router.push('/admin/academic/students')">学业学生 →</button>
          </div>
          <div class="mp-card__body mp-stack">
            <div v-for="t in hero.todos" :key="t.id" class="mp-kv">
              <span class="mp-kv__k">
                <StatusTag type="warning" :label="String(t.value)" dot />
                <span class="adb-todo-label">{{ t.label }}</span>
              </span>
              <button class="mp-link" @click="goLink(t.link)">去处理</button>
            </div>
            <EmptyState v-if="!hero.todos.length" title="当前没有待办" description="待办与预警会按数据范围自动汇聚到这里" />
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">风险提醒</span>
            <button class="mp-link" @click="$router.push('/admin/academic/warnings')">学业预警 →</button>
          </div>
          <div class="mp-card__body">
            <ul class="mp-timeline">
              <li v-for="r in hero.riskAlerts" :key="r.id" class="mp-timeline__item" :class="r.level === 'HIGH' ? 'is-danger' : 'is-warning'">
                <div class="mp-timeline__title">
                  {{ r.title }}
                  <RiskTag :level="r.level" />
                </div>
                <div class="mp-timeline__desc">
                  <button class="mp-link" @click="goLink(r.link)">查看 →</button>
                </div>
              </li>
            </ul>
          </div>
        </section>
      </div>

      <section class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">最近导入批次（教务数据同步）</span>
          <button class="mp-link" @click="$router.push('/admin/academic/grades')">课程成绩 →</button>
        </div>
        <div class="mp-card__body">
          <table class="mp-audit">
            <thead>
              <tr><th>批次号</th><th>内容</th><th>时间</th><th>成功 / 总数</th><th>失败</th><th>操作人</th></tr>
            </thead>
            <tbody>
              <tr v-for="b in hero.recentImportBatches" :key="b.id">
                <td class="is-who">{{ b.id }}</td>
                <td>{{ b.name }}</td>
                <td>{{ b.time }}</td>
                <td>{{ b.success }} / {{ b.total }}</td>
                <td>
                  <StatusTag v-if="b.failed" type="danger" :label="b.failed + ' 条'" />
                  <span v-else class="mp-note">0</span>
                </td>
                <td>{{ b.operator }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <p class="mp-note">
        本中心不替代教务系统：课程、成绩、学分为同步/导入摘要，本页所有操作（含导出）均写入审计日志；指标口径与数据驾驶舱同源。
      </p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 学业过程中心 · 管理看板（/admin/academic）。指标按角色数据范围动态计算，数据全部来自 academic.api。 */
import { ModulePageShell, ModuleHero, ModuleToolbar, StatusTag, RiskTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { getAcademicDashboard, createExport } from '@/modules/academicAffairs/api/academic.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AcademicDashboardView',
  components: { ModulePageShell, ModuleHero, ModuleToolbar, StatusTag, RiskTag, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      hero: { kpis: [], flow: [], todos: [], riskAlerts: [], recentImportBatches: [], termName: '', termRange: '', updateTime: '' }
    }
  },
  computed: {
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'academic.grade.import', label: '导入成绩' },
        { key: 'academic.record.export', label: '导出学业报告' },
        { key: 'academic.audit.view', label: '操作留痕', variant: 'ghost' }
      ]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    },
    heroChips() {
      return ['当前角色：' + this.ctx.currentRole.roleName, '数据范围：' + this.ctx.dataScope.name]
    }
  },
  created() {
    this.load()
  },
  methods: {
    goLink(link) {
      const map = { warnings: '/admin/academic/warnings', makeup: '/admin/academic/makeup-retake', credits: '/admin/academic/credits' }
      this.$router.push(map[link] || '/admin/academic/students')
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await getAcademicDashboard()
      if (res.code === 0) this.hero = res.data
      else this.error = res.message
      this.loading = false
    },
    async onToolbar(key) {
      if (key === 'academic.grade.import') {
        this.$router.push('/admin/academic/grades?import=1')
      } else if (key === 'academic.record.export') {
        const res = await createExport('studentList', { scope: 'SCOPE_ALL', fieldGroups: ['base', 'academic'], mask: true, auditConfirmed: true })
        if (res.code === 0) toast.success('学业报告导出任务已创建（脱敏 + 水印），已写入审计日志')
        else toast.error(res.message)
      } else if (key === 'academic.audit.view') {
        this.$router.push('/admin/academic/students?tab=audit')
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.adb-todo-label {
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
  margin: 0 var(--space-1);
}
</style>
