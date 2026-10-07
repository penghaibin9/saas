<template>
  <view class="page-wrap itn">
    <MobileGlobalState :state="pageState" @retry="load">
      <view class="page-pad stack">
        <view class="card itn__head">
          <text class="card-title">实习意向填报</text>
          <text class="itn__hint">提交后由学院/指导老师进行岗位匹配，可随时撤回修改。</text>
          <view v-if="meta.intention" class="itn__status">
            <MobileStatusTag :status="statusTag(meta.intention.status)" />
            <text class="itn__time">更新于 {{ meta.intention.updatedAt || '—' }}</text>
          </view>
        </view>

        <view class="card stack">
          <view class="itn__field">
            <text class="itn__label">意向城市</text>
            <input v-model="form.preferredCity" class="itn__input" placeholder="如：上海、杭州" :disabled="!canEdit" />
          </view>
          <view class="itn__field">
            <text class="itn__label">意向行业</text>
            <input v-model="form.preferredIndustry" class="itn__input" placeholder="如：软件、智能制造" :disabled="!canEdit" />
          </view>
          <view class="itn__field">
            <text class="itn__label">意向岗位（可选）</text>
            <picker mode="selector" :range="positionLabels" :disabled="!canEdit || !positions.length" @change="onPositionPick">
              <view class="itn__picker">{{ positionLabel || '从已发布岗位中选择' }}</view>
            </picker>
          </view>
          <view class="itn__field">
            <text class="itn__label">补充说明</text>
            <textarea v-model="form.intentionNote" class="itn__textarea" maxlength="500"
              placeholder="可说明期望企业类型、通勤距离、特殊要求等" :disabled="!canEdit" />
          </view>
        </view>

        <MobileInlineAlert v-if="!positions.length" type="info"
          description="暂无可选岗位，可先填写城市/行业意向，待岗位发布后再补充。" />
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar>
      <button v-if="canEdit" class="btn btn-ghost flex-1" :disabled="submitting" @click="save">保存草稿</button>
      <button v-if="canSubmit" class="btn btn-primary flex-1" :disabled="submitting" @click="submit">提交意向</button>
      <button v-if="canWithdraw" class="btn btn-ghost flex-1" :disabled="submitting" @click="withdraw">撤回意向</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { toast } from '@/utils/nav'

export default {
  data() {
    return {
      pageState: 'loading', submitting: false,
      meta: { intention: null, positions: [], canEdit: true, canSubmit: false, canWithdraw: false },
      form: { preferredCity: '', preferredIndustry: '', preferredPositionId: '', intentionNote: '' },
      positions: [], positionIndex: -1
    }
  },
  computed: {
    canEdit() { return this.meta.canEdit },
    canSubmit() { return this.meta.canSubmit },
    canWithdraw() { return this.meta.canWithdraw },
    positionLabels() { return this.positions.map((p) => `${p.companyName} · ${p.title}（余${p.remaining}）`) },
    positionLabel() {
      if (this.positionIndex < 0) return ''
      const p = this.positions[this.positionIndex]
      return p ? `${p.companyName} · ${p.title}` : ''
    }
  },
  onLoad() { this.load() },
  methods: {
    statusTag(st) {
      if (st === 'SUBMITTED') return 'COMPLETED'
      if (st === 'DRAFT') return 'PENDING'
      return 'DEFAULT'
    },
    fillForm(it) {
      if (!it) {
        this.form = { preferredCity: '', preferredIndustry: '', preferredPositionId: '', intentionNote: '' }
        this.positionIndex = -1
        return
      }
      this.form = {
        preferredCity: it.preferredCity || '',
        preferredIndustry: it.preferredIndustry || '',
        preferredPositionId: it.preferredPositionId || '',
        intentionNote: it.intentionNote || ''
      }
      const idx = this.positions.findIndex((p) => p.id === it.preferredPositionId)
      this.positionIndex = idx >= 0 ? idx : -1
    },
    load() {
      this.pageState = 'loading'
      studentApi.getInternshipIntention().then((d) => {
        if (!d || !d.hasData) {
          this.pageState = 'empty'
          return
        }
        this.meta = d
        this.positions = d.positions || []
        this.fillForm(d.intention)
        this.pageState = 'ready'
      }).catch(() => { this.pageState = 'error' })
    },
    onPositionPick(e) {
      const i = Number(e.detail.value)
      this.positionIndex = i
      const p = this.positions[i]
      this.form.preferredPositionId = p ? p.id : ''
      if (p && p.workLocation && !this.form.preferredCity) {
        this.form.preferredCity = p.workLocation
      }
    },
    bodyPayload() {
      const p = { ...this.form }
      if (!p.preferredPositionId) delete p.preferredPositionId
      return p
    },
    save() {
      if (this.submitting || !this.canEdit) return
      if (!this.form.preferredCity.trim() && !this.form.preferredIndustry.trim() && !this.form.intentionNote.trim()) {
        return toast('请至少填写城市、行业或补充说明中的一项')
      }
      this.submitting = true
      studentApi.saveInternshipIntention(this.bodyPayload()).then(() => {
        toast('草稿已保存')
        this.load()
      }).catch((e) => toast((e && e.message) || '保存失败')).finally(() => { this.submitting = false })
    },
    submit() {
      if (this.submitting) return
      this.submitting = true
      const run = () => studentApi.submitInternshipIntention().then(() => {
        toast('意向已提交')
        this.load()
      }).catch((e) => toast((e && e.message) || '提交失败')).finally(() => { this.submitting = false })
      if (this.canEdit) {
        studentApi.saveInternshipIntention(this.bodyPayload()).then(run).catch((e) => {
          this.submitting = false
          toast((e && e.message) || '保存失败')
        })
      } else {
        run()
      }
    },
    withdraw() {
      if (this.submitting) return
      uni.showModal({
        title: '撤回意向',
        content: '撤回后可重新编辑并提交，确认撤回？',
        success: (r) => {
          if (!r.confirm) return
          this.submitting = true
          studentApi.withdrawInternshipIntention().then(() => {
            toast('已撤回')
            this.load()
          }).catch((e) => toast((e && e.message) || '撤回失败')).finally(() => { this.submitting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
.itn__hint { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 6px; }
.itn__status { display: flex; align-items: center; gap: var(--space-2); margin-top: var(--space-3); }
.itn__time { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.itn__field { display: flex; flex-direction: column; gap: 6px; margin-bottom: var(--space-3); }
.itn__label { font-size: var(--font-size-sm); color: var(--text-secondary); }
.itn__input, .itn__picker { padding: 10px 12px; border: 1px solid var(--border-base); border-radius: var(--radius-md); font-size: var(--font-size-base); background: #fff; }
.itn__textarea { min-height: 88px; padding: 10px 12px; border: 1px solid var(--border-base); border-radius: var(--radius-md); font-size: var(--font-size-base); width: 100%; box-sizing: border-box; }
</style>
