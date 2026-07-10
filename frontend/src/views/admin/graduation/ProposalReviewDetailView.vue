<template>
  <ModulePageShell
    title="开题批阅"
    subtitle="独立批阅页（深链 / 窄屏）· 宽屏建议在「开题审核」双栏工作区连续批阅"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="ghost" @click="backToList">← 返回开题审核</AppButton>
    </template>
    <ProposalReviewCard :ctx="ctx" :proposal-id="$route.params.id" @reviewed="onReviewed" />
  </ModulePageShell>
</template>

<script>
/**
 * 开题批阅详情（/admin/graduation/proposals/:id）。
 * 深链与窄屏入口；批阅能力由 _shared/ProposalReviewCard 提供（与双栏工作区同一套真实闭环）。
 */
import { ModulePageShell } from '@/components/business'
import { AppButton } from '@/components/ui'
import ProposalReviewCard from './_shared/ProposalReviewCard.vue'

export default {
  name: 'ProposalReviewDetailView',
  components: { ModulePageShell, AppButton, ProposalReviewCard },
  props: { ctx: { type: Object, required: true } },
  methods: {
    backToList() {
      this.$router.push({ path: '/admin/graduation/proposals', query: { sel: String(this.$route.params.id) } })
    },
    onReviewed() {
      // 批阅完成后停留在详情（深链场景），状态由卡片自身刷新
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
</style>
