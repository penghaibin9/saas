<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" :title="active ? '谈话详情' : '谈心谈话'" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="!active && loaded">
        <view class="section-head"><text class="section-head__title">谈话记录</text><text class="section-head__more" @click="toggleCreate">{{ showForm ? '收起' : '+ 新建谈话' }}</text></view>

        <view class="card stack-sm" v-if="showForm">
          <picker mode="selector" :range="topicOptions" range-key="label" @change="onTopicChange"><view class="tk__input">{{ topicLabel }}</view></picker>
          <input class="tk__input" v-model="form.topic" maxlength="100" placeholder="谈话主题（2-100字，如：期中学业关心）" placeholder-class="tk__ph" />
          <picker mode="selector" :range="students" range-key="label" @change="onStudentChange"><view class="tk__input">{{ selectedStudentLabel }}</view></picker>
          <view class="tk__selected" v-if="form.studentIds.length">
            <text v-for="s in selectedStudents" :key="s.studentId" class="tk__chip" @click.stop="removeStudent(s.studentId)">{{ s.name }} · {{ s.className || s.studentNo }} ×</text>
            <text class="tk__clear" @click="form.studentIds = []">清空</text>
          </view>
          <button class="btn btn-primary" :disabled="creating || !canCreate" @click="createPlan">{{ creating ? '创建中…' : '创建谈话计划' }}</button>
        </view>

        <view class="tk__filters"><text v-for="f in filters" :key="f.key" class="tk__filter" :class="{ 'is-active': filter === f.key }" @click="filter = f.key">{{ f.label }}</text></view>
        <MobileGlobalState v-if="!list.length" state="empty" title="暂无谈话记录" description="点击右上角新建谈话计划。" />
        <view class="list-group" v-else>
          <view v-for="t in list" :key="t.talkId" class="list-row" @click="openTalk(t)">
            <view class="flex-1"><text class="t-md">{{ t.realName }}</text><text class="tk__sub">{{ typeLabel(t.talkType) }} · {{ t.topic }}</text></view>
            <MobileStatusTag :label="t.statusLabel" :type="statusTag(t.status)" />
          </view>
        </view>
      </view>

      <view class="page-pad" v-if="active">
        <text class="tk__back" @click="active = null">‹ 返回列表</text>
        <view class="card">
          <view class="row-between"><text class="t-lg t-bold">{{ active.realName }}</text><MobileStatusTag :label="active.statusLabel" :type="statusTag(active.status)" /></view>
          <text class="tk__sub">{{ typeLabel(active.talkType) }} · {{ active.topic }}</text>
          <template v-if="active.content"><text class="tk__label">谈话内容</text><text class="tk__text">{{ active.content }}</text><template v-if="active.result"><text class="tk__label">谈话结果</text><text class="tk__text">{{ active.result }}</text></template></template>
        </view>

        <template v-if="['PLANNED', 'SCHEDULED'].includes(active.status)">
          <view class="section-head"><text class="section-head__title">填写谈话记录</text></view>
          <view class="card stack-sm">
            <textarea class="tk__textarea" v-model="recordForm.content" :maxlength="500" placeholder="谈话内容（20-500字）" placeholder-class="tk__ph" />
            <text class="tk__counter">{{ recordForm.content.trim().length }}/500</text>
            <textarea class="tk__textarea" v-model="recordForm.result" :maxlength="300" placeholder="谈话结果/结论（选填，最多300字）" placeholder-class="tk__ph" />
            <view class="tk__checkbox" @click="recordForm.needFollow = !recordForm.needFollow"><text class="tk__checkbox-box" :class="{ 'is-on': recordForm.needFollow }">{{ recordForm.needFollow ? '✓' : '' }}</text><text>需要后续跟进</text></view>
            <button class="btn btn-primary" :disabled="recording || recordForm.content.trim().length < 20" @click="submitRecord">{{ recording ? '保存中…' : '保存记录' }}</button>
          </view>
        </template>

        <template v-if="['COMPLETED', 'FOLLOW_UP'].includes(active.status)">
          <view class="section-head"><text class="section-head__title">后续处理</text></view>
          <view class="card stack-sm">
            <textarea class="tk__textarea" v-model="followContent" :maxlength="300" placeholder="填写跟进、办结或转办说明（5-300字）" placeholder-class="tk__ph" />
            <text class="tk__counter">{{ followContent.trim().length }}/300</text>
            <button v-if="canAct('FOLLOW')" class="btn btn-ghost" :disabled="acting || followContent.trim().length < 5" @click="doFollowUp('FOLLOW')">继续跟进</button>
            <button v-if="canAct('CLOSE')" class="btn btn-ghost" :disabled="acting || followContent.trim().length < 5" @click="doFollowUp('CLOSE')">办结（需结论）</button>
            <button v-if="canAct('TO_RISK')" class="btn btn-ghost" :disabled="acting || followContent.trim().length < 5" @click="doFollowUp('TO_RISK')">转风险台账</button>
            <button v-if="canAct('TO_HOME_SCHOOL')" class="btn btn-ghost" :disabled="acting || followContent.trim().length < 5" @click="doFollowUp('TO_HOME_SCHOOL')">转家校联系</button>
            <text v-if="!availableActions.length" class="tk__sub">当前状态暂无可执行动作。</text>
          </view>
        </template>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { affairsContractApi } from '@/services/affairsContractApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const TYPE_OPTS = [
  { value: 'DAILY', label: '日常谈心' }, { value: 'ACADEMIC', label: '学业关心' },
  { value: 'PSYCHOLOGY', label: '心理关怀' }, { value: 'DISCIPLINE', label: '违纪教育' },
  { value: 'EMPLOYMENT', label: '就业指导' }, { value: 'INTERNSHIP', label: '实习关心' },
  { value: 'AID', label: '资助关心' }, { value: 'DORM', label: '宿舍关心' }
]
const TYPE_LABEL = Object.fromEntries(TYPE_OPTS.map((o) => [o.value, o.label]))
const STATUS_TAG = { PLANNED: 'warning', SCHEDULED: 'warning', COMPLETED: 'processing', FOLLOW_UP: 'processing', CLOSED: 'success', CANCELLED: 'default' }
const FILTERS = [{ key: 'all', label: '全部' }, { key: 'PLANNED', label: '待谈' }, { key: 'FOLLOW_UP', label: '跟进中' }, { key: 'CLOSED', label: '已办结' }]
const FALLBACK_ACTIONS = { COMPLETED: ['FOLLOW', 'CLOSE', 'TO_RISK', 'TO_HOME_SCHOOL'], FOLLOW_UP: ['FOLLOW', 'CLOSE', 'TO_RISK', 'TO_HOME_SCHOOL'] }

