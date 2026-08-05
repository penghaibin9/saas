<template>
  <AppDrawer :visible="visible" :title="title" mode="modal" size="large" @update:visible="$emit('update:visible', $event)">
    <div class="exp">
      <div class="exp__sec">
        <div class="exp__sec-t">导出范围</div>
        <label v-for="s in options.scopes" :key="s.value" class="mp-radio" :class="{ 'is-active': scope === s.value }">
          <input v-model="scope" type="radio" :value="s.value" class="exp__radio" />
          <span>
            <span class="mp-radio__title">{{ s.label }}</span>
            <span v-if="s.value === 'SELECTED'" class="mp-radio__desc">已勾选 {{ selectedCount }} 条</span>
            <span v-else-if="s.value === 'ALL'" class="mp-radio__desc">仍受当前数据范围（{{ dataScopeName }}）限制</span>
          </span>
        </label>
      </div>
      <div class="exp__sec">
        <div class="exp__sec-t">导出字段（敏感字段默认脱敏）</div>
        <label v-for="f in fields" :key="f.key" class="exp__field">
          <input v-model="f.checked" type="checkbox" />
          <span>{{ f.label }}</span>
          <span v-if="f.sensitive" class="exp__mask">{{ f.maskNote || '默认脱敏' }}</span>
        </label>
      </div>
      <div class="exp__notice">
        <b>水印与留痕：</b>{{ options.note }}
      </div>
    </div>
    <template #footer>
      <span class="mp-note" style="margin-right: auto">确认即写入审计日志</span>
      <AppButton variant="ghost" @click="$emit('update:visible', false)">取消</AppButton>
      <AppButton variant="primary" :loading="submitting" :disabled="scope === 'SELECTED' && !selectedCount" @click="confirmExport">
        确认导出
      </AppButton>
    </template>
  </AppDrawer>
</template>

<script>
/**
 * ExportDialog — 系统管理模块局部组件：导出确认（范围 / 字段选择 / 脱敏 / 水印 / 审计确认）。
 * options 来自 api.getContext().exportOptions[entity]；runExport({scope, fields, count}) 由父页面传入。
 * 敏感字段永远以脱敏形式导出，本组件不提供明文开关（明文导出须走导出审批流程，超出本页范围）。
 */
import { AppButton } from '@/components/ui'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { toast } from '@/utils/toast'

export default {
  name: 'SystemExportDialog',
  components: { AppButton, AppDrawer },
  props: {
    visible: { type: Boolean, default: false },
    title: { type: String, default: '导出数据' },
    options: { type: Object, required: true },
    selectedCount: { type: Number, default: 0 },
    dataScopeName: { type: String, default: '' },
    runExport: { type: Function, required: true }
  },
  emits: ['update:visible'],
  data() {
    return { scope: 'FILTERED', fields: [], submitting: false }
  },
  watch: {
    visible(v) {
      if (v) {
        this.scope = (this.options.scopes[0] || {}).value || 'FILTERED'
        this.fields = (this.options.fields || []).map((f) => ({ ...f, checked: f.defaultChecked }))
      }
    }
  },
  methods: {
    async confirmExport() {
      const picked = this.fields.filter((f) => f.checked)
      if (!picked.length) {
        toast.error('请至少选择 1 个导出字段')
        return
      }
      this.submitting = true
      const res = await this.runExport({ scope: this.scope, fields: picked, count: this.selectedCount })
      this.submitting = false
      if (res.code === 0) {
        toast.success('文件已下载：' + res.data.fileName + '（脱敏 + 水印），已写入审计日志')
        this.$emit('update:visible', false)
      } else {
        toast.error(res.message)
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.exp {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.exp__sec-t {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  margin-bottom: var(--space-2);
}
.exp__radio {
  margin-top: 3px;
}
.exp__field {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) 0;
  font-size: var(--font-size-sm);
}
.exp__mask {
  font-size: var(--font-size-xs);
  color: var(--warning-600);
  background: var(--warning-50);
  border-radius: var(--radius-full);
  padding: 0 var(--space-2);
}
.exp__notice {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  background: var(--bg-section-blue);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
  line-height: 1.6;
}
</style>
