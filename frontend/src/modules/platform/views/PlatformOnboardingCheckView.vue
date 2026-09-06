<template>
  <ModulePageShell
    title="学校开通、交付验收与首次开户"
    subtitle="只读聚合订单、自动开户、首登改密、学校实施与当前版本消费端冒烟验证；不按账号数量猜测是否就绪。"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    watermark-purpose="学校开通交付"
  >
    <template #actions>
      <AppButton variant="primary" @click="$router.push('/admin/platform/provisioning?create=1')">+ 开通新学校</AppButton>
      <AppButton variant="secondary" :loading="loading" @click="load">刷新权威状态</AppButton>
    </template>

    <div class="mp-stack">
      <section class="poc-note">
        <strong>终态边界</strong>
        <span>自动开户成功只代表基础开户完成。只有已支付订单、首位管理员完成强制改密、学校验收摘要、当前摘要上的消费端冒烟验证全部通过，平台主管才可确认正式交付。</span>
      </section>

      <section class="poc-flow" aria-label="真实交付流程">
        <article v-for="(step, index) in steps" :key="step.title" class="poc-step">
          <span class="poc-step__no">{{ index + 1 }}</span>
          <div><strong>{{ step.title }}</strong><p>{{ step.desc }}</p></div>
        </article>
      </section>

      <LoadingState v-if="loading" text="正在聚合学校交付权威状态…" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="暂未开通学校" description="请从自动开通任务发起可恢复的新校开户。" />
      <section v-else class="mp-card">
        <header class="mp-card__head">
          <span class="mp-card__title">学校交付状态视图</span>
          <span class="mp-note">只聚合权威数据，不提供第二个就绪状态写入口</span>
        </header>
        <DataTable :columns="columns" :rows="rows" row-key="tenantId" row-clickable @row-click="selectRow">
          <template #cell-school="{ row }">
            <div class="mp-cell-main">{{ row.tenantName }}</div>
            <div class="mp-cell-sub">{{ row.tenantCode }} · {{ packageLabel(row.packageCode) }}</div>
          </template>
          <template #cell-progress="{ row }">
            <StatusTag :type="stateTone(row.deliveryState)" :label="stateLabel(row.deliveryState)" dot />
          </template>
          <template #cell-authorities="{ row }">
            <div class="poc-authorities">商业 {{ authorityStateLabel(row.commercialState) }} · 开户 {{ authorityStateLabel(row.provisioningState) }}</div>
            <div class="poc-authorities">首登 {{ authorityStateLabel(row.firstAdminState) }} · 实施 {{ authorityStateLabel(row.implementationState) }}</div>
          </template>
          <template #cell-next="{ row }">
            <span class="poc-next">{{ nextAction(row) }}</span>
          </template>
          <template #cell-actions="{ row }">
            <button class="mp-link" @click.stop="selectRow(row)">查看交付结论</button>
          </template>
        </DataTable>
      </section>

      <section v-if="selected" class="mp-card poc-detail">
        <header class="mp-card__head">
          <span class="mp-card__title">{{ selected.tenantName }} · 交付结论</span>
          <StatusTag :type="stateTone(selected.deliveryState)" :label="stateLabel(selected.deliveryState)" dot />
        </header>
        <div class="poc-detail__grid">
          <div><span>租户</span><strong>{{ authorityStateLabel(selected.tenantState) }}</strong></div>
          <div><span>订单或授权</span><strong>{{ authorityStateLabel(selected.commercialState) }}</strong></div>
          <div><span>基础开户</span><strong>{{ authorityStateLabel(selected.provisioningState) }}</strong></div>
          <div><span>首位管理员</span><strong>{{ authorityStateLabel(selected.firstAdminState) }}</strong></div>
          <div><span>学校实施</span><strong>{{ authorityStateLabel(selected.implementationState) }}</strong></div>
          <div><span>消费端冒烟验证</span><strong>{{ authorityStateLabel(selected.consumerSmokeState) }}</strong></div>
        </div>
        <p v-if="selected.acceptanceDigest" class="poc-digest">学校验收摘要：<code>{{ selected.acceptanceDigest }}</code></p>
        <div v-if="selected.blockers.length" class="poc-blockers">
          <strong>当前阻断项</strong>
          <ul><li v-for="item in selected.blockers" :key="item.code">{{ item.message }}</li></ul>
        </div>
        <div class="poc-detail__actions">
          <AppButton @click="openTenant(selected)">查看学校配置</AppButton>
          <AppButton v-if="selected.deliveryState === 'READY_FOR_PLATFORM_ACCEPTANCE'" variant="primary" @click="acceptSelected">确认平台交付</AppButton>
        </div>
      </section>
    </div>
  </ModulePageShell>
