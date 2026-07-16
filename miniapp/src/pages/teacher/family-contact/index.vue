<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="家校联系" subtitle="登记联系 · 家长回执" show-back />

    <view class="fc__tabs">
      <view class="fc__tab" :class="{ 'is-on': tab === 'list' }" @click="tab = 'list'">
        记录列表<text v-if="list && list.length" class="fc__tab-badge">{{ list.length }}</text>
        <text v-if="tab === 'list'" class="fc__tab-u" />
      </view>
      <view class="fc__tab" :class="{ 'is-on': tab === 'create' }" @click="onCreateTab">
        登记联系<text v-if="tab === 'create'" class="fc__tab-u" />
      </view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <!-- 列表 -->
      <view class="page-pad" v-if="tab === 'list'">
        <MobileGlobalState v-if="!list || !list.length" state="empty" title="暂无家校联系记录"
          description="登记的家校联系会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="c in list" :key="c.contactId" class="card fc">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ c.realName || '—' }}</text>
                <text class="fc__sub">{{ c.studentNo || '' }} · {{ typeLabel(c.contactType) }}</text>
              </view>
              <MobileStatusTag :label="c.receiptStatusLabel" :type="c.receiptStatus === 'RECEIVED' ? 'success' : 'warning'" />
            </view>
            <view class="fc__row" v-if="c.reason"><text class="fc__row-k">事由</text><text class="flex-1 t-sm">{{ c.reason }}</text></view>
            <view class="fc__row" v-if="c.result"><text class="fc__row-k">结果</text><text class="flex-1 t-sm">{{ c.result }}</text></view>
            <text class="fc__time">{{ (c.occurredAt || '').slice(0, 16).replace('T', ' ') }}</text>
            <view class="fc__row" v-if="c.receiptStatus === 'RECEIVED' && c.receiptNote">
              <text class="fc__row-k">回执</text><text class="flex-1 t-sm">{{ c.receiptNote }}</text>
            </view>
            <button v-if="c.receiptStatus === 'PENDING'" class="btn btn-ghost" :disabled="acting" @click="receipt(c)">登记家长回执</button>
          </view>
        </view>
      </view>

      <!-- 登记 -->
      <view class="page-pad" v-if="tab === 'create'">
        <MobileGlobalState v-if="!students.length" state="empty" title="暂无可登记学生"
          description="仅可为本人负责班级学生登记家校联系。" />
        <view class="card fc__form" v-else>
          <view class="fc__row fc__row--field">
            <text class="fc__row-k">联系学生</text>
            <picker class="fc__picker" mode="selector" :range="studentLabels" :value="studentIndex" @change="(e) => studentIndex = Number(e.detail.value)">
              <view class="fc__pick-val">{{ studentLabels[studentIndex] || '请选择' }}<text class="fc__arrow">▾</text></view>
            </picker>
          </view>
          <view class="fc__row fc__row--field">
            <text class="fc__row-k">联系方式</text>
            <picker class="fc__picker" mode="selector" :range="typeLabels" :value="typeIndex" @change="(e) => typeIndex = Number(e.detail.value)">
              <view class="fc__pick-val">{{ typeLabels[typeIndex] }}<text class="fc__arrow">▾</text></view>
            </picker>
          </view>
          <view class="fc__row fc__row--top">
            <text class="fc__row-k">联系事由</text>
            <textarea class="fc__textarea" v-model="reason" :maxlength="500" placeholder="可选" placeholder-class="fc__ph" />
          </view>
          <view class="fc__row fc__row--top" style="border-bottom:none;">
            <text class="fc__row-k">联系结果</text>
            <textarea class="fc__textarea" v-model="result" :maxlength="1000" placeholder="可选" placeholder-class="fc__ph" />
          </view>
        </view>
        <MobileSafeAreaBar v-if="students.length">
          <button class="btn btn-primary flex-1" :disabled="submitting" @click="submit">{{ submitting ? '登记中…' : '登记联系' }}</button>
        </MobileSafeAreaBar>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { createSubmitLock, normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const submitLock = createSubmitLock(1500)
const TYPES = [
  { key: 'PHONE', label: '电话' }, { key: 'WECHAT', label: '微信' },
  { key: 'VISIT', label: '家访' }, { key: 'MESSAGE', label: '短信' }
]

export default {
  data() {
    return {
      tab: 'list', list: null, state: 'loading', acting: false,
      students: [], studentIndex: 0, typeLabels: TYPES.map((t) => t.label), typeIndex: 0,
      reason: '', result: '', submitting: false
    }
  },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  computed: {
    studentLabels() { return this.students.map((s) => `${s.name}（${s.studentNo}）· ${s.className || ''}`) }
  },
  methods: {
    typeLabel(k) { return (TYPES.find((t) => t.key === k) || {}).label || k },
    load(done) {
      this.state = 'loading'
      teacherApi.getFamilyContactList()
        .then((d) => { this.list = (d && d.list) || []; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
        .finally(() => { if (done) done() })
    },
    onCreateTab() {
      this.tab = 'create'
      if (!this.students.length) {
        teacherApi.getFamilyContactStudents().then((d) => { this.students = (d && d.list) || [] }).catch(() => {})
      }
    },
    receipt(c) {
      if (this.acting) return
      uni.showModal({
        title: '登记家长回执', editable: true, placeholderText: '可填写回执内容（可选）', content: '',
        success: (r) => {
          if (!r.confirm) return
          this.acting = true
          teacherApi.markFamilyContactReceipt(c.contactId, (r.content || '').trim())
            .then(() => { toast('回执已登记'); this.load() })
            .catch((e) => {
              const code = e && String(e.code)
              if (code === 'DATA_CONFLICT') { toast('该记录已登记回执，正在刷新'); this.load() }
              else toast((e && e.message) || '登记失败，请重试')
            })
            .finally(() => { this.acting = false })
        }
      })
    },
    submit() {
      if (this.submitting) return
      const stu = this.students[this.studentIndex]
      if (!stu) { toast('请选择联系学生'); return }
      this.submitting = true
      submitLock.run(() => teacherApi.createFamilyContact(stu.studentId, {
        contactType: TYPES[this.typeIndex].key, reason: this.reason.trim(), result: this.result.trim()
      })).then(() => {
        uni.showToast({ title: '已登记', icon: 'success' })
        this.reason = ''; this.result = ''
        this.tab = 'list'; this.load()
      }).catch((e) => {
        if (e && e.code === 'LOCKED') return
        if (e && e.biz) toast(normalizeError(e).text)
        else toast('网络异常，提交未成功，请稍后重试')
      }).finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.fc__tabs { display: flex; gap: var(--space-6); padding: var(--space-3) var(--page-padding-mobile) 0; background: var(--bg-card); }
.fc__tab { position: relative; font-size: var(--font-size-base); color: var(--text-tertiary); font-weight: var(--font-weight-medium); padding-bottom: var(--space-3); }
.fc__tab.is-on { color: var(--text-primary); font-weight: var(--font-weight-semibold); }
.fc__tab-u { position: absolute; left: 50%; bottom: 0; transform: translateX(-50%); width: 22px; height: 3px; border-radius: 2px; background: var(--teacher-600); }
.fc__tab-badge { margin-left: 4px; font-size: 10px; color: #fff; background: var(--danger-500); padding: 1px 5px; border-radius: var(--radius-full); }
.fc { display: flex; flex-direction: column; gap: var(--space-2); }
.fc__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.fc__row { display: flex; gap: var(--space-3); }
.fc__row-k { font-size: var(--font-size-sm); color: var(--text-tertiary); width: 56px; flex-shrink: 0; }
.fc__time { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.fc__form { display: flex; flex-direction: column; }
.fc__row--field { align-items: center; min-height: 44px; }
.fc__row--top { flex-direction: column; gap: 4px; padding-top: var(--space-2); }
.fc__picker { flex: 1; }
.fc__pick-val { font-size: var(--font-size-base); color: var(--text-primary); text-align: right; }
.fc__arrow { color: var(--text-tertiary); font-size: var(--font-size-xs); margin-left: 4px; }
.fc__textarea { min-height: 64px; font-size: var(--font-size-base); color: var(--text-primary); line-height: 1.6; background: var(--gray-50); border-radius: var(--radius-md); padding: var(--space-2); }
.fc__ph { color: var(--text-tertiary); }
</style>
