<template>
  <!-- 内嵌模式：出现在列表筛选栏下方，只占表格区域 -->
  <section v-if="layout === 'inline'" class="gd-inline">
    <header class="gd-inline__head">
      <button type="button" class="gd-inline__back" @click="goBack">
        <span aria-hidden="true">←</span>
        {{ backLabel }}
      </button>
      <div class="gd-inline__titles">
        <h3 class="gd-inline__title">{{ title }}</h3>
        <p v-if="subtitle" class="gd-inline__sub">{{ subtitle }}</p>
      </div>
    </header>
    <div class="gd-inline__body">
      <slot />
    </div>
    <footer v-if="$slots.footer" class="gd-inline__foot">
      <slot name="footer" />
    </footer>
  </section>

  <!-- 整页模式：独立路由页（其它模块仍可用） -->
  <div v-else class="gd-form-page">
    <button type="button" class="gd-form-page__back" @click="goBack">
      <span class="gd-form-page__back-icon">←</span>
      {{ backLabel }}
    </button>
    <ModulePageShell
      :title="title"
      :subtitle="subtitle"
      :role-name="ctx.currentRole.roleName"
      :data-scope-name="ctx.dataScope.scopeName"
    >
      <slot />
      <AppStickyFooter v-if="$slots.footer" raised>
        <slot name="footer" />
      </AppStickyFooter>
    </ModulePageShell>
  </div>
</template>

<script>
import { ModulePageShell } from '@/components/business'
import { AppStickyFooter } from '@/components/common'

export default {
  name: 'GraduationFormPageShell',
  components: { ModulePageShell, AppStickyFooter },
  props: {
    ctx: { type: Object, required: true },
    title: { type: String, required: true },
    subtitle: { type: String, default: '' },
    backLabel: { type: String, default: '返回列表' },
    backTo: { type: String, default: '' },
    /** page = 独立整页；inline = 嵌在列表筛选栏下方 */
    layout: {
      type: String,
      default: 'page',
      validator: (v) => ['page', 'inline'].includes(v)
    }
  },
  methods: {
    goBack() {
      if (this.backTo) {
        this.$router.push(this.backTo)
      } else {
        this.$router.back()
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

/* ── 内嵌卡片（筛选栏下方） ── */
.gd-inline {
  background: var(--bg-card, #fff);
  border: 1px solid var(--border-light, #e4e9f0);
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(15, 40, 90, 0.05);
  overflow: hidden;
}

.gd-inline__head {
  display: flex;
  align-items: flex-start;
  gap: var(--space-4);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-light, #eef1f6);
  background: linear-gradient(180deg, #f8fafc 0%, #fff 100%);
}

.gd-inline__back {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 2px;
  padding: 5px 10px;
  border: 1px solid var(--border-base, #d9dee8);
  border-radius: 8px;
  background: #fff;
  color: var(--text-secondary, #475569);
  font-size: 12px;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s, box-shadow 0.15s;
}

.gd-inline__back:hover {
  color: var(--primary-600, #2563eb);
  border-color: var(--primary-200, #bfdbfe);
  box-shadow: 0 1px 4px rgba(37, 99, 235, 0.08);
}

.gd-inline__titles {
  flex: 1;
  min-width: 0;
}

.gd-inline__title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary, #0f172a);
  line-height: 1.4;
}

.gd-inline__sub {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--text-secondary, #64748b);
  line-height: 1.5;
}

.gd-inline__body {
  padding: var(--space-4) var(--space-5);
  max-height: min(68vh, 620px);
  overflow-y: auto;
}

.gd-inline__foot {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--border-light, #eef1f6);
  background: #f8fafc;
}

/* ── 整页模式 ── */
.gd-form-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  min-height: 100%;
}

.gd-form-page__back {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  align-self: flex-start;
  padding: 0;
  border: none;
  background: none;
  color: var(--pri, #2563eb);
  font-size: 13px;
  cursor: pointer;
}

.gd-form-page__back:hover {
  text-decoration: underline;
}

.gd-form-page__back-icon {
  font-size: 14px;
}
</style>
