<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import FilePreviewer from '@/components/file/FilePreviewer.vue'
import { fileSdk } from '@/services/file/fileSdk'
const props = defineProps({ versions: { type: Array, default: () => [] } })
const selectedVersion = ref(''), selectedFile = ref(''), file = ref(null), error = ref(''), loading = ref(false)
const provider = { fetchBytes: descriptor => fileSdk.blob(descriptor.fileId), dispose() {} }
const versions = computed(() => [...props.versions].sort((a,b) => Number(b.versionNo)-Number(a.versionNo)))
const current = computed(() => versions.value.find(v => String(v.id) === selectedVersion.value) || versions.value[0])
const attachments = computed(() => current.value?.attachments || [])
let epoch = 0
watch(() => props.versions, () => { selectedVersion.value = String(versions.value[0]?.id || ''); selectedFile.value = ''; file.value = null; error.value = ''; epoch++ }, { immediate: true })
watch(selectedVersion, () => { selectedFile.value = ''; file.value = null; error.value = ''; loading.value = false; epoch++ })
onBeforeUnmount(() => { epoch++ })
async function open(item) {
  const ticket = ++epoch
  selectedFile.value = String(item.fileId); file.value = null; error.value = ''; loading.value = true
  try {
    const meta = await fileSdk.metadata(selectedFile.value)
    if (ticket === epoch) file.value = meta
  } catch (e) { if (ticket === epoch) error.value = e?.message || '附件读取失败，请重试' }
  finally { if (ticket === epoch) loading.value = false }
}
</script>
<template>
  <section class="mp-card report-evidence">
    <div class="mp-card__head"><strong>报告附件与历史版本</strong>
      <select v-if="versions.length" v-model="selectedVersion" aria-label="附件所属报告版本">
        <option v-for="version in versions" :key="version.id" :value="String(version.id)">第 {{ version.versionNo }} 版</option>
      </select>
    </div>
    <div class="mp-card__body">
      <p v-if="!attachments.length" class="mp-note">当前版本没有附件。</p>
      <div class="report-evidence__choices"><button v-for="item in attachments" :key="item.fileId" type="button" :class="{ active: selectedFile === String(item.fileId) }" @click="open(item)">{{ item.fileName || '查看附件' }}</button></div>
      <p v-if="loading" role="status">正在读取附件…</p>
      <p v-if="error" role="alert">{{ error }}</p>
      <FilePreviewer v-if="file" :key="selectedFile" :file="file" inline :provider="provider" @error="error = $event?.message || '附件预览失败，请重新打开'" />
    </div>
  </section>
</template>
<style scoped>
.report-evidence{background:var(--bg-card,#fff);border:1px solid var(--border-base,#e1e7f0);border-radius:12px;overflow:hidden}
.report-evidence .mp-card__head{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:16px 20px;border-bottom:1px solid #e9eef5}
.report-evidence .mp-card__body{padding:16px 20px}
.report-evidence select{padding:6px;max-width:180px;border:1px solid #ccd4df;border-radius:6px;font:inherit}
.report-evidence__choices{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
.report-evidence__choices button{padding:8px 12px;border:1px solid #cad5e4;background:white;color:#275caa;border-radius:6px;cursor:pointer;overflow-wrap:anywhere}
.report-evidence__choices button.active{border-color:#275caa;background:#edf4ff}
</style>
