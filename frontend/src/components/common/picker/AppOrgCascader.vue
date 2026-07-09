<template>
  <div class="app-org-cascader" :class="{ 'is-disabled': disabled }">
    <AppSelect
      v-for="(lvl, i) in levelCount"
      :key="i"
      class="app-org-cascader__col"
      :model-value="values[i] || ''"
      :options="optionsAt(i)"
      :placeholder="levels[i] || `第 ${i + 1} 级`"
      :disabled="disabled || (i > 0 && !values[i - 1])"
      :size="size"
      @update:model-value="onSelect(i, $event)"
    />
  </div>
</template>

<script>
/**
 * AppOrgCascader — 组织级联选择（学院 / 专业 / 班级，逐级联动）。
 *
 * ⚠️ partial（部分完成）：基于本地 data 树做级联；远程懒加载（选一级再拉下一级）未接后端，
 *    需要时由业务方注入。真实组织数据与数据范围由后端提供。
 *
 * Props:
 *  - modelValue: 各级选中值数组，如 ['c1','m2','k3']（v-model）
 *  - data: 组织树 [{ value, label, children:[{ value,label,children:[...] }] }]
 *  - levels: 各级占位名，默认 ['学院','专业','班级']
 *  - disabled / size
 * Emits: update:modelValue / change(valuesArray, itemsArray)
 */
import AppSelect from '../form/AppSelect.vue'

export default {
  name: 'AppOrgCascader',
  components: { AppSelect },
  props: {
    modelValue: { type: Array, default: () => [] },
    data: { type: Array, default: () => [] },
    levels: { type: Array, default: () => ['学院', '专业', '班级'] },
    disabled: { type: Boolean, default: false },
    size: { type: String, default: 'normal' }
  },
  emits: ['update:modelValue', 'change'],
  computed: {
    levelCount() { return this.levels.length },
    values() { return Array.isArray(this.modelValue) ? this.modelValue : [] }
  },
  methods: {
    optionsAt(level) {
      let nodes = this.data
      for (let i = 0; i < level; i++) {
        const cur = nodes.find((n) => n.value === this.values[i])
        nodes = cur && cur.children ? cur.children : []
      }
      return nodes.map((n) => ({ label: n.label, value: n.value }))
    },
    onSelect(level, val) {
      const next = this.values.slice(0, level)
      next[level] = val
      // 清空更深层级
      const trimmed = next.slice(0, level + 1)
      this.$emit('update:modelValue', trimmed)
      this.$emit('change', trimmed, this.itemsOf(trimmed))
    },
    itemsOf(vals) {
      const items = []
      let nodes = this.data
      for (const v of vals) {
        const cur = nodes.find((n) => n.value === v)
        if (!cur) break
        items.push({ value: cur.value, label: cur.label })
        nodes = cur.children || []
      }
      return items
    }
  }
}
</script>

<style scoped>
.app-org-cascader {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.app-org-cascader__col { flex: 1; min-width: 120px; }
</style>
