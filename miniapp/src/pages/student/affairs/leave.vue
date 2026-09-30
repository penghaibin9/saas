<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="我的请假" back fallback-url="/pages/student/affairs/index" />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="items">
        <MobileGlobalState v-if="!items.length" state="empty" title="暂无请假记录" description="发起请假后记录会显示在这里。" />
                <MobileInlineAlert v-if="focusMissing" type="warning" title="没有找到这条记录"
          description="消息或待办指向的请假记录不在当前列表里，可能已被处理、撤回或超出本页范围。" />
        <view class="list-group" v-if="items.length">
          <view v-for="x in items" :key="x.leaveId" :id="'leave-' + x.leaveId" :class="{ 'is-focus': isFocused(x) }" class="list-row lv__row">
            <view class="flex-1">
              <text class="t-md">{{ x.leaveTypeLabel }}</text>
              <text class="lv__time">{{ x.startDate }} 至 {{ x.endDate }} · {{ x.days }} 天</text>
              <text class="lv__reason" v-if="x.reason">{{ x.reason }}</text>
              <text class="lv__reason lv__opinion" v-if="x.returnReason || x.rejectReason">处理意见：{{ x.returnReason || x.rejectReason }}</text>
            </view>
            <MobileStatusTag :label="x.statusLabel" :type="badgeType(x.status)" />
            <button class="btn btn-ghost lv__resubmit" @click="openDetail(x.leaveId)">查看进度与办理</button>
          </view>
        </view>
        <view v-if="total > pageSize" class="lv__pagination">
          <button class="btn btn-ghost" :disabled="page <= 1" @click="changePage(-1)">上一页</button>
          <text>{{ page }} / {{ Math.ceil(total / pageSize) }}</text>
          <button class="btn btn-ghost" :disabled="!hasMore" @click="changePage(1)">下一页</button>
        </view>
      </view>
    </MobileGlobalState>

    <MobileLeaveDetail v-if="detailVisible" :detail="detail" :loading="detailLoading" :error="detailError" @close="detailVisible = false; detailEpoch++" @retry="openDetail(detailId)">
      <template #materials><view class="card lv__materials"><text class="t-md t-bold">证明与补交材料</text><text class="lv__time">查看老师要求补充的内容与处理结果。</text><button class="btn btn-ghost" @click="openMaterials">查看材料要求</button></view></template>
      <template #default="{ item: x }"><view class="lv__actions"><button v-if="allows(x, 'EDIT_RETURNED') || allows(x, 'RESUBMIT')" class="btn btn-primary flex-1" :disabled="submitting" @click="editReturned(x)">修改后重提</button><button v-if="allows(x, 'SUBMIT_CANCEL')" class="btn btn-primary flex-1" :disabled="submitting" @click="cancelLeave(x)">我已返校</button><button v-if="allows(x, 'SUBMIT_EXTENSION')" class="btn btn-ghost flex-1" :disabled="submitting" @click="openExtend(x)">申请续假</button></view></template>
    </MobileLeaveDetail>

    <MobileSafeAreaBar v-if="!detailVisible">
      <button class="btn btn-primary flex-1" :disabled="submitting" @click="openApply">新建请假</button>
    </MobileSafeAreaBar>

    <view v-if="formVisible" class="lv__mask" @click.self="closeForm">
      <view class="lv__sheet card">
        <text class="card-title">{{ editTarget ? '修改退回申请' : '请假申请' }}</text>
        <MobileInlineAlert v-if="editTarget" type="warning" title="请按退回意见修改" :description="editNotice || editTarget.returnReason || '修改后将重新进入辅导员审批。'" />
        <view class="lv__field">
          <text class="lv__label">请假类型 <text class="lv__req">*</text></text>
          <picker mode="selector" :range="typeOptions" range-key="label" :value="typeIndex" @change="onType"><view class="lv__picker">{{ typeOptions[typeIndex].label }}</view></picker>
        </view>
        <view class="lv__field">
          <text class="lv__label">开始日期 <text class="lv__req">*</text></text>
          <picker mode="date" :value="form.startTime" :start="startMin" @change="onStart"><view class="lv__picker">{{ form.startTime || '请选择' }}</view></picker>
        </view>
        <view class="lv__field">
          <text class="lv__label">结束日期 <text class="lv__req">*</text></text>
          <picker mode="date" :value="form.endTime" :start="form.startTime || startMin" @change="onEnd"><view class="lv__picker">{{ form.endTime || '请选择' }}</view></picker>
          <text v-if="form.startTime && form.endTime && form.endTime < form.startTime" class="lv__error">结束日期不能早于开始日期</text>
        </view>
        <view class="lv__field">
          <text class="lv__label">请假事由 <text class="lv__req">*</text></text>
          <textarea v-model="form.reason" class="lv__textarea" maxlength="300" placeholder="说明请假原因（5-300字）" />
          <text class="lv__counter">{{ form.reason.trim().length }}/300</text>
        </view>
        <view class="lv__field">
          <MobileAttachmentPicker
            :label="editTarget ? '补充证明材料（可选）' : '证明材料（可选）'"
            biz-purpose="AFFAIRS_LEAVE"
            :file-ids="fileIds"
            :max-count="3"
            :max-size-mb="10"
            :disabled="submitting"
            @update:fileIds="(ids) => (fileIds = ids)"
            @update:ready="(value) => (attachmentsReady = value)"
            @error="onAttachmentError"
          />
          <text v-if="editTarget" class="lv__hint">已正式提交的历史材料会保留在办理详情；此处只可补充新材料。</text>
        </view>
        <view class="lv__actions">
          <button class="btn btn-ghost flex-1" :disabled="submitting" @click="closeForm">取消</button>
          <button class="btn btn-primary flex-1" :disabled="submitting || !formValid" @click="submit">{{ submitting ? '提交中…' : (editTarget ? '保存并重新提交' : '提交申请') }}</button>
        </view>
      </view>
    </view>

    <view v-if="extendVisible" class="lv__mask" @click.self="closeExtend">
      <view class="lv__sheet card">
        <text class="card-title">续假申请</text>
        <text class="lv__time">原结束：{{ originalEnd || '—' }}</text>
        <view class="lv__field">
          <text class="lv__label">新结束日期 <text class="lv__req">*</text></text>
          <picker mode="date" :value="extendForm.newEndTime" :start="extendMin" @change="onExtendEnd"><view class="lv__picker">{{ extendForm.newEndTime || '请选择' }}</view></picker>
          <text v-if="extendForm.newEndTime && extendForm.newEndTime <= originalEnd" class="lv__error">续假结束日期必须晚于原结束日期</text>
        </view>
        <view class="lv__field">
          <text class="lv__label">续假事由 <text class="lv__req">*</text></text>
          <textarea v-model="extendForm.reason" class="lv__textarea" maxlength="300" placeholder="说明续假原因（5-300字）" />
          <text class="lv__counter">{{ extendForm.reason.trim().length }}/300</text>
        </view>
        <view class="lv__actions">
          <button class="btn btn-ghost flex-1" :disabled="submitting" @click="closeExtend">取消</button>
          <button class="btn btn-primary flex-1" :disabled="submitting || !extendValid" @click="submitExtend">{{ submitting ? '提交中…' : '提交续假' }}</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import MobileLeaveDetail from '@/components/MobileLeaveDetail.vue'
