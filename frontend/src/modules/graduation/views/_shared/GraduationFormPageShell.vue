<template>
  <section
    v-if="layout === 'inline'"
    class="gd-form-shell gd-form-shell--inline"
    :class="{ 'is-busy': busy, 'has-aside': hasAside }"
    :aria-busy="busy ? 'true' : 'false'"
  >
    <header class="gd-form-head">
      <button type="button" class="gd-form-back" :disabled="busy" @click="goBack">
        <span aria-hidden="true">←</span>{{ backLabel }}
      </button>
      <div class="gd-form-head__titles">
        <span class="gd-form-head__eyebrow">{{ eyebrow }}</span>
        <h3 class="gd-form-head__title">{{ title }}</h3>
        <p v-if="subtitle" class="gd-form-head__subtitle">{{ subtitle }}</p>
      </div>
      <span v-if="statusText" class="gd-form-status" :class="`is-${statusTone}`">{{ statusText }}</span>
      <div v-if="$slots.headerActions" class="gd-form-head__actions"><slot name="headerActions" /></div>
    </header>

    <div v-if="$slots.context" class="gd-form-context"><slot name="context" /></div>
    <p v-if="purpose" class="gd-form-purpose"><span>{{ purpose }}</span></p>

    <div class="gd-form-body" :class="{ 'gd-form-body--aside': hasAside }">
      <main class="gd-form-content"><slot /></main>
      <aside v-if="hasAside" class="gd-form-aside" aria-label="办理条件与下一步"><slot name="aside" /></aside>
    </div>

    <footer v-if="$slots.footer" class="gd-form-footer">
      <span v-if="busy" class="gd-form-footer__busy" role="status">正在提交，请勿切换页面或重复点击</span>
      <slot name="footer" />
    </footer>
  </section>

  <div v-else class="gd-form-page" :class="{ 'is-busy': busy }" :aria-busy="busy ? 'true' : 'false'">
    <ModulePageShell
      :title="title"
      :subtitle="subtitle"
      :role-name="ctx.currentRole.roleName"
      :data-scope-name="ctx.dataScope.scopeName"
    >
      <template #actions>
        <button type="button" class="gd-form-back" :disabled="busy" @click="goBack">
          <span aria-hidden="true">←</span>{{ backLabel }}
        </button>
        <span v-if="statusText" class="gd-form-status" :class="`is-${statusTone}`">{{ statusText }}</span>
        <slot name="headerActions" />
      </template>

      <section class="gd-form-shell gd-form-shell--page" :class="{ 'has-aside': hasAside }">
        <div v-if="$slots.context" class="gd-form-context"><slot name="context" /></div>
        <p v-if="purpose" class="gd-form-purpose">
          <b>{{ eyebrow }}</b><span>{{ purpose }}</span>
        </p>

        <div class="gd-form-body" :class="{ 'gd-form-body--aside': hasAside }">
          <main class="gd-form-content"><slot /></main>
          <aside v-if="hasAside" class="gd-form-aside" aria-label="办理条件与下一步"><slot name="aside" /></aside>
        </div>

        <footer v-if="$slots.footer" class="gd-form-footer gd-form-footer--sticky">
          <span v-if="busy" class="gd-form-footer__busy" role="status">正在提交，请勿切换页面或重复点击</span>
          <slot name="footer" />
        </footer>
      </section>
    </ModulePageShell>
  </div>
</template>

<script>
import { ModulePageShell } from '@/components/business'

const SAFE_PREFIX = '/admin/graduation/'

export default {
  name: 'GraduationFormPageShell',
  components: { ModulePageShell },
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
      const raw = Array.isArray(this.$route.query.returnTo) ? this.$route.query.returnTo[0] : this.$route.query.returnTo
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
  min-width: 0;
  min-height: 100%;
}

