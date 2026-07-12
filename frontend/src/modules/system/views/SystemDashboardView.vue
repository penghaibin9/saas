<template>
  <ModulePageShell
    title="系统管理中心"
    :subtitle="ctx.tenantBrandConfig.schoolName + ' · 账号 / 角色 / 权限 / 数据范围 / 审计'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <ModuleHero
          :title="ctx.tenantBrandConfig.schoolName + ' · 系统运行总览'"
          :subtitle="'当前角色 ' + ctx.currentRole.roleName + ' · 数据范围 ' + ctx.dataScope.scopeName + ' · 本页所有操作均写入审计日志'"
          :stats="summary.stats"
        />

        <div class="mp-grid-2">
          <section class="mp-card">
            <header class="mp-card__head">
              <span class="mp-card__title">待处理事项</span>
              <button class="mp-link" @click="$router.push('/admin/system/logs')">操作日志 →</button>
            </header>
            <div class="mp-card__body">
              <div v-for="t in summary.todos" :key="t.id" class="sd-todo" @click="$router.push(t.route)">
                <StatusTag :type="t.tone" :label="t.count + ' 项'" />
                <div class="sd-todo__main">
                  <div class="mp-cell-main">{{ t.label }}</div>
                  <div class="mp-cell-sub">{{ t.hint }}</div>
                </div>
                <span class="mp-link">去处理 →</span>
              </div>
            </div>
          </section>

          <section class="mp-card">
            <header class="mp-card__head">
              <span class="mp-card__title">安全提醒</span>
              <button class="mp-link" @click="$router.push('/admin/system/logs?tab=login')">登录日志 →</button>
            </header>
            <div class="mp-card__body">
              <ul class="mp-timeline">
                <li
                  v-for="a in summary.securityAlerts"
                  :key="a.id"
                  class="mp-timeline__item"
                  :class="a.level === 'HIGH' ? 'is-danger' : 'is-warning'"
                >
                  <div class="mp-timeline__title">{{ a.title }} <RiskTag :level="a.level" /></div>
                  <div class="mp-timeline__desc">{{ a.detail }}</div>
                  <div class="mp-timeline__time">{{ a.time }}</div>
                </li>
              </ul>
            </div>
          </section>
        </div>

        <section class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">最近系统操作（审计摘要）</span>
            <span class="mp-note">审计日志不可删除，仅支持只读查看与受控导出</span>
          </header>
          <div class="mp-card__body" style="padding-top: 0">
            <table class="mp-audit">
              <thead>
                <tr><th style="width: 220px">操作人</th><th>动作</th><th style="width: 140px">时间</th></tr>
              </thead>
              <tbody>
                <tr v-for="r in summary.recentOps" :key="r.id">
                  <td class="is-who">{{ r.who }}</td>
                  <td>{{ r.action }}</td>
                  <td>{{ r.time }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/** 系统管理首页（/admin/system）：运行总览 + 待办直达 + 安全提醒 + 审计摘要。 */
import { ModulePageShell, ModuleToolbar, ModuleHero, StatusTag, RiskTag, LoadingState, ErrorState } from '@/components/business'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

export default {
  name: 'SystemDashboardView',
  components: { ModulePageShell, ModuleToolbar, ModuleHero, StatusTag, RiskTag, LoadingState, ErrorState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { loading: true, error: '', summary: null }
  },
  computed: {
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'createUser', label: '＋ 新增用户', variant: 'primary' },
        { key: 'importUsers', label: '批量导入用户' },
        { key: 'viewOperationLogs', label: '≡ 操作日志' }
      ]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    }
  },
  created() {
    this.load()
  },
  methods: {
    onToolbar(key) {
      if (key === 'createUser' || key === 'importUsers') this.$router.push('/admin/system/users?action=' + key)
      if (key === 'viewOperationLogs') this.$router.push('/admin/system/logs')
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await systemApi.getDashboardSummary()
      if (res.code === 0) this.summary = res.data
      else {
        this.error = res.message
        toast.error(res.message)
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.sd-todo {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) 0;
  border-bottom: 1px dashed var(--border-light);
  cursor: pointer;
}
.sd-todo:last-child {
  border-bottom: none;
}
.sd-todo__main {
  flex: 1;
  min-width: 0;
}
</style>
