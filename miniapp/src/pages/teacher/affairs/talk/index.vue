<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" :title="active ? '谈话详情' : '谈心谈话'" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="!active && loaded">
        <view class="section-head">
          <text class="section-head__title">谈话记录</text>
          <text class="section-head__more" @click="toggleCreate">{{ showForm ? '收起' : '+ 新建谈话' }}</text>
        </view>

        <view class="card stack-sm" v-if="showForm">
          <picker mode="selector" :range="topicOptions" range-key="label" @change="onTopicChange">
            <view class="tk__input">{{ topicLabel }}</view>
          </picker>
          <input class="tk__input" v-model="form.topic" placeholder="谈话主题（如：期中学业关心）" placeholder-class="tk__ph" />
          <picker mode="multiSelector" :range="studentRanges" range-key="label" @change="onStudentChange">
            <view class="tk__input">{{ selectedStudentLabel }}</view>
          </picker>
          <view class="tk__selected" v-if="form.studentIds.length">
            <text v-for="s in selectedStudents" :key="s.studentId" class="tk__chip">{{ s.name }} · {{ s.className || s.studentNo }}</text>
          </view>
          <button class="btn btn-primary" :disabled="creating || !form.topic.trim() || !form.studentIds.length" @click="createPlan">
            {{ creating ? '创建中…' : '创建谈话计划' }}
          </button>
        </view>

        <view class="tk__filters">
          <text v-for="f in filters" :key="f.key" class="tk__filter" :class="{ 'is-active': filter === f.key }"
                @click="filter = f.key">{{ f.label }}</text>
        </view>

        <MobileGlobalState v-if="!list.length" state="empty" title="暂无谈话记录" description="点击右上角新建谈话计划。" />
        <view class="list-group" v-else>
          <view v-for="t in list" :key="t.talkId" class="list-row" @click="openTalk(t)">
            <view class="flex-1">
              <text class="t-md">{{ t.realName }}</text>
              <text class="tk__sub">{{ typeLabel(t.talkType) }} · {{ t.topic }}</text>
            </view>
            <MobileStatusTag :label="t.statusLabel" :type="statusTag(t.status)" />
          </view>
        </view>
      </view>

      <view class="page-pad" v-if="active">
        <text class="tk__back" @click="active = null">‹ 返回列表</text>
        <view class="card">
          <view class="row-between">
            <text class="t-lg t-bold">{{ active.realName }}</text>
            <MobileStatusTag :label="active.statusLabel" :type="statusTag(active.status)" />
          </view>
          <text class="tk__sub">{{ typeLabel(active.talkType) }} · {{ active.topic }}</text>
          <template v-if="active.content">
            <text class="tk__label">谈话内容</text>
            <text class="tk__text">{{ active.content }}</text>
            <template v-if="active.result">
              <text class="tk__label">谈话结果</text>
              <text class="tk__text">{{ active.result }}</text>
            </template>
          </template>
        </view>

        <template v-if="['PLANNED', 'SCHEDULED'].includes(active.status)">
          <view class="section-head"><text class="section-head__title">填写谈话记录</text></view>
          <view class="card stack-sm">
            <textarea class="tk__textarea" v-model="recordForm.content" :maxlength="500"
                      placeholder="谈话内容（不少于20字）" placeholder-class="tk__ph" />
            <textarea class="tk__textarea" v-model="recordForm.result" :maxlength="300"
                      placeholder="谈话结果/结论（选填）" placeholder-class="tk__ph" />
            <view class="tk__checkbox" @click="recordForm.needFollow = !recordForm.needFollow">
              <text class="tk__checkbox-box" :class="{ 'is-on': recordForm.needFollow }">{{ recordForm.needFollow ? '✓' : '' }}</text>
              <text>需要后续跟进</text>
            </view>
            <button class="btn btn-primary" :disabled="recording || recordForm.content.trim().length < 20" @click="submitRecord">
              {{ recording ? '保存中…' : '保存记录' }}
            </button>
          </view>
        </template>

        <template v-if="['COMPLETED', 'FOLLOW_UP'].includes(active.status)">
          <view class="section-head"><text class="section-head__title">后续处理</text></view>
          <view class="card stack-sm">
            <textarea class="tk__textarea" v-model="followContent" :maxlength="300" placeholder="跟进、转风险或转家校时填写说明" placeholder-class="tk__ph" />
            <button class="btn btn-ghost" :disabled="acting" @click="doFollowUp('FOLLOW')">继续跟进</button>
            <button class="btn btn-ghost" :disabled="acting" @click="doFollowUp('CLOSE')">办结</button>
            <button class="btn btn-ghost" :disabled="acting || followContent.trim().length < 5" @click="doFollowUp('TO_RISK')">转风险台账</button>
            <button class="btn btn-ghost" :disabled="acting || followContent.trim().length < 5" @click="doFollowUp('TO_HOME_SCHOOL')">转家校联系</button>
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
    topicLabel() {
      const o = TYPE_OPTS.find((x) => x.value === this.form.talkType)
      return o ? o.label : '选择谈话类型'
    },
    list() {
      if (this.filter === 'all') return this.all
      if (this.filter === 'FOLLOW_UP') return this.all.filter((t) => t.status === 'FOLLOW_UP')
      if (this.filter === 'PLANNED') return this.all.filter((t) => ['PLANNED', 'SCHEDULED'].includes(t.status))
      return this.all.filter((t) => t.status === this.filter)
    },
    studentRanges() {
      return [this.students.map((s) => ({ ...s, label: `${s.name} · ${s.className || s.studentNo}` }))]
    },
    selectedStudents() {
      const ids = new Set(this.form.studentIds.map(String))
      return this.students.filter((s) => ids.has(String(s.studentId)))
    },
    selectedStudentLabel() {
      if (!this.form.studentIds.length) return '选择学生（可连续添加）'
      return `已选择 ${this.form.studentIds.length} 人，继续点击可添加`
    }
  },
  onLoad() { this.load() },
  methods: {
    typeLabel(t) { return TYPE_LABEL[t] || t },
    statusTag(s) { return STATUS_TAG[s] || 'default' },
    onTopicChange(e) { this.form.talkType = TYPE_OPTS[e.detail.value].value },
    toggleCreate() {
      this.showForm = !this.showForm
      if (this.showForm && !this.students.length) this.loadStudents()
    },
    loadStudents() {
      teacherApi.getMyStudents().then((d) => {
        this.students = (d && d.items) || []
        if (!this.students.length) toast('当前数据范围内暂无可选择学生')
      }).catch((e) => this.showError(e, '学生名单加载失败'))
    },
    onStudentChange(e) {
      const index = Number((e.detail.value || [0])[0])
      const student = this.students[index]
      if (!student) return
      const id = String(student.studentId)
      if (!this.form.studentIds.map(String).includes(id)) this.form.studentIds.push(id)
      else this.form.studentIds = this.form.studentIds.filter((x) => String(x) !== id)
    },
    load() {
      this.state = 'loading'
      teacherApi.getTalkList().then((d) => {
        this.all = (d && d.items) || []
        this.loaded = true
        this.state = 'ready'
      }).catch((e) => {
        this.state = 'error'
        this.showError(e, '谈话记录加载失败')
      })
    },
    showError(e, fallback) {
      const n = normalizeError(e)
      toast(n.text || (e && e.message) || fallback)
      if (n.kind === 'conflict') this.load()
    },
    createPlan() {
      if (this.creating || !this.form.studentIds.length || !this.form.topic.trim()) return
      this.creating = true
      teacherApi.createTalk({ talkType: this.form.talkType, topic: this.form.topic.trim(), studentIds: this.form.studentIds })
        .then(() => {
          toast('谈话计划已创建')
          this.showForm = false
          this.form = { talkType: 'DAILY', topic: '', studentIds: [] }
          this.load()
        }).catch((e) => this.showError(e, '创建失败'))
        .finally(() => { this.creating = false })
    },
    openTalk(t) {
      teacherApi.getTalkDetail(t.talkId).then((d) => {
        this.active = d
        this.recordForm = { content: '', result: '', needFollow: false }
        this.followContent = ''
      }).catch((e) => this.showError(e, '详情加载失败'))
    },
    submitRecord() {
      if (this.recording || this.recordForm.content.trim().length < 20) return
      if (this.active.version === undefined || this.active.version === null) return toast('记录缺少版本号，请重新打开详情')
      this.recording = true
      affairsContractApi.recordTalk(this.active.talkId, {
        content: this.recordForm.content.trim(), result: this.recordForm.result.trim(), needFollow: this.recordForm.needFollow
      }, this.active.version).then((d) => {
        toast('已保存')
        this.active = d
      }).catch((e) => this.showError(e, '保存失败'))
        .finally(() => { this.recording = false })
    },
    doFollowUp(action) {
      if (this.acting) return
      if (this.active.version === undefined || this.active.version === null) return toast('记录缺少版本号，请重新打开详情')
      if (['TO_RISK', 'TO_HOME_SCHOOL'].includes(action) && this.followContent.trim().length < 5) return toast('转办说明至少5字')
      this.acting = true
      affairsContractApi.followTalk(this.active.talkId, action, this.followContent.trim(), this.active.version).then((d) => {
        toast('处理完成')
        this.active = d
        this.followContent = ''
      }).catch((e) => this.showError(e, '处理失败'))
        .finally(() => { this.acting = false })
    }
  }
}
</script>

