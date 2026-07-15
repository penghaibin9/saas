<template>
  <AppDrawer :visible="visible" :title="template ? template.name : '批量导入'" @update:visible="onClose">
    <div v-if="!template" class="aid-note">导入模板加载中…</div>
    <template v-else>
      <AccountImportBoundaryNotice class="aid-boundary" />

      <section class="aid-sec">
        <div class="aid-sec__title">① 下载模板</div>
        <p class="aid-note">请使用官方模板填写数据，字段说明如下（* 为必填）：</p>
        <table class="aid-table">
          <thead>
            <tr><th>字段</th><th>是否必填</th><th>示例</th></tr>
          </thead>
          <tbody>
            <tr v-for="f in template.fields" :key="f.key">
              <td>{{ f.label }}<span v-if="f.required" class="aid-req">*</span></td>
              <td>{{ f.required ? '必填' : '选填' }}</td>
              <td class="aid-muted">{{ f.example }}</td>
            </tr>
          </tbody>
        </table>
        <AppButton variant="secondary" @click="downloadTemplate">下载模板（{{ template.fileName }}）</AppButton>
      </section>

      <section class="aid-sec">
        <div class="aid-sec__title">② 上传并校验</div>
        <div class="aid-file">
          <input v-model="fileName" type="text" class="aid-input" placeholder="选择文件（演示环境输入文件名模拟上传）" />
          <AppButton variant="primary" :loading="validating" @click="validate">解析校验</AppButton>
        </div>
        <div v-if="preview" class="aid-preview">
          <div class="aid-preview__summary">
            共解析 {{ preview.total }} 行 · 校验通过
            <b class="aid-ok">{{ preview.validCount }}</b> 行 · 失败
            <b class="aid-err">{{ preview.total - preview.validCount }}</b> 行（失败行不会导入）
          </div>
          <table class="aid-table">
            <thead>
              <tr><th>行号</th><th>数据预览</th><th>校验结果</th></tr>
            </thead>
            <tbody>
              <tr v-for="r in preview.rows" :key="r.row">
                <td>{{ r.row }}</td>
                <td class="aid-muted">{{ r.data }}</td>
                <td>
                  <span v-if="r.valid" class="aid-ok">通过</span>
                  <span v-else class="aid-err">{{ r.error }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="receipt" class="aid-sec">
        <div class="aid-sec__title">③ 导入回执</div>
        <p class="aid-note">
          成功导入 <b class="aid-ok">{{ receipt.imported }}</b> 条，回执编号
          <b>{{ receipt.receiptId }}</b>。本次导入已写入审计日志，可在操作留痕中追溯。
        </p>
      </section>
    </template>

    <template #footer>
      <AppButton variant="ghost" @click="onClose">关闭</AppButton>
      <AppButton variant="primary" :disabled="!preview || !preview.validCount || !!receipt" :loading="importing" @click="confirmImport">
        确认导入校验通过数据
      </AppButton>
    </template>
  </AppDrawer>
</template>

<script>
/**
 * ImportDrawer — 学业过程中心批量导入抽屉（模块局部组件）。
 * 闭环：模板下载 → 字段校验 → 错误预览 → 导入回执 → 审计留痕。
 * 本组件不直接依赖 api，校验/导入函数由页面注入（validateFn / confirmFn），便于替换真实后端。
 */
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { AppButton } from '@/components/ui'
import AccountImportBoundaryNotice from '@/components/common/AccountImportBoundaryNotice.vue'
import { toast } from '@/utils/toast'

export default {
  name: 'AcademicImportDrawer',
  components: { AppDrawer, AppButton, AccountImportBoundaryNotice },
  props: {
    visible: { type: Boolean, default: false },
    template: { type: Object, default: null },
    validateFn: { type: Function, required: true },
    confirmFn: { type: Function, required: true }
  },
  emits: ['update:visible', 'done'],
  data() {
    return { fileName: '', validating: false, importing: false, preview: null, receipt: null }
  },
  watch: {
    visible(v) {
      if (v) {
        this.fileName = ''
        this.preview = null
        this.receipt = null
      }
    }
  },
  methods: {
    onClose() {
      this.$emit('update:visible', false)
    },
    downloadTemplate() {
      toast.info(`模板「${this.template.fileName}」已开始下载（演示环境）`)
    },
    async validate() {
      if (!this.fileName.trim()) {
        toast.warning('请先选择要上传的文件')
        return
      }
      this.validating = true
      const res = await this.validateFn(this.fileName.trim())
      this.validating = false
      if (res.code === 0) this.preview = res.data
      else toast.error(res.message)
    },
    async confirmImport() {
      this.importing = true
      const res = await this.confirmFn({ validCount: this.preview.validCount, fileName: this.preview.fileName })
      this.importing = false
      if (res.code === 0) {
        this.receipt = res.data
        toast.success(`导入完成：成功 ${res.data.imported} 条，已写入审计日志`)
        this.$emit('done')
      } else {
        toast.error(res.message)
      }
    }
  }
}
</script>

<style scoped>
.aid-sec {
  margin-bottom: var(--space-5);
}
.aid-boundary {
  margin-bottom: var(--space-4);
}
.aid-sec__title {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  margin-bottom: var(--space-2);
}
.aid-note {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin: 0 0 var(--space-3);
  line-height: var(--line-height-base);
}
.aid-req {
  color: var(--danger-600);
  margin-left: 2px;
}
.aid-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: var(--space-3);
  font-size: var(--font-size-xs);
}
.aid-table th {
  text-align: left;
  padding: var(--space-1) var(--space-2);
  color: var(--text-tertiary);
  background: var(--bg-section-blue);
  border-bottom: 1px solid var(--border-base);
  white-space: nowrap;
}
.aid-table td {
  padding: var(--space-2);
  border-bottom: 1px solid var(--border-light);
  vertical-align: top;
}
.aid-muted {
  color: var(--text-tertiary);
}
.aid-ok {
  color: var(--success-700);
}
.aid-err {
  color: var(--danger-600);
}
.aid-file {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}
.aid-input {
  flex: 1;
  height: 36px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  padding: 0 var(--space-3);
  font-size: var(--font-size-sm);
  color: var(--text-primary);
  background: var(--bg-card);
}
.aid-input:focus {
  outline: none;
  border-color: var(--primary-500);
}
.aid-preview__summary {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}
</style>
