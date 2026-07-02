<template>
  <section class="app-lifecycle-banner">
    <div class="app-lifecycle-banner__content">
      <span class="app-lifecycle-banner__eyebrow">VOCATIONAL EDUCATION · STUDENT SUCCESS</span>
      <h1>{{ title }}</h1>
      <p>{{ subtitle }}</p>

      <div class="app-lifecycle-banner__stages">
        <div
          v-for="(stage, idx) in stages"
          :key="stage.key"
          class="app-lifecycle-banner__stage"
          :class="`is-${stage.status}`"
        >
          <div class="app-lifecycle-banner__stage-track">
            <span class="app-lifecycle-banner__stage-dot" />
            <span v-if="idx < stages.length - 1" class="app-lifecycle-banner__stage-line" />
          </div>
          <div class="app-lifecycle-banner__stage-info">
            <span class="app-lifecycle-banner__stage-label">{{ stage.label }}</span>
            <span class="app-lifecycle-banner__stage-detail">{{ stage.detail }}</span>
          </div>
        </div>
      </div>

      <div class="app-lifecycle-banner__capsules">
        <span v-for="cap in capsules" :key="cap.label" class="app-lifecycle-banner__capsule">
          <i class="app-lifecycle-banner__capsule-dot" :class="`is-${cap.type}`" />
          {{ cap.label }} <strong>{{ cap.value }}</strong>
        </span>
      </div>
    </div>
    <div class="app-lifecycle-banner__visual" aria-hidden="true">
      <div class="app-lifecycle-banner__ring app-lifecycle-banner__ring--outer" />
      <div class="app-lifecycle-banner__ring app-lifecycle-banner__ring--inner" />
      <div class="app-lifecycle-banner__core">全周期<br /><strong>360°</strong></div>
    </div>
  </section>
</template>

<script>
export default {
  name: 'AppLifecycleBanner',
  props: {
    title: { type: String, required: true },
    subtitle: { type: String, required: true },
    stages: { type: Array, default: () => [] },
    capsules: { type: Array, default: () => [] }
  }
}
</script>

<style scoped>
.app-lifecycle-banner {
  position: relative;
  overflow: hidden;
  min-height: 200px;
  max-height: 220px;
  padding: var(--space-5) var(--space-6);
  border: 1px solid var(--card-border);
  border-radius: var(--radius-xl);
  background: linear-gradient(135deg, var(--bg-card) 0%, var(--primary-50) 100%);
  box-shadow: var(--shadow-section);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}
.app-lifecycle-banner__content {
  position: relative;
  z-index: 1;
  flex: 1;
  min-width: 0;
}
.app-lifecycle-banner__eyebrow {
  color: var(--primary-600);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  letter-spacing: 0.12em;
}
.app-lifecycle-banner h1 {
  margin: var(--space-1) 0;
  color: var(--text-primary);
  font-size: 26px;
  font-weight: var(--font-weight-bold);
  line-height: 1.25;
}
.app-lifecycle-banner p {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  line-height: 1.5;
  max-width: 680px;
}
.app-lifecycle-banner__stages {
  display: flex;
  gap: 0;
  margin-top: var(--space-4);
  overflow-x: auto;
  padding-bottom: 2px;
}
.app-lifecycle-banner__stage {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 120px;
  flex: 1;
}
.app-lifecycle-banner__stage-track {
  display: flex;
  align-items: center;
  height: 12px;
}
.app-lifecycle-banner__stage-dot {
  width: 10px;
  height: 10px;
  border-radius: var(--radius-full);
  background: var(--border-base);
  flex-shrink: 0;
  border: 2px solid var(--bg-card);
  box-shadow: 0 0 0 1px var(--border-base);
}
.app-lifecycle-banner__stage.is-done .app-lifecycle-banner__stage-dot {
  background: var(--success-500);
  box-shadow: 0 0 0 1px var(--success-500);
}
.app-lifecycle-banner__stage.is-active .app-lifecycle-banner__stage-dot {
  background: var(--primary-600);
  box-shadow: 0 0 0 1px var(--primary-600);
}
.app-lifecycle-banner__stage-line {
  flex: 1;
  height: 2px;
  background: var(--border-base);
  margin: 0 2px;
}
.app-lifecycle-banner__stage.is-done .app-lifecycle-banner__stage-line {
  background: var(--success-500);
  opacity: 0.5;
}
.app-lifecycle-banner__stage-label {
  font-size: var(--font-size-xs);
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
  white-space: nowrap;
}
.app-lifecycle-banner__stage-detail {
  font-size: 11px;
  color: var(--text-secondary);
  white-space: nowrap;
}
.app-lifecycle-banner__capsules {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-3);
}
.app-lifecycle-banner__capsule {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 5px var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-full);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  box-shadow: var(--shadow-capsule);
}
.app-lifecycle-banner__capsule strong {
  color: var(--text-primary);
  font-weight: var(--font-weight-bold);
}
.app-lifecycle-banner__capsule-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
}
.app-lifecycle-banner__capsule-dot.is-todo {
  background: var(--warning-500);
}
.app-lifecycle-banner__capsule-dot.is-risk {
  background: var(--danger-500);
}
.app-lifecycle-banner__capsule-dot.is-update {
  background: var(--success-500);
}
.app-lifecycle-banner__visual {
  position: relative;
  width: 130px;
  height: 120px;
  flex-shrink: 0;
  display: grid;
  place-items: center;
  opacity: 0.35;
}
.app-lifecycle-banner__ring {
  position: absolute;
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-full);
}
.app-lifecycle-banner__ring--outer {
  width: 110px;
  height: 110px;
}
.app-lifecycle-banner__ring--inner {
  width: 76px;
  height: 76px;
  background: var(--primary-50);
}
.app-lifecycle-banner__core {
  text-align: center;
  color: var(--slate-blue-600);
  font-size: var(--font-size-xs);
  line-height: 1.4;
}
.app-lifecycle-banner__core strong {
  color: var(--primary-600);
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-bold);
}
@media (max-width: 1200px) {
  .app-lifecycle-banner__visual {
    display: none;
  }
}
@media (max-width: 760px) {
  .app-lifecycle-banner {
    max-height: none;
    min-height: auto;
  }
}
</style>
