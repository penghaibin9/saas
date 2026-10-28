<template>
  <view class="mobile-page mobile-student page-wrap agr">
    <MobileNavBar variant="brand" title="三方协议" show-back :before-back="beforeBack" :fallback-url="'/pages/student-internship/index' + (requestedBatchId ? '?batchId=' + encodeURIComponent(requestedBatchId) : '')" />
    <MobileGlobalState :state="pageState" @retry="loadList">
      <view class="page-pad stack">
        <MobileInlineAlert v-if="!list.length" type="info" title="暂无三方协议" description="教师下发后，请阅读正文并确认。" />

        <view v-for="item in list" :key="item.id" class="card agr__item" @click="openDetail(item)">
          <view class="row-between">
            <text class="agr__title">{{ item.enterpriseName || '实习企业' }}</text>
            <MobileStatusTag :status="item.status" />
          </view>
          <text class="agr__meta">{{ item.positionName || '岗位待定' }} · {{ item.templateName || '三方协议' }}</text>
          <text v-if="item.status !== 'EFFECTIVE'" class="agr__hint">{{ statusHint(item.status) }}</text>
        </view>
      </view>
    </MobileGlobalState>

    <view v-if="detail" class="agr__mask" @click.self="!submitting && closeDetail()">
      <view class="agr__sheet">
        <view class="agr__sheet-head">
          <text class="agr__sheet-title">实习协议确认</text>
          <button class="mobile-control agr__close" :disabled="submitting" @click="closeDetail">关闭</button>
        </view>
        <scroll-view scroll-y class="agr__scroll">
          <view class="agr__info card">
            <text class="agr__row">企业：{{ detail.enterpriseName }}</text>
            <text class="agr__row">岗位：{{ detail.positionName }}</text>
            <text class="agr__row">模板：{{ detail.templateName || '三方协议' }}</text>
            <text class="agr__row">状态：{{ detail.statusLabel }}</text>
            <text class="agr__row">第{{ detail.version }}版 · 学生{{ detail.studentConfirmLabel || '待核对' }} · 企业{{ detail.enterpriseConfirmLabel || '待核对' }} · 学校{{ detail.schoolConfirmLabel || '待核对' }}</text>
            <button v-if="detail.fileId" class="mobile-control btn btn-ghost" :disabled="attachmentBusy" @click="openAttachment">查看本协议签署件</button>
          </view>
          <view v-if="detail.renderedBody" class="card agr__body-wrap">
            <text class="agr__body-title">协议正文（请仔细阅读后确认）</text>
            <text class="agr__body">{{ detail.renderedBody }}</text>
          </view>
          <MobileInlineAlert v-else type="warning" description="协议正文尚未生成，请联系指导教师。" />
        </scroll-view>
        <MobileSafeAreaBar v-if="detail.status === 'PENDING_STUDENT'">
          <button class="mobile-control btn btn-ghost flex-1" :disabled="submitting" @click="openReject">驳回</button>
          <button class="mobile-control btn btn-primary flex-1" :disabled="submitting || !detail.renderedBody" @click="confirm">
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
import { openBusinessFile } from '@/services/fileApi'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'

