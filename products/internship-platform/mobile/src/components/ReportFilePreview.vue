<template>
  <view v-if="visible" class="report-preview card">
    <view class="row-between"><text class="report-preview__name">{{ name }}</text><button class="report-preview__close" @click="reset">关闭</button></view>
    <text v-if="state === 'loading'">正在安全读取附件…</text>
    <text v-else-if="state === 'error'" class="report-preview__error">{{ errorText }}</text>
    <template v-else-if="state === 'ready'">
      <image v-if="kind === 'image'" :src="url" class="report-preview__image" mode="widthFix" />
      <video v-else-if="kind === 'video'" :key="url" :src="url" controls class="report-preview__video" @error="playbackError" />
      <view v-else>
        <text>文件已安全读取，可打开或保存后查看。</text>
        <button class="btn btn-secondary" @click="openDocument">打开或保存文件</button>
      </view>
    </template>
  </view>
</template>
<script>
import fileSdk from '@/services/fileSdk'
import { normalizeError } from '@/services/request'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { loadReportMedia, releasePreview } from '@/services/reportMedia.mjs'

export default {
  data() { return { visible: false, state: 'loading', name: '', kind: '', url: '', file: null, errorText: '', sequence: 0 } },
  beforeUnmount() { this.reset() },
  methods: {
    reset() {
      this.sequence += 1
      releasePreview(this.url)
      this.url = ''; this.file = null; this.visible = false
    },
    async open(file) {
      this.reset()
      const sequence = this.sequence, generation = currentSessionGeneration()
      const current = () => sequence === this.sequence && generation === currentSessionGeneration()
      this.visible = true; this.state = 'loading'; this.name = file.fileName || '报告附件'
      try {
        const result = await loadReportMedia(file, fileSdk, current)
        if (!result || !current()) return
        this.file = result.file; this.name = result.file.fileName || '报告附件'
        this.kind = result.kind; this.url = result.url; this.state = 'ready'
      } catch (error) {
        if (current()) { this.state = 'error'; this.errorText = normalizeError(error).text }
      }
    },
    playbackError() { this.state = 'error'; this.errorText = '视频暂时无法播放，请重新打开或联系学校核对文件' },
    openDocument() {
      // #ifdef H5
      const link = document.createElement('a')
      link.href = this.url; link.download = this.name; link.rel = 'noopener noreferrer'
      document.body.appendChild(link); link.click(); link.remove()
      return
      // #endif
      // #ifndef H5
      uni.openDocument({ filePath: this.url, showMenu: true, success() {}, fail: () => {
        this.state = 'error'; this.errorText = '此文件类型暂不支持手机内查看，请在学生电脑端下载'
      } })
      // #endif
    }
  }
}
</script>
<style scoped>
.report-preview { margin-top: var(--card-gap-mobile); padding: 14px; }
.report-preview__name { min-width: 0; word-break: break-all; font-weight: 600; }
.report-preview__close { flex-shrink: 0; margin: 0; padding: 0 10px; font-size: 13px; background: transparent; }
.report-preview__image { width: 100%; margin-top: 12px; }
.report-preview__video { display: block; width: 100%; height: 220px; margin-top: 12px; }
.report-preview__error { display: block; color: var(--danger-600); margin-top: 10px; }
</style>
