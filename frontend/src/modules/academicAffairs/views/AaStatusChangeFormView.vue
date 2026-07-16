<template>
  <ModulePageShell
    title="发起学籍异动"
    subtitle="提交后进入多节点审批，终审通过才写入学籍主档"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn" @click="goBack">返回列表</button>
    </template>

    <AppSectionCard title="异动信息">
      <div class="aa-form">
        <div class="aa-form__row">
          <label class="aa-form__label required">学生</label>
          <div class="aa-form__field">
            <div v-if="form.studentId" class="aa-picked">
              {{ form.name || '学生' }} · ID {{ form.studentId }}
              <button class="mp-link" @click="clearStudent">重选</button>
            </div>
            <div v-else class="aa-reg-search">
              <input v-model.trim="kw" class="aa-input aa-input--grow" placeholder="按姓名/学号检索学生" @keyup.enter="searchStudents" />
              <button class="mp-btn" :disabled="searching" @click="searchStudents">检索</button>
            </div>
            <ul v-if="!form.studentId && candidates.length" class="aa-cand-list">
              <li v-for="s in candidates" :key="s.studentId" class="aa-cand-item">
                <span>{{ s.realName }} · 学号 {{ s.studentNo }} · {{ s.studentStatus }}</span>
                <button class="mp-link" @click="pickStudent(s)">选择</button>
              </li>
            </ul>
          </div>
        </div>

        <div class="aa-form__row">
          <label class="aa-form__label required">异动类型</label>
          <div class="aa-form__field">
            <select v-if="!lockedType" v-model="form.changeType" class="aa-input">
              <option v-for="(label, val) in TYPE_LABEL" :key="val" :value="val">{{ label }}</option>
            </select>
            <div v-else class="aa-picked">{{ TYPE_LABEL[form.changeType] || form.changeType }}</div>
            <div class="aa-form__hint">{{ typeHint }}</div>
          </div>
        </div>

        <template v-if="form.changeType === 'TRANSFER_MAJOR'">
          <div class="aa-form__row">
            <label class="aa-form__label">转入学院ID</label>
            <div class="aa-form__field"><input v-model.trim="form.toCollegeId" class="aa-input aa-input--num" placeholder="目标学院ID" /></div>
          </div>
          <div class="aa-form__row">
            <label class="aa-form__label">转入专业ID</label>
            <div class="aa-form__field"><input v-model.trim="form.toMajorId" class="aa-input aa-input--num" placeholder="目标专业ID" /></div>
          </div>
          <div class="aa-form__row">
            <label class="aa-form__label">转入班级ID</label>
            <div class="aa-form__field">
              <input v-model.trim="form.toClassId" class="aa-input aa-input--num" placeholder="目标班级ID（选填）" />
              <div class="aa-form__hint">组织选择器待 R3「学院专业班级」上线后接入，当前先填目标 ID。</div>
            </div>
          </div>
        </template>

        <template v-if="form.changeType === 'TRANSFER_CLASS'">
          <div class="aa-form__row" v-if="form.studentId">
            <label class="aa-form__label">当前专业/班级</label>
            <div class="aa-form__field aa-form__hint">{{ form.studentMajorName || '（读取中…）' }} · {{ form.currentClassName || '未编班' }}</div>
          </div>
          <div class="aa-form__row">
            <label class="aa-form__label required">转入班级</label>
            <div class="aa-form__field">
              <select v-model="form.toClassId" class="aa-input" :disabled="!form.studentId || loadingClasses">
                <option value="">{{ classSelectPlaceholder }}</option>
                <option v-for="c in targetClassOptions" :key="c.id" :value="c.id">{{ c.className }}（{{ c.grade || '—' }}）</option>
              </select>
              <div class="aa-form__hint">仅同专业在读班级可选，跨专业请改用「转专业申请」；已在班级不出现在候选内。</div>
            </div>
          </div>
        </template>

        <div class="aa-form__row">
          <label class="aa-form__label">申请原因</label>
          <div class="aa-form__field">
            <textarea ref="reasonInput" v-model.trim="form.reason" class="aa-textarea" rows="3" maxlength="500" placeholder="选填，便于审批参考"></textarea>
            <!-- 仅当该异动类型有专属词条时才展示；否则分组未命中会回落显示全部类型的词条（如转班表单弹出休学词条） -->
            <AppQuickPhrases v-if="reasonPhraseScene" :scene-key="reasonPhraseScene" :group="form.changeType" @pick="onPickReason" />
          </div>
        </div>
      </div>

      <div class="aa-form__actions">
        <button class="mp-btn" @click="goBack">取消</button>
        <button class="mp-btn mp-btn--primary" :disabled="submitting || !form.studentId" @click="submit">
          {{ submitting ? '提交中…' : '提交异动' }}
        </button>
      </div>
    </AppSectionCard>
  </ModulePageShell>