export default {
  data() {
    return {
      state: 'loading', loaded: false, all: [], filter: 'all', showForm: false, creating: false,
      form: { talkType: 'DAILY', topic: '', studentIds: [] }, students: [],
      active: null, recordForm: { content: '', result: '', needFollow: false },
      recording: false, acting: false, followContent: '', topicOptions: TYPE_OPTS, filters: FILTERS
    }
  },
  computed: {
    topicLabel() { const o = TYPE_OPTS.find((x) => x.value === this.form.talkType); return o ? o.label : '选择谈话类型' },
    list() {
      if (this.filter === 'all') return this.all
      if (this.filter === 'FOLLOW_UP') return this.all.filter((t) => t.status === 'FOLLOW_UP')
      if (this.filter === 'PLANNED') return this.all.filter((t) => ['PLANNED', 'SCHEDULED'].includes(t.status))
      return this.all.filter((t) => t.status === this.filter)
    },
    selectedStudents() { const ids = new Set(this.form.studentIds.map(String)); return this.students.filter((s) => ids.has(String(s.studentId))) },
    selectedStudentLabel() { return this.form.studentIds.length ? `已选择 ${this.form.studentIds.length} 人，继续点击可添加或移除` : '选择学生（可连续添加）' },
    canCreate() { const len = this.form.topic.trim().length; return len >= 2 && len <= 100 && this.form.studentIds.length > 0 },
    availableActions() { return Array.isArray(this.active && this.active.allowedActions) ? this.active.allowedActions : (FALLBACK_ACTIONS[(this.active && this.active.status) || ''] || []) }
  },
  onLoad() { this.load() },
  methods: {
    typeLabel(t) { return TYPE_LABEL[t] || t }, statusTag(s) { return STATUS_TAG[s] || 'default' }, canAct(a) { return this.availableActions.includes(a) },
    onTopicChange(e) { this.form.talkType = TYPE_OPTS[e.detail.value].value },
    toggleCreate() { this.showForm = !this.showForm; if (this.showForm && !this.students.length) this.loadStudents() },
    loadStudents() {
      teacherApi.getMyStudents().then((d) => {
        this.students = ((d && d.items) || []).map((s) => ({ ...s, label: `${s.name} · ${s.className || s.studentNo}` }))
        if (!this.students.length) toast('当前数据范围内暂无可选择学生')
      }).catch((e) => this.showError(e, '学生名单加载失败'))
    },
    onStudentChange(e) {
      const student = this.students[Number(e.detail.value)]; if (!student) return
      const id = String(student.studentId)
      if (!this.form.studentIds.map(String).includes(id)) this.form.studentIds.push(id)
      else this.removeStudent(id)
    },
    removeStudent(id) { this.form.studentIds = this.form.studentIds.filter((x) => String(x) !== String(id)) },
    load() {
      this.state = 'loading'
      teacherApi.getTalkList().then((d) => { this.all = (d && d.items) || []; this.loaded = true; this.state = 'ready' })
        .catch((e) => { this.state = 'error'; this.showError(e, '谈话记录加载失败') })
    },
    showError(e, fallback) { const n = normalizeError(e); toast(n.text || (e && e.message) || fallback); if (n.kind === 'conflict') this.load(); return n },
    createPlan() {
      if (this.creating || !this.canCreate) return
      this.creating = true
      teacherApi.createTalk({ talkType: this.form.talkType, topic: this.form.topic.trim(), studentIds: this.form.studentIds })
        .then(() => { toast('谈话计划已创建'); this.showForm = false; this.form = { talkType: 'DAILY', topic: '', studentIds: [] }; this.load() })
        .catch((e) => this.showError(e, '创建失败')).finally(() => { this.creating = false })
    },
    openTalk(t) {
      teacherApi.getTalkDetail(t.talkId).then((d) => { this.active = d; this.recordForm = { content: '', result: '', needFollow: false }; this.followContent = '' })
        .catch((e) => this.showError(e, '详情加载失败'))
    },
    submitRecord() {
      const content = this.recordForm.content.trim(); if (this.recording || content.length < 20 || content.length > 500) return
      if (this.active.version === undefined || this.active.version === null) return toast('记录缺少版本号，请重新打开详情')
      this.recording = true
      affairsContractApi.recordTalk(this.active.talkId, { content, result: this.recordForm.result.trim(), needFollow: this.recordForm.needFollow }, this.active.version)
        .then((d) => { toast('已保存'); this.active = d; this.recordForm = { content: '', result: '', needFollow: false } })
        .catch((e) => this.showError(e, '保存失败')).finally(() => { this.recording = false })
    },
    doFollowUp(action) {
      const content = this.followContent.trim()
      if (this.acting || !this.canAct(action) || content.length < 5 || content.length > 300) return toast('处理说明需5-300字')
      if (this.active.version === undefined || this.active.version === null) return toast('记录缺少版本号，请重新打开详情')
      const run = () => {
        this.acting = true
        affairsContractApi.followTalk(this.active.talkId, action, content, this.active.version).then((d) => { toast('处理完成'); this.active = d; this.followContent = '' }).catch((e) => this.showError(e, '处理失败')).finally(() => { this.acting = false })
      }
      if (action === 'CLOSE') {
        uni.showModal({ title: '确认办结谈话', content: `办结结论：${content}\n\n办结后该记录转为只读，请确认后续事项已处理。`, confirmText: '确认办结', success: (r) => { if (r.confirm) run() } })
      } else run()
    }
  }
}
</script>

