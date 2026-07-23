<template>
  <view class="page-wrap app">
    <MobileGlobalState :state="pageState" @retry="load">
      <view class="page-pad stack">
        <view class="card">
          <text class="card-title">正式实习申请</text>
          <text class="app__hint">可申请校内岗位志愿或自主实习；自主实习须完整填写单位与证明材料。</text>
        </view>

        <view class="card stack">
          <view class="app__field">
            <text class="app__label">申请类型</text>
            <picker mode="selector" :range="typeLabels" @change="onTypePick">
              <view class="app__picker">{{ typeLabels[typeIndex] }}</view>
            </picker>
          </view>
          <view v-if="isPosition" class="app__field">
            <text class="app__label">岗位编号 <text class="app__req">*</text></text>
            <input v-model="form.positionId" class="app__input" placeholder="填写拟申请岗位 ID" />
          </view>
          <template v-else>
            <view class="app__field">
              <text class="app__label">企业名称 <text class="app__req">*</text></text>
              <input v-model="form.companyName" class="app__input" placeholder="不少于 2 字" />
            </view>
            <view class="app__field">
              <text class="app__label">岗位名称 <text class="app__req">*</text></text>
              <input v-model="form.positionName" class="app__input" placeholder="不少于 2 字" />
            </view>
            <view class="app__field">
              <text class="app__label">工作地址 <text class="app__req">*</text></text>
              <input v-model="form.workAddress" class="app__input" placeholder="不少于 5 字" />
            </view>
            <view class="app__field">
              <text class="app__label">单位联系人 <text class="app__req">*</text></text>
              <input v-model="form.contactName" class="app__input" placeholder="联系人姓名" />
            </view>
            <view class="app__field">
              <text class="app__label">联系人电话 <text class="app__req">*</text></text>
              <input v-model="form.contactPhone" class="app__input" placeholder="手机号" />
            </view>
            <view class="app__field">
              <text class="app__label">证明材料文件 ID <text class="app__req">*</text></text>
              <input v-model="form.evidenceFileId" class="app__input" placeholder="文件中心上传后的 fileId" />
            </view>
          </template>
          <view class="app__field">
            <text class="app__label">申请说明 <text class="app__req">*</text></text>
            <textarea v-model="form.applicationNote" class="app__textarea" maxlength="500" placeholder="不少于 5 字" />
          </view>
        </view>

        <view v-if="history.length" class="card">
          <text class="card-title">我的申请</text>
          <view v-for="h in history" :key="h.id" class="app__hist">
            <view class="row-between">
              <text>{{ h.applicationTypeLabel || h.applicationType }} · {{ h.statusLabel || h.status }}</text>
              <button v-if="h.status === 'SUBMITTED'" class="btn btn-ghost app__wd" @click="withdraw(h)">撤回</button>
            </view>
            <text class="app__hist-note">{{ h.applicationNote || h.companyName || '' }}</text>
          </view>
        </view>
      </view>
    </MobileGlobalState>
    <MobileSafeAreaBar>
      <button class="btn btn-ghost flex-1" :disabled="submitting" @click="saveDraft">保存草稿</button>
      <button class="btn btn-primary flex-1" :disabled="submitting" @click="submit">{{ submitting ? '提交中…' : '提交审核' }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { toast } from '@/utils/nav'

const TYPES = [
  { value: 'POSITION', label: '校内岗位志愿' },
  { value: 'SELF_ARRANGED', label: '自主实习' }
]

export default {
  data() {
    return {
      pageState: 'loading', submitting: false,
      typeIndex: 1, typeLabels: TYPES.map((t) => t.label),
      form: {
        positionId: '', companyName: '', positionName: '', workAddress: '',
        contactName: '', contactPhone: '', evidenceFileId: '', applicationNote: ''
      },
      history: [], draftId: ''
    }
  },
  computed: {
    isPosition() { return TYPES[this.typeIndex].value === 'POSITION' }
  },
  onLoad() { this.load() },
  methods: {
    onTypePick(e) { this.typeIndex = Number(e.detail.value) || 0 },
    load() {
      this.pageState = 'loading'
      studentApi.getInternshipApplications().then((rows) => {
        const list = Array.isArray(rows) ? rows : (rows && rows.items) || []
        this.history = list
        const draft = list.find((x) => x.status === 'DRAFT')
        if (draft) {
          this.draftId = draft.id
          const ti = TYPES.findIndex((t) => t.value === draft.applicationType)
          if (ti >= 0) this.typeIndex = ti
          Object.assign(this.form, {
            positionId: draft.positionId || '',
            companyName: draft.companyName || '',
            positionName: draft.positionName || '',
            workAddress: draft.workAddress || '',
            contactName: draft.contactName || '',
            contactPhone: draft.contactPhone || '',
            evidenceFileId: draft.evidenceFileId || '',
            applicationNote: draft.applicationNote || ''
          })
        }
        this.pageState = 'ready'
      }).catch(() => { this.pageState = 'error' })
    },
    payload() {
      const applicationType = TYPES[this.typeIndex].value
      const body = {
        applicationType,
        applicationNote: (this.form.applicationNote || '').trim()
      }
      if (this.draftId) body.id = this.draftId
      if (applicationType === 'POSITION') {
        body.positionId = this.form.positionId
      } else {
        Object.assign(body, {
          companyName: this.form.companyName,
          positionName: this.form.positionName,
          workAddress: this.form.workAddress,
          contactName: this.form.contactName,
          contactPhone: this.form.contactPhone,
          evidenceFileId: this.form.evidenceFileId
        })
      }
      return body
    },
    saveDraft() {
      if (this.submitting) return
      this.submitting = true
      studentApi.saveInternshipApplication(this.payload()).then((d) => {
        this.draftId = (d && d.id) || this.draftId
        toast('草稿已保存')
        this.load()
      }).catch((e) => toast((e && e.message) || '保存失败'))
        .finally(() => { this.submitting = false })
    },
    submit() {
      if (this.submitting) return
      const note = (this.form.applicationNote || '').trim()
      if (note.length < 5) return toast('申请说明不少于 5 字')
      if (this.isPosition && !this.form.positionId) return toast('请填写岗位编号')
      if (!this.isPosition) {
        if ((this.form.companyName || '').trim().length < 2) return toast('请填写企业名称')
        if ((this.form.positionName || '').trim().length < 2) return toast('请填写岗位名称')
        if ((this.form.workAddress || '').trim().length < 5) return toast('请填写工作地址')
        if ((this.form.contactName || '').trim().length < 2) return toast('请填写联系人')
        if (!(this.form.contactPhone || '').trim()) return toast('请填写联系电话')
        if (!(this.form.evidenceFileId || '').trim()) return toast('请填写证明材料文件 ID')
      }
      this.submitting = true
      studentApi.saveInternshipApplication(this.payload()).then((d) => {
        const id = (d && d.id) || this.draftId
        if (!id) throw new Error('保存失败，无法提交')
        if (d && d.status === 'SUBMITTED') return d
        return studentApi.submitInternshipApplication(id)
      }).then(() => {
        toast('申请已提交审核')
        this.load()
      }).catch((e) => toast((e && e.message) || '提交失败'))
        .finally(() => { this.submitting = false })
    },
    withdraw(h) {
      uni.showModal({
        title: '撤回申请',
        content: '确认撤回该待审核申请？',
        success: (r) => {
          if (!r.confirm) return
          studentApi.withdrawInternshipApplication(h.id).then(() => {
            toast('已撤回')
            this.load()
          }).catch((e) => toast((e && e.message) || '撤回失败'))
        }
      })
    }
  }
}
</script>

<style scoped>
.app__hint { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: var(--space-2); }
.app__field { display: flex; flex-direction: column; gap: 6px; margin-bottom: var(--space-3); }
.app__label { font-size: var(--font-size-sm); color: var(--text-secondary); }
.app__req { color: var(--danger-500); }
.app__input, .app__picker { border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 10px 12px; font-size: var(--font-size-sm); }
.app__textarea { border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 10px 12px; min-height: 90px; width: 100%; box-sizing: border-box; font-size: var(--font-size-sm); }
.app__hist { padding: var(--space-2) 0; border-bottom: 1px solid var(--border-light); font-size: var(--font-size-sm); }
.app__hist-note { display: block; margin-top: 4px; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.app__wd { margin-left: 8px; font-size: 12px; padding: 4px 10px; }
</style>
