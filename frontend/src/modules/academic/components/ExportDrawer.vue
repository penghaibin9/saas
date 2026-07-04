<template>
  <AppDrawer :visible="visible" title="导出数据" @update:visible="onClose">
    <div v-if="!options" class="aed-note">导出配置加载中…</div>
    <template v-else>
      <section class="aed-sec">
        <div class="aed-sec__title">导出范围</div>
        <label v-for="s in options.scopes" :key="s.value" class="aed-radio">
          <input v-model="scope" type="radio" :value="s.value" :disabled="s.value === 'SELECTED' && !selectedCount" />
          <span>{{ s.label }}<i v-if="s.value === 'SELECTED'" class="aed-muted">（已选 {{ selectedCount }} 条）</i></span>
        </label>
        <p class="aed-note">导出数据不会超出当前角色的数据范围（{{ dataScopeName }}）。</p>
      </section>

      <section class="aed-sec">
        <div class="aed-sec__title">字段选择</div>
        <label v-for="g in options.fieldGroups" :key="g.key" class="aed-check">
          <input v-model="fieldGroups" type="checkbox" :value="g.key" />
          <span>
            {{ g.label }}
            <span v-if="g.sensitive" class="aed-sensitive">敏感</span>
            <i class="aed-muted">（{{ g.fields.join('、') }}）</i>
          </span>
        </label>
      </section>

      <section class="aed-sec">
        <div class="aed-sec__title">脱敏与水印</div>
        <label class="aed-check">
          <input v-model="mask" type="checkbox" :disabled="options.maskDefault" />
          <span>敏感字段脱敏导出（默认开启，不可关闭）</span>
        </label>
        <p v-if="options.idCardPlainForbidden" class="aed-warn">按平台安全规范：身份证完整号码不支持导出，仅可导出脱敏形态。</p>
        <p class="aed-note">{{ options.watermarkNote }}</p>
      </section>

      <section class="aed-sec">
        <div class="aed-sec__title">审计确认</div>
        <label class="aed-check aed-check--audit">
          <input v-model="auditConfirmed" type="checkbox" />
          <span>{{ options.auditNotice }}</span>
        </label>
      </section>

      <section v-if="receipt" class="aed-sec aed-receipt">
        <div class="aed-sec__title">导出回执</div>
        <p class="aed-note">
          文件 <b>{{ receipt.fileName }}</b> 已生成（{{ receipt.masked ? '已脱敏' : '未脱敏' }}）。<br />
          水印：{{ receipt.watermarkText }}<br />
          审计编号：{{ receipt.auditId }}
        </p>
      </section>
    </template>

    <template #footer>
      <AppButton variant="ghost" @click="onClose">关闭</AppButton>
      <AppButton variant="primary" :disabled="!options || !auditConfirmed || !fieldGroups.length" :loading="exporting" @click="doExport">
        确认导出
      </AppButton>
    </template>
  </AppDrawer>
</template>

<script>
/**
 * ExportDrawer — 学业过程中心导出抽屉（模块局部组件）。
 * 覆盖：导出范围 / 字段选择 / 数据范围限制 / 默认脱敏 / 水印说明 / 审计确认 / 导出回执。
 * exportFn 由页面注入（对接 modules/academic/api 的 createExport）。
 */
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { AppButton } from '@/components/ui'
import { toast } from '@/utils/toast'

export default {
  name: 'AcademicExportDrawer',
  components: { AppDrawer, AppButton },
  props: {
    visible: { type: Boolean, default: false },
    options: { type: Object, default: null },
    selectedCount: { type: Number, default: 0 },
    dataScopeName: { type: String, default: '' },
    exportFn: { type: Function, required: true }
  },
  emits: ['update:visible', 'done'],
  data() {
    return { scope: 'FILTERED', fieldGroups: [], mask: true, auditConfirmed: false, exporting: false, receipt: null }
  },
  watch: {
    visible(v) {
      if (v) {
        this.scope = 'FILTERED'
        this.fieldGroups = (this.options?.fieldGroups || []).filter((g) => !g.sensitive).map((g) => g.key)
        this.mask = true
        this.auditConfirmed = false
        this.receipt = null
      }
    },
    options(o) {
      if (o && this.visible && !this.fieldGroups.length) {
        this.fieldGroups = (o.fieldGroups || []).filter((g) => !g.sensitive).map((g) => g.key)
      }
    }
  },
  methods: {
    onClose() {
      this.$emit('update:visible', false)
    },
    async doExport() {
      this.exporting = true
      const res = await this.exportFn({
        scope: this.scope,
        fieldGroups: this.fieldGroups,
        mask: true,
        auditConfirmed: this.auditConfirmed
      })
      this.exporting = false
      if (res.code === 0) {
        this.receipt = res.data
        toast.success('导出任务已创建：敏感字段已脱敏、文件含水印，本次导出已写入审计日志')
        this.$emit('done')
      } else {
        toast.error(res.message)
      }
    }
  }
}
</script>

<style scoped>
.aed-sec {
  margin-bottom: var(--space-5);
}
.aed-sec__title {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  margin-bottom: var(--space-2);
}
.aed-note {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin: var(--space-2) 0 0;
  line-height: var(--line-height-base);
}
.aed-warn {
  font-size: var(--font-size-xs);
  color: var(--warning-700);
  background: var(--warning-50);
  border: 1px solid var(--warning-100);
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
  margin: var(--space-2) 0 0;
}
.aed-radio,
.aed-check {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-1) 0;
  font-size: var(--font-size-sm);
  color: var(--text-primary);
  cursor: pointer;
}
.aed-radio input,
.aed-check input {
  margin-top: 3px;
}
.aed-muted {
  font-style: normal;
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}
.aed-sensitive {
  display: inline-block;
  font-size: var(--font-size-xs);
  color: var(--danger-600);
  background: var(--danger-50);
  border: 1px solid var(--danger-100);
  border-radius: var(--radius-full);
  padding: 0 var(--space-2);
  margin: 0 var(--space-1);
}
.aed-check--audit {
  background: var(--primary-50);
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
}
.aed-receipt {
  background: var(--success-50);
  border: 1px solid var(--success-100);
  border-radius: var(--radius-base);
  padding: var(--space-3);
}
</style>