<style scoped>
.tk__filters { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); }
.tk__filter { padding: 5px 14px; border-radius: var(--radius-full); background: var(--bg-card); font-size: var(--font-size-sm); color: var(--text-secondary); border: 1px solid var(--border-base); }
.tk__filter.is-active { background: var(--teacher-600); color: #fff; border-color: var(--teacher-600); }
.tk__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.tk__input { width: 100%; height: 40px; line-height: 40px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 0 var(--space-3); box-sizing: border-box; }
.tk__selected { display: flex; flex-wrap: wrap; gap: 6px; }
.tk__chip { font-size: 12px; padding: 4px 8px; background: #eff6ff; color: #1d4ed8; border-radius: 999px; }
.tk__ph { color: var(--text-tertiary); }
.tk__back { display: inline-block; font-size: var(--font-size-sm); color: var(--teacher-700); margin-bottom: var(--space-3); }
.tk__label { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: var(--space-3); }
.tk__text { display: block; font-size: var(--font-size-base); color: var(--text-primary); line-height: 1.6; margin-top: 4px; }
.tk__textarea { width: 100%; min-height: 70px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: var(--space-2); box-sizing: border-box; }
.tk__checkbox { display: flex; align-items: center; gap: var(--space-2); font-size: var(--font-size-sm); color: var(--text-secondary); }
.tk__checkbox-box { width: 20px; height: 20px; border: 1px solid var(--border-base); border-radius: var(--radius-sm); display: flex; align-items: center; justify-content: center; color: #fff; }
.tk__checkbox-box.is-on { background: var(--teacher-600); border-color: var(--teacher-600); }
</style>