</template>

<script>
/** 发起学籍异动（/admin/academic-affairs/status-changes/new）：POST /academic-affairs/status-changes。
 *  支持 ?type=SUSPEND|RESUME|WITHDRAW|TRANSFER_MAJOR|TRANSFER_CLASS|RETAIN 预设并锁定异动类型
 *  （供休学/复学/退学/转专业/转班/留级(保留学籍) 六个分类申请入口跳转带入，锁定后类型下拉隐藏，
 *  仅显示只读标签，业务逻辑与通用入口完全一致）。
 *  TRANSFER_CLASS（转班）目标班选择器：选定学生后拉取其当前专业（GET /roster/{id}），
 *  再按该专业过滤班级候选（GET /orgs/classes?majorId=），跨专业一致性由后端 submit() 强制复核。 */
import { ModulePageShell } from '@/components/business'
import { AppSectionCard, AppQuickPhrases } from '@/components/common'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { hasGroupPhrases } from '@/utils/quickPhrases'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { TYPE_LABEL, TYPE_PATH_SEGMENT } from '@/modules/academicAffairs/constants/status-change'
import { toast } from '@/utils/toast'

const TYPE_HINT = {
  SUSPEND: '仅在籍学生可休学；到期日按规则中心最长年限自动计算。',
  WITHDRAW: '退学为终态，终审生效后不可再发起其它异动。',
  RESUME: '仅休学中的学生可复学；休学超最长年限不可复学。',
  RETAIN: '留级（保留学籍）：仅在籍学生可发起，按学业成绩条件命中的留级认定处理。',
  TRANSFER_MAJOR: '转专业：需填目标院系，终审生效后同步迁移主档院系班。',
  TRANSFER_CLASS: '转班：仅限同专业换班，学院/专业不变；终审生效后同步迁移主档班级。'
}