import { leaveDate, leaveError, leaveStatusText } from '@/services/leavePresentation'
import { hasFocusRow, isFocusRow, readFocusId, scrollToFocus } from '@/utils/listFocus.mjs'
import { studentApi } from '@/services/studentApi'
import { affairsContractApi } from '@/services/affairsContractApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const TYPE = { SICK: '病假', PERSONAL: '事假', HOME: '探亲假', HOSPITAL: '住院假', GOOUT: '外出', OTHER: '其他' }

export default {
  components: { MobileLeaveDetail },
  data() {
    return { detail: null, detailId: '', detailVisible: false, detailLoading: false, detailError: '', detailEpoch: 0, focusId: '', focusMissing: false,
      items: null, state: 'loading', page: 1, pageSize: 20, total: 0, hasMore: false, loadEpoch: 0, formVisible: false, editTarget: null, editNotice: '',
      extendVisible: false, extendTarget: {}, extendForm: { newEndTime: '', reason: '' },
      submitting: false, typeIndex: 0,
      typeOptions: [
        { label: '事假', value: 'PERSONAL' }, { label: '病假', value: 'SICK' },
        { label: '探亲假', value: 'HOME' }, { label: '住院假', value: 'HOSPITAL' },
        { label: '外出', value: 'GOOUT' }, { label: '其他', value: 'OTHER' }
      ],
      form: { startTime: '', endTime: '', reason: '' },
      // 上传阶段仅保存 TEMP_PRIVATE fileId；正式绑定由后端同一请假事务完成。
      fileIds: [], attachmentsReady: true
    }
  },
  computed: {
    startMin() { return this.editTarget ? '' : this.today() },
    originalEnd() { return leaveDate(this.extendTarget.endTime) },
    extendMin() { return this.dayAfter(this.originalEnd) || this.today() },
    formValid() {
      const reason = this.form.reason.trim()
      return !!this.form.startTime && !!this.form.endTime && this.form.endTime >= this.form.startTime && reason.length >= 5 && reason.length <= 300 && this.attachmentsReady
    },
    extendValid() {
      const reason = this.extendForm.reason.trim()
      return !!this.extendForm.newEndTime && this.extendForm.newEndTime > this.originalEnd && reason.length >= 5 && reason.length <= 300
    }
  },
  // V3 §4.4 LIST_FOCUS：待办/消息深链带 recordId 进来时必须定位到那条记录。
  onLoad(query) { this.focusId = readFocusId(query); this.load(); if (this.focusId) this.openDetail(this.focusId) },
  onShow() { if (this.state === 'ready' && !this.submitting) this.load() },
  onUnload() { this.detailEpoch++; this.loadEpoch++ },
  methods: {
    async openDetail(id) {
      const ticket = ++this.detailEpoch
      this.detailId = String(id); this.detailVisible = true; this.detailLoading = true; this.detailError = ''; this.detail = null
      try { const data = await affairsContractApi.getLeaveDetail(id); if (ticket === this.detailEpoch) this.detail = data }
      catch (e) { if (ticket === this.detailEpoch) this.detailError = leaveError(e, '暂时无法读取申请详情，请重试。') }
      finally { if (ticket === this.detailEpoch) this.detailLoading = false }
    },
    openMaterials() { uni.navigateTo({ url: '/pages/student/affairs/index?bizType=LEAVE&bizId=' + encodeURIComponent(this.detailId) }) },
    isFocused(row) { return isFocusRow(row, this.focusId, ['leaveId']) },
    applyFocus() {
      if (!this.focusId) return
      const rows = this.items
      this.focusMissing = !hasFocusRow(rows, this.focusId, ['leaveId'])
      if (this.focusMissing) return
      this.$nextTick(() => scrollToFocus('#leave-', this.focusId))
    },
    allows(item, action) { return Array.isArray(item && item.allowedActions) && item.allowedActions.includes(action) },
    async load(targetPage = this.page) {
      const parsedPage = Number(targetPage)
      const requestedPage = Number.isInteger(parsedPage) && parsedPage > 0 ? parsedPage : this.page
      const ticket = ++this.loadEpoch
      this.state = 'loading'
      try {
        const d = await studentApi.getMyLeaves(requestedPage, this.pageSize)
        if (ticket !== this.loadEpoch) return
        this.items = (d && d.items) || []
        this.total = Number((d && d.total) || 0)
        this.page = Number((d && d.page) || requestedPage)
        this.hasMore = Boolean(d && d.hasMore)
        if (!this.items.length && this.page > 1 && this.total > 0) return this.load(Math.ceil(this.total / this.pageSize))
        this.state = 'ready'; this.applyFocus(); if (this.detailVisible && this.detailId) this.openDetail(this.detailId)
      } catch (e) {
        if (ticket !== this.loadEpoch) return
        this.state = 'error'; this.showError(e, '请假记录加载失败')
      }
    },
    changePage(delta) { if (this.submitting) return; this.load(this.page + delta) },
    today() {
      const d = new Date(); const pad = (n) => (n < 10 ? '0' + n : '' + n)
      return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate())
    },
    dayAfter(value) {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) return ''
      const d = new Date(`${value}T00:00:00`); if (Number.isNaN(d.getTime())) return ''
      d.setDate(d.getDate() + 1); const pad = (n) => String(n).padStart(2, '0')
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
    },
    openApply() {
      this.editTarget = null; this.editNotice = ''; this.typeIndex = 0
      const today = this.today(); this.form = { startTime: today, endTime: today, reason: '' }; this.fileIds = []; this.attachmentsReady = true; this.formVisible = true
    },
    closeForm() { if (!this.submitting) { this.formVisible = false; this.editTarget = null; this.editNotice = '' } },
    editReturned(item) {
      if (this.submitting) return
      this.submitting = true
      affairsContractApi.getReturnedLeave(item.leaveId).then((d) => {
        this.editTarget = { ...item, ...d }; this.editNotice = ''
        const idx = this.typeOptions.findIndex((x) => x.value === d.leaveType); this.typeIndex = idx >= 0 ? idx : 0
        this.form = { startTime: leaveDate(d.startTime), endTime: leaveDate(d.endTime), reason: d.reason || '' }
        this.fileIds = []; this.attachmentsReady = true
        this.formVisible = true
      }).catch((e) => this.showError(e, '加载退回申请失败')).finally(() => { this.submitting = false })
    },
    openExtend(item) { this.extendTarget = item; this.extendForm = { newEndTime: this.dayAfter(leaveDate(item.endTime)), reason: '' }; this.extendVisible = true },
    closeExtend() { if (!this.submitting) this.extendVisible = false },
    onType(e) { this.typeIndex = Number(e.detail.value) },
    onStart(e) { this.form.startTime = e.detail.value; if (this.form.endTime && this.form.endTime < this.form.startTime) this.form.endTime = this.form.startTime },
    onEnd(e) { this.form.endTime = e.detail.value },
    onExtendEnd(e) { this.extendForm.newEndTime = e.detail.value },
    showError(e, fallback) {
      const n = normalizeError(e); toast(leaveError(e, fallback))
      if (n.kind === 'conflict') this.load()
      return n
    },
    onAttachmentError(error) { this.showError(error, '附件处理失败，请重新选择') },
    async submit() {
      if (this.submitting) return
      if (!this.formValid) {
        if (!this.attachmentsReady) return toast('证明材料仍在上传或安全检查，请完成后再提交')
        return toast(this.form.endTime < this.form.startTime ? '结束日期不能早于开始日期' : '请填写有效起止日期与5-300字事由')
      }
      this.submitting = true
      const payload = { leaveType: this.typeOptions[this.typeIndex].value, startTime: this.form.startTime, endTime: this.form.endTime, reason: this.form.reason.trim(), fileIds: this.fileIds }
      try {
        if (this.editTarget) {
          const updated = await affairsContractApi.updateReturnedLeave(this.editTarget.leaveId, { ...payload, version: this.editTarget.version })
          this.editTarget = { ...this.editTarget, ...(updated || {}), leaveId: updated.id || updated.leaveId || this.editTarget.leaveId, version: updated.version }
          try {
            await affairsContractApi.resubmitLeave(this.editTarget.leaveId, this.editTarget.version)
          } catch (e) {
            this.editNotice = `修改已保存，但重新提交失败：${leaveError(e, '请重试')}`
            this.showError(e, '重新提交失败')
            return
          }
          toast('已修改并重新提交')
        } else {
          await studentApi.applyLeave(payload)
          toast('请假已提交，等待辅导员审批')
        }
        this.formVisible = false; this.editTarget = null; this.editNotice = ''; this.fileIds = []; this.attachmentsReady = true; this.load()
      } catch (e) { this.showError(e, this.editTarget ? '保存修改失败' : '提交失败') }
      finally { this.submitting = false }
    },
    submitExtend() {
      if (this.submitting) return
      if (!this.extendValid) return toast(this.extendForm.newEndTime <= this.originalEnd ? '新结束日期必须晚于原结束日期' : '请填写5-300字续假事由')
      this.submitting = true
      affairsContractApi.extendLeave(this.extendTarget.leaveId, this.extendForm.newEndTime, this.extendForm.reason.trim(), this.extendTarget.version)
        .then(() => { toast('续假已提交，等待辅导员审批'); this.extendVisible = false; this.load() })
        .catch((e) => this.showError(e, '续假失败')).finally(() => { this.submitting = false })
    },
    typeText(t) { return TYPE[t] || '假种待确认' }, statusText(s) { return leaveStatusText(s) },
    badgeType(s) { if (['APPROVED', 'CLOSED'].includes(s)) return 'success'; if (['REJECTED', 'OVERDUE'].includes(s)) return 'danger'; return 'warning' },
    cancelLeave(item) {
      if (this.submitting) return
      uni.showModal({ title: '确认申请销假', content: '确认你已返校或请假事项已结束，并提交销假申请？', confirmText: '提交销假', success: (r) => {
        if (!r.confirm) return
        this.submitting = true
        affairsContractApi.cancelLeave(item.leaveId, '学生本人申请销假', item.version)
          .then(() => { toast('销假已提交，等待辅导员确认'); this.load() })
          .catch((e) => this.showError(e, '销假失败')).finally(() => { this.submitting = false })
      } })
    }
  }
}
</script>

