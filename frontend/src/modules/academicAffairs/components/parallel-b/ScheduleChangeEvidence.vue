<template>
  <section class="change-evidence" aria-label="调停课审核证据">
    <header><h2>当前对象 · 审核证据</h2><AppButton @click="$emit('close')">返回原队列</AppButton></header>
    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <template v-else-if="detail">
      <div class="change-evidence__identity">
        <div>
          <strong>{{ detail.courseName || '课程信息待确认' }} · {{ detail.className || '教学班待确认' }}</strong>
          <p>调停课申请 {{ detail.changeId }} · {{ detail.teacherName || '任课教师待确认' }} · 版本 {{ detail.version ?? '未提供' }}</p>
          <p>来源：正式课表项 {{ detail.originItemId || '未提供' }} · 批次 {{ detail.batchId || '未提供' }}</p>
        </div>
        <div class="change-evidence__owner"><small>当前责任</small><b>{{ ownerLabel }}</b><StatusTag :label="statusLabel" /></div>
        <div class="change-evidence__owner"><small>下一责任</small><b>{{ nextOwnerLabel }}</b></div>
      </div>
      <ol class="change-evidence__rail" aria-label="调停课办理阶段">
        <li v-for="(stage, index) in stages" :key="stage" :class="stageClass(index + 1)"><b>{{ index + 1 }}</b><span>{{ stage }}</span><small>{{ stageNote(index + 1) }}</small></li>
      </ol>
      <div class="change-evidence__compare">
        <section v-for="slot in slots" :key="slot.title">
          <h3>{{ slot.title }}</h3>
          <p v-if="slot.stopped">停课</p>
          <dl v-else>
            <div><dt>星期 / 节次</dt><dd>{{ weekday(slot.value?.weekday) }} · 第 {{ slot.value?.slotNo ?? '—' }} 节</dd></div>
            <div><dt>教室</dt><dd>{{ slot.value?.classroom || '未提供' }}</dd></div>
            <div><dt>适用周次</dt><dd>第 {{ slot.value?.startWeek ?? '—' }}—{{ slot.value?.endWeek ?? '—' }} 周 · {{ parity(slot.value?.weekParity) }}</dd></div>
          </dl>
        </section>
      </div>
      <section class="change-evidence__proof"><h3>申请与办理证据</h3><div class="change-evidence__proof-grid">
        <article v-for="item in evidenceCards" :key="item.title">
          <header><strong>{{ item.title }}</strong><StatusTag :type="item.tone" :label="item.status" /></header>
          <p>{{ item.description }}</p>
          <small>{{ item.source }}</small>
        </article>
      </div></section>
      <p class="change-evidence__note">正式课表生效与通知送达分别核对；详情接口未返回送达数量时，不把“已生成通知”写成“全部送达”。</p>
      <AppButton v-if="detail.status === 'APPLIED'" @click="$emit('notice', detail)">查看通知单</AppButton>
    </template>
  </section>
</template>

<script>
import { LoadingState, ErrorState, StatusTag } from '@/components/business'
import { AppButton } from '@/components/ui'
import { scheduleChangeApi, CHANGE_STATUS } from '@/modules/academicAffairs/api/academic-schedule-change.api'
import { currentUserFromToken } from '@/services/http/client'

