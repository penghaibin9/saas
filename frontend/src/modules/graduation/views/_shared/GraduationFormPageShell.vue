<template>
  <section
    v-if="layout === 'inline'"
    class="gd-form-shell gd-form-shell--inline"
    :class="{ 'is-busy': busy, 'has-aside': hasAside }"
    :aria-busy="busy ? 'true' : 'false'"
  >
    <header class="gd-form-head">
      <button type="button" class="gd-form-back" :disabled="busy" @click="goBack">
        <span aria-hidden="true">←</span>
        {{ backLabel }}
      </button>
      <div class="gd-form-head__titles">
        <span class="gd-form-head__eyebrow">{{ eyebrow }}</span>
        <h3 class="gd-form-head__title">{{ title }}</h3>
        <p v-if="subtitle" class="gd-form-head__subtitle">{{ subtitle }}</p>
      </div>
      <div v-if="$slots.headerActions" class="gd-form-head__actions">
        <slot name="headerActions" />
      </div>
    </header>

    <div v-if="$slots.context" class="gd-form-context">
      <slot name="context" />
    </div>

    <div class="gd-form-body" :class="{ 'gd-form-body--aside': hasAside }">
      <main class="gd-form-content">
        <slot />
      </main>
      <aside v-if="hasAside" class="gd-form-aside" aria-label="办理条件与下一步">
        <slot name="aside" />
      </aside>
    </div>

    <footer v-if="$slots.footer" class="gd-form-footer">
      <span v-if="busy" class="gd-form-footer__busy" role="status">正在提交，请勿切换页面或重复点击</span>
      <slot name="footer" />
    </footer>
  </section>

  <div v-else class="gd-form-page" :class="{ 'is-busy': busy }" :aria-busy="busy ? 'true' : 'false'">
    <nav class="gd-form-page__trail" aria-label="毕业设计办理路径">
      <button type="button" class="gd-form-back" :disabled="busy" @click="goBack">
        <span aria-hidden="true">←</span>
        {{ backLabel }}
      </button>
      <div class="gd-form-page__crumb">
        <span>毕业设计中心</span>
        <b aria-hidden="true">/</b>
        <strong>{{ title }}</strong>
      </div>
      <span v-if="statusText" class="gd-form-status" :class="`is-${statusTone}`">{{ statusText }}</span>
    </nav>

    <ModulePageShell
      :title="title"
      :subtitle="subtitle"
      :role-name="ctx.currentRole.roleName"
      :data-scope-name="ctx.dataScope.scopeName"
    >
      <section class="gd-form-shell gd-form-shell--page" :class="{ 'has-aside': hasAside }">
        <header v-if="purpose || $slots.headerActions" class="gd-form-purpose">
          <div>
            <span>{{ eyebrow }}</span>
            <strong v-if="purpose">{{ purpose }}</strong>
          </div>
          <div v-if="$slots.headerActions" class="gd-form-head__actions">
            <slot name="headerActions" />
          </div>
        </header>

        <div v-if="$slots.context" class="gd-form-context">
          <slot name="context" />
        </div>

        <div class="gd-form-body" :class="{ 'gd-form-body--aside': hasAside }">
          <main class="gd-form-content">
            <slot />
          </main>
          <aside v-if="hasAside" class="gd-form-aside" aria-label="办理条件与下一步">
            <slot name="aside" />
          </aside>
        </div>
      </section>

      <AppStickyFooter v-if="$slots.footer" raised>
        <span v-if="busy" class="gd-form-footer__busy" role="status">正在提交，请勿切换页面或重复点击</span>
        <slot name="footer" />
      </AppStickyFooter>
    </ModulePageShell>
  </div>
</template>

<script>
import { ModulePageShell } from '@/components/business'
import { AppStickyFooter } from '@/components/common'

const SAFE_PREFIX = '/admin/graduation/'

