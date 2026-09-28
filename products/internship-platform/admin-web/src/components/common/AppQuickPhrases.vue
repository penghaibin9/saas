<template>
  <div v-if="items.length" class="app-qp">
    <div class="app-qp__row">
      <button
        v-for="(p, i) in visibleItems"
        :key="i"
        type="button"
        class="app-qp__chip"
        :title="p"
        @click="$emit('pick', p)"
      >{{ shorten(p) }}</button>
      <button v-if="hasMore" type="button" class="app-qp__more" @click="expanded = !expanded">
        {{ expanded ? '收起' : `更多(${items.length - maxVisible})` }}
      </button>
    </div>
  </div>
</template>

<script>
/**
 * AppQuickPhrases — 快捷用语 chips。点击某条 emit('pick', 全文)，由调用方插入到自己文本框的光标处
 * （见 @/utils/insertAtCursor.js），本组件不直接操作任何外部 DOM，只负责词条展示与选择。
 * L1 词库固定来源于 @/utils/quickPhrases.js；sceneKey 对应场景，group 命中时该分组词条置顶。
 */
import { getQuickPhrases } from '@/utils/quickPhrases'

export default {
  name: 'AppQuickPhrases',
  props: {
    sceneKey: { type: String, required: true },
    group: { type: String, default: '' },
    maxVisible: { type: Number, default: 4 }
  },
  emits: ['pick'],
  data() {
    return { expanded: false }
  },
  computed: {
    items() { return getQuickPhrases(this.sceneKey, this.group) },
    hasMore() { return this.items.length > this.maxVisible },
    visibleItems() { return this.expanded ? this.items : this.items.slice(0, this.maxVisible) }
  },
  watch: {
    sceneKey() { this.expanded = false },
    group() { this.expanded = false }
  },
  methods: {
    shorten(text) {
      return text.length > 16 ? text.slice(0, 16) + '…' : text
    }
  }
}
</script>

<style scoped>
.app-qp { margin: 4px 0; }
.app-qp__row { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.app-qp__chip {
  max-width: 220px;
  height: 24px;
  padding: 0 10px;
  border: 1px solid var(--border-base, #e2e8f0);
  border-radius: 999px;
  background: var(--bg-section-blue, #f8fafc);
  color: var(--text-secondary, #64748b);
  font-size: 12px;
  line-height: 22px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: pointer;
}
.app-qp__chip:hover {
  border-color: var(--primary-500, #2563eb);
  color: var(--primary-600, #2563eb);
  background: var(--primary-50, #eff6ff);
}
.app-qp__more {
  height: 24px; padding: 0 8px;
  border: 1px dashed var(--border-base, #e2e8f0);
  border-radius: 999px;
  background: transparent;
  color: var(--text-tertiary, #94a3b8);
  font-size: 12px;
  cursor: pointer;
}
.app-qp__more:hover { color: var(--primary-600, #2563eb); border-color: var(--primary-500, #2563eb); }
</style>