</template>

<script>
import { AppButton } from '@/components/ui'
import { DataTable, EmptyState, ErrorState, LoadingState, ModulePageShell, StatusTag } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { toast } from '@/utils/toast'

export default {
  name: 'PlatformOnboardingCheckView',
  components: { AppButton, DataTable, EmptyState, ErrorState, LoadingState, ModulePageShell, StatusTag },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      selected: null,
      columns: [
        { key: 'school', title: '学校', width: '230px' },
        { key: 'progress', title: '交付终态', width: '210px' },
        { key: 'authorities', title: '权威状态', width: '330px' },
        { key: 'next', title: '下一步', width: '270px' },
        { key: 'actions', title: '操作', width: '150px' }
      ],
      steps: [
        { title: '自动开户', desc: '可恢复任务创建试用租户、角色、首位管理员与实施项目。' },
        { title: '订单授权', desc: '已支付订单是正式套餐与到期时间的商业权威来源。' },
        { title: '学校首登', desc: '学校管理员用一次性凭据登录并完成强制改密。' },
        { title: '学校实施', desc: '组织、师生、身份权限、模块与流程完成后冻结学校摘要。' },
        { title: '消费端冒烟验证', desc: '在当前部署版本验证四大业务与教师端、学生端接线。' },
        { title: '平台交付', desc: '仅引用学校摘要与冒烟验证证据完成商业交接。' }
      ]
    }
  },
  created() { this.load() },
  methods: {
    packageLabel(code) {
      return ({ trial: '试用版', basic: '基础版', standard: '标准版', professional: '专业版', private: '私有化版' })[code] || '套餐待确认'
    },
    authorityStateLabel(state) {
      return ({
        ACTIVE: '正式可用', TRIAL: '试用中', EXPIRED: '已到期', DISABLED: '已停用', UNRESOLVED: '状态待确认',
        NOT_STARTED: '未开始', BOOTSTRAP_READY: '基础开户完成', RUNNING: '执行中', SUCCEEDED: '已成功', FAILED: '失败',
        NOT_CREATED: '未创建', TEMP_PASSWORD_PENDING: '待首次登录改密', PASSWORD_CHANGED: '已完成首次改密',
        TRIAL_ONLY: '仅试用授权', PAID_ACTIVE: '付费授权已生效', PAID_REPAIR_REQUIRED: '付费授权需修复',
        ACCEPTED: '已验收', PENDING: '待处理', PASS: '已通过', BLOCKED: '已阻断',
        STALE_HEAD: '验证版本已过期', NOT_RUN: '尚未验证', STALE: '验收证据已过期', NOT_ACCEPTED: '尚未验收'
      })[String(state || '').toUpperCase()] || '状态待确认'
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await platformControlApi.listDeliveryReadModels()
      this.loading = false
      if (res.code !== 0) {
        this.error = res.message || '学校交付状态加载失败'
        return
      }
      this.rows = res.data.items || []
      if (this.selected) this.selected = this.rows.find((item) => item.tenantId === this.selected.tenantId) || null
    },
    stateTone(state) {
      return { SCHOOL_DELIVERY_PRODUCTION_READY: 'success', READY_FOR_PLATFORM_ACCEPTANCE: 'processing', BLOCKED: 'warning' }[state] || 'default'
    },
    stateLabel(state) {
      return {
        SCHOOL_DELIVERY_PRODUCTION_READY: '学校交付已封板',
        READY_FOR_PLATFORM_ACCEPTANCE: '待平台确认交付',
        BLOCKED: '尚有交付阻断项'
      }[state] || '交付状态待确认'
    },
    nextAction(row) {
      if (row.deliveryState === 'SCHOOL_DELIVERY_PRODUCTION_READY') return '进入客户运营、续费与健康管理'
      if (row.deliveryState === 'READY_FOR_PLATFORM_ACCEPTANCE') return '引用学校摘要确认平台交付'
      return row.blockers?.[0]?.message || '刷新权威状态'
    },
    selectRow(row) { this.selected = row },
    openTenant(row) { this.$router.push(`/admin/platform/tenants/${row.tenantId}`) },
    async acceptSelected() {
      const comment = window.prompt('请输入平台交付意见（至少 2 个字符）')
      if (!comment || comment.trim().length < 2) return
      const confirmText = window.prompt('输入“确认交付”完成商业交接')
      if (confirmText !== '确认交付') return
      const res = await platformControlApi.acceptDelivery(this.selected.tenantId, {
        confirmText,
        comment: comment.trim(),
        expectedReadModelDigest: this.selected.readModelDigest
      })
      if (res.code === 0) {
        toast.success('平台交付已确认；学校验收摘要保持原样引用')
        await this.load()
      } else toast.error(res.message)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.poc-note { display: flex; gap: var(--space-3); align-items: flex-start; padding: var(--space-3) var(--space-4); border: 1px solid var(--primary-100); border-radius: var(--radius-md); background: var(--primary-50); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.7; }
.poc-note strong { flex: 0 0 auto; color: var(--primary-700); }
.poc-flow { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-3); }
.poc-step { min-height: 112px; display: flex; gap: var(--space-2); padding: var(--space-3); border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--bg-card); }
.poc-step__no { flex: 0 0 24px; height: 24px; display: inline-flex; align-items: center; justify-content: center; border-radius: 50%; background: var(--primary-100); color: var(--primary-700); font-weight: var(--font-weight-bold); }
.poc-step strong { color: var(--text-primary); font-size: var(--font-size-sm); }
.poc-step p { margin: var(--space-1) 0 0; color: var(--text-secondary); font-size: var(--font-size-xs); line-height: 1.6; }
.poc-authorities, .poc-next { color: var(--text-secondary); font-size: var(--font-size-xs); line-height: 1.7; }
.poc-detail { padding: var(--space-4); }
.poc-detail__grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-3); }
.poc-detail__grid > div { display: grid; gap: 4px; padding: var(--space-3); border: 1px solid var(--border-light); border-radius: var(--radius-sm); }
.poc-detail__grid span { color: var(--text-secondary); font-size: var(--font-size-xs); }
.poc-detail__grid strong { color: var(--text-primary); font-size: var(--font-size-sm); }
.poc-digest { overflow-wrap: anywhere; color: var(--text-secondary); font-size: var(--font-size-xs); }
.poc-blockers { margin-top: var(--space-3); padding: var(--space-3); border: 1px solid var(--warning-300, #f5c26b); border-radius: var(--radius-sm); background: var(--warning-50, #fff8e8); }
.poc-blockers ul { margin: var(--space-2) 0 0; padding-left: 20px; color: var(--text-secondary); font-size: var(--font-size-sm); }
.poc-detail__actions { display: flex; gap: var(--space-2); margin-top: var(--space-3); }
@media (max-width: 900px) { .poc-flow, .poc-detail__grid { grid-template-columns: 1fr 1fr; } }
@media (max-width: 640px) { .poc-flow, .poc-detail__grid { grid-template-columns: 1fr; } .poc-note { display: block; } }
</style>