export default {
  name: 'GraduationFormPageShell',
  components: { ModulePageShell, AppStickyFooter },
  emits: ['blocked-back'],
  props: {
    ctx: { type: Object, required: true },
    title: { type: String, required: true },
    subtitle: { type: String, default: '' },
    eyebrow: { type: String, default: '毕业设计业务办理' },
    purpose: { type: String, default: '' },
    statusText: { type: String, default: '' },
    statusTone: {
      type: String,
      default: 'info',
      validator: (value) => ['info', 'success', 'warning', 'danger'].includes(value)
    },
    backLabel: { type: String, default: '返回列表' },
    backTo: { type: String, default: '' },
    busy: { type: Boolean, default: false },
    /** page = 独立整页；inline = 嵌在列表筛选栏下方 */
    layout: {
      type: String,
      default: 'page',
      validator: (value) => ['page', 'inline'].includes(value)
    }
  },
  computed: {
    hasAside() {
      return Boolean(this.$slots.aside)
    },
    safeReturnTo() {
      const raw = Array.isArray(this.$route.query.returnTo)
        ? this.$route.query.returnTo[0]
        : this.$route.query.returnTo
      const value = String(raw || '').trim()
      return value.startsWith(SAFE_PREFIX) ? value : ''
    },
    backTarget() {
      return this.safeReturnTo || this.backTo || ''
    }
  },
  methods: {
    goBack() {
      if (this.busy) {
        this.$emit('blocked-back')
        return
      }
      if (this.backTarget) this.$router.push(this.backTarget)
      else this.$router.back()
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.gd-form-page {
  display: grid;
  min-width: 0;
  gap: 10px;
  min-height: 100%;
}

.gd-form-page__trail {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 12px;
  padding: 10px 14px;
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 12px;
  background: var(--bg-card, #fff);
  box-shadow: 0 4px 16px rgba(15, 40, 90, .04);
}

.gd-form-page__crumb {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 7px;
  color: var(--text-tertiary, #64748b);
  font-size: 12px;
}

.gd-form-page__crumb strong {
  overflow: hidden;
  color: var(--text-primary, #0f172a);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.gd-form-page__crumb b {
  color: var(--border-base, #cbd5e1);
  font-weight: 400;
}

.gd-form-back {
  display: inline-flex;
  flex: none;
  align-items: center;
  gap: 5px;
  min-height: 34px;
  padding: 0 11px;
  border: 1px solid var(--border-base, #d7deea);
  border-radius: 8px;
  background: var(--bg-card, #fff);
  color: var(--text-secondary, #475569);
  cursor: pointer;
  font-size: 12px;
  transition: border-color .15s ease, color .15s ease, box-shadow .15s ease;
}

.gd-form-back:hover:not(:disabled) {
  border-color: var(--primary-300, #93c5fd);
  color: var(--primary-700, #1d4ed8);
  box-shadow: 0 4px 12px rgba(37, 99, 235, .09);
}

.gd-form-back:disabled {
  cursor: not-allowed;
  opacity: .5;
}

.gd-form-status {
  margin-left: auto;
  padding: 4px 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 650;
  white-space: nowrap;
}

.gd-form-status.is-info { background: #eff6ff; color: #1d4ed8; }
.gd-form-status.is-success { background: #ecfdf3; color: #15803d; }
.gd-form-status.is-warning { background: #fff7ed; color: #b45309; }
.gd-form-status.is-danger { background: #fef2f2; color: #b91c1c; }

.gd-form-shell {
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--border-light, #e1e8f2);
  border-radius: 14px;
  background: var(--bg-card, #fff);
  box-shadow: 0 10px 30px rgba(15, 40, 90, .06);
}

.gd-form-shell--inline {
  margin-top: 2px;
}

.gd-form-head {
  display: flex;
  align-items: flex-start;
  min-width: 0;
  gap: 14px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--border-light, #e8edf5);
  background: linear-gradient(135deg, #f7fbff 0%, #fff 76%);
}

.gd-form-head__titles {
  display: grid;
  flex: 1;
  min-width: 0;
  gap: 2px;
}

.gd-form-head__eyebrow,
.gd-form-purpose span {
  color: var(--primary-600, #2563eb);
  font-size: 10px;
  font-weight: 750;
  letter-spacing: .08em;
}

.gd-form-head__title {
  margin: 0;
  color: var(--text-primary, #0f172a);
  font-size: 18px;
  line-height: 1.35;
}

.gd-form-head__subtitle {
  margin: 2px 0 0;
  color: var(--text-secondary, #64748b);
  font-size: 12px;
  line-height: 1.55;
}

.gd-form-head__actions {
  display: flex;
  flex: none;
  align-items: center;
  gap: 8px;
}

.gd-form-purpose {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-width: 0;
  gap: 16px;
  padding: 11px 16px;
  border-bottom: 1px solid var(--border-light, #e8edf5);
  background: linear-gradient(135deg, #f7fbff 0%, #fff 76%);
}

.gd-form-purpose > div:first-child {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.gd-form-purpose strong {
  color: var(--text-primary, #0f172a);
  font-size: 13px;
  line-height: 1.45;
}

.gd-form-context {
  display: flex;
  align-items: stretch;
  min-width: 0;
  gap: 8px;
  padding: 10px 14px;
  overflow-x: auto;
  border-bottom: 1px solid var(--border-light, #edf1f7);
  background: var(--bg-subtle, #f8fafc);
}

.gd-form-body {
  min-width: 0;
  padding: 18px;
}

.gd-form-body--aside {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(250px, 310px);
  align-items: start;
  gap: 16px;
}

.gd-form-content,
.gd-form-aside {
  min-width: 0;
}

.gd-form-aside {
  position: sticky;
  top: 12px;
  display: grid;
  gap: 10px;
}

.gd-form-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--border-light, #e8edf5);
  background: var(--bg-subtle, #f8fafc);
}

.gd-form-footer__busy {
  margin-right: auto;
  color: var(--warning-700, #a16207);
  font-size: 11px;
}

.is-busy .gd-form-body {
  pointer-events: none;
  opacity: .72;
}

:deep(.ie-form) {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  min-width: 0;
  gap: 14px 16px;
}

:deep(.ie-fld) {
  display: grid;
  align-content: start;
  min-width: 0;
  gap: 6px;
  margin: 0;
}

:deep(.ie-fld--full) {
  grid-column: 1 / -1;
}

:deep(.ie-lbl) {
  color: var(--text-secondary, #475569);
  font-size: 12px;
  font-weight: 650;
  line-height: 1.45;
}

:deep(.ie-lbl i) {
  color: var(--danger-600, #dc2626);
  font-style: normal;
}

:deep(.ie-in) {
  width: 100%;
  min-width: 0;
  min-height: 40px;
  box-sizing: border-box;
  padding: 8px 10px;
  border: 1px solid var(--border-base, #cfd8e6);
  border-radius: 8px;
  outline: none;
  background: var(--bg-card, #fff);
  color: var(--text-primary, #0f172a);
  font-size: 13px;
  transition: border-color .15s ease, box-shadow .15s ease, background .15s ease;
}

:deep(textarea.ie-in) {
  min-height: 88px;
  resize: vertical;
  line-height: 1.55;
}

:deep(.ie-in:focus) {
  border-color: var(--primary-400, #60a5fa);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, .1);
}

:deep(.ie-in:disabled) {
  background: var(--gray-50, #f8fafc);
  color: var(--text-tertiary, #64748b);
}

:deep(.ie-hint) {
  margin: 0;
  color: var(--text-tertiary, #64748b);
  font-size: 11px;
  line-height: 1.5;
}

:deep(.ie-err) {
  grid-column: 1 / -1;
  margin: 0;
  padding: 10px 12px;
  border: 1px solid var(--danger-200, #fecaca);
  border-radius: 8px;
  background: var(--danger-50, #fef2f2);
  color: var(--danger-700, #b91c1c);
  font-size: 12px;
  line-height: 1.5;
}

:deep(.gd-form-section) {
  grid-column: 1 / -1;
  display: grid;
  min-width: 0;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px 16px;
  padding: 16px;
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 12px;
  background: var(--bg-card, #fff);
}

:deep(.gd-form-section__head) {
  grid-column: 1 / -1;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border-light, #edf1f7);
}

:deep(.gd-form-section__head > div) {
  display: grid;
  min-width: 0;
  gap: 2px;
}

:deep(.gd-form-section__head span) {
  color: var(--primary-600, #2563eb);
  font-size: 10px;
  font-weight: 750;
  letter-spacing: .06em;
}

:deep(.gd-form-section__head strong) {
  color: var(--text-primary, #0f172a);
  font-size: 14px;
}

:deep(.gd-form-section__head small) {
  color: var(--text-tertiary, #64748b);
  font-size: 11px;
  line-height: 1.5;
}

:deep(.gd-form-section__full) {
  grid-column: 1 / -1;
}

:deep(.gd-form-aside-card) {
  display: grid;
  gap: 9px;
  padding: 14px;
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 11px;
  background: var(--bg-card, #fff);
}

:deep(.gd-form-aside-card > span) {
  color: var(--primary-600, #2563eb);
  font-size: 10px;
  font-weight: 750;
  letter-spacing: .06em;
}

:deep(.gd-form-aside-card > strong) {
  color: var(--text-primary, #0f172a);
  font-size: 14px;
  line-height: 1.45;
}

:deep(.gd-form-aside-card > p) {
  margin: 0;
  color: var(--text-secondary, #64748b);
  font-size: 11px;
  line-height: 1.6;
}

:deep(.gd-form-checklist) {
  display: grid;
  gap: 7px;
  margin: 0;
  padding: 0;
  list-style: none;
}

:deep(.gd-form-checklist li) {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  color: var(--text-secondary, #475569);
  font-size: 11px;
  line-height: 1.45;
}

:deep(.gd-form-checklist li::before) {
  content: '○';
  flex: none;
  color: var(--text-tertiary, #94a3b8);
}

:deep(.gd-form-checklist li.is-ready::before) {
  content: '✓';
  color: var(--success-600, #16a34a);
  font-weight: 800;
}

@media (max-width: 1080px) {
  .gd-form-body--aside {
    grid-template-columns: minmax(0, 1fr) 250px;
  }
}

@media (max-width: 860px) {
  .gd-form-body--aside {
    grid-template-columns: 1fr;
  }

  .gd-form-aside {
    position: static;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .gd-form-page__crumb,
  .gd-form-status {
    display: none;
  }

  .gd-form-page__trail,
  .gd-form-head {
    padding: 10px 12px;
  }

  .gd-form-head {
    flex-wrap: wrap;
  }

  .gd-form-head__actions {
    width: 100%;
  }

  .gd-form-body {
    padding: 12px;
  }

  .gd-form-aside,
  :deep(.ie-form),
  :deep(.gd-form-section) {
    grid-template-columns: 1fr;
  }

  :deep(.ie-fld--full),
  :deep(.gd-form-section),
  :deep(.gd-form-section__head),
  :deep(.gd-form-section__full) {
    grid-column: 1;
  }

  .gd-form-footer {
    flex-wrap: wrap;
  }

  .gd-form-footer__busy {
    width: 100%;
  }
}
</style>
