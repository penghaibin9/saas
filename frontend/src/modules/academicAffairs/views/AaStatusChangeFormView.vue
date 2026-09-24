<template>
  <ModulePageShell
    :title="applicationTitle"
    subtitle="先看清当前与目标，再选择生效方式；提交后查询审批和生效结果"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    show-subtitle-in-concise
  >
    <template #actions>
      <AppButton :disabled="submitting || !!pending" @click="goBack">返回列表</AppButton>
      <AppButton variant="primary" :disabled="!canSubmit" :loading="submitting" @click="askSubmit">提交异动申请</AppButton>
    </template>

    <ol class="aa-apply-progress" aria-label="学籍异动办理顺序">
      <li v-for="(step,index) in ['发起申请','岗位审核','终审决定','按期生效','档案回写']" :key="step" :class="{ 'is-current': index === 0 }"><span>{{ index + 1 }}</span><div><strong>{{ step }}</strong><small>{{ ['当前设计视角','按责任状态解锁','按真实状态解锁','按真实状态解锁','按真实状态解锁'][index] }}</small></div></li>
    </ol>
    <div class="aa-apply-layout"><AppSectionCard title="学籍异动申请 · 完整表单">
      <p v-if="error" class="aa-form-error" role="alert">{{ error }}</p><section v-if="receipt" class="aa-form-receipt" role="status"><b>{{ receipt.verified ? '已核对正式申请' : '结果待核实' }}</b><p>{{ receipt.label }}</p><AppButton v-if="pending" :disabled="submitting || checking" @click="verify">查询原申请结果</AppButton><template v-else><AppButton @click="goResult">查看申请详情</AppButton><AppButton @click="startNew">另起申请</AppButton></template></section>
      <fieldset class="aa-form" :disabled="submitting || !!pending || confirmVisible || !!receipt?.verified">
        <div class="aa-form__row">
          <label class="aa-form__label required">学生</label>
          <div class="aa-form__field">
            <AppStudentPicker v-model="form.studentId" placeholder="选择发起异动的学生" @change="onStudentChange" />
            <div v-if="loadingStudent" class="aa-form__hint">正在读取当前学籍组织与状态…</div>
          </div>
        </div>

        <div class="aa-form__row">
          <label class="aa-form__label required">异动类型</label>
          <div class="aa-form__field">
            <AppSelect v-if="!lockedType" v-model="form.changeType" :options="changeTypeOptions" placeholder="" />
            <div v-else class="aa-picked">{{ TYPE_LABEL[form.changeType] || form.changeType }}</div>
            <div class="aa-form__hint">{{ typeHint }}</div>
          </div>
        </div>

        <div v-if="form.studentId" class="aa-transition" aria-label="学籍异动前后对照">
          <section class="aa-transition__card">
            <div class="aa-transition__eyebrow">当前</div>
            <strong class="aa-transition__title">{{ form.name || '已选学生' }}</strong>
            <dl class="aa-transition__grid">
              <div><dt>学院</dt><dd>{{ form.currentCollegeName || '—' }}</dd></div>
              <div><dt>专业</dt><dd>{{ form.studentMajorName || '—' }}</dd></div>
              <div><dt>班级</dt><dd>{{ form.currentClassName || '未编班' }}</dd></div>
              <div><dt>状态</dt><dd>{{ form.currentStatusLabel || '—' }}</dd></div>
            </dl>
          </section>
          <div class="aa-transition__arrow" aria-hidden="true">→</div>
          <section class="aa-transition__card aa-transition__card--target">
            <div class="aa-transition__eyebrow">目标</div>
            <strong class="aa-transition__title">{{ TYPE_LABEL[form.changeType] || form.changeType }}</strong>
            <dl class="aa-transition__grid">
              <div><dt>学院</dt><dd>{{ targetCollegeName }}</dd></div>
              <div><dt>专业</dt><dd>{{ targetMajorName }}</dd></div>
              <div><dt>班级</dt><dd>{{ targetClassName }}</dd></div>
              <div><dt>状态</dt><dd>{{ targetStatusLabel }}</dd></div>
            </dl>
          </section>
        </div>

        <template v-if="form.changeType === 'TRANSFER_MAJOR'">
          <div class="aa-form__row">
            <label class="aa-form__label required">目标组织</label>
            <div class="aa-form__field">
              <AppOrgCascader v-model="targetOrg" @change="onTargetOrgChange" />
              <div class="aa-form__hint">按学院 → 专业 → 班级逐级选择；专业必选，班级可由教务后续编排。</div>
            </div>
          </div>
        </template>

        <template v-if="form.changeType === 'TRANSFER_CLASS'">
          <div class="aa-form__row">
            <label class="aa-form__label required">转入班级</label>
            <div class="aa-form__field">
              <AppClassPicker
                v-model="form.toClassId"
                :options="targetClassPickerOptions"
                :placeholder="classSelectPlaceholder"
                :disabled="!form.studentId || loadingClasses"
              />
              <button v-if="classPage*20<classTotal" :disabled="loadingClasses" @click="loadTargetClasses(true)">加载更多班级</button>
              <div class="aa-form__hint">仅同专业在读班级可选，跨专业请改用「转专业申请」；当前班级不会出现在候选内。</div>
            </div>
          </div>
        </template>

        <div class="aa-form__row">
          <label class="aa-form__label required">生效方式</label>
          <div class="aa-form__field">
            <div class="aa-radio-group">
              <label class="aa-radio">
                <input v-model="form.effectiveMode" type="radio" value="IMMEDIATE" />
                <span><strong>终审通过立即生效</strong><small>沿用现有正式异动入口</small></span>
              </label>
              <label class="aa-radio">
                <input v-model="form.effectiveMode" type="radio" value="SCHEDULED" />
                <span><strong>指定日期</strong><small>终审通过后等待计划时间，再核对正式生效结果</small></span>
              </label>
            </div>
            <div v-if="form.effectiveMode === 'SCHEDULED'" class="aa-effective-date">
              <input v-model="form.effectiveDate" class="aa-input" type="datetime-local" :min="minEffectiveDate" />
              <div class="aa-form__hint">必须晚于当前时间；到期前学生主档状态不会被提前改写。</div>
            </div>
          </div>
        </div>

        <div class="aa-form__row">
          <label class="aa-form__label">申请原因</label>
          <div class="aa-form__field">
            <textarea ref="reasonInput" v-model.trim="form.reason" class="aa-textarea" rows="3" maxlength="500" placeholder="选填，便于审批参考"></textarea>
            <AppQuickPhrases v-if="reasonPhraseScene" :scene-key="reasonPhraseScene" :group="form.changeType" @pick="onPickReason" />
          </div>
        </div>

        <div class="aa-form__row">
          <label class="aa-form__label">申请材料</label>
          <div class="aa-form__field">
            <FileUploader
              :key="identity + ':' + fileSeq"
              biz-type="AA_STATUS_CHANGE"
              :disabled="!form.studentId || submitting || materialUploadBusy || materialFiles.length >= 10"
              button-text="上传材料"
              @progress="onMaterialProgress"
              @uploaded="onMaterialUploaded"
              @error="onMaterialUploadError"
              @cancelled="onMaterialUploadCancelled"
            />
            <div class="aa-form__hint">最多 10 份。上传先进入私有隔离区；安全检查通过且异动提交成功后，才能成为正式申请材料。</div>
            <div v-if="materialFiles.length" class="aa-materials">
              <div v-for="file in materialFiles" :key="file.fileId" class="aa-material">
                <div class="aa-material__meta">
                  <strong>{{ file.fileName || '申请材料' }}</strong>
                  <span :class="['aa-material__status', { 'is-ready': file.readyForBusiness }]">
                    {{ file.readyForBusiness ? '安全可用' : '安全状态待核对' }}
                  </span>
                </div>
                <div class="aa-material__actions">
                  <button v-if="!file.readyForBusiness" type="button" @click="refreshMaterial(file.fileId)">刷新状态</button>
                  <button type="button" @click="removeMaterial(file.fileId)">移除</button>
                </div>
              </div>
            </div>
            <div v-if="materialUploadBusy" class="aa-form__hint aa-form__hint--warn">材料仍在上传，完成前不能提交异动。</div>
            <div v-else-if="hasPendingMaterial" class="aa-form__hint aa-form__hint--warn">存在尚未安全可用的材料，请刷新状态或移除后再提交。</div>
          </div>
        </div>
      </fieldset>

      <div class="aa-form__actions">
        <AppButton :disabled="submitting || !!pending" @click="goBack">取消</AppButton>
        <AppButton variant="primary" :disabled="!canSubmit" :loading="submitting" @click="askSubmit">
          {{ form.effectiveMode === 'SCHEDULED' ? '提交计划生效异动' : '提交异动' }}
        </AppButton>
      </div>
    </AppSectionCard><aside class="aa-conditions"><h3>启动条件</h3><dl><div><dt>来源学生</dt><dd>{{ factsReady ? '当前学籍已读取' : '待选择并读取' }}</dd></div><div><dt>当前岗位</dt><dd>{{ canApply ? '有申请权限，范围由服务器核对' : '无申请权限' }}</dd></div><div><dt>申请材料</dt><dd>{{ materialUploadBusy ? '正在上传或核对' : hasPendingMaterial ? '有材料尚未安全可用' : materialFiles.length ? '已附材料，提交前再次核对' : '未附材料（选填）' }}</dd></div><div><dt>审批与生效</dt><dd>提交后进入正式审批；终审结果与实际生效分开核对。</dd></div></dl><h3>后续办理</h3><p>发起申请 → 当前审批节点 → 终审决定 → 正式生效与档案回写</p><p>回读受理记录后，可进入申请详情查询材料和办理结果。</p></aside></div>
    <AppConfirmDialog v-model:visible="confirmVisible" title="确认提交学籍异动申请" confirm-text="确认提交申请" :message="confirmMessage" :submitting="submitting" @confirm="submit" />
  </ModulePageShell>
