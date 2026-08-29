<template>
  <view class="page-wrap"><view class="page-pad stack">
    <view class="hero card"><text class="eyebrow">冻结证据</text><text class="title">我的毕业归档包</text><text class="desc">归档时的材料版本与业务快照固定保存，下载统一经过文件中心授权。</text></view>
    <MobileGlobalState v-if="state !== 'ready'" :state="state" @retry="load" />
    <view v-else class="card package-card">
      <text class="label">当前状态</text><text class="status">{{ statusText }}</text>
      <text v-if="data.manifestId" class="meta">Manifest #{{ data.manifestId }} · r{{ data.revision }}</text>
      <button v-if="data.artifact && data.artifact.fileId" class="btn btn-primary" :disabled="busy" @click="download">{{ busy ? '下载中…' : '下载冻结证据包' }}</button>
      <text v-else class="desc">{{ data.packageStatus === 'LEGACY_UNAVAILABLE' ? '历史归档请使用原导出入口。' : '归档完成后系统会异步生成，请稍后刷新。' }}</text>
    </view>
  </view></view>
</template>

<script>
import fileSdk from '@/services/fileSdk'
import { platformIntegrityApi } from '@/services/platformIntegrityApi'
import { normalizeError, safeToast } from '@/services/request'
export default {
  data: () => ({ state: 'loading', data: {}, busy: false }),
  computed: { statusText() { return ({ AVAILABLE: '可下载', PENDING: '等待生成', RUNNING: '正在生成', RETRY: '等待重试', NOT_FROZEN: '尚未归档', LEGACY_UNAVAILABLE: '历史归档' }[this.data.packageStatus] || this.data.packageStatus || '暂无') } },
  onLoad() { this.load() },
  onPullDownRefresh() { this.load().finally(() => uni.stopPullDownRefresh()) },
  methods: {
    async load() { this.state = 'loading'; try { this.data = await platformIntegrityApi.myFrozenPackage(); this.state = 'ready' } catch (e) { this.state = 'error'; safeToast(normalizeError(e).text) } },
    async download() { if (this.busy) return; this.busy = true; try { await fileSdk.download(this.data.artifact.fileId); safeToast('下载已完成') } catch (e) { safeToast(normalizeError(e).text) } finally { this.busy = false } }
  }
}
</script>

<style scoped>
.page-pad{padding:16px}.hero,.package-card{padding:18px}.eyebrow,.title,.desc,.label,.status,.meta{display:block}.eyebrow{font-size:12px;color:#1769e0;font-weight:700}.title{margin-top:6px;font-size:22px;font-weight:700}.desc,.meta,.label{margin-top:7px;color:#718096;font-size:13px;line-height:1.6}.status{margin:6px 0 16px;font-size:21px;font-weight:700}.btn{margin-top:14px}
</style>