export default {
  components: { LoadingState, ErrorState, StatusTag, AppButton },
  props: { changeId: { type: String, required: true }, ctx: { type: Object, default: () => ({}) } },
  emits: ['close', 'notice', 'loaded', 'read-denied'],
  data() { return { detail: null, loading: false, error: '', sequence: 0 } },
  computed: {
    identity() { return JSON.stringify([currentUserFromToken(), this.ctx]) },
    statusLabel() { return CHANGE_STATUS.find(item => item.value === this.detail?.status)?.label || '状态待确认' },
    slots() { return [{ title: '原正式课位', value: this.detail.origin }, { title: '拟调整课位', value: this.detail.target, stopped: this.detail.changeType === 'STOP' }] },
    stages() { return ['正式课位', '发起申请', '冲突预检', '审批生效', '通知回执'] },
    stageIndex() { return this.detail?.status === 'APPLIED' ? 5 : 4 },
    ownerLabel() {
      return { SUBMITTED: '学院教务审核岗', COLLEGE_REVIEW: '教务审核岗', ACADEMIC_REVIEW: '教务终审岗', APPROVED: '课表生效服务', APPLIED: '申请人与通知核对岗', REJECTED: '任课教师', CANCELLED: '任课教师' }[this.detail?.status] || '当前受理岗待确认'
    },
    nextOwnerLabel() {
      return { SUBMITTED: '教务审核岗', COLLEGE_REVIEW: '教务终审岗', ACADEMIC_REVIEW: '课表生效服务', APPROVED: '师生通知', APPLIED: '流程结束', REJECTED: '修正后重新发起', CANCELLED: '流程结束' }[this.detail?.status] || '按正式状态继续'
    },
    evidenceCards() {
      const detail = this.detail || {}
      const targetRequired = detail.changeType !== 'STOP'
      const targetReady = !targetRequired || Boolean(detail.target?.weekday && detail.target?.slotNo)
      const materialReady = String(detail.reason || '').trim().length >= 5
      const appliedReady = detail.status === 'APPLIED' && Boolean(detail.appliedAt)
      return [
        { title: '来源对象与身份', status: detail.originItemId && detail.changeId ? '已核对 · PASS' : '待核对 · WARNING', tone: detail.originItemId && detail.changeId ? 'success' : 'warning', description: `申请 ${detail.changeId || '未提供'} 来源于正式课表项 ${detail.originItemId || '未提供'}。`, source: `批次 ${detail.batchId || '未提供'} · 课程 ${detail.courseName || '未提供'}` },
        { title: '原正式课位', status: detail.origin?.weekday && detail.origin?.slotNo ? '已核对 · PASS' : '待核对 · WARNING', tone: detail.origin?.weekday && detail.origin?.slotNo ? 'success' : 'warning', description: detail.origin?.weekday && detail.origin?.slotNo ? `${this.weekday(detail.origin.weekday)}第 ${detail.origin.slotNo} 节 · ${detail.origin.classroom || '教室未提供'}` : '原课位字段不完整。', source: '来源：正式课表快照' },
        { title: '目标课位与冲突', status: targetReady ? (targetRequired ? '已预检 · PASS' : '不适用 · N/A') : '待核对 · WARNING', tone: targetReady ? 'success' : 'warning', description: targetRequired ? (targetReady ? `${this.weekday(detail.target.weekday)}第 ${detail.target.slotNo} 节 · ${detail.target.classroom || '教室未提供'}` : '目标课位字段不完整。') : '停课不生成目标课位。', source: '提交服务在建单时执行正式冲突预检' },
        { title: '材料与事实依据', status: materialReady ? '已核对 · PASS' : '待核对 · WARNING', tone: materialReady ? 'success' : 'warning', description: detail.reason || '未提供申请原因。', source: `后续安排：${detail.makeupPlan || '未提供'}` },
        { title: '当前节点与版本', status: detail.status && detail.version != null ? '已核对 · PASS' : '待核对 · WARNING', tone: detail.status && detail.version != null ? 'success' : 'warning', description: `${this.statusLabel} · ${this.ownerLabel}`, source: `当前节点 ${detail.currentNode || '未提供'} · 版本 ${detail.version ?? '未提供'}` },
        { title: '生效与通知回执', status: appliedReady ? '课表已生效 · WARNING' : '等待办理 · WAITING', tone: appliedReady ? 'warning' : 'info', description: appliedReady ? `生效时间 ${detail.appliedAt}；通知送达数量未随详情返回。` : '尚未到达正式生效与通知回执阶段。', source: appliedReady ? `新课表项 ${detail.newItemId || '停课无新项'}` : `申请时间 ${detail.createdAt || '未提供'}` }
      ]
    }
  },
  watch: { changeId: 'load', identity: 'load' },
  created() { this.load() },
  beforeUnmount() { this.sequence++ },
  methods: {
    weekday(day) { return '周' + ('一二三四五六日'[Number(day) - 1] || '次待确认') },
    parity(value) { return { ALL: '全周', ODD: '单周', EVEN: '双周' }[value] || '单双周待确认' },
    stageClass(index) { return { 'is-done': index < this.stageIndex, 'is-active': index === this.stageIndex } },
    stageNote(index) {
      if (index < this.stageIndex) return '已由正式状态确认'
      if (index === this.stageIndex) return '当前办理阶段'
      return '等待前序完成'
    },
    async load() {
      const sequence = ++this.sequence
      const id = this.changeId
      const identity = this.identity
      const current = () => sequence === this.sequence && id === this.changeId && identity === this.identity
      this.detail = null; this.error = ''; this.loading = true
      this.$emit('loaded', null)
      try {
        if (!id) { this.error = '请先选择调停课申请'; return }
        const response = await scheduleChangeApi.detail(id)
        if (!current()) return
        if (response.code !== 0) {
          this.error = response.message || '申请详情加载失败'
          if (Number(response.code) === 403 || Math.floor(Number(response.code) / 1000) === 403) this.$emit('read-denied')
          return
        }
        if (String(response.data?.changeId) !== id) { this.error = '返回的申请对象不匹配，请重新选择'; return }
        this.detail = response.data
        this.$emit('loaded', response.data)
      } catch (error) { if (current()) this.error = error?.message || '申请详情加载失败' }
      finally { if (current()) this.loading = false }
    }
  }
}
</script>

