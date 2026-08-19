<template>
  <view class="map">
    <view class="row-between map__hd">
      <text class="map__label">
        {{ label }}<text v-if="required" class="map__req"> *</text>
      </text>
      <text class="map__hint">{{ files.length }}/{{ maxCount }} · 单个 ≤{{ maxSizeMb }}MB</text>
    </view>

    <view v-if="files.length" class="map__list">
      <view v-for="file in files" :key="file.fileId" class="map__row">
        <view class="flex-1" @click="preview(file)">
          <text class="map__name ellipsis">{{ file.fileName || '附件' }}</text>
          <text class="map__status" :class="statusClass(file)">{{ file.statusText }}</text>
        </view>
        <text v-if="!disabled" class="map__remove" @click="remove(file)">移除</text>
      </view>
    </view>

    <button class="btn btn-secondary map__add" :disabled="!canAdd" @click="pick">
      {{ uploading ? '上传中…' : '添加附件' }}
    </button>

    <MobileInlineAlert v-if="blockedReason" type="warning" title="附件还不能用于提交"
      :description="blockedReason" />
  </view>
</template>

<script setup>
import { computed, onUnmounted, ref, watch } from 'vue'
import { fileSdk } from '@/services/fileSdk'

/**
 * V3 §8.1 移动附件选择器。
 *
 * 只调用既有 fileSdk（choose/upload/metadata/open），不自建第二套上传请求。
 *
 * 安全语义严格照搬 File Center，不在客户端放宽：
 *   1. 上传成功只拿到 TEMP_PRIVATE fileId，**不是**业务绑定；
 *   2. 界面如实显示扫描中 / 可用 / 已拒绝；
 *   3. 只要还有文件 readyForBusiness=false，就不允许业务提交；
 *   4. 正式绑定由业务 command 带 fileIds 回 canonical service，在同一事务里校验
 *      owner/tenant/scanStatus/purpose 后创建 FileBinding——客户端永远不能指定绑定；
 *   5. 业务提交失败时临时文件保持私有，由清理任务按 TTL 回收，客户端不提前绑定。
 */
const props = defineProps({
  fileIds: { type: Array, default: () => [] },
  bizPurpose: { type: String, required: true },
  label: { type: String, default: '附件' },
  maxCount: { type: Number, default: 3 },
  maxSizeMb: { type: Number, default: 10 },
  accept: { type: String, default: 'image,file' },
  required: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false }
})
const emit = defineEmits(['update:fileIds', 'update:ready', 'error'])

const files = ref([])
const uploading = ref(false)
let pollTimer = null

const canAdd = computed(() =>
  !props.disabled && !uploading.value && files.value.length < props.maxCount)

const pending = computed(() =>
  files.value.filter((file) => ['PENDING', 'RUNNING'].includes(file.scanStatus)))
const rejected = computed(() =>
  files.value.filter((file) => ['INFECTED', 'ERROR'].includes(file.scanStatus)))

/** 业务可提交 = 必填已满足 且 没有待扫描 且 没有被拒绝 且 每个都 readyForBusiness。 */
const ready = computed(() => {
  if (props.required && !files.value.length) return false
  if (pending.value.length || rejected.value.length) return false
  return files.value.every((file) => file.readyForBusiness)
})

const blockedReason = computed(() => {
  if (rejected.value.length) return '有附件未通过安全扫描，请移除后重新上传。'
  if (pending.value.length) return '附件正在安全扫描，扫描通过后才能提交。'
  if (props.required && !files.value.length) return '该业务需要至少一个附件。'
  return ''
})

watch(ready, (value) => emit('update:ready', value), { immediate: true })
watch(files, (value) => {
  emit('update:fileIds', value.map((file) => file.fileId))
  schedulePoll()
}, { deep: true })

function statusClass(file) {
  if (['INFECTED', 'ERROR'].includes(file.scanStatus)) return 'is-bad'
  if (file.readyForBusiness) return 'is-ok'
  return 'is-wait'
}

async function pick() {
  if (!canAdd.value) return
  uploading.value = true
  try {
    const chosen = await fileSdk.choose()
    if (!chosen) return
    const size = Number(chosen.size || 0)
    if (size && size > props.maxSizeMb * 1024 * 1024) {
      emit('error', { biz: true, message: `单个附件不能超过 ${props.maxSizeMb}MB` })
      return
    }
    // bizId 留空：上传只产出 TEMP_PRIVATE 文件，正式归属由业务 command 在服务端绑定。
    const uploaded = await fileSdk.upload(chosen, { bizType: props.bizPurpose, bizId: '' })
    files.value = [...files.value, uploaded]
  } catch (error) {
    emit('error', error)
  } finally {
    uploading.value = false
  }
}

function remove(target) {
  files.value = files.value.filter((file) => file.fileId !== target.fileId)
}

async function preview(file) {
  if (!file.canPreview) return
  try {
    await fileSdk.open(file.fileId)
  } catch (error) {
    emit('error', error)
  }
}

/** 扫描中的附件按 metadata 复核真实状态，不在客户端猜「应该扫完了」。 */
function schedulePoll() {
  if (pollTimer) return
  if (!pending.value.length) return
  pollTimer = setTimeout(async () => {
    pollTimer = null
    const refreshed = await Promise.all(files.value.map(async (file) => {
      if (!['PENDING', 'RUNNING'].includes(file.scanStatus)) return file
      try {
        return await fileSdk.metadata(file.fileId)
      } catch (error) {
        return file
      }
    }))
    files.value = refreshed
  }, 3000)
}

onUnmounted(() => {
  if (pollTimer) clearTimeout(pollTimer)
  pollTimer = null
})
</script>

<style scoped>
.map { display: flex; flex-direction: column; gap: var(--space-2); }
.map__hd { align-items: baseline; }
.map__label { font-size: var(--font-size-sm); color: var(--text-secondary); }
.map__req { color: var(--danger-500); }
.map__hint { font-size: 11px; color: var(--text-tertiary); }
.map__list { display: flex; flex-direction: column; gap: 6px; }
.map__row { display: flex; align-items: center; gap: var(--space-2); padding: 6px 8px; border-radius: var(--radius-sm); background: var(--bg-subtle, #f5f6f8); }
.map__name { display: block; font-size: var(--font-size-sm); color: var(--text-primary); }
.map__status { display: block; font-size: 11px; margin-top: 2px; }
.map__status.is-ok { color: var(--success-600, #16a34a); }
.map__status.is-wait { color: var(--warning-700); }
.map__status.is-bad { color: var(--danger-600); }
.map__remove { font-size: var(--font-size-xs); color: var(--danger-600); padding: 0 4px; }
.map__add { align-self: flex-start; }
</style>
