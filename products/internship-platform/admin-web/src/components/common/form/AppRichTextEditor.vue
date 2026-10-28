<template>
  <div class="app-rte" :class="{ 'is-disabled': disabled, 'is-focus': focused }">
    <div v-if="!readonly" class="app-rte__toolbar">
      <button
        v-for="c in commands"
        :key="c.cmd"
        type="button"
        class="app-rte__btn"
        :title="c.title"
        :disabled="disabled"
        @mousedown.prevent="exec(c.cmd, c.value)"
      >{{ c.icon }}</button>
    </div>
    <div
      ref="editor"
      class="app-rte__body"
      :class="{ 'is-empty': isEmpty }"
      :contenteditable="!disabled && !readonly"
      :data-placeholder="placeholder"
      role="textbox"
      aria-multiline="true"
      @input="onInput"
      @focus="focused = true"
      @blur="focused = false"
    />
  </div>
</template>

<script>
/**
 * AppRichTextEditor —（partial 部分完成）轻量富文本编辑器。
 *
 * ⚠️ 现状：未引入任何第三方富文本库（避免重依赖），基于 contenteditable + execCommand 实现
 *    加粗/斜体/下划线/列表等基础排版；v-model 输出 HTML 字符串。
 * ⚠️ 安全：HTML 未做前端消毒；正式落库/展示前必须由后端做 XSS 清洗与白名单过滤。
 *    图片上传、粘贴清洗、表格等能力未做。故本组件标 partial，不能当成熟富文本对外宣称。
 *
 * Props: modelValue(HTML) / placeholder / disabled / readonly
 * Emits: update:modelValue
 */
export default {
  name: 'AppRichTextEditor',
  props: {
    modelValue: { type: String, default: '' },
    placeholder: { type: String, default: '请输入内容…' },
    disabled: { type: Boolean, default: false },
    readonly: { type: Boolean, default: false }
  },
  emits: ['update:modelValue'],
  data() {
    return {
      focused: false,
      isEmpty: !this.modelValue,
      commands: [
        { cmd: 'bold', icon: 'B', title: '加粗' },
        { cmd: 'italic', icon: 'I', title: '斜体' },
        { cmd: 'underline', icon: 'U', title: '下划线' },
        { cmd: 'insertUnorderedList', icon: '•', title: '无序列表' },
        { cmd: 'insertOrderedList', icon: '1.', title: '有序列表' },
        { cmd: 'removeFormat', icon: '✕', title: '清除格式' }
      ]
    }
  },
  watch: {
    modelValue(v) {
      if (this.$refs.editor && v !== this.$refs.editor.innerHTML) {
        this.$refs.editor.innerHTML = v || ''
        this.isEmpty = !v
      }
    }
  },
  mounted() {
    if (this.$refs.editor) this.$refs.editor.innerHTML = this.modelValue || ''
  },
  methods: {
    exec(cmd, value) {
      if (this.disabled || this.readonly) return
      this.$refs.editor.focus()
      // execCommand 已废弃但适合轻量内网场景；后续接成熟编辑器时整体替换
      document.execCommand(cmd, false, value)
      this.sync()
    },
    onInput() { this.sync() },
    sync() {
      const html = this.$refs.editor.innerHTML
      this.isEmpty = !this.$refs.editor.textContent.trim()
      this.$emit('update:modelValue', html)
    }
  }
}
</script>

<style scoped>
.app-rte {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  overflow: hidden;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.app-rte.is-focus { border-color: var(--primary-500); box-shadow: 0 0 0 3px var(--primary-100); }
.app-rte.is-disabled { background: var(--bg-disabled); }
.app-rte__toolbar {
  display: flex;
  gap: 2px;
  padding: var(--space-1);
  border-bottom: 1px solid var(--border-light);
  background: var(--bg-subtle);
}
.app-rte__btn {
  min-width: 28px;
  height: 26px;
  border: none;
  background: none;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: var(--font-size-sm);
}
.app-rte__btn:hover:not(:disabled) { background: var(--primary-50); color: var(--primary-600); }
.app-rte__body {
  min-height: 120px;
  padding: var(--space-3);
  font-size: var(--font-size-base);
  color: var(--text-primary);
  line-height: var(--line-height-base);
  outline: none;
  overflow-y: auto;
}
.app-rte__body.is-empty::before {
  content: attr(data-placeholder);
  color: var(--text-disabled);
  pointer-events: none;
}
</style>
