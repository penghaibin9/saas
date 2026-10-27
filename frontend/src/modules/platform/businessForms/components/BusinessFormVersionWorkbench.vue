<template>
  <section class="version-workbench">
    <header><h3>表单定义与版本</h3><details><summary>实施人员使用</summary><p>表单编码：{{ formCode }}</p></details></header>
    <div class="version-table-scroll" tabindex="0" role="region" aria-label="表单版本列表，可横向滚动">
    <table>
      <thead><tr><th>版本</th><th>结构摘要</th><th>支持端</th><th>状态</th><th>操作</th></tr></thead>
      <tbody>
        <tr v-for="version in versions" :key="version.id || version.versionId">
          <td>第 {{ version.versionNo || version.version_no }} 版</td>
          <td><details><summary>实施人员使用</summary><code>{{ version.schemaHash || version.schema_hash }}</code></details></td>
          <td>{{ clientLabels(version.supportedClients || version.supported_clients) }}</td>
          <td>{{ platformStatusLabel(version.status) }}</td>
          <td>
            <button class="mp-btn" type="button" :disabled="busy" @click="$emit('preview', version)">预览</button>
            <button class="mp-btn" type="button" :disabled="busy" @click="$emit('validate', version)">校验</button>
            <button v-if="version.status === 'DRAFT'" class="mp-btn" type="button" :disabled="busy || !canManage" @click="$emit('publish', version)">发布</button>
            <button v-if="version.status === 'PUBLISHED'" class="mp-btn" type="button" :disabled="busy || !canManage" @click="$emit('disable', version)">停用</button>
            <button class="mp-btn" type="button" :disabled="busy" @click="$emit('impact', version)">影响分析</button>
          </td>
        </tr>
      </tbody>
    </table>
    </div>
  </section>
</template>

<script setup>
import { platformEnumLabel, platformStatusLabel } from '@/modules/platform/constants/platform-display.constants'

defineProps({ formCode: { type: String, required: true }, versions: { type: Array, default: () => [] }, canManage: { type: Boolean, default: true }, busy: { type: Boolean, default: false } })
defineEmits(['preview', 'validate', 'publish', 'disable', 'impact'])

const clientLabels = values => (values || []).map(value => platformEnumLabel(value, '其他终端')).join(' / ') || '—'
</script>

<style scoped>
@import '@/styles/module-page.css';
.version-workbench { min-width: 0; background: #fff; border: 1px solid #e4e7ec; border-radius: 12px; padding: 16px; }
header { display: flex; flex-wrap: wrap; gap: 12px; justify-content: space-between; align-items: center; }
.version-table-scroll { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; }
@media (max-width: 600px) { table { min-width: 560px; } }
th, td { padding: 10px; text-align: left; border-top: 1px solid #eaecf0; }
code { font-size: 11px; word-break: break-all; }
button + button { margin-left: 6px; }
</style>