</template>

<script>
/** D3-U 学籍异动便利性工作台。
 * 当前事实只读 roster detail；提交统一进入 convenience wrapper，wrapper 内部仍调用 canonical submit；
 * effectiveDate 由既有 temporal guard 处理，materialFileIds 只通过同事务 FileBinding 落正式证据。 */
import { ModulePageShell } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppQuickPhrases, AppSelect, AppStudentPicker, AppClassPicker, AppOrgCascader } from '@/components/common'
import {currentUserFromToken} from '@/services/http/client'
import {matchPermission} from '@/config/navPlan'
import {gradeError} from './parallel-c/grade-review'
import {rememberStatusChangeRecovery,getStatusChangeRecovery,clearStatusChangeRecovery} from './parallel-c/status-change-recovery'
import {ACADEMIC_STUDENT_STATUS_LABELS} from '../config/academicStudentLabels'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { hasGroupPhrases } from '@/utils/quickPhrases'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { statusChangeConvenienceApi } from '@/modules/academicAffairs/api/status-change-convenience.api'
import { TYPE_LABEL, TYPE_PATH_SEGMENT } from '@/modules/academicAffairs/constants/status-change'
import { fileSdk } from '@/services/file/fileSdk'
import FileUploader from '@/components/file/FileUploader.vue'