<style scoped>
.lv__row { align-items: flex-start; }
.lv__time { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 2px; }
.lv__reason { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 4px; }
.lv__opinion { color: var(--danger-600, #dc2626); }
.lv__mask { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: flex-end; z-index: 1000; }
.lv__sheet { width: 100%; border-radius: 16px 16px 0 0; padding: 16px; max-height: 86vh; overflow-y: auto; }
.lv__field { margin-top: 12px; }
.lv__label { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-bottom: 6px; }
.lv__req { color: #dc2626; }
.lv__picker, .lv__textarea { width: 100%; box-sizing: border-box; border: 1px solid var(--border-color, #e2e8f0); border-radius: 8px; padding: 10px 12px; background: #fff; font-size: var(--font-size-md); }
.lv__textarea { min-height: 88px; }
.lv__actions { display: flex; gap: 12px; margin-top: 16px; }
.lv__resubmit { margin-top: 8px; font-size: var(--font-size-sm); }
.lv__error { display: block; margin-top: 5px; font-size: 12px; color: #dc2626; }
.lv__counter { display: block; margin-top: 3px; font-size: 11px; text-align: right; color: #94a3b8; }
.lv__hint { display:block; margin-top:6px; font-size:12px; color:var(--text-secondary); line-height:1.5; }
.lv__pagination { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-top:16px; font-size:13px; color:var(--text-secondary); }
.is-focus { outline: 2px solid var(--brand-primary); outline-offset: 2px; border-radius: var(--radius-md); }
.lv__row{flex-wrap:wrap}.lv__row>.flex-1{min-width:65%}.lv__resubmit{width:100%;margin:12px 0 0}.lv__materials{margin-top:12px}.lv__materials button{margin-top:12px}.lv__actions{flex-wrap:wrap}.lv__picker,.lv__textarea{background:var(--bg-card,#fff);color:var(--text-primary)}
</style>
