<template>
  <view class="materials">
    <MobilePrivacyGate />
    <text class="materials__title">申请材料（选填）</text>
    <view v-for="file in files" :key="file.fileId" class="materials__file">
      <view>
        <text class="materials__name">{{ file.fileName || '附件名称待核对' }}</text>
        <text class="materials__status">{{ materialStatus(file) }}</text>
      </view>
      <button class="materials__remove" :disabled="disabled || busy" @click="remove(file)">移除</button>
    </view>
    <view class="materials__actions">
      <button class="materials__action" :disabled="disabled || busy" @click="add">{{ busy ? '正在处理…' : '添加材料' }}</button>
      <button v-if="needsCheck" class="materials__action" :disabled="disabled || busy" @click="refresh">核对检查结果</button>
    </view>
    <text class="materials__status">上传只是材料候选。系统按学校规则检查文件；检查通过后，才可随本次申请提交。正式受理和材料绑定以学校记录为准。</text>
    <text v-if="errorText" class="materials__error">{{ errorText }}</text>
  </view>
</template>

<script>
import { fileSdk } from '@/services/fileSdk'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'

const fileId = file => String(file?.fileId || file?.id || '').trim()
const isFormalFileId = value => /^[1-9]\d*$/.test(String(value || ''))
const isForbidden = error => Number(error?.httpStatus || error?.statusCode || error?.status || error?.response?.status) === 403 ||
  [error?.code, error?.bizCode].some(code => /^403/.test(String(code || '')) || code === 'NO_PERMISSION')

function verifiedCandidate(file) {
  const id = fileId(file)
  if (!file || typeof file !== 'object' || !isFormalFileId(id)) return null
  return { ...file, fileId: id, readyForBusiness: file.readyForBusiness === true }
}

export default {
  props: { files: { type: Array, default: () => [] }, purpose: { type: String, required: true }, disabled: Boolean },
  emits: ['update:files', 'busy', 'forbidden'],
  data() { return { busy: false, alive: true, errorText: '', materialEpoch: 0, filesRevision: 0, operationIdentity: 0 } },
  computed: { needsCheck() { return this.files.some(file => !file?.readyForBusiness) } },
  watch: {
    files: { handler() { this.filesRevision += 1 }, deep: true },
    purpose() { this.invalidateMaterialOperation() }
  },
  beforeUnmount() { this.alive = false; this.invalidateMaterialOperation() },
  methods: {
    invalidateMaterialOperation() { this.materialEpoch += 1 },
    handleMaterialError(error, fallback) {
      if (isForbidden(error)) {
        this.invalidateMaterialOperation()
        this.$emit('update:files', [])
        this.$emit('forbidden')
        this.errorText = '当前无权读取材料，请重新核对权限。'
      } else this.errorText = fallback
    },
    materialStatus(file) {
      if (file?.readyForBusiness) return '安全检查通过，可随申请提交'
      const status = String(file?.scanStatus || '').toUpperCase()
      if (status === 'RUNNING') return '正在进行安全检查'
      if (status === 'PENDING') return '等待安全检查'
      if (status === 'INFECTED') return '安全检查未通过，请移除后重新选择材料'
      if (status === 'ERROR') return '安全检查暂未完成，请稍后核对'
      return '文件状态待核对'
    },
    isCurrent(identity, epoch, revision) {
      return this.alive && identity === currentSessionGeneration() && epoch === this.materialEpoch && revision === this.filesRevision
    },
    finishOperation() {
      if (!this.alive) return
      this.busy = false
      if (currentSessionGeneration() === this.operationIdentity) this.$emit('busy', false)
    },
    remove(file) {
      if (this.disabled || this.busy) return
      this.invalidateMaterialOperation()
      const id = fileId(file)
      this.$emit('update:files', this.files.filter(row => fileId(row) !== id))
    },
    async add() {
      if (this.disabled || this.busy) return
      const identity = currentSessionGeneration()
      const epoch = ++this.materialEpoch
      const revision = this.filesRevision
      this.operationIdentity = identity
      const current = () => this.isCurrent(identity, epoch, revision)
      this.busy = true; this.$emit('busy', true); this.errorText = ''
      try {
        const chosen = await fileSdk.choose()
        if (!current() || !chosen) return
        const uploaded = verifiedCandidate(await fileSdk.upload(chosen, { bizType: this.purpose, bizId: '' }))
        if (!current()) return
        if (!uploaded) {
          this.errorText = '材料上传回执暂时无法核对，请重新上传。'
          return
        }
        if (this.files.some(file => fileId(file) === uploaded.fileId)) {
          this.errorText = '该材料已在本次申请中，请勿重复添加。'
          return
        }
        this.$emit('update:files', [...this.files, uploaded])
      } catch (error) {
        if (current()) this.handleMaterialError(error, '材料上传未完成，请保留原文件后重试。')
      } finally {
        this.finishOperation()
      }
    },
    async refresh() {
      if (this.disabled || this.busy) return
      const input = this.files.map(file => fileId(file))
      if (!input.length) return
      if (input.some(id => !isFormalFileId(id)) || new Set(input).size !== input.length) {
        this.errorText = '材料标识无法核对，请移除后重新上传。'
        return
      }
      const identity = currentSessionGeneration()
      const epoch = ++this.materialEpoch
      const revision = this.filesRevision
      this.operationIdentity = identity
      const current = () => this.isCurrent(identity, epoch, revision)
      this.busy = true; this.$emit('busy', true); this.errorText = ''
      try {
        const checked = await Promise.all(input.map(id => fileSdk.metadata(id)))
        if (!current()) return
        const files = checked.map(verifiedCandidate)
        if (files.some((file, index) => !file || file.fileId !== input[index])) {
          this.errorText = '材料状态回执无法核对，请重新上传。'
          return
        }
        this.$emit('update:files', files)
      } catch (error) {
        if (current()) this.handleMaterialError(error, '暂时无法核对材料状态，请稍后重试。')
      } finally {
        this.finishOperation()
      }
    }
  }
}
</script>

<style scoped>
.materials { display:flex; flex-direction:column; gap:10px; padding:12px; border:1px solid var(--border-base); border-radius:10px; }
.materials__title,.materials__name { display:block; font-size:14px; color:var(--text-primary); overflow-wrap:anywhere; }
.materials__status { display:block; margin-top:3px; font-size:12px; line-height:1.6; color:var(--text-secondary); }
.materials__file { display:flex; justify-content:space-between; align-items:center; gap:10px; }
.materials__actions { display:flex; flex-wrap:wrap; gap:8px; }
.materials__remove,.materials__action { margin:0; min-height:40px; font-size:12px; color:var(--brand-primary); background:var(--bg-page); border:0; }
.materials__error { font-size:12px; color:var(--danger-600); }
</style>
