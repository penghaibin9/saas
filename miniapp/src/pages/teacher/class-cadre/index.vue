<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="班干部管理" subtitle="任命 · 免去" show-back />

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="classes.length">
        <view class="card cc__class-row">
          <text class="cc__row-k">选择班级</text>
          <picker class="cc__picker" mode="selector" :range="classLabels" :value="classIndex" @change="onClass">
            <view class="cc__pick-val">{{ classLabels[classIndex] || '请选择' }}<text class="cc__arrow">▾</text></view>
          </picker>
        </view>

        <view class="section-head">
          <text class="section-head__title">在任班干部</text>
          <text class="section-head__more" @click="onAppointTab">+ 任命</text>
        </view>
        <MobileGlobalState v-if="!cadres.length" state="empty" title="暂无在任班干部" description="点击右上角「+ 任命」新增。" />
        <view class="stack" v-else>
          <view v-for="c in cadres" :key="c.cadreId" class="card cc">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ positionLabel(c.position) }}</text>
                <text class="cc__sub">{{ c.studentName || '—' }} · {{ c.studentNo || '' }}</text>
              </view>
              <button class="cc__remove" :disabled="acting" @click="doRemove(c)">免去</button>
            </view>
            <text class="cc__time" v-if="c.appointedAt">任命于 {{ c.appointedAt.slice(0, 10) }}</text>
          </view>
        </view>

        <!-- 任命表单 -->
        <template v-if="showAppoint">
          <view class="section-head"><text class="section-head__title">任命班干部</text></view>
          <view class="card cc__form">
            <view class="cc__row">
              <text class="cc__row-k">学生</text>
              <picker class="cc__picker" mode="selector" :range="studentLabels" :value="studentIndex" @change="(e) => studentIndex = Number(e.detail.value)">
                <view class="cc__pick-val">{{ studentLabels[studentIndex] || '请选择' }}<text class="cc__arrow">▾</text></view>
              </picker>
            </view>
            <view class="cc__row">
              <text class="cc__row-k">职务</text>
              <picker class="cc__picker" mode="selector" :range="positionLabels" :value="positionIndex" @change="(e) => positionIndex = Number(e.detail.value)">
                <view class="cc__pick-val">{{ positionLabels[positionIndex] }}<text class="cc__arrow">▾</text></view>
              </picker>
            </view>
            <view class="cc__row" style="border-bottom:none;">
              <text class="cc__row-k">学年学期</text>
              <input class="cc__input" v-model="termCode" placeholder="可选，如 2025-2026-1" />
            </view>
          </view>
          <MobileSafeAreaBar>
            <button class="btn btn-ghost flex-1" :disabled="submitting" @click="showAppoint = false">取消</button>
            <button class="btn btn-primary flex-1" :disabled="submitting" @click="submitAppoint">{{ submitting ? '提交中…' : '确认任命' }}</button>
          </MobileSafeAreaBar>
        </template>
      </view>
      <MobileGlobalState v-else state="empty" title="暂无负责班级" description="如信息有误请联系系统管理员核实班级归属。" />
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { toast } from '@/utils/nav'

const POSITIONS = [
  { key: 'MONITOR', label: '班长' }, { key: 'VICE_MONITOR', label: '副班长' },
  { key: 'LEAGUE_SECRETARY', label: '团支书' }, { key: 'STUDY', label: '学习委员' },
  { key: 'LIFE', label: '生活委员' }, { key: 'SPORTS', label: '体育委员' },
  { key: 'PSYCHOLOGY', label: '心理委员' }, { key: 'ORGANIZATION', label: '组织委员' },
  { key: 'PUBLICITY', label: '宣传委员' }, { key: 'OTHER', label: '其他' }
]

