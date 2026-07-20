<template>
  <ModulePageShell
    title="学校开通与首次开户"
    subtitle="平台开通学校与首位管理员；学校管理员在本校系统完成师生账号导入和角色分配。"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    watermark-purpose="学校开通交付"
  >
    <template #actions>
      <AppButton variant="primary" @click="$router.push('/admin/platform/tenants/create')">+ 开通新学校</AppButton>
      <AppButton variant="secondary" :loading="loading" @click="load">刷新进度</AppButton>
    </template>

    <div class="mp-stack">
      <section class="poc-note">
        <strong>权限边界</strong>
        <span>平台运营只能创建学校租户、首位学校管理员并查看交付进度；学生和教师账号必须由学校管理员在“系统管理 → 导入老师和学生”中预检后整批创建。</span>
      </section>

      <section class="poc-flow" aria-label="首次开户流程">
        <article v-for="(step, index) in steps" :key="step.title" class="poc-step">
          <span class="poc-step__no">{{ index + 1 }}</span>
          <div><strong>{{ step.title }}</strong><p>{{ step.desc }}</p></div>
        </article>
      </section>

      <LoadingState v-if="loading" text="正在读取学校开通进度…" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="暂未开通学校" description="先创建租户并交付首位学校管理员账号。" />
      <section v-else class="mp-card">
        <header class="mp-card__head">
          <span class="mp-card__title">学校首次开户进度</span>
          <span class="mp-note">只读统计，不展示师生明细或初始密码</span>
        </header>
        <DataTable :columns="columns" :rows="rows" row-key="tenantId" row-clickable @row-click="openTenant">
          <template #cell-school="{ row }">
            <div class="mp-cell-main">{{ row.tenantName }}</div>
            <div class="mp-cell-sub">{{ row.tenantCode }} · {{ row.packageName }}</div>
          </template>
          <template #cell-progress="{ row }">
            <StatusTag :type="phaseTone(row.onboarding.phase)" :label="row.onboarding.label" dot />
          </template>
          <template #cell-accounts="{ row }">
            管理员 {{ row.onboarding.schoolAdminCount }} · 教师 {{ row.onboarding.teacherAccountCount }} · 学生 {{ row.onboarding.studentAccountCount }}
          </template>
          <template #cell-next="{ row }">
            <span class="poc-next">{{ nextAction(row.onboarding.phase) }}</span>
          </template>
          <template #cell-actions="{ row }">
            <button class="mp-link" @click.stop="openTenant(row)">查看学校配置</button>
          </template>
        </DataTable>
      </section>
    </div>
  </ModulePageShell>
</template>

<script>
import { AppButton } from '@/components/ui'
import { DataTable, EmptyState, ErrorState, LoadingState, ModulePageShell, StatusTag } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'

const fallbackOnboarding = (row) => {
  const users = Number(row.userCount || 0)
  const students = Number(row.studentCount || 0)
  if (!users) return { phase: 'WAITING_ADMIN', label: '待交付学校管理员', schoolAdminCount: 0, teacherAccountCount: 0, studentAccountCount: students }
  if (users <= 1) return { phase: 'WAITING_IDENTITY_IMPORT', label: '待学校导入师生账号', schoolAdminCount: 1, teacherAccountCount: 0, studentAccountCount: students }
  if (!students) return { phase: 'TEACHER_IMPORTED', label: '已导入教师，待导入学生', schoolAdminCount: 1, teacherAccountCount: users - 1, studentAccountCount: 0 }
  return { phase: 'READY_FOR_ACCEPTANCE', label: '师生账号已导入，可上线验收', schoolAdminCount: 1, teacherAccountCount: Math.max(users - students - 1, 0), studentAccountCount: students }
}

export default {
  name: 'PlatformOnboardingCheckView',
  components: { AppButton, DataTable, EmptyState, ErrorState, LoadingState, ModulePageShell, StatusTag },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', rows: [],
      columns: [
        { key: 'school', title: '学校', width: '250px' },
        { key: 'progress', title: '当前进度', width: '200px' },
        { key: 'accounts', title: '已开户账号', width: '220px' },
        { key: 'next', title: '下一步', width: '260px' },
        { key: 'actions', title: '操作', width: '150px' }
      ],
      steps: [
        { title: '平台开通学校', desc: '创建租户、套餐和品牌基础配置。' },
        { title: '交付首位管理员', desc: '仅本次显示初始凭据，首次登录必须改密。' },
        { title: '学校导入师生', desc: '校方在系统管理中上传模板，系统预检后整批开户。' },
        { title: '角色与范围生效', desc: '学生固定学生角色；教师按预设角色和数据范围生效。' },
        { title: '平台上线验收', desc: '核对账号数量和学校配置后再确认交付完成。' }
      ]
    }
  },
  created() { this.load() },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const res = await platformControlApi.listTenants({})
      this.loading = false
      if (res.code !== 0) {
        this.error = res.message || '学校开通进度加载失败'
        return
      }
      this.rows = (res.data.list || []).map((item) => ({ ...item, onboarding: item.onboarding || fallbackOnboarding(item) }))
    },
    phaseTone(phase) {
      return { WAITING_ADMIN: 'danger', WAITING_IDENTITY_IMPORT: 'warning', TEACHER_IMPORTED: 'processing', READY_FOR_ACCEPTANCE: 'success' }[phase] || 'default'
    },
    nextAction(phase) {
      return {
        WAITING_ADMIN: '创建或恢复首位学校管理员账号',
        WAITING_IDENTITY_IMPORT: '通知学校管理员导入老师和学生',
        TEACHER_IMPORTED: '学校管理员继续导入学生账号',
        READY_FOR_ACCEPTANCE: '核对配置后执行学校上线验收'
      }[phase] || '查看学校配置'
    },
    openTenant(row) { this.$router.push(`/admin/platform/tenants/${row.tenantId}`) }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.poc-note { display: flex; gap: var(--space-3); align-items: flex-start; padding: var(--space-3) var(--space-4); border: 1px solid var(--primary-100); border-radius: var(--radius-md); background: var(--primary-50); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.7; }
.poc-note strong { flex: 0 0 auto; color: var(--primary-700); }
.poc-flow { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: var(--space-3); }
.poc-step { min-height: 112px; display: flex; gap: var(--space-2); padding: var(--space-3); border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--bg-card); }
.poc-step__no { flex: 0 0 24px; height: 24px; display: inline-flex; align-items: center; justify-content: center; border-radius: 50%; background: var(--primary-100); color: var(--primary-700); font-weight: var(--font-weight-bold); }
.poc-step strong { color: var(--text-primary); font-size: var(--font-size-sm); }
.poc-step p { margin: var(--space-1) 0 0; color: var(--text-secondary); font-size: var(--font-size-xs); line-height: 1.6; }
.poc-next { color: var(--text-secondary); font-size: var(--font-size-sm); }
@media (max-width: 1100px) { .poc-flow { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 640px) { .poc-flow { grid-template-columns: 1fr; } .poc-note { display: block; } }
</style>
