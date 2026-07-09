<template>
  <div class="app-column-config">
    <button type="button" class="app-column-config__trigger" @click.stop="open = !open">
      ⚙ 列设置<span v-if="hiddenCount" class="app-column-config__badge">{{ hiddenCount }}</span>
    </button>

    <div v-if="open" class="app-column-config__panel">
      <div class="app-column-config__head">
        <span>显示列（{{ visibleCount }}/{{ columns.length }}）</span>
        <button type="button" class="app-column-config__reset" @click="resetAll">全选</button>
      </div>
      <ul class="app-column-config__list">
        <li v-for="(c, i) in columns" :key="c.key" class="app-column-config__item">
          <label class="app-column-config__check" :class="{ 'is-locked': c.required }">
            <input
              type="checkbox"
              :checked="c.visible !== false"
              :disabled="c.required"
              @change="toggle(i)"
            />
            {{ c.label }}
            <span v-if="c.required" class="app-column-config__lock">必显</span>
          </label>
          <span class="app-column-config__move">
            <button type="button" :disabled="i === 0" aria-label="上移" @click="move(i, -1)">↑</button>
            <button type="button" :disabled="i === columns.length - 1" aria-label="下移" @click="move(i, 1)">↓</button>
          </span>
        </li>
      </ul>
    </div>
  </div>
</template>

<script>
/**
 * AppColumnConfig — 表格列显示/顺序配置（配合既有 DataTable 使用，不改 DataTable 本体）。
 * v-model:columns 绑定列定义数组。
 * Props: columns: [{ key, label, visible?, required?(必显不可关) }]
 * Emits: update:columns（返回新的列数组，业务方据此渲染 DataTable 列）
 */
export default {
  name: 'AppColumnConfig',
  props: {
    columns: { type: Array, default: () => [] }
  },
  emits: ['update:columns'],
  data() {
    return { open: false }
  },
  computed: {
    visibleCount() { return this.columns.filter((c) => c.visible !== false).length },
    hiddenCount() { return this.columns.filter((c) => c.visible === false).length }
  },
  methods: {
    emit(next) { this.$emit('update:columns', next) },
    toggle(i) {
      const next = this.columns.map((c, idx) => (idx === i ? { ...c, visible: c.visible === false } : c))
      this.emit(next)
    },
    move(i, dir) {
      const j = i + dir
      if (j < 0 || j >= this.columns.length) return
      const next = this.columns.slice()
      ;[next[i], next[j]] = [next[j], next[i]]
      this.emit(next)
    },
    resetAll() {
      this.emit(this.columns.map((c) => ({ ...c, visible: true })))
    },
    onOutside(e) { if (!this.$el.contains(e.target)) this.open = false }
  },
  mounted() { document.addEventListener('click', this.onOutside) },
  beforeUnmount() { document.removeEventListener('click', this.onOutside) }
}
</script>

<style scoped>
.app-column-config { position: relative; display: inline-block; }
.app-column-config__trigger {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  height: 32px;
  padding: 0 var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.app-column-config__trigger:hover { border-color: var(--primary-500); color: var(--primary-600); }
.app-column-config__badge {
  min-width: 16px; height: 16px; padding: 0 4px;
  border-radius: var(--radius-full); background: var(--warning-500); color: #fff;
  font-size: 10px; display: inline-flex; align-items: center; justify-content: center;
}
.app-column-config__panel {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  z-index: 30;
  width: 240px;
  background: var(--bg-card);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  box-shadow: var(--shadow-md);
}
.app-column-config__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-light);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.app-column-config__reset { border: none; background: none; color: var(--text-link); cursor: pointer; font-size: var(--font-size-xs); }
.app-column-config__list { list-style: none; margin: 0; padding: var(--space-1); max-height: 280px; overflow-y: auto; }
.app-column-config__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
}
.app-column-config__item:hover { background: var(--bg-hover); }
.app-column-config__check {
  display: flex; align-items: center; gap: var(--space-2);
  font-size: var(--font-size-sm); color: var(--text-primary); cursor: pointer;
}
.app-column-config__check.is-locked { color: var(--text-tertiary); cursor: default; }
.app-column-config__lock { font-size: 10px; color: var(--text-tertiary); border: 1px solid var(--border-light); border-radius: var(--radius-sm); padding: 0 3px; }
.app-column-config__move { display: flex; gap: 2px; }
.app-column-config__move button {
  width: 20px; height: 20px; border: 1px solid var(--border-light);
  background: var(--bg-card); border-radius: var(--radius-sm); cursor: pointer; color: var(--text-secondary); font-size: 10px;
}
.app-column-config__move button:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