<style scoped>
.tk__filters { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); }.tk__filter { padding: 5px 14px; border-radius: var(--radius-full); background: var(--bg-card); font-size: var(--font-size-sm); color: var(--text-secondary); border: 1px solid var(--border-base); }.tk__filter.is-active { background: var(--teacher-600); color: #fff; border-color: var(--teacher-600); }.tk__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }.tk__input { width: 100%; height: 40px; line-height: 40px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 0 var(--space-3); box-sizing: border-box; }.tk__ph { color: var(--text-tertiary); }.tk__selected { display: flex; flex-wrap: wrap; gap: 6px; }.tk__chip { font-size: 11px; background: #eef2ff; color: #3730a3; border-radius: 999px; padding: 4px 8px; }.tk__clear { font-size: 11px; color: #dc2626; padding: 4px 6px; }.tk__back { display: inline-block; color: var(--teacher-700); margin-bottom: var(--space-3); }.tk__label { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: var(--space-3); }.tk__text { display: block; margin-top: 4px; line-height: 1.6; }.tk__textarea { width: 100%; min-height: 76px; box-sizing: border-box; border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: var(--space-2); }.tk__counter { display: block; text-align: right; font-size: 11px; color: #94a3b8; }.tk__checkbox { display: flex; align-items: center; gap: 8px; }.tk__checkbox-box { width: 18px; height: 18px; border: 1px solid var(--border-base); border-radius: 4px; text-align: center; line-height: 18px; }.tk__checkbox-box.is-on { background: var(--teacher-600); color: #fff; }.row-between { display: flex; justify-content: space-between; align-items: center; }
</style>
