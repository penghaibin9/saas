<template>
  <view class="page-wrap">
    <MobileNavBar variant="default" title="办理详情" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="row">
        <view class="card stack-sm">
          <view class="row-between">
            <text class="wd__title flex-1">{{ row.title }}</text>
            <MobileStatusTag :label="row.statusLabel" :type="tagType(row.statusGroup)" />
          </view>
          <view class="wd__meta">
            <text class="wd__meta-item">单号 {{ row.no }}</text>
            <text class="wd__meta-item">{{ row.dept }}</text>
            <text class="wd__meta-item">当前节点：{{ row.handler }}</text>
          </view>
          <text class="wd__meta-item">提交 {{ shortTime(row.applyTime) }} · 更新 {{ shortTime(row.updatedAt) }}</text>
          <MobileInlineAlert v-if="row.latestOpinion" type="warning" title="处理意见"
            :description="row.latestOpinion" />
        </view>

        <view class="section-head"><text class="section-head__title">办理进度</text></view>
        <view class="card">
          <MobileTimeline v-if="timelineNodes.length" :nodes="timelineNodes" />
          <MobileGlobalState v-else state="empty" title="暂无进度节点"
            description="该业务尚未产生可展示的审批节点。" />
        </view>
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar v-if="row && canRun(row.action)">
      <button class="btn btn-primary flex-1" @click="runAction(row.action)">
        {{ row.statusGroup === 'returned' ? '修改后重提' : '打开原业务' }}
      </button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { canNavigate, runAction } from '@/services/actionRouter'

const TAG_TYPE = { pending: 'warning', processing: 'processing', returned: 'danger', done: 'success' }

// V3 §7.1：时间线节点来自服务端聚合的 workflow task / 域事件，每个节点保留自己的出处。
// 本页不推断状态，也不在客户端合并跨域节点。
export default {
  data() { return { row: null, state: 'loading', caseId: '' } },
  computed: {
    timelineNodes() {
      return ((this.row && this.row.timeline) || []).map((node, index) => ({
        id: node.source || `node-${index}`,
        title: node.label || node.nodeCode || '节点',
        status: node.status,
        desc: node.opinion || '',
        time: node.at ? String(node.at).slice(0, 16).replace('T', ' ') : ''
      }))
    }
  },
  onLoad(query) {
    this.caseId = (query && query.caseId) || ''
    this.load()
  },
  methods: {
    tagType(group) { return TAG_TYPE[group] || 'default' },
    shortTime(iso) { return iso ? String(iso).slice(0, 16).replace('T', ' ') : '—' },
    canRun(action) { return canNavigate(action, 'student') },
    runAction(action) { return runAction(action, { side: 'student' }) },
    load() {
      if (!this.caseId) { this.state = 'error'; return }
      this.state = 'loading'
      return studentApi.getCaseDetail(this.caseId)
        .then((data) => { this.row = data; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    }
  }
}
</script>

<style scoped>
.wd__title { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.wd__meta { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: 4px; }
.wd__meta-item { font-size: var(--font-size-xs); color: var(--text-tertiary); }
</style>
