<template>
  <ul class="app-file-preview">
    <li v-for="file in files" :key="file.id || file.name" class="app-file-preview__item">
      <span class="app-file-preview__icon">{{ iconOf(file) }}</span>
      <div class="app-file-preview__info">
        <span class="app-file-preview__name" :title="file.name">{{ file.name }}</span>
        <span class="app-file-preview__meta">
          <template v-if="file.size">{{ file.size }}</template>
          <template v-if="file.uploadedAt"> · {{ file.uploadedAt }}</template>
          <template v-if="file.sensitive"> · 敏感材料，下载将记录审计</template>
        </span>
      </div>
      <div class="app-file-preview__actions">
        <button type="button" class="afp-btn" @click="$emit('preview', file)">预览</button>
        <button v-if="downloadable" type="button" class="afp-btn" @click="$emit('download', file)">
          下载
        </button>
      </div>
    </li>
    <li v-if="!files.length" class="app-file-preview__empty">暂无附件</li>
  </ul>
</template>

<script>
/**
 * AppFilePreview 附件列表与预览入口
 * 依据 V1.0 §8.6：业务表只保存 file_id；预览/下载动作由调用方对接文件中心签名 URL，
 * 本组件只负责展示与触发事件，不发起任何真实请求。
 * Props:
 *  - files: [{ id(file_id), name, type?, size?, uploadedAt?, sensitive? }]
 *  - downloadable: 是否显示下载按钮（移动端/企业端场景可关闭）
 * Emits: preview(file)、download(file)（敏感附件下载调用方必须写审计）
 */
const TYPE_ICON = {
  image: '🖼',
  pdf: '📄',
  word: '📝',
  excel: '📊',
  zip: '🗜',
  other: '📎'
}

export default {
  name: 'AppFilePreview',
  props: {
    files: { type: Array, default: () => [] },
    downloadable: { type: Boolean, default: true }
  },
  emits: ['preview', 'download'],
  methods: {
    iconOf(file) {
      const t = (file.type || file.name || '').toLowerCase()
      if (/(png|jpe?g|gif|webp|image)/.test(t)) return TYPE_ICON.image
      if (/pdf/.test(t)) return TYPE_ICON.pdf
      if (/(docx?|word)/.test(t)) return TYPE_ICON.word
      if (/(xlsx?|excel|csv)/.test(t)) return TYPE_ICON.excel
      if (/(zip|rar|7z)/.test(t)) return TYPE_ICON.zip
      return TYPE_ICON.other
    }
  }
}
</script>

<style scoped>
.app-file-preview {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.app-file-preview__item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
  background: var(--bg-card);
}
.app-file-preview__icon {
  font-size: var(--font-size-lg);
  flex-shrink: 0;
}
.app-file-preview__info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.app-file-preview__name {
  font-size: var(--font-size-base);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.app-file-preview__meta {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.app-file-preview__actions {
  display: flex;
  gap: var(--space-2);
  flex-shrink: 0;
}
.afp-btn {
  border: none;
  background: none;
  padding: 0;
  font-size: var(--font-size-sm);
  color: var(--text-link);
  cursor: pointer;
}
.afp-btn:hover {
  color: var(--primary-700);
}
.app-file-preview__empty {
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
  padding: var(--space-3);
  text-align: center;
}
</style>
