<template>
  <section class="version-workbench">
    <header><h3>表单定义与版本</h3><span>{{ formCode }}</span></header>
    <table>
      <thead><tr><th>版本</th><th>Schema Hash</th><th>支持端</th><th>状态</th><th>操作</th></tr></thead>
      <tbody>
        <tr v-for="version in versions" :key="version.id || version.versionId">
          <td>v{{ version.versionNo || version.version_no }}</td>
          <td><code>{{ version.schemaHash || version.schema_hash }}</code></td>
          <td>{{ (version.supportedClients || version.supported_clients || []).join(' / ') }}</td>
          <td>{{ version.status }}</td>
          <td>
            <button type="button" @click="$emit('preview', version)">预览</button>
            <button type="button" @click="$emit('validate', version)">校验</button>
            <button v-if="version.status === 'DRAFT'" type="button" @click="$emit('publish', version)">发布</button>
            <button v-if="version.status === 'PUBLISHED'" type="button" @click="$emit('disable', version)">停用</button>
            <button type="button" @click="$emit('impact', version)">影响分析</button>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup>
defineProps({ formCode: { type: String, required: true }, versions: { type: Array, default: () => [] } })
defineEmits(['preview', 'validate', 'publish', 'disable', 'impact'])
</script>

<style scoped>
.version-workbench { background: #fff; border: 1px solid #e4e7ec; border-radius: 12px; padding: 16px; }
header { display: flex; justify-content: space-between; align-items: center; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 10px; text-align: left; border-top: 1px solid #eaecf0; }
code { font-size: 11px; word-break: break-all; }
button + button { margin-left: 6px; }
</style>
