<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="o">
        <view class="card oc__identity">
          <text class="card-title">基础信息</text>
          <view class="oc__row"><text class="oc__k">姓名</text><text class="oc__v">{{ o.identity.name }}</text></view>
          <view class="oc__row"><text class="oc__k">性别</text><text class="oc__v">{{ o.identity.gender || '—' }}</text></view>
          <view class="oc__row"><text class="oc__k">录取编号</text><text class="oc__v">{{ o.identity.admissionNo }}</text></view>
          <view class="oc__row"><text class="oc__k">学院</text><text class="oc__v">{{ o.identity.collegeName || '—' }}</text></view>
          <view class="oc__row"><text class="oc__k">专业</text><text class="oc__v">{{ o.identity.majorName || '—' }}</text></view>
          <view class="oc__row"><text class="oc__k">班级</text><text class="oc__v">{{ o.identity.className || '待分班' }}</text></view>
        </view>

        <view class="card oc__form">
          <text class="card-title">联系方式与生源地</text>
          <view class="oc__field">
            <text class="oc__label">手机号</text>
            <input class="oc__input" v-model="phone" type="number" maxlength="20"
              :placeholder="existingPhoneMasked ? `已留存 ${existingPhoneMasked}（留空沿用）` : '请输入常用手机号'" placeholder-class="oc__ph" />
          </view>
          <view class="oc__field">
            <text class="oc__label">生源地</text>
            <MobileRegionPicker v-model="origin" :placeholder="o.identity.origin || '请选择省 / 市 / 区县'" />
          </view>
          <view class="oc__field">
            <text class="oc__label">紧急联系人</text>
            <input class="oc__input" v-model="emergencyContactName" maxlength="100" placeholder="请输入姓名" placeholder-class="oc__ph" />
          </view>
          <view class="oc__field">
            <text class="oc__label">紧急电话</text>
            <input class="oc__input" v-model="emergencyPhone" type="number" maxlength="20"
              :placeholder="existingEmergencyPhoneMasked ? `已留存 ${existingEmergencyPhoneMasked}（留空沿用）` : '请输入联系电话'" placeholder-class="oc__ph" />
          </view>
          <view class="oc__confirm" @click="confirmed = !confirmed"><text>{{ confirmed ? '☑' : '☐' }}</text><text>我确认信息真实有效并用于迎新联络</text></view>
        </view>

        <MobileInlineAlert type="info" description="提交后信息核对环节即完成，可在报到总览中查看后续环节。" />
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar v-if="o">
      <button class="btn btn-primary flex-1" :disabled="submitting" @click="submit">{{ submitting ? '提交中…' : '保存并提交' }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { createSubmitLock, normalizeError } from '@/services/request'
import { toast, back } from '@/utils/nav'

const submitLock = createSubmitLock(1500)

export default {
  data() { return { o: null, state: 'loading', phone: '', existingPhoneMasked: '', origin: '', emergencyContactName: '', emergencyPhone: '', existingEmergencyPhoneMasked: '', confirmed: false, submitting: false } },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      studentApi.getOrientation().then((d) => {
        this.o = d
        const info = (d.selfService && d.selfService.information) || {}
        this.existingPhoneMasked = info.phoneMasked || d.identity.phoneMasked || ''
        this.origin = info.origin || d.identity.origin || ''
        this.emergencyContactName = info.emergencyContactName || ''
        this.existingEmergencyPhoneMasked = info.emergencyPhoneMasked || ''
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    },
    submit() {
      if (this.submitting) return
      const phone = this.phone.trim()
      const emergencyPhone = this.emergencyPhone.trim()
      const useExistingPhone = !phone && !!this.existingPhoneMasked
      const useExistingEmergencyPhone = !emergencyPhone && !!this.existingEmergencyPhoneMasked
      if (!useExistingPhone && !(/^\d{6,20}$/.test(phone))) { toast('请输入有效手机号'); return }
      if (!this.origin.trim() || !this.emergencyContactName.trim() || (!useExistingEmergencyPhone && !(/^\d{6,20}$/.test(emergencyPhone)))) { toast('请完整填写生源地和紧急联系人'); return }
      if (!this.confirmed) { toast('请先确认信息真实有效'); return }
      this.submitting = true
      submitLock.run(() => studentApi.submitOrientationCollect({
        phone: phone || undefined, useExistingPhone,
        origin: this.origin.trim(), emergencyContactName: this.emergencyContactName.trim(),
        emergencyPhone: emergencyPhone || undefined, useExistingEmergencyPhone,
        confirmed: true
      }))
        .then(() => {
          uni.showToast({ title: '提交成功', icon: 'success' })
          setTimeout(() => back(), 700)
        })
        .catch((e) => {
          if (e && e.code === 'LOCKED') return
          toast(e && e.biz ? normalizeError(e).text : '网络异常，提交未成功，请稍后重试')
        })
        .finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.oc__identity { margin-bottom: var(--card-gap-mobile); }
.oc__row { display: flex; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--border-light); }
.oc__row:last-child { border-bottom: none; }
.oc__k { width: 76px; flex-shrink: 0; font-size: var(--font-size-sm); color: var(--text-tertiary); }
.oc__v { font-size: var(--font-size-base); color: var(--text-primary); }
.oc__field { display: flex; align-items: center; min-height: 48px; border-bottom: 1px solid var(--border-light); }
.oc__field:last-child { border-bottom: none; }
.oc__label { width: 76px; flex-shrink: 0; font-size: var(--font-size-base); color: var(--text-secondary); }
.oc__input { flex: 1; font-size: var(--font-size-base); color: var(--text-primary); text-align: right; }
.oc__ph { color: var(--text-tertiary); }
.oc__confirm { display:flex; gap:8px; align-items:center; padding-top:14px; font-size:var(--font-size-sm); color:var(--text-secondary); }
</style>