export default {
  data() {
    return {
      state: 'loading', classes: [], classIndex: 0, cadres: [],
      showAppoint: false, students: [], studentIndex: 0,
      positionLabels: POSITIONS.map((p) => p.label), positionIndex: 0, termCode: '',
      acting: false, submitting: false
    }
  },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  computed: {
    classLabels() { return this.classes.map((c) => `${c.className}${c.grade ? '（' + c.grade + '级）' : ''}`) },
    studentLabels() { return this.students.map((s) => `${s.name}（${s.studentNo}）`) },
    currentClassId() { const c = this.classes[this.classIndex]; return c ? c.classId : null }
  },
  methods: {
    positionLabel(k) { return (POSITIONS.find((p) => p.key === k) || {}).label || k },
    load(done) {
      this.state = 'loading'
      teacherApi.getAffairsMyClasses().then((d) => {
        this.classes = (d && d.list) || []
        this.state = 'ready'
        if (this.classes.length) return this.loadCadres()
      }).catch(() => { this.state = 'error' }).finally(() => { if (done) done() })
    },
    onClass(e) { this.classIndex = Number(e.detail.value); this.showAppoint = false; this.loadCadres() },
    loadCadres() {
      if (!this.currentClassId) return
      teacherApi.getAffairsCadreList(this.currentClassId).then((d) => {
        this.cadres = (d && d.list) || []
      }).catch(() => { this.cadres = [] })
    },
    onAppointTab() {
      if (!this.currentClassId) return
      this.showAppoint = true
      teacherApi.getAffairsClassStudents(this.currentClassId).then((d) => {
        this.students = (d && d.list) || []
      }).catch(() => { this.students = [] })
    },
    doRemove(c) {
      if (this.acting) return
      uni.showModal({
        title: '免去班干部', content: `确认免去「${c.studentName}」的${this.positionLabel(c.position)}职务？`,
        editable: true, placeholderText: '可填写原因（可选）',
        success: (r) => {
          if (!r.confirm) return
          this.acting = true
          teacherApi.removeAffairsCadre(c.cadreId, r.content || '')
            .then(() => { toast('已免去'); this.loadCadres() })
            .catch((e) => toast((e && e.message) || '操作失败，请重试'))
            .finally(() => { this.acting = false })
        }
      })
    },
    submitAppoint() {
      if (this.submitting) return
      const stu = this.students[this.studentIndex]
      if (!stu) { toast('请选择学生'); return }
      this.submitting = true
      teacherApi.appointAffairsCadre(this.currentClassId, {
        studentId: stu.studentId, position: POSITIONS[this.positionIndex].key, termCode: this.termCode.trim() || null
      }).then(() => {
        toast('已任命')
        this.showAppoint = false; this.termCode = ''; this.studentIndex = 0; this.positionIndex = 0
        this.loadCadres()
      }).catch((e) => {
        const code = e && String(e.code)
        if (code === 'DATA_CONFLICT') toast((e && e.message) || '该班级该职务已有在任班干部')
        else toast((e && e.message) || '任命失败，请重试')
      }).finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.cc__class-row { display: flex; align-items: center; gap: var(--space-3); }
.cc__row-k { font-size: var(--font-size-sm); color: var(--text-tertiary); flex-shrink: 0; width: 64px; }
.cc__picker { flex: 1; }
.cc__pick-val { font-size: var(--font-size-base); color: var(--text-primary); text-align: right; }
.cc__arrow { color: var(--text-tertiary); font-size: var(--font-size-xs); margin-left: 4px; }
.cc { display: flex; flex-direction: column; gap: 4px; }
.cc__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.cc__time { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.cc__remove { font-size: var(--font-size-sm); color: var(--danger-600); background: var(--bg-card); border: 1px solid var(--danger-500); border-radius: var(--radius-md); padding: 4px 12px; line-height: 1.6; }
.cc__remove::after { border: none; }
.cc__form { display: flex; flex-direction: column; }
.cc__row { display: flex; align-items: center; gap: var(--space-3); min-height: 44px; border-bottom: 1px solid var(--border-light); }
.cc__input { flex: 1; font-size: var(--font-size-base); color: var(--text-primary); text-align: right; }
</style>
