<template>
  <div class="app-pagination" :class="{ 'is-disabled': disabled }">
    <span v-if="showTotal" class="app-pagination__total">共 {{ total }} 条</span>

    <div class="app-pagination__pages">
      <button
        type="button"
        class="app-pagination__btn"
        :disabled="disabled || page <= 1"
        aria-label="上一页"
        @click="go(page - 1)"
      >‹</button>

      <button
        v-for="p in pageItems"
        :key="p.key"
        type="button"
        class="app-pagination__btn"
        :class="{ 'is-active': p.num === page, 'is-ellipsis': p.ellipsis }"
        :disabled="disabled || p.ellipsis"
        @click="!p.ellipsis && go(p.num)"
      >{{ p.ellipsis ? '…' : p.num }}</button>

      <button
        type="button"
        class="app-pagination__btn"
        :disabled="disabled || page >= totalPages"
        aria-label="下一页"
        @click="go(page + 1)"
      >›</button>
    </div>

    <label v-if="showSizeChanger" class="app-pagination__size">
      每页
      <select class="app-pagination__size-el" :value="pageSize" :disabled="disabled" @change="onSize">
        <option v-for="s in pageSizes" :key="s" :value="s">{{ s }}</option>
      </select>
      条
    </label>

    <label v-if="showJumper" class="app-pagination__jumper">
      跳至
      <input
        class="app-pagination__jumper-el"
        type="text"
        inputmode="numeric"
        :disabled="disabled"
        @keydown.enter="onJump"
      />
      页
    </label>
  </div>
</template>

<script>
/**
 * AppPagination — 统一分页器（页码 + 每页条数 + 跳页）。
 * Props: total / page(当前页,v-model:page) / pageSize(v-model:pageSize) / pageSizes /
 *   showTotal / showSizeChanger / showJumper / disabled
 * Emits: update:page / update:pageSize / change({ page, pageSize })
 */
export default {
  name: 'AppPagination',
  props: {
    total: { type: Number, default: 0 },
    page: { type: Number, default: 1 },
    pageSize: { type: Number, default: 20 },
    pageSizes: { type: Array, default: () => [10, 20, 50, 100] },
    showTotal: { type: Boolean, default: true },
    showSizeChanger: { type: Boolean, default: true },
    showJumper: { type: Boolean, default: false },
    disabled: { type: Boolean, default: false }
  },
  emits: ['update:page', 'update:pageSize', 'change'],
  computed: {
    totalPages() {
      return Math.max(1, Math.ceil(this.total / this.pageSize))
    },
    pageItems() {
      const total = this.totalPages
      const cur = this.page
      const nums = new Set([1, total, cur, cur - 1, cur + 1])
      const sorted = [...nums].filter((n) => n >= 1 && n <= total).sort((a, b) => a - b)
      const items = []
      let prev = 0
      for (const n of sorted) {
        if (n - prev > 1) items.push({ key: `e${n}`, ellipsis: true })
        items.push({ key: n, num: n })
        prev = n
      }
      return items
    }
  },
  methods: {
    go(p) {
      const next = Math.min(this.totalPages, Math.max(1, p))
      if (next === this.page || this.disabled) return
      this.$emit('update:page', next)
      this.$emit('change', { page: next, pageSize: this.pageSize })
    },
    onSize(e) {
      const size = Number(e.target.value)
      this.$emit('update:pageSize', size)
      this.$emit('update:page', 1)
      this.$emit('change', { page: 1, pageSize: size })
    },
    onJump(e) {
      const p = Number(e.target.value)
      if (!Number.isNaN(p)) this.go(p)
      e.target.value = ''
    }
  }
}
</script>

<style scoped>
.app-pagination {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.app-pagination__pages { display: flex; align-items: center; gap: var(--space-1); }
.app-pagination__btn {
  min-width: 30px;
  height: 30px;
  padding: 0 var(--space-2);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
  transition: all 0.12s;
}
.app-pagination__btn:hover:not(:disabled):not(.is-active) { border-color: var(--primary-300, var(--primary-500)); color: var(--primary-600); }
.app-pagination__btn.is-active {
  background: var(--primary-600);
  border-color: var(--primary-600);
  color: #fff;
  font-weight: var(--font-weight-medium);
}
.app-pagination__btn.is-ellipsis { border: none; background: none; cursor: default; }
.app-pagination__btn:disabled { opacity: 0.5; cursor: not-allowed; }
.app-pagination__size-el, .app-pagination__jumper-el {
  height: 28px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  font-size: var(--font-size-sm);
  font-family: inherit;
  margin: 0 var(--space-1);
}
.app-pagination__size-el { padding: 0 var(--space-1); }
.app-pagination__jumper-el { width: 48px; text-align: center; padding: 0 var(--space-1); }
.app-pagination__size, .app-pagination__jumper { display: inline-flex; align-items: center; }
</style>