.gd-form-shell {
  min-width: 0;
  overflow: visible;
  border: 1px solid var(--border-light, #e1e8f2);
  border-radius: 11px;
  background: var(--bg-card, #fff);
  box-shadow: 0 6px 20px rgba(15, 40, 90, .045);
}

.gd-form-shell--inline {
  margin-top: 2px;
  overflow: hidden;
}

.gd-form-head {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 10px;
  padding: 11px 13px;
  border-bottom: 1px solid var(--border-light, #e8edf5);
  background: var(--bg-subtle, #f8fafc);
}

.gd-form-head__titles {
  display: grid;
  flex: 1;
  min-width: 0;
  gap: 1px;
}

.gd-form-head__eyebrow {
  color: var(--primary-600, #2563eb);
  font-size: 9px;
  font-weight: 750;
  letter-spacing: .06em;
}

.gd-form-head__title {
  margin: 0;
  color: var(--text-primary, #0f172a);
  font-size: 16px;
  line-height: 1.35;
}

.gd-form-head__subtitle {
  margin: 1px 0 0;
  overflow: hidden;
  color: var(--text-tertiary, #64748b);
  font-size: 11px;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.gd-form-head__actions {
  display: flex;
  flex: none;
  align-items: center;
  gap: 7px;
}

.gd-form-back {
  display: inline-flex;
  flex: none;
  align-items: center;
  gap: 4px;
  min-height: 32px;
  padding: 0 10px;
  border: 1px solid var(--border-base, #d7deea);
  border-radius: 8px;
  background: var(--bg-card, #fff);
  color: var(--text-secondary, #475569);
  cursor: pointer;
  font-size: 12px;
}

.gd-form-back:hover:not(:disabled) {
  border-color: var(--primary-300, #93c5fd);
  color: var(--primary-700, #1d4ed8);
}

.gd-form-back:disabled {
  cursor: not-allowed;
  opacity: .5;
}

.gd-form-status {
  flex: none;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 650;
  white-space: nowrap;
}

.gd-form-status.is-info { background: #eff6ff; color: #1d4ed8; }
.gd-form-status.is-success { background: #ecfdf3; color: #15803d; }
.gd-form-status.is-warning { background: #fff7ed; color: #b45309; }
.gd-form-status.is-danger { background: #fef2f2; color: #b91c1c; }

.gd-form-context {
  display: flex;
  align-items: stretch;
  min-width: 0;
  gap: 6px;
  padding: 7px 11px;
  overflow-x: auto;
  border-bottom: 1px solid var(--border-light, #edf1f7);
  background: var(--bg-subtle, #f8fafc);
}

.gd-form-purpose {
  display: flex;
  align-items: baseline;
  gap: 7px;
  margin: 0;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-light, #edf1f7);
  color: var(--text-secondary, #475569);
  font-size: 11px;
  line-height: 1.45;
}

.gd-form-purpose b {
  flex: none;
  color: var(--primary-700, #1d4ed8);
  font-size: 9px;
  letter-spacing: .05em;
}

.gd-form-purpose span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.gd-form-body {
  min-width: 0;
  padding: 13px;
}

.gd-form-body--aside {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(225px, 270px);
  align-items: start;
  gap: 12px;
}

.gd-form-content,
.gd-form-aside {
  min-width: 0;
}

.gd-form-aside {
  position: sticky;
  top: 10px;
  display: grid;
  gap: 8px;
}

.gd-form-footer {
  position: relative;
  z-index: 3;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  min-height: 58px;
  gap: 8px;
  padding: 9px 13px;
  border-top: 1px solid var(--border-light, #e8edf5);
  background: rgba(255, 255, 255, .97);
}

.gd-form-footer--sticky {
  position: sticky;
  bottom: 0;
  box-shadow: 0 -5px 14px rgba(15, 40, 90, .055);
}

.gd-form-footer__busy {
  margin-right: auto;
  color: var(--warning-700, #a16207);
  font-size: 10px;
}

.is-busy .gd-form-body {
  pointer-events: none;
  opacity: .72;
}

:deep(.ie-form) {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  min-width: 0;
  gap: 11px 13px;
}

:deep(.ie-fld) {
  display: grid;
  align-content: start;
  min-width: 0;
  gap: 5px;
  margin: 0;
}

:deep(.ie-fld--full) {
  grid-column: 1 / -1;
}

:deep(.ie-lbl) {
  color: var(--text-secondary, #475569);
  font-size: 11px;
  font-weight: 650;
  line-height: 1.4;
}

:deep(.ie-lbl i) {
  color: var(--danger-600, #dc2626);
  font-style: normal;
}

:deep(.ie-in) {
  width: 100%;
  min-width: 0;
  min-height: 38px;
  box-sizing: border-box;
  padding: 7px 9px;
  border: 1px solid var(--border-base, #cfd8e6);
  border-radius: 8px;
  outline: none;
  background: var(--bg-card, #fff);
  color: var(--text-primary, #0f172a);
  font-size: 12px;
}

:deep(textarea.ie-in) {
  min-height: 78px;
  resize: vertical;
  line-height: 1.5;
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
  font-size: 10px;
  line-height: 1.45;
}

:deep(.ie-err) {
  grid-column: 1 / -1;
  margin: 0;
  padding: 8px 10px;
  border: 1px solid var(--danger-200, #fecaca);
  border-radius: 8px;
  background: var(--danger-50, #fef2f2);
  color: var(--danger-700, #b91c1c);
  font-size: 11px;
}

:deep(.gd-form-section) {
  grid-column: 1 / -1;
  overflow: hidden;
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 9px;
  background: var(--bg-card, #fff);
}

:deep(.gd-form-section__head) {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  padding: 9px 11px;
  border-bottom: 1px solid var(--border-light, #e8edf5);
  background: var(--bg-subtle, #f8fafc);
}

:deep(.gd-form-section__head > div:first-child) {
  display: grid;
  gap: 1px;
}

:deep(.gd-form-section__head span) {
  color: var(--primary-600, #2563eb);
  font-size: 9px;
  font-weight: 750;
  letter-spacing: .05em;
}

:deep(.gd-form-section__head strong) {
  color: var(--text-primary, #0f172a);
  font-size: 12px;
}

:deep(.gd-form-section__head small) {
  color: var(--text-tertiary, #64748b);
  font-size: 9px;
  line-height: 1.35;
}

:deep(.gd-form-section > .ie-fld),
:deep(.gd-form-section > .ie-form),
:deep(.gd-form-section > .gd-form-grid) {
  margin: 0 11px;
}

:deep(.gd-form-section > .ie-fld:first-of-type),
:deep(.gd-form-section > .ie-form:first-of-type),
:deep(.gd-form-section > .gd-form-grid:first-of-type) {
  margin-top: 11px;
}

:deep(.gd-form-section > .ie-fld:last-child),
:deep(.gd-form-section > .ie-form:last-child),
:deep(.gd-form-section > .gd-form-grid:last-child) {
  margin-bottom: 11px;
}

:deep(.gd-form-aside-card) {
  display: grid;
  gap: 5px;
  padding: 10px;
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 9px;
  background: var(--bg-card, #fff);
}

:deep(.gd-form-aside-card > span) {
  color: var(--text-tertiary, #64748b);
  font-size: 9px;
}

:deep(.gd-form-aside-card > strong) {
  color: var(--text-primary, #0f172a);
  font-size: 11px;
}

:deep(.gd-form-aside-card > p) {
  margin: 0;
  color: var(--text-secondary, #475569);
  font-size: 9px;
  line-height: 1.45;
}

:deep(.gd-form-checklist) {
  display: grid;
  gap: 5px;
  margin: 2px 0 0;
  padding: 0;
  list-style: none;
}

:deep(.gd-form-checklist li) {
  position: relative;
  padding-left: 17px;
  color: var(--text-tertiary, #64748b);
  font-size: 9px;
}

:deep(.gd-form-checklist li::before) {
  position: absolute;
  left: 0;
  top: 1px;
  display: grid;
  width: 13px;
  height: 13px;
  place-items: center;
  border-radius: 50%;
  background: var(--gray-100, #f1f5f9);
  content: '·';
}

:deep(.gd-form-checklist li.is-ready) {
  color: var(--success-700, #047857);
}

:deep(.gd-form-checklist li.is-ready::before) {
  background: var(--success-50, #ecfdf5);
  content: '✓';
}

@media (max-width: 1060px) {
  .gd-form-body--aside {
    grid-template-columns: 1fr;
  }
  .gd-form-aside {
    position: static;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .gd-form-head__subtitle,
  .gd-form-purpose span {
    white-space: normal;
  }
  .gd-form-context {
    flex-wrap: wrap;
    overflow: visible;
  }
  .gd-form-body {
    padding: 10px;
  }
  :deep(.ie-form) {
    grid-template-columns: 1fr;
  }
  .gd-form-aside {
    grid-template-columns: 1fr;
  }
  .gd-form-footer {
    flex-wrap: wrap;
  }
  .gd-form-footer__busy {
    width: 100%;
  }
}
</style>
