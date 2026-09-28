<template>
  <div class="mps" :class="{ 'mps--compact': compactHeader }">
    <SecurityWatermark :visible="watermark" :purpose="watermarkPurpose" />
    <div class="mps__head">
      <div class="mps__title-wrap">
        <h1 class="mps__title">{{ title }}</h1>
        <slot name="title-meta" />
        <p v-if="!compactHeader && subtitle && (!conciseBusinessHeader || showSubtitleInConcise)" class="mps__subtitle">{{ subtitle }}</p>
      </div>
      <slot name="context"><component :is="businessHeader.component" v-if="businessHeader" class="mps__context" /></slot>
      <div v-if="compactHeader && !$slots.summary && $slots.actions" class="mps__actions"><slot name="actions" /></div>
      <div v-if="!compactHeader && (!conciseBusinessHeader || $slots.actions)" class="mps__meta">
        <span v-if="roleName && !conciseBusinessHeader" class="mps__chip mps__chip--role">{{ roleName }}</span>
        <span v-if="dataScopeName && !conciseBusinessHeader" class="mps__chip mps__chip--scope">
          <span class="mps__chip-dot" />数据范围：{{ dataScopeName }}
        </span>
        <div v-if="$slots.actions" class="mps__actions"><slot name="actions" /></div>
      </div>
    </div>
    <div v-if="compactHeader && $slots.summary" class="mps__toolbar">
      <div class="mps__summary"><slot name="summary" /></div>
      <div class="mps__actions"><slot name="actions" /></div>
    </div>
    <slot />
  </div>
</template>

<script>
/**
 * ModulePageShell — PC 业务模块页面外壳（通用，不绑定任何业务）。
 * 职责：页面标题区 + 当前角色 + 数据范围提示 + 页面级水印容器。
 * Props:
 *  - title / subtitle：页面标题（业务方传入，禁止在此写死业务名）
 *  - roleName：当前角色显示名（来自模块 api 的 currentRole，禁止硬编码）
 *  - dataScopeName：数据范围显示名（来自模块 api 的 dataScope）
 *  - watermark：是否渲染页面水印（默认开）
 * Slots：actions（标题右侧操作区）/ default（页面内容）
 */
import SecurityWatermark from '@/security/components/SecurityWatermark.vue'

export default {
  name: 'ModulePageShell',
  components: { SecurityWatermark },
  inject: { compactWorkspace: { default: false }, conciseBusinessHeader: { default: false }, businessHeader: { default: null } },
  provide() { return { businessHeader: null } },
  data() { return { releaseHeader: null } },
  computed: { compactHeader() { return this.compact || this.compactWorkspace || this.conciseBusinessHeader || !!this.businessHeader } },
  mounted() { this.releaseHeader = this.businessHeader?.register() || null },
  beforeUnmount() { this.releaseHeader?.() },
  props: {
    compact: { type: Boolean, default: false },
    title: { type: String, required: true },
    subtitle: { type: String, default: '' },
    roleName: { type: String, default: '' },
    dataScopeName: { type: String, default: '' },
    showSubtitleInConcise: { type: Boolean, default: false },
    watermark: { type: Boolean, default: true },
    watermarkPurpose: { type: String, default: '' }
  }
}
</script>

<style scoped>
.mps__context { margin-left: auto; max-width: 65%; min-width: 0; padding: 0; border: 0; background: transparent; }
.mps__context :deep(select) { min-width: 0; max-width: 340px; }
.mps__context :deep(.gbs__meta) { display: none; }
@media(max-width: 900px) { .mps__context { max-width: 100%; } }
@media(max-width: 700px) {
  .mps__toolbar { flex-wrap: wrap; overflow: visible; padding-block: 4px; }
  .mps__summary { flex: 1 1 100%; overflow-x: auto; scrollbar-width: none; }
  .mps__summary::-webkit-scrollbar { display: none; }
  .mps__toolbar .mps__actions { width: 100%; margin-left: 0; }
}

.mps--compact { gap: 12px; }
.mps--compact .mps__head { align-items: center; min-height: 48px; gap: 12px; }
.mps--compact .mps__title-wrap { display: flex; align-items: center; gap: 12px; }
.mps--compact .mps__title { font-size: 22px; }
.mps__toolbar { display: flex; align-items: center; gap: 16px; min-height: 44px; border-block: 1px solid var(--line, #dce5f3); overflow-x: auto; scrollbar-width: none; }
.mps__toolbar::-webkit-scrollbar { display: none; }
.mps__summary { display: flex; align-items: center; flex: 1; min-width: 0; }
.mps__toolbar .mps__actions { flex-shrink: 0; margin-left: auto; }
.mps {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-height: 100%;
}
.mps__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
}
.mps__title {
  margin: 0;
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-bold);
  letter-spacing: -0.01em;
}
.mps__subtitle {
  margin: var(--space-1) 0 0;
  font-size: var(--font-size-sm);
  color: var(--t3);
}
.mps__meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.mps__actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.mps__chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  height: 28px;
  padding: 0 var(--space-3);
  border-radius: var(--radius-full);
  font-size: var(--font-size-xs);
  white-space: nowrap;
}
.mps__chip--role {
  color: var(--pri);
  background: var(--pri-bg);
  border: 1px solid var(--pri-100);
  font-weight: var(--font-weight-medium);
}
.mps__chip--scope {
  color: var(--t2);
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid var(--card-b);
}
.mps__chip-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--pri);
}
</style>
