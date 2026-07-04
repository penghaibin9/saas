<template>
  <div class="mps">
    <SecurityWatermark :visible="watermark" :purpose="watermarkPurpose" />
    <div class="mps__head">
      <div class="mps__title-wrap">
        <h1 class="mps__title">{{ title }}</h1>
        <p v-if="subtitle" class="mps__subtitle">{{ subtitle }}</p>
      </div>
      <div class="mps__meta">
        <span v-if="roleName" class="mps__chip mps__chip--role">{{ roleName }}</span>
        <span v-if="dataScopeName" class="mps__chip mps__chip--scope">
          <span class="mps__chip-dot" />数据范围：{{ dataScopeName }}
        </span>
        <div v-if="$slots.actions" class="mps__actions"><slot name="actions" /></div>
      </div>
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
  props: {
    title: { type: String, required: true },
    subtitle: { type: String, default: '' },
    roleName: { type: String, default: '' },
    dataScopeName: { type: String, default: '' },
    watermark: { type: Boolean, default: true },
    watermarkPurpose: { type: String, default: '' }
  }
}
</script>

<style scoped>
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
  font-size: 20px;
  font-weight: var(--font-weight-bold);
  letter-spacing: -0.01em;
}
.mps__subtitle {
  margin: var(--space-1) 0 0;
  font-size: 12.5px;
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
  height: 26px;
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
