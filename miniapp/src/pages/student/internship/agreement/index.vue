<template>
  <view class="page-wrap agr">
    <MobileGlobalState :state="pageState" @retry="loadList">
      <view class="page-pad stack">
        <MobileInlineAlert v-if="!list.length" type="info" description="暂无三方协议。教师下发后，您可在此阅读正文并确认。" />

        <view v-for="item in list" :key="item.id" class="card agr__item" @click="openDetail(item)">
          <view class="row-between">
            <text class="agr__title">{{ item.enterpriseName || '实习企业' }}</text>
            <MobileStatusTag :status="item.status" />
          </view>
          <text class="agr__meta">{{ item.positionName || '岗位待定' }} · {{ item.templateName || '三方协议' }}</text>
          <text class="agr__hint">{{ statusHint(item.status) }}</text>
        </view>
      </view>
    </MobileGlobalState>

    <view v-if="detail" class="agr__mask" @click.self="closeDetail">
      <view class="agr__sheet">
        <view class="agr__sheet-head">
          <text class="agr__sheet-title">实习协议确认</text>
          <text class="agr__close" @click="closeDetail">关闭</text>
        </view>
        <scroll-view scroll-y class="agr__scroll">
          <view class="agr__info card">
            <text class="agr__row">企业：{{ detail.enterpriseName }}</text>
            <text class="agr__row">岗位：{{ detail.positionName }}</text>
            <text class="agr__row">模板：{{ detail.templateName || '三方协议' }}</text>
            <text class="agr__row">状态：{{ detail.statusLabel }}</text>
          </view>
          <view v-if="detail.renderedBody" class="card agr__body-wrap">
            <text class="agr__body-title">协议正文（请仔细阅读后确认）</text>
            <text class="agr__body">{{ detail.renderedBody }}</text>
          </view>
          <MobileInlineAlert v-else type="warning" description="协议正文尚未生成，请联系指导教师。" />
        </scroll-view>
        <MobileSafeAreaBar v-if="detail.status === 'PENDING_STUDENT'">
          <button class="btn btn-ghost flex-1" :disabled="submitting" @click="openReject">驳回</button>
          <button class="btn btn-primary flex-1" :disabled="submitting || !detail.renderedBody" @click="confirm">
            {{ submitting ? '提交中…' : '确认协议' }}
          </button>
        </MobileSafeAreaBar>
      </view>
    </view>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { toast } from '@/utils/nav'

const HINT = {
  PENDING_STUDENT: '待您阅读正文并确认',
  PENDING_ENTERPRISE: '待企业签署（由学校代录纸质件，非企业端登录）',
  PENDING_SCHOOL: '待学校确认',
  EFFECTIVE: '协议已生效',
  REJECTED: '已驳回',
  VOIDED: '已作废',
  ARCHIVED: '已归档',
  DRAFT: '草稿（未下发）'
}

export default {
  data() {
    return {
      list: [],
      pageState: 'loading',
      detail: null,
      submitting: false
    }
  },
  onLoad(q) {
    this._openId = q && q.id ? String(q.id) : ''
    this.loadList()
  },
  methods: {
    statusHint(s) { return HINT[s] || '请查看详情' },
    loadList() {
      this.pageState = 'loading'
      studentApi.getInternshipAgreements().then((rows) => {
        this.list = rows || []
        this.pageState = 'ready'
        if (this._openId) {
          const hit = this.list.find((x) => String(x.id) === this._openId)
          if (hit) this.openDetail(hit)
          this._openId = ''
        }
      }).catch(() => { this.pageState = 'error' })
    },
    openDetail(item) {
      this.pageState = 'loading'
      studentApi.getInternshipAgreementDetail(item.id).then((d) => {
        this.detail = d
        this.pageState = 'ready'
      }).catch((e) => {
        this.pageState = 'ready'
        toast((e && e.message) || '加载协议详情失败')
      })
    },
    closeDetail() { this.detail = null },
    confirm() {
      if (this.submitting || !this.detail) return
      uni.showModal({
        title: '确认协议',
        content: '已阅读并同意协议正文内容？确认后将进入企业签署环节。',
        success: (r) => {
          if (!r.confirm) return
          this.submitting = true
          studentApi.confirmInternshipAgreement(this.detail.id, { action: 'CONFIRM' }).then(() => {
            toast('协议已确认')
            this.closeDetail()
            this.loadList()
          }).catch((e) => {
            toast((e && e.message) || '确认失败，请稍后重试')
          }).finally(() => { this.submitting = false })
        }
      })
    },
    openReject() {
      if (this.submitting || !this.detail) return
      uni.showModal({
        title: '驳回协议',
        editable: true,
        placeholderText: '请填写驳回原因（不少于5字）',
        success: (r) => {
          if (!r.confirm) return
          const reason = (r.content || '').trim()
          if (reason.length < 5) return toast('驳回原因不少于 5 字')
          this.submitting = true
          studentApi.confirmInternshipAgreement(this.detail.id, { action: 'REJECT', reason }).then(() => {
            toast('已提交驳回')
            this.closeDetail()
            this.loadList()
          }).catch((e) => {
            toast((e && e.message) || '驳回失败，请稍后重试')
          }).finally(() => { this.submitting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
.agr__item { margin-bottom: 12px; }
.agr__title { font-size: var(--font-size-md); font-weight: var(--font-weight-medium); color: var(--text-primary); }
.agr__meta { display: block; margin-top: 4px; font-size: var(--font-size-sm); color: var(--text-secondary); }
.agr__hint { display: block; margin-top: 6px; font-size: var(--font-size-xs); color: var(--brand-primary); }
.agr__mask { position: fixed; inset: 0; background: rgba(0,0,0,.45); z-index: 100; display: flex; align-items: flex-end; }
.agr__sheet { width: 100%; max-height: 92vh; background: var(--bg-page, #f5f6f8); border-radius: 16px 16px 0 0; display: flex; flex-direction: column; }
.agr__sheet-head { display: flex; justify-content: space-between; align-items: center; padding: 14px 16px; border-bottom: 1px solid var(--border-subtle, #eee); }
.agr__sheet-title { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); }
.agr__close { color: var(--text-secondary); font-size: var(--font-size-sm); }
.agr__scroll { flex: 1; max-height: calc(92vh - 120px); padding: 12px 16px; box-sizing: border-box; }
.agr__info { margin-bottom: 12px; }
.agr__row { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-bottom: 4px; }
.agr__body-wrap { padding: 12px; }
.agr__body-title { display: block; font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); margin-bottom: 8px; color: var(--text-primary); }
.agr__body { display: block; white-space: pre-wrap; font-size: var(--font-size-sm); line-height: 1.6; color: var(--text-primary); }
</style>
