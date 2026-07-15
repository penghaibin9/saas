<template>
  <ModulePageShell
    title="教务归档 · 归档缺失提醒"
    subtitle="归档批次创建前的早期预检看板 · 实时计算不落库"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="primary" @click="goBatch">创建归档批次</AppButton>
    </template>

    <div class="aapc-toolbar">
      <AppFormItem label="学期">
        <AppSelect v-model="termId" :options="termOptions" placeholder="默认当前学期" @change="load" />
      </AppFormItem>
      <AppButton size="small" variant="ghost" :loading="loading" @click="load">立即检查</AppButton>
    </div>

    <AppInlineAlert v-if="scopeNote" type="info" :description="scopeNote" />

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <EmptyState v-else-if="!domains.length" title="暂无数据" description="请选择学期后重试" />
    <div v-else class="aapc-grid">
      <div v-for="d in domains" :key="d.domain" class="aapc-card" :class="cardClass(d.status)" @click="jump(d)">
        <div class="aapc-card-head">
          <span class="aapc-card-title">{{ d.domainLabel }}</span>
          <StatusTag :type="tagType(d.status)" :label="tagLabel(d.status)" dot />
        </div>
        <div class="aapc-card-count">{{ d.recordCount }}<span class="aapc-card-unit">条记录</span></div>
        <div v-if="d.note" class="aapc-card-note">{{ d.note }}</div>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
/** 教务归档 · 归档缺失提醒（10 卡，/admin/academic-affairs/archive/precheck）：
 * 归档批次创建前的实时预检看板；不落库、不写审计、不产生正式缺项清单（那是「批量归档」的职责）。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState, StatusTag } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSelect, AppFormItem, AppInlineAlert } from '@/components/common'
import { academicAffairsApi, academicAffairsArchiveApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'

// 域码 → 补录入口路由（跳转对应源模块处理缺项）
const _JUMP = {
  STUDENT_STATUS: '/admin/academic-affairs/roster',
  REGISTRATION: '/admin/academic-affairs/registration',
  STATUS_CHANGE: '/admin/academic-affairs/status-changes',
  PROGRAM: '/admin/academic-affairs/programs',
  TEACHING_TASK: '/admin/academic-affairs/teaching-tasks',
  SCHEDULE: '/admin/academic-affairs/schedule',
  EXAM: '/admin/academic-affairs/exam',
  GRADE: '/admin/academic-affairs/grade-tasks',
  GRADUATION: '/admin/academic-affairs/graduation-audit'
}

export default {
  name: 'ArchivePrecheckView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, StatusTag, AppButton, AppSelect, AppFormItem, AppInlineAlert },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      loading: true, error: '', domains: [], scopeNote: '', termId: '', termOptions: []
    }
  },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    await this.loadTerms()
    this.load()
  },
  methods: {
    async loadTerms() {
      const res = await academicAffairsApi.getTerms({ pageSize: 100 })
      if (res.code === 0) {
        this.termOptions = res.data.list.map(t => ({ label: `${t.yearCode} 第${t.termNo}学期${t.isCurrent ? '（当前）' : ''}`, value: t.termId }))
        const cur = res.data.list.find(t => t.isCurrent)
        if (cur) this.termId = cur.termId
      }
    },
    async load() {
      this.loading = true; this.error = ''
      const res = await api.precheck(this.termId || undefined)
      this.loading = false
      if (res.code === 0) {
        this.domains = res.data.domains || []
        this.scopeNote = res.data.scopeNote || ''
        if (!this.termId && res.data.termId) this.termId = res.data.termId
      } else this.error = res.message
    },
    cardClass(s) { return s === 'MISSING' ? 'is-missing' : s === 'ERROR' ? 'is-error' : 'is-ok' },
    tagType(s) { return s === 'OK' ? 'success' : s === 'MISSING' ? 'danger' : 'warning' },
    tagLabel(s) { return s === 'OK' ? '完整' : s === 'MISSING' ? '缺失' : '检查异常' },
    jump(d) {
      if (d.status !== 'MISSING') return
      const p = _JUMP[d.domain]
      if (p) this.$router.push(p)
    },
    goBatch() { this.$router.push('/admin/academic-affairs/archive') }
  }
}
</script>

<style scoped>
.aapc-toolbar { display: flex; align-items: center; gap: 16px; margin-bottom: 12px; }
.aapc-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 14px; margin-top: 12px; }
.aapc-card { padding: 16px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 10px; cursor: default; transition: box-shadow .15s; }
.aapc-card.is-missing { cursor: pointer; border-color: var(--danger-color, #dc2626); }
.aapc-card.is-missing:hover { box-shadow: 0 2px 8px rgba(220, 38, 38, .15); }
.aapc-card.is-error { border-color: var(--warning-color, #d97706); }
.aapc-card-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.aapc-card-title { font-weight: 600; }
.aapc-card-count { font-size: 24px; font-weight: 700; color: var(--primary-color, #2563eb); }
.aapc-card-unit { font-size: 12px; font-weight: 400; color: var(--text-tertiary, #94a3b8); margin-left: 4px; }
.aapc-card-note { margin-top: 6px; font-size: 12px; color: var(--text-tertiary, #94a3b8); }
</style>