export default {
  name: 'AaStatusChangeFormView',
  components: { ModulePageShell, AppSectionCard, AppQuickPhrases },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      TYPE_LABEL,
      submitting: false,
      kw: '',
      searching: false,
      candidates: [],
      loadingClasses: false,
      targetClassOptions: [],
      form: {
        studentId: this.$route.query.studentId || '',
        name: this.$route.query.name || '',
        changeType: (this.$route.query.type && TYPE_LABEL[this.$route.query.type]) ? this.$route.query.type : 'SUSPEND',
        reason: '',
        toCollegeId: '',
        toMajorId: '',
        toClassId: '',
        studentMajorId: '',
        studentMajorName: '',
        currentClassId: '',
        currentClassName: ''
      }
    }
  },
  computed: {
    lockedType() {
      return !!(this.$route.query.type && TYPE_LABEL[this.$route.query.type])
    },
    typeHint() {
      return TYPE_HINT[this.form.changeType] || ''
    },
    /** 该异动类型有专属词条才给 sceneKey；无专属词条（如转班/留级）返回空 → 不展示 chips */
    reasonPhraseScene() {
      return hasGroupPhrases('aa.statuschg.reason', this.form.changeType) ? 'aa.statuschg.reason' : ''
    },
    classSelectPlaceholder() {
      if (!this.form.studentId) return '请先选择学生'
      if (this.loadingClasses) return '加载班级中…'
      if (!this.targetClassOptions.length) return '该专业下暂无其它可选班级'
      return '请选择目标班级'
    }
  },
  watch: {
    'form.changeType'(val) {
      if (val === 'TRANSFER_CLASS' && this.form.studentId) this.loadStudentOrgInfo()
    }
  },
  created() {
    if (this.form.changeType === 'TRANSFER_CLASS' && this.form.studentId) this.loadStudentOrgInfo()
  },
  methods: {
    onPickReason(text) {
      const el = this.$refs.reasonInput
      const { value, selStart, selEnd } = insertAtCursor(el, this.form.reason, text)
      this.form.reason = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    goBack() {
      const seg = this.lockedType && TYPE_PATH_SEGMENT[this.form.changeType]
      this.$router.push(seg ? `/admin/academic-affairs/status-changes/${seg}` : '/admin/academic-affairs/status-changes')
    },
    clearStudent() {
      this.form.studentId = ''
      this.form.name = ''
      this.form.studentMajorId = ''
      this.form.studentMajorName = ''
      this.form.currentClassId = ''
      this.form.currentClassName = ''
      this.form.toClassId = ''
      this.targetClassOptions = []
    },
    pickStudent(s) {
      this.form.studentId = s.studentId
      this.form.name = s.realName
      this.candidates = []
      if (this.form.changeType === 'TRANSFER_CLASS') this.loadStudentOrgInfo()
    },
    async searchStudents() {
      if (this.searching) return
      this.searching = true
      const res = await academicAffairsApi.getRoster({ keyword: this.kw || undefined, page: 1, pageSize: 20 })
      this.candidates = res.code === 0 ? res.data.list : []
      this.searching = false
    },
    /** 转班专用：拉取学生当前专业/班级，再按专业过滤目标班候选（不含学生当前班）。 */
    async loadStudentOrgInfo() {
      this.form.toClassId = ''
      this.targetClassOptions = []
      if (!this.form.studentId) return
      const res = await academicAffairsApi.getRosterDetail(this.form.studentId)
      if (res.code !== 0) {
        toast.error(res.message || '读取学生专业信息失败')
        return
      }
      this.form.studentMajorId = res.data.majorId || ''
      this.form.studentMajorName = res.data.majorName || '（未编专业）'
      this.form.currentClassId = res.data.classId || ''
      this.form.currentClassName = res.data.className || '未编班'
      await this.loadTargetClasses()
    },
    async loadTargetClasses() {
      if (!this.form.studentMajorId) return
      this.loadingClasses = true
      const res = await academicAffairsApi.listClasses({ majorId: this.form.studentMajorId, classStatus: 'NORMAL', pageSize: 100 })
      this.targetClassOptions = res.code === 0
        ? res.data.list.filter((c) => String(c.id) !== String(this.form.currentClassId))
        : []
      this.loadingClasses = false
    },
    async submit() {
      if (this.submitting || !this.form.studentId) return
      if (this.form.changeType === 'TRANSFER_CLASS' && !this.form.toClassId) {
        toast.error('请先选择转班目标班级')
        return
      }
      this.submitting = true
      const body = {
        studentId: this.form.studentId,
        changeType: this.form.changeType,
        reason: this.form.reason || '',
        toCollegeId: this.form.changeType === 'TRANSFER_MAJOR' ? (this.form.toCollegeId || undefined) : undefined,
        toMajorId: this.form.changeType === 'TRANSFER_MAJOR' ? (this.form.toMajorId || undefined) : undefined,
        toClassId: (this.form.changeType === 'TRANSFER_MAJOR' || this.form.changeType === 'TRANSFER_CLASS') ? (this.form.toClassId || undefined) : undefined
      }
      const res = await academicAffairsApi.submitStatusChange(body)
      this.submitting = false
      if (res.code === 0) {
        toast.success('异动已提交，进入审批流程')
        this.$router.push(`/admin/academic-affairs/status-changes/${res.data.changeId}`)
      } else {
        toast.error(res.message || '提交失败')
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-form { display: flex; flex-direction: column; gap: 16px; max-width: 680px; }
.aa-form__row { display: flex; align-items: flex-start; gap: 16px; }
.aa-form__label { width: 96px; flex-shrink: 0; padding-top: 8px; font-size: 13px; color: var(--text-700, #4e5969); text-align: right; }
.aa-form__label.required::before { content: '*'; color: var(--danger-600, #f53f3f); margin-right: 4px; }
.aa-form__field { flex: 1; }
.aa-input, .aa-textarea { width: 100%; padding: 8px 12px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 14px; box-sizing: border-box; }
.aa-input { height: 34px; padding: 0 12px; }
.aa-input--num { width: 220px; }
.aa-input--grow { flex: 1; }
.aa-reg-search { display: flex; gap: 10px; }
.aa-picked { display: flex; align-items: center; gap: 12px; font-size: 14px; color: var(--text-900, #1f2329); }
.aa-cand-list { list-style: none; margin: 10px 0 0; padding: 0; border: 1px solid var(--border-100, #f0f1f2); border-radius: 6px; }
.aa-cand-item { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; border-bottom: 1px solid var(--border-100, #f0f1f2); font-size: 13px; }
.aa-cand-item:last-child { border-bottom: none; }
.aa-form__hint { margin-top: 4px; font-size: 12px; color: var(--text-400, #8a9099); }
.aa-form__actions { margin-top: 24px; display: flex; gap: 12px; padding-left: 112px; }
</style>