const TYPE_HINT = {
  SUSPEND: '仅在籍学生可休学；到期日按规则中心最长年限自动计算。休学≠保留学籍。',
  PRESERVE: '保留学籍：人离校、学籍保留（如应征入伍/联合培养），离校后可按学校要求申请复学。',
  WITHDRAW: '退学为终态，终审生效后不可再发起其它异动。',
  RESUME: '仅休学中或保留学籍中的学生可复学；休学超最长年限不可复学。',
  RETAIN: '留级：降级继续修读，与「保留学籍」不是同一业务。',
  TRANSFER_MAJOR: '转专业：必须选择目标专业，终审生效后同步迁移主档院系班。',
  TRANSFER_CLASS: '转班：仅限同专业换班，学院/专业不变；终审生效后同步迁移主档班级。'
}

const TARGET_STATUS = {
  SUSPEND: ['SUSPENDED', '休学'],
  PRESERVE: ['PRESERVED', '保留学籍'],
  WITHDRAW: ['WITHDRAWN', '退学'],
  RESUME: ['REGISTERED', '在籍'],
  RETAIN: ['RETAINED', '留级'],
  TRANSFER_MAJOR: ['REGISTERED', '在籍'],
  TRANSFER_CLASS: ['REGISTERED', '在籍']
}

