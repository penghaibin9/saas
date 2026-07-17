<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="班级材料" subtitle="班会 · 活动 · 总结" show-back />

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="classes.length">
        <view class="card cm__class-row">
          <text class="cm__row-k">选择班级</text>
          <picker class="cm__picker" mode="selector" :range="classLabels" :value="classIndex" @change="onClass">
            <view class="cm__pick-val">{{ classLabels[classIndex] || '请选择' }}<text class="cm__arrow">▾</text></view>
          </picker>
        </view>

        <view class="section-head">
          <text class="section-head__title">材料列表</text>
          <text class="section-head__more" @click="showAdd = !showAdd">{{ showAdd ? '收起' : '+ 新增' }}</text>
        </view>

        <!-- 新增表单 -->
        <template v-if="showAdd">
          <view class="card cm__form">
            <view class="cm__row">
              <text class="cm__row-k">类型</text>
              <picker class="cm__picker" mode="selector" :range="typeLabels" :value="typeIndex" @change="(e) => typeIndex = Number(e.detail.value)">
                <view class="cm__pick-val">{{ typeLabels[typeIndex] }}<text class="cm__arrow">▾</text></view>
              </picker>
            </view>
            <view class="cm__row"><text class="cm__row-k">标题</text><input class="cm__input" v-model="title" placeholder="必填，如「第10周主题班会」" /></view>
            <view class="cm__row"><text class="cm__row-k">日期</text><input class="cm__input" v-model="materialAt" placeholder="可选，如 2026-05-10" /></view>
            <view class="cm__row" style="border-bottom:none; align-items:flex-start;">
              <text class="cm__row-k" style="padding-top:10px;">备注</text>
              <textarea class="cm__textarea" v-model="remark" placeholder="可选，暂不支持附件上传" />
            </view>
          </view>
          <MobileSafeAreaBar>
            <button class="btn btn-ghost flex-1" :disabled="submitting" @click="showAdd = false">取消</button>
            <button class="btn btn-primary flex-1" :disabled="submitting" @click="submitAdd">{{ submitting ? '提交中…' : '确认新增' }}</button>
          </MobileSafeAreaBar>
        </template>

        <MobileGlobalState v-if="!showAdd && !materials.length" state="empty" title="暂无班级材料"
          description="点击「+ 新增」登记班会记录/主题活动/评优材料等。" />
        <view class="stack" v-else-if="!showAdd">
          <view v-for="m in materials" :key="m.id" class="card cm">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ m.title }}</text>
                <text class="cm__sub">{{ m.materialTypeLabel }} · {{ m.materialAt || m.createdAt || '' }}</text>
              </view>
              <button class="cm__void" :disabled="acting" @click="doVoid(m)">作废</button>
            </view>
            <text class="cm__remark" v-if="m.remark">{{ m.remark }}</text>
          </view>
        </view>
      </view>
      <MobileGlobalState v-else state="empty" title="暂无负责班级" description="如信息有误请联系系统管理员核实班级归属。" />
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { toast } from '@/utils/nav'

const TYPES = [
  { key: 'CLASS_MEETING', label: '班会记录' }, { key: 'THEME_ACTIVITY', label: '主题活动' },
  { key: 'EVALUATION', label: '评优材料' }, { key: 'ATTENDANCE', label: '考勤台账' },
  { key: 'SUMMARY', label: '班级总结' }, { key: 'OTHER', label: '其他' }
]

export default {
  data() {
    return {
      state: 'loading', classes: [], classIndex: 0, materials: [], showAdd: false,
      typeIndex: 0, title: '', materialAt: '', remark: '', acting: false, submitting: false
    }
  },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  computed: {
    classLabels() { return this.classes.map((c) => `${c.className}${c.grade ? '（' + c.grade + '级）' : ''}`) },
    typeLabels() { return TYPES.map((t) => t.label) },
    currentClassId() { const c = this.classes[this.classIndex]; return c ? c.classId : null }
  },
  methods: {
    load(done) {
      this.state = 'loading'
      teacherApi.getAffairsMyClasses().then((d) => {
        this.classes = (d && d.list) || []
        this.state = 'ready'
        if (this.classes.length) return this.loadMaterials()
      }).catch(() => { this.state = 'error' }).finally(() => { if (done) done() })
    },
    onClass(e) { this.classIndex = Number(e.detail.value); this.showAdd = false; this.loadMaterials() },
    loadMaterials() {
      if (!this.currentClassId) return
      teacherApi.getAffairsClassMaterials(this.currentClassId).then((d) => {
        this.materials = (d && d.list) || []
      }).catch(() => { this.materials = [] })
    },
    submitAdd() {
      if (this.submitting) return
      const title = this.title.trim()
      if (!title) { toast('请填写标题'); return }
      this.submitting = true
      teacherApi.addAffairsClassMaterial(this.currentClassId, {
        materialType: TYPES[this.typeIndex].key, title,
        materialAt: this.materialAt.trim() || null, remark: this.remark.trim() || null
      }).then(() => {
        toast('已新增')
        this.showAdd = false; this.title = ''; this.materialAt = ''; this.remark = ''; this.typeIndex = 0
        this.loadMaterials()
      }).catch((e) => toast((e && e.message) || '新增失败，请重试'))
        .finally(() => { this.submitting = false })
    },
    doVoid(m) {
      if (this.acting) return
      uni.showModal({
        title: '作废材料', content: `确认作废「${m.title}」？`,
        editable: true, placeholderText: '可填写作废原因（可选）',
        success: (r) => {
          if (!r.confirm) return
          this.acting = true
          teacherApi.voidAffairsClassMaterial(m.id, r.content || '')
            .then(() => { toast('已作废'); this.loadMaterials() })
            .catch((e) => toast((e && e.message) || '操作失败，请重试'))
            .finally(() => { this.acting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
.cm__class-row { display: flex; align-items: center; gap: var(--space-3); }
.cm__row-k { font-size: var(--font-size-sm); color: var(--text-tertiary); flex-shrink: 0; width: 56px; }
.cm__picker { flex: 1; }
.cm__pick-val { font-size: var(--font-size-base); color: var(--text-primary); text-align: right; }
.cm__arrow { color: var(--text-tertiary); font-size: var(--font-size-xs); margin-left: 4px; }
.cm { display: flex; flex-direction: column; gap: 4px; }
.cm__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.cm__remark { font-size: var(--font-size-sm); color: var(--text-secondary); }
.cm__void { font-size: var(--font-size-sm); color: var(--danger-600); background: var(--bg-card); border: 1px solid var(--danger-500); border-radius: var(--radius-md); padding: 4px 12px; line-height: 1.6; }
.cm__void::after { border: none; }
.cm__form { display: flex; flex-direction: column; }
.cm__row { display: flex; align-items: center; gap: var(--space-3); min-height: 44px; border-bottom: 1px solid var(--border-light); }
.cm__input { flex: 1; font-size: var(--font-size-base); color: var(--text-primary); text-align: right; }
.cm__textarea { flex: 1; min-height: 64px; font-size: var(--font-size-base); color: var(--text-primary); padding: 10px 0; }
</style>
