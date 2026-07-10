<template>
  <section class="mh">
    <div class="mh__top">
      <div class="mh__title-wrap">
        <div class="mh__title">{{ title }}</div>
        <div v-if="subtitle" class="mh__subtitle">{{ subtitle }}</div>
      </div>
      <div v-if="chips.length" class="mh__chips">
        <span v-for="c in chips" :key="c" class="mh__chip">{{ c }}</span>
      </div>
    </div>
    <div v-if="stats.length" class="mh__stats">
      <div v-for="s in stats" :key="s.label" class="mh__stat">
        <div class="mh__stat-value">{{ s.value }}</div>
        <div class="mh__stat-label">{{ s.label }}</div>
        <div v-if="s.trend" class="mh__stat-trend" :class="trendClass(s)">{{ s.trend }}</div>
      </div>
    </div>
    <div v-if="flow.length" class="mh__flow">
      <div v-for="(f, i) in flow" :key="f.label" class="mh__flow-node" :class="{ 'is-active': f.active }">
        <span class="mh__flow-count">{{ f.value }}</span>
        <span class="mh__flow-label">{{ f.label }}</span>
        <span v-if="i < flow.length - 1" class="mh__flow-arrow">›</span>
      </div>
    </div>
  </section>
</template>

<script>
/**
 * ModuleHero — 模块看板头部概览条（通用）。
 * Props:
 *  - title / subtitle：概览标题（如批次名，由业务传入）
 *  - chips: string[] 关键信息胶囊（角色 / 范围 / 批次时间等）
 *  - stats: [{ label, value, trend?, trendQuality?: 'good'|'bad'|'neutral' }]
 *  - flow:  [{ label, value, active? }] 主状态机各阶段人数轨道
 * 趋势颜色只由 trendQuality 决定（V2.1 冻结），禁止按正负号推断。
 */
export default {
  name: 'ModuleHero',
  props: {
    title: { type: String, required: true },
    subtitle: { type: String, default: '' },
    chips: { type: Array, default: () => [] },
    stats: { type: Array, default: () => [] },
    flow: { type: Array, default: () => [] }
  },
  methods: {
    trendClass(s) {
      const q = s.trendQuality || 'neutral'
      return `is-${q}`
    }
  }
}
</script>

<style scoped>
/* 玻璃 Hero：深蓝渐变 + 网格纹理 + orbit 数字站点（母版 .hb / .orbit） */
.mh {
  position: relative;
  border-radius: 18px;
  overflow: hidden;
  background: var(--hero-grad);
  border: 1px solid var(--hero-bd);
  color: var(--hero-tx);
  padding: 22px 26px;
  box-shadow: var(--hero-shadow);
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.mh::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    linear-gradient(var(--hero-grid) 1px, transparent 1px),
    linear-gradient(90deg, var(--hero-grid) 1px, transparent 1px);
  background-size: 30px 30px;
  pointer-events: none;
}
.mh__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
  position: relative;
}
.mh__title {
  font-size: 18px;
  font-weight: var(--font-weight-bold);
  letter-spacing: -0.01em;
}
.mh__subtitle {
  margin-top: var(--space-1);
  font-size: 12.5px;
  color: var(--hero-sub);
}
.mh__chips {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.mh__chip {
  height: 26px;
  display: inline-flex;
  align-items: center;
  padding: 0 12px;
  border-radius: 20px;
  background: var(--hero-chip-bg);
  border: 1px solid var(--hero-chip-bd);
  color: var(--hero-chip-tx);
  font-size: 12px;
  font-weight: var(--font-weight-medium);
  white-space: nowrap;
}
.mh__stats {
  display: flex;
  gap: 40px;
  flex-wrap: wrap;
  position: relative;
}
.mh__stat {
  background: transparent;
  border: none;
  border-radius: 0;
  padding: 0;
  box-shadow: none;
}
.mh__stat-value {
  font-size: 24px;
  font-weight: var(--font-weight-bold);
  font-variant-numeric: var(--font-numeric);
  line-height: 1.15;
  color: var(--hero-tx);
  letter-spacing: -0.02em;
}
.mh__stat-label {
  margin-top: 3px;
  font-size: 11.5px;
  color: var(--hero-sub);
  white-space: nowrap;
}
.mh__stat-trend {
  margin-top: 2px;
  font-size: 11px;
  font-weight: var(--font-weight-medium);
  white-space: nowrap;
}
.mh__stat-trend.is-good { color: var(--hero-ok); }
.mh__stat-trend.is-bad { color: var(--hero-err); }
.mh__stat-trend.is-neutral { color: var(--hero-dim); }
/* orbit 数字站点 */
.mh__flow {
  display: flex;
  justify-content: space-between;
  position: relative;
  padding: 0 4px;
  margin-top: 2px;
}
.mh__flow::before {
  content: '';
  position: absolute;
  left: 34px;
  right: 34px;
  top: 22px;
  height: 2px;
  border-radius: 1px;
  background: var(--hero-line);
}
.mh__flow-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  position: relative;
  z-index: 1;
  flex: 1;
  color: var(--hero-sub);
  font-size: 11px;
}
.mh__flow-count {
  min-width: 46px;
  height: 46px;
  padding: 0 8px;
  border-radius: 23px;
  background: var(--hero-dot-bg);
  border: 1.5px solid var(--hero-dot-bd);
  color: var(--hero-dot-tx);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: var(--font-weight-bold);
  font-variant-numeric: var(--font-numeric);
}
.mh__flow-node.is-active .mh__flow-count {
  background: var(--hero-dot-hot-bg);
  border-color: var(--hero-dot-hot-bd);
  color: var(--hero-dot-hot-tx);
  box-shadow: 0 0 18px var(--glow);
  animation: pulseRing 2.4s infinite;
}
.mh__flow-label {
  white-space: nowrap;
}
.mh__flow-arrow {
  display: none;
}
@media (max-width: 900px) {
  .mh__flow {
    flex-wrap: wrap;
    gap: 10px;
  }
  .mh__flow::before {
    display: none;
  }
  .mh__stats {
    gap: 24px;
  }
}
</style>