<style scoped>
.change-evidence { display: grid; gap: 16px; min-width: 0; }
header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
h2 { margin: 0; font-size: 22px; } h3 { margin: 0 0 16px; font-size: 15px; }
.change-evidence__identity, .change-evidence__compare > section, .change-evidence > section { padding: 18px; background: var(--bg-card, #fff); border: 1px solid var(--line, #dce4ee); border-radius: 12px; }
.change-evidence__identity { display: grid; grid-template-columns: minmax(0, 1fr) minmax(150px, auto) minmax(150px, auto); gap: 20px; align-items: center; border-left: 3px solid var(--pri, #2b5bb4); }
.change-evidence__identity p, .change-evidence__note { font-size: 12px; color: var(--t2, #52647a); }
.change-evidence__owner { display: grid; gap: 5px; font-size: 13px; }.change-evidence__owner small { color: var(--t2, #52647a); }
.change-evidence__rail { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 0; list-style: none; margin: 0; padding: 15px 10px; background: var(--bg-card, #fff); border: 1px solid var(--line, #dce4ee); border-radius: 12px; }
.change-evidence__rail li { position: relative; display: grid; justify-items: center; gap: 4px; color: var(--t2, #52647a); text-align: center; font-size: 12px; }
.change-evidence__rail li::after { content: ''; position: absolute; top: 12px; left: calc(50% + 18px); width: calc(100% - 36px); height: 1px; background: var(--line, #dce4ee); }.change-evidence__rail li:last-child::after { display: none; }
.change-evidence__rail b { position: relative; z-index: 1; display: grid; place-items: center; width: 24px; height: 24px; border-radius: 50%; background: #f5f7fa; border: 1px solid var(--line, #dce4ee); }
.change-evidence__rail .is-done b { color: #16803c; border-color: #b7dfc2; background: #f0f9f2; }.change-evidence__rail .is-active b { color: #fff; border-color: var(--pri, #2b5bb4); background: var(--pri, #2b5bb4); }.change-evidence__rail small { color: var(--t3, #94a3b8); }
.change-evidence__compare { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.change-evidence__proof-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.change-evidence__proof-grid article { padding: 14px; border: 1px solid var(--line, #dce4ee); border-radius: 9px; min-width: 0; }.change-evidence__proof-grid article header { align-items: flex-start; }.change-evidence__proof-grid article p { margin: 10px 0; color: var(--t2, #52647a); font-size: 13px; line-height: 1.6; }.change-evidence__proof-grid article small { color: var(--t3, #94a3b8); overflow-wrap: anywhere; }
dl { display: grid; gap: 14px; margin: 0; } dt { color: var(--t2, #52647a); font-size: 12px; } dd { margin: 5px 0 0; font-size: 14px; overflow-wrap: anywhere; white-space: pre-wrap; }
@media (max-width: 900px) { .change-evidence__identity, .change-evidence__compare, .change-evidence__proof-grid { grid-template-columns: 1fr; }.change-evidence__rail { grid-template-columns: 1fr; gap: 10px; }.change-evidence__rail li { justify-items: start; grid-template-columns: 26px auto; text-align: left; }.change-evidence__rail li::after { display: none; }.change-evidence__rail li small { grid-column: 2; } }
</style>
