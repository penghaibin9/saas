<template>
  <view class="page-wrap"><view class="page-pad stack">
    <view class="card head"><text class="eyebrow">数据范围摘要</text><text class="title">完整性异常</text><text class="desc">仅显示当前教师权限和学生范围内的状态，不提供跨范围明细。</text></view>
    <MobileGlobalState v-if="state !== 'ready'" :state="state" @retry="load" />
    <template v-else><view class="stats card"><view><text>{{ data.total || 0 }}</text><text>待关注</text></view><view><text>{{ data.statusCounts && data.statusCounts.OPEN || 0 }}</text><text>未确认</text></view><view><text>{{ (data.packages || []).filter((p) => p.packageStatus === 'AVAILABLE').length }}</text><text>归档包就绪</text></view></view>
      <view class="section-label"><text>冻结包状态</text></view>
      <view v-for="pkg in data.packages || []" :key="pkg.manifestId" class="card item" @click="openTarget(pkg.target)"><text class="item-title">{{ pkg.studentName || pkg.studentNo || ('学生 #' + pkg.studentId) }}</text><text class="desc">第 {{ pkg.revision }} 版 · {{ packageStatus(pkg.packageStatus) }} · 文件编号 {{ pkg.artifact && pkg.artifact.fileId || '—' }}</text></view>
      <view v-if="!(data.packages || []).length" class="card empty"><text>当前范围内没有冻结归档包</text></view>
      <view class="section-label"><text>一致性异常</text></view>
      <view v-for="item in data.items || []" :key="item.id" class="card item" @click="openTarget(item.target)"><text class="item-title">{{ exceptionTypeLabel(item.exceptionType) }}</text><text class="desc">{{ integrityStatusLabel(item.status) }} · {{ severityLabel(item.severity) }} · {{ item.lastDetectedAt }}</text><text class="item-code">异常编号 {{ item.exceptionType || '—' }}</text></view>
      <view v-if="!(data.items || []).length" class="card empty"><text>当前范围内没有待关注异常</text></view>
    </template>
  </view></view>
</template>

<script>
import { platformIntegrityApi } from '@/services/platformIntegrityApi'
import { normalizeError, safeToast } from '@/services/request'
export default { data: () => ({ state: 'loading', data: {} }), onLoad() { this.load() }, onPullDownRefresh() { this.load().finally(() => uni.stopPullDownRefresh()) }, methods: { async load() { this.state = 'loading'; try { this.data = await platformIntegrityApi.teacherSummary(); this.state = 'ready' } catch (e) { this.state = 'error'; safeToast(normalizeError(e).text) } }, packageStatus(value) { return ({ AVAILABLE: '已完成', PENDING: '生成中', RUNNING: '生成中', RETRY: '等待重试', DEAD: '生成失败', UNAVAILABLE: '文件不可用', NOT_REQUESTED: '待生成' })[value] || (value ? `状态待确认（${value}）` : '未知') }, exceptionTypeLabel(value) { return ({ FROZEN_MANIFEST_ITEM_DRIFT: '冻结清单项发生变化', PACKAGED_FILE_MISSING: '归档包文件缺失', PACKAGE_SOURCE_VERSION_MISMATCH: '归档包源文件版本不一致', FILE_BINDING_BROKEN_REFERENCE: '文件绑定引用失效', MANIFEST_ITEM_LIMIT_EXCEEDED: '冻结清单项目数量超限' })[value] || '完整性异常' }, integrityStatusLabel(value) { return ({ OPEN: '待处理', ACKNOWLEDGED: '已确认', RESOLVED: '已解决', IGNORED: '已忽略' })[value] || (value ? `状态待确认（${value}）` : '状态未知') }, severityLabel(value) { return ({ CRITICAL: '严重', HIGH: '高风险', ERROR: '错误', MEDIUM: '中风险', WARNING: '警告', LOW: '低风险', INFO: '提示' })[value] || (value ? `级别待确认（${value}）` : '级别未知') }, openTarget(target) { if (!target || !target.path) return; const query = Object.entries(target.query || {}).filter(([, value]) => value !== '' && value != null).map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`).join('&'); uni.navigateTo({ url: target.path + (query ? `?${query}` : '') }) } } }
</script>

<style scoped>
.page-pad{padding:16px}.head,.item,.empty{padding:17px}.eyebrow,.title,.desc,.item-title,.item-code{display:block}.eyebrow{font-size:12px;color:#1769e0;font-weight:700}.title{margin-top:5px;font-size:22px;font-weight:700}.desc{margin-top:6px;color:#718096;font-size:12px;line-height:1.5}.item-code{margin-top:4px;color:#94a3b8;font-size:10px;word-break:break-all}.stats{display:grid;grid-template-columns:repeat(3,1fr);padding:14px}.stats view{text-align:center;border-left:1px solid #edf0f4}.stats view:first-child{border:0}.stats text{display:block}.stats text:first-child{font-size:21px;font-weight:700}.stats text:last-child{margin-top:4px;color:#7b8798;font-size:11px}.section-label{padding:4px 2px;color:#59687a;font-size:13px;font-weight:700}.item-title{font-weight:700}.empty{text-align:center;color:#718096}
</style>