function toLocalInputMin() {
  const d = new Date(Date.now() + 60 * 1000)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function newIdempotencyKey() {
  if (globalThis.crypto?.randomUUID) return `aa-sc-${globalThis.crypto.randomUUID()}`
  return `aa-sc-${Date.now()}-${Math.random().toString(16).slice(2)}-${Math.random().toString(16).slice(2)}`
}

function exactId(value) {
  if (typeof value === 'number') return Number.isSafeInteger(value) ? String(value) : ''
  return typeof value === 'string' && value.trim() ? value : ''
}

export default {
  name: 'AaStatusChangeFormView',
  components: { ModulePageShell, AppButton, AppSectionCard, AppQuickPhrases, AppSelect, AppStudentPicker, AppClassPicker, AppOrgCascader, AppConfirmDialog, FileUploader },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      TYPE_LABEL,
      alive:true,scope:0,studentSeq:0,classSeq:0,fileSeq:0,uploadTask:null,factsReady:false,error:'',pending:null,receipt:null,checking:false,command:null,confirmVisible:false,classPage:1,classTotal:0,
      submitting: false,
      loadingStudent: false,
      loadingClasses: false,
      materialUploadBusy: false,
      targetClassOptions: [],
      targetOrg: [],
      targetOrgItems: [],
      materialFiles: [],
      idempotencyKey: newIdempotencyKey(),
      form: {
        studentId: this.$route.query.studentId || '',
        name: this.$route.query.name || '',
        changeType: (this.$route.query.type && TYPE_LABEL[this.$route.query.type]) ? this.$route.query.type : 'SUSPEND',
        reason: '',
        effectiveMode: 'IMMEDIATE',
        effectiveDate: '',
        toCollegeId: '',
        toMajorId: '',
        toClassId: '',
        currentCollegeId: '',
        currentCollegeName: '',
        studentMajorId: '',
        studentMajorName: '',
        currentClassId: '',
        currentClassName: '',
        currentStatus: '',
        studentVersion: null,
        currentStatusLabel: ''
      }
    }
  },
  computed: {
    identity(){const u=currentUserFromToken()||{};return JSON.stringify([u.tenantId,u.userId,u.activeContextId,u.currentRoleCode,this.ctx.currentRole,this.ctx.dataScope,this.ctx.permissionPatterns])},
    canApply(){return matchPermission(this.ctx.permissionPatterns||[],'academicAffairs.statusChange.apply')},
    applicationTitle(){return this.lockedType?(TYPE_LABEL[this.form.changeType]||'发起异动'):'发起异动'},
    confirmMessage(){return this.command?`${this.command.form.name} · ${TYPE_LABEL[this.command.body.changeType]}。${this.command.body.effectiveDate?'计划日期：'+this.command.form.effectiveDate:'终审后按正式流程生效'}。当前学籍不会因提交申请立即改变。`:''},
    lockedType() {
      return !!(this.$route.query.type && TYPE_LABEL[this.$route.query.type])
    },
    typeHint() {
      return TYPE_HINT[this.form.changeType] || ''
    },
    changeTypeOptions() {
      return Object.entries(TYPE_LABEL).map(([value, label]) => ({ value, label }))
    },
    reasonPhraseScene() {
      return hasGroupPhrases('aa.statuschg.reason', this.form.changeType) ? 'aa.statuschg.reason' : ''
    },
    classSelectPlaceholder() {
      if (!this.form.studentId) return '请先选择学生'
      if (this.loadingClasses) return '加载班级中…'
      if (!this.targetClassOptions.length) return '该专业下暂无其它可选班级'
      return '请选择目标班级'
    },
    targetClassPickerOptions() {
      return this.targetClassOptions.map((c) => ({ value: c.id, label: `${c.className}（${c.grade || '—'}）`, raw: c }))
    },
    targetStatusLabel() {
      return TARGET_STATUS[this.form.changeType]?.[1] || '—'
    },
    targetCollegeName() {
      if (this.form.changeType === 'TRANSFER_MAJOR') return this.targetOrgItems[0]?.label || '请选择目标学院'
      return this.form.currentCollegeName || '—'
    },
    targetMajorName() {
      if (this.form.changeType === 'TRANSFER_MAJOR') return this.targetOrgItems[1]?.label || '请选择目标专业'
      return this.form.studentMajorName || '—'
    },
    targetClassName() {
      if (this.form.changeType === 'TRANSFER_MAJOR') return this.targetOrgItems[2]?.label || '待教务编班'
      if (this.form.changeType === 'TRANSFER_CLASS') {
        const found = this.targetClassOptions.find((c) => String(c.id) === String(this.form.toClassId))
        return found?.className || '请选择目标班级'
      }
      return this.form.currentClassName || '未编班'
    },
    minEffectiveDate() {
      return toLocalInputMin()
    },
    hasPendingMaterial() {
      return this.materialFiles.some((item) => !item.readyForBusiness)
    },
    canSubmit() {
      if (!this.canApply || this.submitting || this.pending || this.receipt?.verified || !this.factsReady || !this.form.studentId || this.loadingStudent || this.loadingClasses || this.materialUploadBusy || this.hasPendingMaterial) return false
      if (!Number.isSafeInteger(this.form.studentVersion) || this.form.studentVersion < 0) return false
      if([this.form.studentId,this.form.toCollegeId,this.form.toMajorId,this.form.toClassId].some(v=>typeof v==='number'&&!Number.isSafeInteger(v)))return false
      if (this.form.changeType === 'TRANSFER_CLASS' && !this.form.toClassId) return false
      if (this.form.changeType === 'TRANSFER_MAJOR' && !this.form.toMajorId) return false
      if (this.form.effectiveMode === 'SCHEDULED' && !this.form.effectiveDate) return false
      return true
    }
  },
  watch: {
    identity(){this.invalidate();this.form.studentId='';this.form.name='';this.form.reason='';this.resetCurrentStudentFacts()},
    '$route.query'(){this.invalidate();this.form.studentId=String(this.$route.query.studentId||'');this.form.name='';this.form.reason='';this.form.changeType=TYPE_LABEL[this.$route.query.type]?this.$route.query.type:'SUSPEND';this.resetCurrentStudentFacts();if(this.form.studentId)this.loadStudentOrgInfo()},
    'form.changeType'(val) {
      this.invalidate();
      this.form.toCollegeId = ''
      this.form.toMajorId = ''
      this.form.toClassId = ''
      this.targetOrg = []
      this.targetOrgItems = []
      this.targetClassOptions = []
      if(this.form.studentId&&!this.factsReady)this.loadStudentOrgInfo()
      else if (val === 'TRANSFER_CLASS' && this.form.studentId && this.form.studentMajorId) this.loadTargetClasses()
    }
  },
  created() {
    if (this.form.studentId) this.loadStudentOrgInfo()
  },
  beforeUnmount(){this.alive=false;this.invalidate()},
  methods: {
    capture(){return {scope:this.scope,identity:this.identity,studentId:String(this.form.studentId)}},
    current(c){return this.alive&&c.scope===this.scope&&c.identity===this.identity&&c.studentId===String(this.form.studentId)},
    invalidate(){this.scope++;this.studentSeq++;this.classSeq++;this.fileSeq++;this.uploadTask?.cancel?.();this.uploadTask=null;this.materialFiles=[];this.materialUploadBusy=false;this.loadingStudent=false;this.loadingClasses=false;this.submitting=false;this.checking=false;this.pending=null;this.receipt=null;this.command=null;this.confirmVisible=false;this.error='';this.idempotencyKey=newIdempotencyKey()},
    fail(err,fallback){if(/403|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN/.test([err?.code,err?.bizCode].join(' '))){this.invalidate();this.form.studentId='';this.form.name='';this.form.reason='';this.targetOrg=[];this.targetOrgItems=[];this.resetCurrentStudentFacts()}this.error=gradeError(err,fallback)},
    onStudentChange(_value, items) {
      this.invalidate();this.form.reason='';this.form.effectiveDate='';this.form.toCollegeId='';this.form.toMajorId='';this.targetOrg=[];this.targetOrgItems=[];
      const selected = items?.[0]
      this.form.name = selected?.raw?.realName || selected?.label || ''
      this.materialFiles = []
      this.resetCurrentStudentFacts()
      if (this.form.studentId) this.loadStudentOrgInfo()
    },
    resetCurrentStudentFacts() {
      this.factsReady=false;this.classSeq++;this.loadingClasses=false;this.form.toCollegeId='';this.form.toMajorId='';
      this.form.currentCollegeId = ''
      this.form.currentCollegeName = ''
      this.form.studentMajorId = ''
      this.form.studentMajorName = ''
      this.form.currentClassId = ''
      this.form.currentClassName = ''
      this.form.currentStatus = ''
      this.form.studentVersion = null
      this.form.currentStatusLabel = ''
      this.form.toClassId = ''
      this.targetClassOptions = []
    },
    onTargetOrgChange(values, items) {
      this.fileSeq++;this.uploadTask?.cancel?.();this.uploadTask=null;this.materialUploadBusy=false;this.materialFiles=[];
      this.targetOrgItems = items || []
      this.form.toCollegeId = values?.[0] || ''
      this.form.toMajorId = values?.[1] || ''
      this.form.toClassId = values?.[2] || ''
    },
    onPickReason(text) {
      const el = this.$refs.reasonInput
      const { value, selStart, selEnd } = insertAtCursor(el, this.form.reason, text)
      this.form.reason = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    onMaterialProgress(){this.materialUploadBusy=true;this.error=''},
    async onMaterialUploaded(uploaded){
      const c=this.capture(),seq=this.fileSeq;const valid=()=>this.current(c)&&seq===this.fileSeq
      try{const fileId=exactId(uploaded?.fileId);if(!fileId)throw {code:503};const meta=await fileSdk.metadata(fileId);if(!valid())return;if(!this.materialFiles.some(file=>String(file.fileId)===fileId))this.materialFiles.push({...meta,fileId,fileName:meta.fileName||uploaded.fileName||'申请材料'})}
      catch(err){if(valid())this.fail(err,'材料安全状态读取失败，请重试。')}finally{if(valid())this.materialUploadBusy=false}
    },
    onMaterialUploadError(err){this.materialUploadBusy=false;this.fail(err,'材料上传失败，请重试。')},
    onMaterialUploadCancelled(){this.materialUploadBusy=false},
    async pickMaterial(event){
      const file=event.target.files?.[0];event.target.value='';if(!file||this.materialUploadBusy||this.submitting||this.pending||!this.form.studentId||this.materialFiles.length>=10)return
      const c=this.capture(),seq=++this.fileSeq;const valid=()=>this.current(c)&&seq===this.fileSeq;this.materialUploadBusy=true;this.error=''
      try{this.uploadTask=fileSdk.upload(file,{bizType:'AA_STATUS_CHANGE'});const uploaded=await this.uploadTask.promise;if(!valid())return;if(!exactId(uploaded.fileId))throw {code:503};const meta=await fileSdk.metadata(uploaded.fileId);if(!valid())return;this.materialFiles.push({...meta,fileId:String(uploaded.fileId),fileName:meta.fileName||file.name})}
      catch(err){if(valid())this.fail(err,'材料上传失败，请重试。')}finally{if(valid()){this.materialUploadBusy=false;this.uploadTask=null}}
    },
    async refreshMaterial(fileId){if(this.materialUploadBusy||this.submitting||this.pending)return;const c=this.capture(),seq=++this.fileSeq;const valid=()=>this.current(c)&&seq===this.fileSeq;this.materialUploadBusy=true;try{const meta=await fileSdk.metadata(fileId);if(!valid())return;const i=this.materialFiles.findIndex(f=>String(f.fileId)===String(fileId));if(i>=0)this.materialFiles.splice(i,1,{...meta,fileId:String(fileId)})}catch(err){if(valid())this.fail(err,'材料安全状态读取失败，请重试。')}finally{if(valid())this.materialUploadBusy=false}},
    removeMaterial(fileId){if(this.submitting||this.pending)return;this.fileSeq++;this.materialUploadBusy=false;this.materialFiles=this.materialFiles.filter(f=>String(f.fileId)!==String(fileId))},
    goBack(){if(this.submitting||this.pending)return;const seg=this.lockedType&&TYPE_PATH_SEGMENT[this.form.changeType];this.$router.push(seg?`/admin/academic-affairs/status-changes/${seg}`:'/admin/academic-affairs/status-changes')},
    goResult(){if(this.receipt?.verified)this.$router.push(`/admin/academic-affairs/status-changes/${encodeURIComponent(this.receipt.id)}`)},
    startNew(){if(!this.receipt?.verified||!this.form.studentId)return;clearStatusChangeRecovery(this.identity,String(this.form.studentId));this.pending=null;this.receipt=null;this.command=null;this.idempotencyKey=newIdempotencyKey();this.error=''},
    applyStudent(data){this.form.studentVersion=Number.isSafeInteger(data.studentVersion)&&data.studentVersion>=0?data.studentVersion:null;this.form.name=data.realName||'';this.form.currentCollegeId=data.collegeId||'';this.form.currentCollegeName=data.collegeName||'学院未返回';this.form.studentMajorId=data.majorId||'';this.form.studentMajorName=data.majorName||'专业未返回';this.form.currentClassId=data.classId||'';this.form.currentClassName=data.className||'未编班';this.form.currentStatus=data.studentStatus||'';this.form.currentStatusLabel=ACADEMIC_STUDENT_STATUS_LABELS[data.studentStatus]||'状态待核对';this.factsReady=!!this.form.currentStatus&&Number.isSafeInteger(this.form.studentVersion)},
    restoreRecovery(c){const ref=getStatusChangeRecovery(c.identity,c.studentId);if(!ref)return;this.idempotencyKey=ref.idempotencyKey;if(ref.verified&&ref.acceptedChangeId){this.pending=null;this.receipt={verified:true,id:ref.acceptedChangeId,label:'正式申请与材料已核对；提交申请不等于学籍已变更。'};return}this.pending={...c,id:ref.acceptedChangeId||null,recovered:true,lookupPage:ref.lookupPage,body:{studentId:ref.studentId,idempotencyKey:ref.idempotencyKey,changeType:ref.changeType,toMajorId:ref.toMajorId||undefined,toClassId:ref.toClassId||undefined,effectiveDate:ref.effectiveDate||undefined,materialFileIds:[...ref.materialFileIds]}};this.receipt={verified:false,label:'检测到该学生有一笔未核实申请，请查询原申请结果，勿重复提交。'}},
    async loadStudentOrgInfo(){
      if(!this.form.studentId)return;this.resetCurrentStudentFacts();const c=this.capture(),seq=++this.studentSeq;const valid=()=>this.current(c)&&seq===this.studentSeq;this.loadingStudent=true
      try{const res=await academicAffairsApi.getRosterDetail(c.studentId);if(!valid())return;if(res?.code!==0)throw res;if(exactId(res.data?.studentId)!==c.studentId)throw {code:409,message:'学生学籍回包与所选学生不一致'};this.applyStudent(res.data);this.restoreRecovery(c);if(this.form.changeType==='TRANSFER_CLASS')await this.loadTargetClasses()}
      catch(err){if(valid())this.fail(err,'学生学籍读取失败，请重新选择学生。')}finally{if(valid())this.loadingStudent=false}
    },
    async loadTargetClasses(more=false){
      if(this.loadingClasses&&more)return
      if(!more){this.form.toClassId='';this.targetClassOptions=[];this.classPage=1;this.classTotal=0}
      if(!this.form.studentMajorId)return
      const c=this.capture(),seq=++this.classSeq,major=String(this.form.studentMajorId),page=more?this.classPage+1:1
      const valid=()=>this.current(c)&&seq===this.classSeq&&major===String(this.form.studentMajorId)&&this.form.changeType==='TRANSFER_CLASS';this.loadingClasses=true
      try{const res=await academicAffairsApi.listClasses({majorId:major,classStatus:'NORMAL',page,pageSize:20});if(!valid())return;if(res?.code!==0)throw res;this.targetClassOptions=[...this.targetClassOptions,...(res.data?.list||[]).filter(r=>String(r.id)!==String(this.form.currentClassId))];this.classPage=page;this.classTotal=res.data?.total??this.targetClassOptions.length}
      catch(err){if(valid())this.fail(err,'候选班级读取失败，请重试。')}finally{if(valid())this.loadingClasses=false}
    },
    buildBody() {
      const scheduled = this.form.effectiveMode === 'SCHEDULED'
      return {
        studentId: this.form.studentId,
        expectedStudentVersion: this.form.studentVersion,
        changeType: this.form.changeType,
        reason: this.form.reason || '',
        idempotencyKey: this.idempotencyKey,
        effectiveDate: scheduled ? new Date(this.form.effectiveDate).toISOString() : undefined,
        materialFileIds: this.materialFiles.map((item) => String(item.fileId)),
        toCollegeId: this.form.changeType === 'TRANSFER_MAJOR' ? (this.form.toCollegeId || undefined) : undefined,
        toMajorId: this.form.changeType === 'TRANSFER_MAJOR' ? (this.form.toMajorId || undefined) : undefined,
        toClassId: (this.form.changeType === 'TRANSFER_MAJOR' || this.form.changeType === 'TRANSFER_CLASS') ? (this.form.toClassId || undefined) : undefined
      }
    },
    askSubmit(){
      if(!this.canSubmit)return
      if(this.form.effectiveMode==='SCHEDULED'&&(!Number.isFinite(new Date(this.form.effectiveDate).getTime())||new Date(this.form.effectiveDate).getTime()<=Date.now())){this.error='计划生效时间必须晚于当前时间';return}
      this.command={...this.capture(),form:{...this.form},body:this.buildBody()};this.confirmVisible=true;this.error=''
    },
    async submit(){
      const c=this.command;if(!c||!this.current(c)||!this.canSubmit||this.submitting)return
      this.submitting=true;this.error=''
      try{const before=await academicAffairsApi.getRosterDetail(c.studentId);if(!this.current(c))return;if(before?.code!==0)throw before
        if(exactId(before.data?.studentId)!==c.studentId)throw {code:409,message:'学生学籍回包与所选学生不一致'}
        if(before.data?.studentVersion!==c.body.expectedStudentVersion||String(before.data?.studentStatus||'')!==c.form.currentStatus||String(before.data?.collegeId||'')!==String(c.form.currentCollegeId)||String(before.data?.majorId||'')!==String(c.form.studentMajorId)||String(before.data?.classId||'')!==String(c.form.currentClassId)){this.applyStudent(before.data);throw {code:409}}
        for(const id of c.body.materialFileIds){const meta=await fileSdk.metadata(id);if(!this.current(c))return;if(meta.readyForBusiness!==true)throw {code:422}}
        if(!this.current(c))return
        if(JSON.stringify(this.buildBody())!==JSON.stringify(c.body))throw {code:409}
        this.pending=c;this.receipt={verified:false,label:'申请提交结果待核实，请勿重复提交。'};rememberStatusChangeRecovery(c.identity,c)
        let res;try{res=await statusChangeConvenienceApi.submit(c.body)}catch(err){res=err}
        if(res?.code!==0&&/403|404|409|422|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN|CONFLICT|VALIDATION/.test([res?.code,res?.bizCode].join(' '))){clearStatusChangeRecovery(c.identity,c.studentId);if(!this.current(c))return;this.pending=null;this.receipt=null;throw res}
        c.id=res?.code===0&&exactId(res.data?.changeId)?exactId(res.data.changeId):null;rememberStatusChangeRecovery(c.identity,c)
        if(!this.current(c))return
        this.command=null;this.confirmVisible=false;await this.verify()
      }catch(err){if(this.current(c)){this.command=null;this.confirmVisible=false;this.fail(err,'提交前核对未完成，请核对学生与材料后重试。')}}finally{if(this.current(c))this.submitting=false}
    },
    async findSubmitted(c){
      let page=c.lookupPage||1
      for(let i=0;i<3;i++,page++){
        const res=await academicAffairsApi.getStatusChanges({studentId:c.studentId,page,pageSize:20})
        if(!this.current(c))return null
        if(res?.code!==0)throw res
        if(!Array.isArray(res.data?.list))throw {code:503}
        const row=res.data.list.find(r=>r.idempotencyKey===c.body.idempotencyKey)
        if(row)return row
        if((Number.isFinite(res.data.total)&&page*20>=res.data.total)||res.data.list.length<20){c.lookupPage=1;return null}
        c.lookupPage=page+1
      }
      return null
    },
    async verify(){
      const c=this.pending;if(!c||!this.current(c)||this.checking)return;this.checking=true
      try{let row
        if(c.id){const res=await academicAffairsApi.getStatusChange(c.id);if(!this.current(c))return;if(res?.code!==0)throw res;row=res.data}
        else{row=await this.findSubmitted(c);if(!this.current(c))return}
        const same=!!row&&(!c.id||exactId(row.changeId)===exactId(c.id))&&String(row.studentId)===c.studentId&&row.idempotencyKey===c.body.idempotencyKey&&row.changeType===c.body.changeType&&(c.recovered||String(row.reason||'')===c.body.reason)&&['SUBMITTED','IN_REVIEW','RETURNED','REJECTED','APPROVED_PENDING_EFFECTIVE','EFFECTIVE'].includes(row.status)&&['toMajorId','toClassId'].every(k=>String(row[k]||'')===String(c.body[k]||''))&&String(row.effectiveDate||'').replace(' ','T').slice(0,19)===String(c.body.effectiveDate||'').slice(0,19)
        if(!same){this.error='结果待核实：尚未找到与本次申请准确一致的正式记录，请勿重复提交。';return}
        const materials=await statusChangeConvenienceApi.listMaterials(row.changeId);if(!this.current(c))return;if(materials?.code!==0)throw materials
        if(!Array.isArray(materials.data?.items))throw {code:503}
        if(JSON.stringify((materials.data?.items||[]).map(f=>String(f.fileId)).sort())!==JSON.stringify([...c.body.materialFileIds].sort())){this.error='结果待核实：正式绑定材料与本次申请尚不一致。';return}
        this.receipt={verified:true,id:row.changeId,label:'正式申请与材料已核对；提交申请不等于学籍已变更。'};this.pending=null;this.error='';rememberStatusChangeRecovery(c.identity,{...c,id:row.changeId,verified:true})
      }catch(err){if(this.current(c))this.fail(err,'结果待核实，请稍后查询原申请。')}finally{if(this.current(c))this.checking=false}
    }
  }
}
</script>