const HINT = {
  PENDING_STUDENT: '待您阅读正文并确认',
  PENDING_ENTERPRISE: '待企业签署，由学校登记纸质协议',
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
      list: [], requestedBatchId: '', sequence:0, generation:currentSessionGeneration(), hidden:false, attachmentBusy:false,
      pageState: 'loading',
      detail: null,
      submitting: false,
      rejectReasonDraft: ''
    }
  },
  onLoad(q) {
    this.requestedBatchId = String(q?.batchId || '')
    this._openId = q && q.id ? String(q.id) : ''
    if (this._openId) this.openExactDetail(this._openId)
    else this.loadList()
  },
  onShow() { if(this.generation!==currentSessionGeneration()){this.generation=currentSessionGeneration();this.requestedBatchId='';this._openId='';this.rejectReasonDraft='';this.detail=null;this.list=[];this.hidden=false;this.loadList()}else if(this.hidden){this.hidden=false;this.loadList()} },
  onHide() { this.hidden=true;this.sequence++;this.detail=null;this.list=[];this.submitting=false;this.attachmentBusy=false },
  onUnload() { this.hidden=true;this.sequence++;this.detail=null;this.list=[] },
  methods: {
    current(sequence,generation) { return !this.hidden && sequence===this.sequence && generation===currentSessionGeneration() },
    async openAttachment(){if(!this.detail?.fileId || this.attachmentBusy || this.hidden || this.generation!==currentSessionGeneration())return;const sequence=this.sequence,generation=this.generation;this.attachmentBusy=true;try{await openBusinessFile(String(this.detail.fileId),'三方协议签署件')}catch{if(this.current(sequence,generation))toast('签署件暂时无法打开，请核对文件安全状态或联系学校')}finally{if(this.current(sequence,generation))this.attachmentBusy=false}},
    beforeBack() {
      if (this.submitting) return false
      if (this.detail) { this.closeDetail(); return false }
      return true
    },
    statusHint(s) { return HINT[s] || '请查看详情' },
    async loadList() {
      const sequence=++this.sequence,generation=currentSessionGeneration()
      this.pageState = 'loading'
      this.list=[]
      try {
        const dashboard=await studentApi.getInternship(this.requestedBatchId)
        if(!this.current(sequence,generation))return
        const batchId=String(dashboard?.batchId || ''),internshipId=String(dashboard?.recordId || '')
        if(!batchId || !internshipId || (this.requestedBatchId && batchId!==this.requestedBatchId))throw Error('请重新选择本人的实习批次')
        const rows=await studentApi.getInternshipAgreements(batchId,internshipId)
        if(!this.current(sequence,generation))return
        this.list = (rows || []).filter(row=>!this.requestedBatchId || String(row.batchId)===this.requestedBatchId)
        this.pageState = 'ready'
      } catch { if(this.current(sequence,generation))this.pageState = 'error' }
    },
    openExactDetail(id, keepList=false) {
      const sequence=++this.sequence,generation=currentSessionGeneration()
      const previousList=this.list;this.detail=null
      this.pageState = 'loading'
      return studentApi.getInternshipAgreementDetail(id).then((d) => {
        if(!this.current(sequence,generation))return
        if(String(d?.id)!==String(id) || (this.requestedBatchId && String(d.batchId)!==this.requestedBatchId))throw Error('协议不属于当前批次，请从原列表重新进入')
        this.detail = d
        this.list = keepList ? previousList : d ? [d] : []
        this.pageState = 'ready'
        this._openId = ''
      }).catch((e) => {
        if(!this.current(sequence,generation))return
        this.pageState = 'error'
        toast((e && e.message) || '加载协议详情失败')
      })
    },
    openDetail(item) {
      if(this.submitting || this.hidden)return
      this.rejectReasonDraft=''
      return this.openExactDetail(String(item.id),true)
    },
    closeDetail() { this.sequence++;this.detail = null },
    contextPayload() {
      return {
        batchId: this.detail?.batchId,
        internshipId: this.detail?.internId,
        expectedVersion: this.detail?.version
      }
    },
    submitError(e, fallback) {
      const code = String(e?.code || e?.status || '')
      if (code.includes('409') || code.includes('CONFLICT')) {
        toast('协议已更新，请重新打开核对；你的填写内容已保留')
        return
      }
      toast((e && e.message) || fallback)
    },
    confirm() {
      if (this.submitting || this.hidden || this.generation!==currentSessionGeneration() || this.detail?.status!=='PENDING_STUDENT' || !this.detail.renderedBody) return
      const sequence=this.sequence,generation=this.generation,detail=this.detail,payload=this.contextPayload(),current=()=>this.current(sequence,generation) && this.detail===detail
      uni.showModal({
        title: '确认协议',
        content: '已阅读并同意协议正文内容？确认后将进入企业签署环节。',
        success: (r) => {
          if (!r.confirm || !current() || this.submitting) return
          this.submitting = true
          studentApi.confirmInternshipAgreement(detail.id, {
            action: 'CONFIRM', ...payload
          }).then(() => {
            if(!current())return
            this.submitting=false
            toast('协议已确认')
            this.closeDetail()
            this.loadList()
          }).catch((e) => {
            if(!current())return
            this.submitError(e, '确认失败，请稍后重试')
          }).finally(() => { if(current())this.submitting = false })
        }
      })
    },
    openReject() {
      if (this.submitting || this.hidden || this.generation!==currentSessionGeneration() || this.detail?.status!=='PENDING_STUDENT') return
      const sequence=this.sequence,generation=this.generation,detail=this.detail,payload=this.contextPayload(),current=()=>this.current(sequence,generation) && this.detail===detail
      uni.showModal({
        title: '驳回协议',
        editable: true,
        content: this.rejectReasonDraft,
        placeholderText: '请填写驳回原因（不少于5字）',
        success: (r) => {
          if (!r.confirm || !current() || this.submitting) return
          const reason = (r.content || '').trim()
          this.rejectReasonDraft = reason
          if (reason.length < 5) return toast('驳回原因不少于 5 字')
          this.submitting = true
          studentApi.confirmInternshipAgreement(detail.id, {
            action: 'REJECT', reason, ...payload
          }).then(() => {
            if(!current())return
            this.submitting=false
            this.rejectReasonDraft = ''
            toast('已提交驳回')
            this.closeDetail()
            this.loadList()
          }).catch((e) => {
            if(!current())return
            this.submitError(e, '驳回失败，请稍后重试')
          }).finally(() => { if(current())this.submitting = false })
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
.agr__hint { display: block; margin-top: 6px; font-size: 14px; line-height:1.6; color: var(--brand-primary); }
.agr__mask { position: fixed; inset: 0; background: rgba(0,0,0,.45); z-index: 100; display: flex; align-items: flex-end; }
.agr__sheet { width: 100%; max-height: 92vh; background: var(--bg-page, #f5f6f8); border-radius: 16px 16px 0 0; display: flex; flex-direction: column; }
.agr__sheet-head { display: flex; justify-content: space-between; align-items: center; padding: 14px 16px; border-bottom: 1px solid var(--border-subtle, #eee); }
.agr__sheet-title { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); }
.agr__close { min-width:44px;min-height:44px;margin:0;padding:0 8px;border:0;background:transparent;line-height:44px;color: var(--text-secondary); font-size:14px; }
.agr__close::after { border:0; }
.agr__scroll { flex: 1; max-height: calc(92vh - 120px); padding: 12px 16px; box-sizing: border-box; }
.agr__info { margin-bottom: 12px; }
.agr__row { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-bottom: 4px; }
.agr__body-wrap { padding: 12px; }
.agr__body-title { display: block; font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); margin-bottom: 8px; color: var(--text-primary); }
.agr__body { display: block; white-space: pre-wrap; font-size: var(--font-size-sm); line-height: 1.6; color: var(--text-primary); }
.agr :deep(.page-pad){max-width:760px;margin:0 auto;box-sizing:border-box;width:100%}.agr .card{border-radius:8px;box-shadow:none}.agr__title{font-size:16px}.agr__meta,.agr__row,.agr__body-title,.agr__body{font-size:14px;line-height:1.6}.agr .btn{min-height:44px;font-size:15px}
</style>
