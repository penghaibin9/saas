<template>
  <AppButton
    :variant="variant"
    :loading="busy"
    :disabled="!allowed"
    :title="allowed ? '' : '无导出权限'"
    @click="onClick"
  >
    <slot>导出 Excel 台账</slot>
  </AppButton>
</template>

<script>
/**
 * AppExportButton — 公共「导出 Excel 台账」按钮。
 * 由页面注入 exportFn（返回 { code, data } 且 data 为后端 pack_xlsx_result 结构），
 * 组件负责触发浏览器下载 + 权限不足提示。真实导出走后端并写审计（后端负责）。
 * Props:
 *  - exportFn: () => Promise<{ code, data:{ filename, contentBase64, mediaType } }>
 *  - hasPermission: 无权限时禁用并提示
 */
import { AppButton } from '@/components/ui'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import { toast } from '@/utils/toast'

export default {
  name: 'AppExportButton',
  components: { AppButton },
  props: {
    exportFn: { type: Function, required: true },
    variant: { type: String, default: 'secondary' },
    hasPermission: { type: Boolean, default: true }
  },
  emits: ['exported'],
  data() {
    return { busy: false }
  },
  computed: {
    allowed() {
      return this.hasPermission && !this.busy
    }
  },
  methods: {
    async onClick() {
      if (!this.hasPermission) {
        toast.error('无导出权限，请联系管理员')
        return
      }
      this.busy = true
      try {
        const res = await this.exportFn()
        if (res?.code === 0) {
          downloadXlsxFromApi(res.data)
          toast.success('导出成功，已写入审计')
          this.$emit('exported', res.data)
        } else {
          toast.error(res?.message || '导出失败')
        }
      } catch (e) {
        toast.error(e?.message || '导出失败')
      } finally {
        this.busy = false
      }
    }
  }
}
</script>