<style scoped>
.aa-form{border:0;padding:0;margin:0}.aa-form-error{color:var(--danger-600,#b42318)}.aa-form-receipt{padding:14px;background:var(--primary-50,#edf3ff);margin-bottom:16px;border-radius:8px}
.aa-apply-progress{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;list-style:none;margin:0;padding:15px 16px;border:1px solid var(--card-b,#dce5ef);border-radius:12px;background:#fff}.aa-apply-progress li{display:flex;gap:9px;color:var(--t3,#65778b);font-size:12px}.aa-apply-progress li>span{display:grid;place-items:center;flex:0 0 24px;height:24px;border:1px solid var(--card-b,#dce5ef);border-radius:50%}.aa-apply-progress strong,.aa-apply-progress small{display:block}.aa-apply-progress strong{padding-top:3px;color:var(--t2,#40536b)}.aa-apply-progress small{margin-top:7px;line-height:1.45}.aa-apply-progress .is-current>span{border-color:var(--pri,#2f66bd);background:var(--pri,#2f66bd);color:#fff}
.aa-form { display: flex; flex-direction: column; gap: 18px; max-width: 920px; }
.aa-form__row { display: flex; align-items: flex-start; gap: 16px; }
.aa-form__label { width: 96px; flex-shrink: 0; padding-top: 8px; font-size: 13px; color: var(--text-700, #4e5969); text-align: right; }
.aa-form__label.required::before { content: '*'; color: var(--danger-600, #f53f3f); margin-right: 4px; }
.aa-form__field { flex: 1; min-width: 0; }
.aa-input, .aa-textarea { width: 100%; padding: 8px 12px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 14px; box-sizing: border-box; }
.aa-input { height: 36px; }
.aa-picked { display: flex; align-items: center; gap: 12px; font-size: 14px; color: var(--text-900, #1f2329); }
.aa-form__hint { margin-top: 5px; font-size: 12px; line-height: 1.5; color: var(--text-400, #8a9099); }
.aa-form__hint--warn { color: var(--warning-700, #b76700); }
.aa-transition { margin-left: 112px; display: grid; grid-template-columns: minmax(0, 1fr) 36px minmax(0, 1fr); gap: 12px; align-items: stretch; }
.aa-transition__card { padding: 16px; border: 1px solid var(--border-200, #e5e6eb); border-radius: 10px; background: var(--bg-white, #fff); }
.aa-transition__card--target { background: var(--fill-50, #f7f8fa); }
.aa-transition__eyebrow { margin-bottom: 4px; font-size: 12px; color: var(--text-400, #8a9099); }
.aa-transition__title { display: block; margin-bottom: 14px; font-size: 15px; color: var(--text-900, #1f2329); }
.aa-transition__grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin: 0; }
.aa-transition__grid div { min-width: 0; }
.aa-transition__grid dt { margin-bottom: 3px; font-size: 11px; color: var(--text-400, #8a9099); }
.aa-transition__grid dd { margin: 0; overflow-wrap: anywhere; font-size: 13px; color: var(--text-800, #31343a); }
.aa-transition__arrow { align-self: center; justify-self: center; font-size: 22px; color: var(--text-400, #8a9099); }
.aa-radio-group { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.aa-radio { display: flex; gap: 9px; align-items: flex-start; padding: 12px; border: 1px solid var(--border-200, #e5e6eb); border-radius: 8px; cursor: pointer; }
.aa-radio input { margin-top: 3px; }
.aa-radio span { display: flex; flex-direction: column; gap: 3px; }
.aa-radio strong { font-size: 13px; font-weight: 600; color: var(--text-900, #1f2329); }
.aa-radio small { font-size: 11px; line-height: 1.4; color: var(--text-400, #8a9099); }
.aa-effective-date { margin-top: 10px; max-width: 360px; }
.aa-materials { display: grid; gap: 8px; margin-top: 10px; }
.aa-material { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 12px; border: 1px solid var(--border-200, #e5e6eb); border-radius: 8px; background: var(--fill-50, #f7f8fa); }
.aa-material__meta { min-width: 0; display: flex; align-items: center; gap: 10px; }
.aa-material__meta strong { max-width: 420px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }
.aa-material__status { flex-shrink: 0; font-size: 11px; color: var(--warning-700, #b76700); }
.aa-material__status.is-ready { color: var(--success-700, #16803c); }
.aa-material__actions { display: flex; gap: 8px; }
.aa-material__actions button { border: 0; background: transparent; color: var(--primary-600, #1769e0); cursor: pointer; font-size: 12px; }
.aa-form__actions { margin-top: 24px; display: flex; gap: 12px; padding-left: 112px; }
.aa-apply-layout{display:grid;grid-template-columns:minmax(0,1fr) 260px;gap:16px}.aa-conditions{align-self:start;padding:18px;border:1px solid var(--border-200,#e1e7ef);border-radius:9px;background:var(--bg-white,#fff)}.aa-conditions h3{font-size:14px;margin:0 0 16px}.aa-conditions dl{display:grid;gap:16px;margin:0 0 24px}.aa-conditions dt{font-size:13px;font-weight:600}.aa-conditions dd{margin:7px 0 0;font-size:12px;line-height:1.6;color:var(--text-500,#607087)}.aa-conditions p{font-size:13px;line-height:1.7;color:var(--text-500,#607087)}.aa-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}.aa-form>*{grid-column:1/-1}.aa-form>.aa-form__row:nth-child(-n+2){grid-column:auto}.aa-form__row{flex-direction:column;gap:8px}.aa-form__label{width:auto;text-align:left;padding-top:0}.aa-form__field{width:100%}.aa-transition{margin-left:0}.aa-form__actions{padding-left:0}
@media (max-width: 1100px){.aa-apply-layout{grid-template-columns:1fr}.aa-conditions{display:block}}
@media (max-width: 820px) {
  .aa-apply-progress { grid-template-columns: 1fr; }
  .aa-form__row { display: block; }
  .aa-form__label { display: block; width: auto; padding: 0 0 6px; text-align: left; }
  .aa-transition { margin-left: 0; grid-template-columns: 1fr; }
  .aa-transition__arrow { transform: rotate(90deg); }
  .aa-radio-group { grid-template-columns: 1fr; }
  .aa-form__actions { padding-left: 0; }
  .aa-material { align-items: flex-start; flex-direction: column; }
}
</style>
