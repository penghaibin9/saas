<template>
  <section class="fund-files" :aria-label="title">
    <div class="fund-files__head"><strong>{{ title }} <small>选填</small></strong><span>{{ files.length }}/{{ maxCount }} · 单个不超过 10 MB</span></div>
    <p>{{ description }}</p>
    <ul v-if="files.length">
      <li v-for="item in files" :key="item.key">
        <div><strong>{{ item.name }}</strong><small :class="{ error: item.error }">{{ item.error || (item.fileId ? (item.readyForBusiness ? '已上传，可随申请提交' : item.statusText || '等待安全检查') : '等待上传') }}</small></div>
        <button v-if="item.error && !item.fileId" type="button" :disabled="locked" @click="upload(item)">重试</button>
        <button v-if="item.fileId && !item.readyForBusiness" type="button" :disabled="locked" @click="check(item)">检查状态</button>
        <button type="button" :disabled="locked" :aria-label="`移除${item.name}`" @click="remove(item)">移除</button>
      </li>
    </ul>
    <label class="fund-files__pick" :class="{ disabled: locked || files.length >= maxCount }">
      <input type="file" :multiple="maxCount > 1" :disabled="locked || files.length >= maxCount" @change="choose" />
      {{ uploading ? '正在上传…' : '添加材料' }}
    </label>
    <p v-if="notice" class="error" role="alert">{{ notice }}</p>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { fileSdk } from '../../services/fileSdk'
const props = defineProps({
  disabled: Boolean,
  initialFiles: { type: Array, default: () => [] },
  bizType: { type: String, default: 'FUNDING' },
  maxCount: { type: Number, default: 5 },
  title: { type: String, default: '佐证材料' },
  description: { type: String, default: '上传与申请相关的证明，确认提交后交给负责老师核验。' }
})
const emit = defineEmits(['change'])
const files = ref([...props.initialFiles]), uploading = ref(false), notice = ref('')
const locked = computed(() => props.disabled || uploading.value)
let nextKey = Math.max(0, ...props.initialFiles.map(x => x.key)), active = true
watch([files, uploading], () => emit('change', {
  fileIds: files.value.filter(x => x.fileId).map(x => x.fileId),
  ready: !uploading.value && files.value.every(x => x.fileId && x.readyForBusiness === true && !x.error),
  hasDraft: files.value.length > 0, busy: uploading.value, items: files.value
}), { deep: true, immediate: true, flush: 'sync' })
onBeforeUnmount(() => { active = false })
async function send(item) {
  try {
    const result = await fileSdk.upload(item.source, { bizType: props.bizType, bizId: '' })
    if (active) Object.assign(item, result, { error: '' })
  } catch (e) { if (active) item.error = e.message || '上传失败，请重试' }
}
async function choose(event) {
  const picked = Array.from(event.target.files || []); event.target.value = ''
  if (locked.value || !picked.length) return
  if (files.value.length + picked.length > props.maxCount) { notice.value = `最多可添加${props.maxCount}份材料，请减少选择数量。`; return }
  if (picked.some(x => x.size > 10 * 1024 * 1024)) { notice.value = '单个材料不能超过10 MB，请重新选择。'; return }
  notice.value = ''; uploading.value = true
  const rows = picked.map(source => ({ key: ++nextKey, name: source.name, source, fileId: '', readyForBusiness: false, error: '' }))
  files.value.push(...rows)
  try { for (const item of files.value.filter(x => rows.some(row => row.key === x.key))) { if (!active) break; await send(item) } }
  finally { if (active) uploading.value = false }
}
async function upload(item) {
  if (locked.value || item.fileId) return
  uploading.value = true
  try { await send(item) } finally { if (active) uploading.value = false }
}
async function check(item) {
  if (locked.value || !item.fileId) return
  uploading.value = true
  try { const latest = await fileSdk.metadata(item.fileId); if (active) Object.assign(item, latest, {error:''}) }
  catch (e) { if (active) item.error = e.message || '检查失败，请重试' }
  finally { if (active) uploading.value = false }
}
function remove(item) { if (!locked.value) files.value = files.value.filter(x => x.key !== item.key) }
</script>

<style scoped>
.fund-files { border: 1px solid var(--border-light); border-radius: 10px; padding: 14px; background: var(--bg-card); }
.fund-files__head { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
.fund-files__head strong { font-size: 14px; }.fund-files__head span, .fund-files small, .fund-files p { color: var(--text-secondary); font-size: 12px; }
.fund-files__head small { font-weight: 400; margin-left: 6px; }.fund-files p { margin: 8px 0 12px; }
.fund-files ul { list-style: none; padding: 0; margin: 0 0 10px; }.fund-files li { display: flex; gap: 10px; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--border-light); }
.fund-files li > div { min-width: 0; flex: 1; display: grid; gap: 4px; }.fund-files li strong { font-size: 13px; overflow-wrap: anywhere; }.fund-files li button { flex: none; }
.fund-files button { border: 0; background: transparent; color: var(--primary); cursor: pointer; min-height: 32px; }.fund-files__pick { display: inline-flex; position: relative; border: 1px solid var(--border-light); border-radius: 7px; padding: 8px 14px; font-size: 13px; cursor: pointer; }
.fund-files__pick input { position: absolute; inset: 0; opacity: 0; width: 100%; cursor: pointer; }.fund-files .error { color: var(--danger, #b45309); }.fund-files .disabled, .fund-files button:disabled { opacity: .55; cursor: not-allowed; }
</style>
