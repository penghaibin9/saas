<template>
  <div class="app-file-list">
    <!-- loading -->
    <div v-if="loading" class="app-file-list__state">
      <span class="app-file-list__spinner" /> 加载附件…
    </div>

    <!-- empty -->
    <div v-else-if="!files.length" class="app-file-list__empty">{{ emptyText }}</div>

    <!-- list -->
    <ul v-else class="app-file-list__ul">
      <li
        v-for="(f, i) in files"
        :key="f.id || f.name || i"
        class="app-file-list__item"
        :class="`is-${statusOf(f)}`"
      >
        <span class="app-file-list__icon">{{ iconOf(f) }}</span>
        <div class="app-file-list__info">
          <div class="app-file-list__name-row">
            <span class="app-file-list__name" :title="f.name">{{ f.name }}</span>
            <span v-if="f.sensitive" class="app-file-list__badge">敏感</span>
          </div>
          <div class="app-file-list__meta">
            <template v-if="f.size">{{ humanSize(f.size) }}</template>
            <template v-if="f.uploadedAt"> · {{ f.uploadedAt }}</template>
            <template v-if="f.uploader"> · {{ f.uploader }}</template>
            <template v-if="statusOf(f) === 'error'"> · <span class="app-file-list__err">上传失败</span></template>
            <template v-if="f.sensitive"> · 下载将写入审计</template>
          </div>
          <div v-if="statusOf(f) === 'uploading'" class="app-file-list__progress">
            <span class="app-file-list__bar" :style="{ width: (f.progress || 0) + '%' }" />
          </div>
        </div>
        <div class="app-file-list__actions">
          <button
            v-if="previewable && statusOf(f) === 'done'"
            type="button"
            class="afl-btn"
            @click="$emit('preview', f)"
          >预览</button>
          <button
            v-if="downloadable && statusOf(f) === 'done'"
            type="button"
            class="afl-btn"
            @click="$emit('download', f)"
          >下载</button>
          <button
            v-if="removable"
            type="button"
            class="afl-btn is-danger"
            @click="$emit('remove', f)"
          >移除</button>
        </div>
      </li>
    </ul>
  </div>
</template>

<script>
/**
 * AppFileList — 附件清单（展示 + 预览/下载/移除动作触发）。
 *
 * ⚠️ 声明：业务表只存 file_id；预览/下载的签名 URL、真实上传、对象存储由调用方对接文件中心，
 *    本组件不发起任何真实请求，只渲染与派发事件。敏感附件下载调用方必须写审计。
 *    未接入真实文件中心/对象存储前，上传类能力只能标 partial（见 CLAUDE.md §38）。
 *
 * Props:
 *  - files: [{ id, name, ext?, size?, uploadedAt?, uploader?, sensitive?, status?, progress?, url? }]
 *      status: uploading | done | error（缺省视为 done）
 *  - previewable / downloadable / removable
 *  - loading / emptyText
 * Emits: preview(f) / download(f) / remove(f)
 */
const TYPE_ICON = {
  image: '🖼', pdf: '📄', word: '📝', excel: '📊', ppt: '📽', zip: '🗜', other: '📎'
}
export default {
  name: 'AppFileList',
  props: {
    files: { type: Array, default: () => [] },
    previewable: { type: Boolean, default: true },
    downloadable: { type: Boolean, default: true },
    removable: { type: Boolean, default: false },
    loading: { type: Boolean, default: false },
    emptyText: { type: String, default: '暂无附件' }
  },
  emits: ['preview', 'download', 'remove'],
  methods: {
    statusOf(f) {
      return f.status || 'done'
    },
    iconOf(f) {
      const t = (f.ext || f.type || f.name || '').toLowerCase()
      if (/(png|jpe?g|gif|webp|image)/.test(t)) return TYPE_ICON.image
      if (/pdf/.test(t)) return TYPE_ICON.pdf
      if (/(docx?|word)/.test(t)) return TYPE_ICON.word
      if (/(xlsx?|excel|csv)/.test(t)) return TYPE_ICON.excel
      if (/(pptx?|ppt)/.test(t)) return TYPE_ICON.ppt
      if (/(zip|rar|7z)/.test(t)) return TYPE_ICON.zip
      return TYPE_ICON.other
    },
    humanSize(size) {
      if (typeof size !== 'number') return size
      if (size < 1024) return size + ' B'
      if (size < 1024 * 1024) return (size / 1024).toFixed(1) + ' KB'
      return (size / 1024 / 1024).toFixed(1) + ' MB'
    }
  }
}
</script>

<style scoped>
.app-file-list__state,
.app-file-list__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-4);
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
}
.app-file-list__empty {
  border: 1px dashed var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-subtle);
}
.app-file-list__spinner {
  width: 14px; height: 14px;
  border: 2px solid var(--primary-100);
  border-top-color: var(--primary-500);
  border-radius: var(--radius-full);
  animation: afl-spin 0.7s linear infinite;
}
@keyframes afl-spin { to { transform: rotate(360deg); } }
.app-file-list__ul {
  list-style: none; margin: 0; padding: 0;
  display: flex; flex-direction: column; gap: var(--space-2);
}
.app-file-list__item {
  display: flex; align-items: center; gap: var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
  background: var(--bg-card);
  transition: border-color 0.15s, box-shadow 0.15s;
}
.app-file-list__item:hover {
  border-color: var(--primary-200, var(--primary-100));
  box-shadow: var(--shadow-sm);
}
.app-file-list__item.is-error { border-color: var(--danger-100); background: var(--danger-50); }
.app-file-list__icon { font-size: var(--font-size-lg); flex-shrink: 0; }
.app-file-list__info { flex: 1; min-width: 0; }
.app-file-list__name-row { display: flex; align-items: center; gap: var(--space-2); }
.app-file-list__name {
  font-size: var(--font-size-base); color: var(--text-primary);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.app-file-list__badge {
  flex-shrink: 0;
  font-size: var(--font-size-xs);
  padding: 0 var(--space-2);
  border-radius: var(--radius-full);
  background: var(--danger-50); color: var(--danger-600);
}
.app-file-list__meta {
  font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px;
}
.app-file-list__err { color: var(--danger-600); }
.app-file-list__progress {
  margin-top: var(--space-2); height: 4px;
  background: var(--gray-100); border-radius: var(--radius-full); overflow: hidden;
}
.app-file-list__bar {
  display: block; height: 100%;
  background: var(--primary-500); border-radius: var(--radius-full);
  transition: width 0.2s;
}
.app-file-list__actions { display: flex; gap: var(--space-2); flex-shrink: 0; }
.afl-btn {
  border: none; background: none; padding: 0;
  font-size: var(--font-size-sm); color: var(--text-link); cursor: pointer;
}
.afl-btn:hover { color: var(--primary-700); }
.afl-btn.is-danger { color: var(--danger-600); }
.afl-btn.is-danger:hover { color: var(--danger-700); }
</style>
