<template>
  <view class="page-wrap sa">
    <view class="page-pad">
      <view class="sa__head card">
        <text class="card-title">{{ svcName }}</text>
        <text class="sa__dept">承办部门：{{ dept }}{{ needApprove ? ' · 需审批' : ' · 免审批' }}</text>
      </view>

      <view class="card sa__form">
        <view class="sa__row">
          <text class="sa__label">申请类型</text>
          <picker class="sa__picker" mode="selector" :range="typeOptions" :value="typeIndex" @change="onType">
            <view class="sa__pick-val">{{ typeOptions[typeIndex] }} <text class="sa__arrow">▾</text></view>
          </picker>
        </view>

        <view class="sa__row">
          <text class="sa__label">开始日期</text>
          <picker class="sa__picker" mode="date" :value="startDate" @change="onStart">
            <view class="sa__pick-val">{{ startDate || '请选择' }} <text class="sa__arrow">▾</text></view>
          </picker>
        </view>
        <view class="sa__row">
          <text class="sa__label">结束日期</text>
          <picker class="sa__picker" mode="date" :value="endDate" @change="onEnd">
            <view class="sa__pick-val">{{ endDate || '请选择' }} <text class="sa__arrow">▾</text></view>
          </picker>
        </view>

        <view class="sa__row sa__row--top">
          <text class="sa__label">申请事由</text>
          <textarea
            class="sa__textarea"
            v-model="reason"
            :maxlength="200"
            placeholder="请填写事由（必填）"
            placeholder-class="sa__ph"
          />
        </view>
        <text class="sa__count">{{ reason.length }}/200</text>

        <view class="sa__row sa__row--upload">
          <text class="sa__label">附件材料</text>
          <view class="sa__upload is-disabled" @click="pickFile">
            <text class="sa__upload-icon">！</text>
            <text class="sa__upload-txt">附件上传暂未开放，请携带纸质材料至窗口办理</text>
          </view>
        </view>
      </view>

      <MobileInlineAlert type="info" description="提交后可在「我的申请」查看进度；需审批的事项将推送给辅导员/相关老师。" />
    </view>

    <MobileSafeAreaBar>
      <button class="btn btn-ghost flex-1" :disabled="submitting" @click="reset">重置</button>
      <button class="btn btn-primary flex-1" :disabled="submitting" @click="submit">{{ submitting ? '提交中…' : '提交申请' }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { useSubmissionsStore } from '@/stores/submissions'
import { studentApi } from '@/services/studentApi'
import { createSubmitLock, normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const submitLock = createSubmitLock(1500)

const TYPE_MAP = {
  学生请假: ['事假', '病假', '公假', '其他'],
  奖助学金申请: ['国家励志奖学金', '国家助学金', '校级奖学金', '临时困难补助'],
  default: ['常规办理', '加急办理']
}
const LEAVE_TYPE_CODE = { 事假: 'PERSONAL', 病假: 'SICK', 公假: 'OTHER', 其他: 'OTHER' }

export default {
  data() {
    return {
      svcName: '服务申请',
      dept: '相关部门',
      needApprove: true,
      typeOptions: TYPE_MAP.default,
      typeIndex: 0,
      startDate: '',
      endDate: '',
      reason: '',
      fileName: '',
      submitting: false
    }
  },
  onLoad(q) {
    if (q && q.name) this.svcName = decodeURIComponent(q.name)
    if (q && q.dept) this.dept = decodeURIComponent(q.dept)
    if (q) this.needApprove = q.approve !== '0'
    this.typeOptions = TYPE_MAP[this.svcName] || TYPE_MAP.default
    const d = new Date()
    const pad = (n) => (n < 10 ? '0' + n : '' + n)
    this.startDate = d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate())
    this.endDate = this.startDate
  },
  methods: {
    onType(e) { this.typeIndex = Number(e.detail.value) },
    onStart(e) { this.startDate = e.detail.value },
    onEnd(e) { this.endDate = e.detail.value },
    // 后端服务申请暂无附件存储字段，选完文件也无法真实提交，禁止假装"已选择"误导用户
    pickFile() {
      toast('附件上传暂未开放，请携带纸质材料至窗口办理')
    },
    reset() {
      this.typeIndex = 0
      this.reason = ''
      this.fileName = ''
    },
    submit() {
      if (this.submitting) return
      if (this.reason.trim().length < 5) {
        toast('申请事由至少 5 个字')
        return
      }
      const content = this.typeOptions[this.typeIndex] + ' · ' + this.startDate + '~' + this.endDate + ' · ' + this.reason.trim()
      const isLeave = this.svcName.indexOf('请假') >= 0
      const localAdd = () => useSubmissionsStore().addApplication({
        name: this.svcName + '（' + this.typeOptions[this.typeIndex] + '）',
        dept: this.dept, needApprove: this.needApprove, detail: content
      })
      this.submitting = true
      // 真实提交（提交锁防连点）；业务错误（403/409/422）绝不假装成功
      submitLock.run(() => studentApi.submitServiceApply({
        serviceKey: isLeave ? 'LEAVE' : this.svcName,
        reason: content, startTime: this.startDate, endTime: this.endDate,
        ...(isLeave ? { leaveType: LEAVE_TYPE_CODE[this.typeOptions[this.typeIndex]] || 'OTHER' } : {})
      })).then(() => {
        localAdd()
        uni.showToast({ title: '提交成功', icon: 'success' })
        setTimeout(() => { uni.redirectTo({ url: '/pages/student/my-applications/index' }) }, 700)
      }).catch((e) => {
        if (e && e.code === 'LOCKED') return
        if (e && e.biz) {
          toast(normalizeError(e).text) // 409 重复 / 422 字段 / 403 权限：清晰提示
        } else {
          toast('网络异常，提交未成功，请稍后重试')
        }
      }).finally(() => {
        this.submitting = false
      })
    }
  }
}
</script>

<style scoped>
.sa__dept { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 4px; }
.sa__form { margin-top: var(--card-gap-mobile); }
.sa__row { display: flex; align-items: center; min-height: 48px; border-bottom: 1px solid var(--border-light); }
.sa__row--top { align-items: flex-start; padding-top: var(--space-3); border-bottom: none; }
.sa__row--upload { border-bottom: none; }
.sa__label { width: 80px; flex-shrink: 0; font-size: var(--font-size-base); color: var(--text-secondary); }
.sa__picker { flex: 1; }
.sa__pick-val { font-size: var(--font-size-base); color: var(--text-primary); text-align: right; }
.sa__arrow { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.sa__textarea { flex: 1; min-height: 88px; font-size: var(--font-size-base); color: var(--text-primary); line-height: 1.6; }
.sa__ph { color: var(--text-tertiary); }
.sa__count { display: block; text-align: right; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 4px; }
.sa__upload { flex: 1; display: flex; align-items: center; gap: var(--space-2); border: 1px dashed var(--border-dark); border-radius: var(--radius-md); padding: var(--space-3); color: var(--text-tertiary); }
.sa__upload.is-disabled { background: var(--gray-50); }
.sa__upload-icon { font-size: var(--font-size-lg); }
.sa__upload-txt { font-size: var(--font-size-sm); }
</style>
