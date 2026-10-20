<template>
  <BasePortalLayout :ctx="ctx" workspace @menu-select="selectMenu">
    <section class="route-access-notice" role="status" aria-live="polite">
      <p class="route-access-notice__page">{{ $route.meta.title || '业务办理' }}</p>
      <h1>{{ notice.title }}</h1>
      <p>{{ notice.message }}</p>
      <div class="route-access-notice__actions">
        <AppButton :loading="retrying" @click="retry">重新检查</AppButton>
        <AppButton variant="ghost" @click="$router.push('/workbench')">返回工作台</AppButton>
      </div>
    </section>
  </BasePortalLayout>
</template>

<script>
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { AppButton } from '@/components/ui'
import { fetchLayoutContext } from '@/modules/workbench/api/workbench.api'
import { clearPermissionPatterns } from '@/security/permissionGate'

export default {
  name: 'RouteAccessNotice',
  components: { BasePortalLayout, AppButton },
  props: { notice: { type: Object, required: true } },
  data: () => ({ ctx: null, retrying: false }),
  async created() { this.ctx = await fetchLayoutContext() },
  methods: {
    selectMenu(item) { if (item.path) this.$router.push(item.path) },
    async retry() {
      if (this.retrying) return
      this.retrying = true
      try {
        clearPermissionPatterns()
        await this.$router.replace({ path: this.$route.path, query: this.$route.query, hash: this.$route.hash, force: true })
      } finally { this.retrying = false }
    }
  }
}
</script>

<style scoped>
.route-access-notice { padding: clamp(24px, 4vw, 56px); margin: 24px; background: var(--bg-card, #fff); border: 1px solid var(--border-color, #e2e8f0); border-radius: 12px; }
.route-access-notice__page { color: var(--text-secondary, #64748b); }
.route-access-notice h1 { font-size: 22px; margin: 16px 0; }
.route-access-notice p { max-width: 680px; line-height: 1.8; }
.route-access-notice__actions { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 24px; }
</style>
