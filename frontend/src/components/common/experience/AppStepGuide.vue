<template>
  <div v-if="modelValue" class="app-step-guide__mask">
    <div class="app-step-guide" role="dialog" aria-modal="false" aria-label="页面操作引导" @click.stop>
      <div class="app-step-guide__badge">{{ current + 1 }} / {{ steps.length }}</div>
      <h3 class="app-step-guide__title">{{ step.title }}</h3>
      <p class="app-step-guide__desc">{{ step.description }}</p>
      <div v-if="step.image" class="app-step-guide__img">
        <img :src="step.image" :alt="step.title" />
      </div>

      <div class="app-step-guide__dots">
        <span
          v-for="(s, i) in steps"
          :key="i"
          class="app-step-guide__dot"
          :class="{ 'is-active': i === current }"
        />
      </div>

      <div class="app-step-guide__actions">
        <button type="button" class="app-step-guide__skip" @click="onSkip">跳过引导</button>
        <div class="app-step-guide__nav">
          <button v-if="current > 0" type="button" class="app-step-guide__btn" @click="prev">上一步</button>
          <button v-if="!isLast" type="button" class="app-step-guide__btn is-primary" @click="next">下一步</button>
          <button v-else type="button" class="app-step-guide__btn is-primary" @click="finish">开始使用</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
/**
 * AppStepGuide —（轻量）新手引导。首次进入模块时的分步说明卡片。
 *
 * 交互原则：
 * - 这是“辅助说明”而不是业务确认弹窗，因此绝不能锁死应用级控制（身份切换、帮助、账户菜单）。
 * - 背景蒙层只承担视觉弱化，不拦截鼠标/触摸；只有引导卡片自身接收指针事件。
 * - 引导仍可通过“跳过 / 下一步 / 开始使用”显式关闭，页面业务操作可在引导打开时继续进行。
 *
 * 需要「箭头指向具体按钮」的强引导时，再单独评估引入 tour 库，不在本组件伪造全屏模态行为。
 * Props: modelValue(v-model 显隐) / steps:[{ title, description, image? }] / startIndex
 * Emits: update:modelValue / change(index) / finish / skip
 */
export default {
  name: 'AppStepGuide',
  props: {
    modelValue: { type: Boolean, default: false },
    steps: { type: Array, default: () => [] },
    startIndex: { type: Number, default: 0 }
  },
  emits: ['update:modelValue', 'change', 'finish', 'skip'],
  data() {
    return { current: this.startIndex }
  },
  watch: {
    modelValue(v) { if (v) this.current = this.startIndex }
  },
  computed: {
    step() { return this.steps[this.current] || {} },
    isLast() { return this.current >= this.steps.length - 1 }
  },
  methods: {
    next() { if (!this.isLast) { this.current++; this.$emit('change', this.current) } },
    prev() { if (this.current > 0) { this.current--; this.$emit('change', this.current) } },
    close() { this.$emit('update:modelValue', false) },
    finish() { this.close(); this.$emit('finish') },
    onSkip() { this.close(); this.$emit('skip') }
  }
}
</script>

<style scoped>
.app-step-guide__mask {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal, 1000);
  background: var(--bg-mask, rgba(15, 23, 42, 0.35));
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-5);
  /*
   * 轻量引导只弱化背景，不得拦截应用级操作。
   * 卡片在下方单独恢复 pointer-events，因此身份切换/帮助/账户菜单仍可直接操作。
   */
  pointer-events: none;
}
.app-step-guide {
  width: 420px;
  max-width: 100%;
  background: var(--bg-card);
  border: 1px solid rgba(255, 255, 255, 0.72);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  padding: var(--space-6);
  text-align: center;
  pointer-events: auto;
}
.app-step-guide__badge {
  display: inline-block;
  padding: 2px var(--space-3);
  border-radius: var(--radius-full);
  background: var(--primary-50);
  color: var(--primary-700);
  font-size: var(--font-size-xs);
  margin-bottom: var(--space-3);
}
.app-step-guide__title { margin: 0 0 var(--space-2); font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.app-step-guide__desc { margin: 0; font-size: var(--font-size-sm); color: var(--text-secondary); line-height: var(--line-height-base); }
.app-step-guide__img { margin: var(--space-4) 0; }
.app-step-guide__img img { max-width: 100%; border-radius: var(--radius-base); border: 1px solid var(--border-light); }
.app-step-guide__dots { display: flex; justify-content: center; gap: var(--space-1); margin: var(--space-4) 0; }
.app-step-guide__dot { width: 7px; height: 7px; border-radius: var(--radius-full); background: var(--gray-200); transition: all 0.2s; }
.app-step-guide__dot.is-active { width: 18px; border-radius: var(--radius-full); background: var(--primary-500); }
.app-step-guide__actions { display: flex; align-items: center; justify-content: space-between; }
.app-step-guide__skip { border: none; background: none; color: var(--text-tertiary); cursor: pointer; font-size: var(--font-size-sm); }
.app-step-guide__skip:hover { color: var(--text-secondary); }
.app-step-guide__nav { display: flex; gap: var(--space-2); }
.app-step-guide__btn {
  height: 32px;
  padding: 0 var(--space-4);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.app-step-guide__btn.is-primary { background: var(--primary-600); border-color: var(--primary-600); color: #fff; }
.app-step-guide__btn.is-primary:hover { background: var(--primary-700); }
</style>
