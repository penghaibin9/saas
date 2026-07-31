<template>
  <div class="sp-page">
    <StateBlock v-if="loading" type="loading" text="正在加载学籍信息…" />
    <StateBlock v-else-if="error" type="error" :text="error" />
    <div v-else class="grid">
      <!-- 左列 -->
      <div style="display:flex;flex-direction:column;gap:18px">
        <section class="card">
          <div class="phead">
            <span class="avatar">{{ initial }}</span>
            <div><div class="pname">{{ info.name || '同学' }}</div><div class="pmeta">{{ info.studentNo }} · {{ info.collegeName || '—' }} · 学生</div></div>
          </div>
          <div class="srow"><span class="stitle">基本信息</span></div>
          <div class="basic">
            <div v-for="b in basic" :key="b.label" class="brow"><span class="bl">{{ b.label }}</span><span class="bv">{{ b.value }}</span></div>
          </div>
        </section>

        <section class="card">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
            <span class="stitle">敏感信息</span>
            <span class="masktag"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="10" width="16" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></svg>脱敏展示 · 查看留痕</span>
          </div>
          <div class="sp-muted" style="margin-bottom:14px">默认脱敏，授权查看明文将写入审计日志。</div>
          <div style="display:flex;flex-direction:column;gap:12px">
            <div v-for="f in sens" :key="f.field" class="sens">
              <span style="font-size:13px;color:var(--t3);flex:none">{{ f.label }}</span>
              <span style="flex:1;text-align:right;font-size:14px;color:var(--t1);font-variant-numeric:tabular-nums;letter-spacing:.5px">{{ reveal[f.field] || f.masked || '—' }}</span>
              <template v-if="f.can && !reveal[f.field]">
                <template v-if="revealing !== f.field">
                  <button class="eye" @click="startReveal(f.field)"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" /></svg>授权查看</button>
                </template>
                <template v-else>
                  <input v-model.trim="reason" class="sp-inp" style="flex:none;width:150px;height:30px" placeholder="查看原因" @keyup.enter="confirmReveal(f.field)" />
                  <button class="eye" :disabled="!reason" @click="confirmReveal(f.field)">确认</button>
                  <button class="eye" style="color:var(--danger-fg)" @click="revealing=''">取消</button>
                </template>
              </template>
            </div>
          </div>
        </section>
      </div>

      <!-- 右列 -->
      <div style="display:flex;flex-direction:column;gap:18px">
        <section class="card">
          <div class="stitle" style="margin-bottom:14px">学籍卡片</div>
          <div class="idcard">
            <div style="display:flex;justify-content:space-between"><span style="font-size:12.5px;color:var(--t3)">学号</span><span style="font-size:12.5px;color:var(--ok-fg);font-weight:500">● {{ statusText(info.studentStatus) }}</span></div>
            <div style="font-size:22px;font-weight:700;color:var(--t1);font-variant-numeric:tabular-nums;letter-spacing:1px;margin-top:4px">{{ info.studentNo || '—' }}</div>
            <div style="margin-top:14px;display:grid;grid-template-columns:1fr 1fr;gap:10px">
              <div><div class="idlbl">院系</div><div class="idval">{{ info.collegeName || '—' }}</div></div>
              <div><div class="idlbl">专业</div><div class="idval">{{ info.majorName || '—' }}</div></div>
              <div><div class="idlbl">班级</div><div class="idval">{{ info.className || '—' }}</div></div>
              <div><div class="idlbl">年级</div><div class="idval">{{ info.grade || '—' }} 级</div></div>
            </div>
          </div>
        </section>

        <section class="card">
          <div class="srow"><span class="stitle">我的申请</span><span class="sp-muted">在办 / 历史</span></div>
          <StateBlock v-if="!apps.length" type="empty" text="暂无申请记录" />
          <div v-else style="display:flex;flex-direction:column;gap:10px">
            <div v-for="a in apps" :key="a.id" class="approw">
              <span class="atag" :style="modTagStyle(a.sourceType)">{{ a.dept || '事务' }}</span>
              <div style="flex:1;min-width:0"><div class="atitle">{{ applicationName(a) }}</div><div style="font-size:12px;color:var(--t4);margin-top:2px">{{ fmt(a.applyTime) }}</div></div>
              <StatusTag :text="applicationStatusText(a)" :tone="groupTone(a.group)" />
            </div>
          </div>
        </section>

        <section class="card">
          <div class="srow"><span class="stitle">家长授权管理</span><button class="linkbtn" @click="showBind=!showBind">+ 添加绑定</button></div>
          <div class="sp-muted" style="margin-bottom:12px">家长凭手机号验证码登录只读家长端，仅见授权范围，可随时撤销。</div>
          <div v-if="showBind" class="bindform">
            <input v-model.trim="bindForm.phone" class="sp-inp" placeholder="家长手机号" style="margin-bottom:8px" />
            <input v-model.trim="bindForm.name" class="sp-inp" placeholder="家长姓名" style="margin-bottom:8px" />
            <div class="sp-muted" style="margin-bottom:8px">可见范围（固定）：学业成绩与课表、缴费与资助、异常与安全提醒、毕业/实习/就业进度</div>
            <div style="display:flex;gap:10px">
              <button class="sp-btn sp-btn--sm" :disabled="busy || !bindForm.phone" @click="bind">发送验证码并绑定</button>
              <button class="sp-btn sp-btn--ghost sp-btn--sm" @click="showBind=false">取消</button>
            </div>
          </div>
          <StateBlock v-if="guardianError" type="error" :text="guardianError" />
          <StateBlock v-else-if="!guardians.length" type="empty" text="尚未授权任何家长" />
          <div v-else style="display:flex;flex-direction:column;gap:10px">
            <div v-for="g in guardians" :key="g.id || g.linkId" class="prow">
              <span class="pav">{{ (g.guardianName || g.name || '家').slice(0,1) }}</span>
              <div style="flex:1;min-width:0"><div style="font-size:13.5px;color:var(--t1)">{{ g.guardianName || g.name || '家长' }} · {{ relationText(g.relation) }} · {{ g.guardianPhone || g.phoneMasked || '' }}</div><div style="font-size:11.5px;color:var(--t4);margin-top:2px">可见：成绩课表 / 缴费资助 / 异常提醒 / 就业进度</div></div>
              <template v-if="confirmRevoke === (g.id || g.linkId)">
                <button class="linkbtn" style="color:var(--danger-fg)" :disabled="busy" @click="doRevoke(g.id||g.linkId)">确认</button>
                <button class="linkbtn" @click="confirmRevoke=''">取消</button>
              </template>
              <button v-else-if="g.status !== 'REVOKED'" class="linkbtn" style="color:var(--danger-fg)" @click="confirmRevoke=(g.id||g.linkId)">撤销</button>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { portalApi } from '../../services/portalApi'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const info = ref({})
const apps = ref([])
const guardians = ref([])
const guardianError = ref('')
const reveal = reactive({ phone: '', idCard: '' })
const revealing = ref('')
const reason = ref('')
const showBind = ref(false)
const bindForm = reactive({ name: '', phone: '' })
const confirmRevoke = ref('')

const initial = computed(() => (info.value.name || '同').slice(0, 1))
const STATUS_MAP = { NORMAL: '在读', ACTIVE: '在读', SUSPENDED: '休学', TRANSFERRED: '转学', WITHDRAWN: '退学', GRADUATED: '毕业' }
function statusText(s) { return STATUS_MAP[s] || s || '在读' }
const APPLICATION_STATUS_MAP = { SUBMITTED: '已提交', PENDING_REVIEW: '待审核', CLASS_REVIEW: '班级审核中', COUNSELOR_REVIEW: '辅导员审核中', COLLEGE_REVIEW: '学院审核中', SCHOOL_REVIEW: '学校审核中', APPROVED: '已通过', REJECTED: '未通过', RETURNED: '已退回', PROCESSING: '处理中', COMPLETED: '已完成' }
const APPLICATION_NAME_MAP = { PERSONAL: '事假申请', SICK: '病假申请', OFFICIAL: '公假申请', LEAVE: '请假申请', AID: '困难认定', FUNDING: '奖助申请', DORM: '宿舍事务' }
function readableCode(value, mapping, fallback = '状态待确认') {
  const raw = String(value || '').trim()
  if (!raw) return fallback
  const key = raw.toUpperCase()
  if (mapping[key]) return mapping[key]
  return /^[A-Z0-9_]+$/.test(raw) ? fallback : raw
}
function applicationName(item) { return readableCode(item?.name || item?.type || item?.leaveType, APPLICATION_NAME_MAP, '业务申请') }
function applicationStatusText(item) { return item?.statusText || readableCode(item?.status || item?.currentNode, APPLICATION_STATUS_MAP) }

const basic = computed(() => {
  const i = info.value
  return [
    { label: '姓名', value: i.name || '—' }, { label: '学号', value: i.studentNo || '—' },
    { label: '性别', value: i.gender || '—' }, { label: '年级', value: (i.grade || '—') + ' 级' },
    { label: '学院', value: i.collegeName || '—' }, { label: '专业', value: i.majorName || '—' },
    { label: '班级', value: i.className || '—' }, { label: '学籍状态', value: statusText(i.studentStatus) }
  ]
})
const sens = computed(() => {
  const view = info.value.sensitiveViewable || []
  return [
    { field: 'phone', label: '手机号', masked: info.value.phoneMasked, can: view.includes('phone') },
    { field: 'idCard', label: '身份证号', masked: info.value.idCardMasked, can: view.includes('idCard') }
  ]
})

function groupTone(g) { return g === 'approved' || g === 'done' ? 'success' : g === 'rejected' ? 'danger' : 'warn' }
function modTagStyle() { return { background: 'var(--pri-50)', color: 'var(--pri-text, var(--pri))' } }
function fmt(t) { return t ? String(t).replace('T', ' ').slice(0, 16) : '—' }

function startReveal(field) { revealing.value = field; reason.value = '' }
async function confirmReveal(field) {
  if (!reason.value) return
  busy.value = true
  try {
    const data = await portalApi.profileSensitive(field, reason.value)
    reveal[field] = data?.value || data?.plain || data?.[field] || '（已授权）'
    ui.notify('已按你的授权展示明文并写入审计日志')
    revealing.value = ''; reason.value = ''
  } catch (e) { ui.notify(e?.message || '查看明文失败') } finally { busy.value = false }
}
async function bind() {
  busy.value = true
  try {
    await portalApi.bindGuardian({
      guardianName: bindForm.name, guardianPhone: bindForm.phone, relation: 'PARENT',
      visibleScopes: ['ACADEMIC_GRADE', 'FEE_AID_STATUS', 'CAMPUS_ALERT', 'CAREER_PROGRESS']
    })
    ui.notify('已提交家长授权'); showBind.value = false; bindForm.name = ''; bindForm.phone = ''; loadGuardians()
  } catch (e) { ui.notify(e?.message || '授权失败') } finally { busy.value = false }
}
const RELATION_MAP = { FATHER: '父亲', MOTHER: '母亲', GUARDIAN: '监护人', PARENT: '家长', OTHER: '其他' }
function relationText(r) { return RELATION_MAP[r] || r || '监护人' }
async function doRevoke(id) {
  busy.value = true
  try { await portalApi.revokeGuardian(id); ui.notify('已撤销授权'); confirmRevoke.value = ''; loadGuardians() }
  catch (e) { ui.notify(e?.message || '撤销失败') } finally { busy.value = false }
}
async function loadGuardians() {
  guardianError.value = ''
  try { const d = await portalApi.listGuardians(); guardians.value = Array.isArray(d) ? d : (d?.items || d?.guardians || []) }
  catch (e) { guardianError.value = '家长授权信息暂时读取失败，可稍后重试。'; guardians.value = [] }
}
async function load() {
  loading.value = true; error.value = ''
  try {
    const [i, a] = await Promise.all([portalApi.profileEnrollment(), portalApi.affairsApplications().catch(() => ({}))])
    info.value = i || {}
    apps.value = (a && a.applications) ? a.applications.slice(0, 5) : []
  } catch (e) { error.value = e?.message || '学籍信息加载失败' } finally { loading.value = false }
  loadGuardians()
}
onMounted(load)
</script>

<style scoped>
.grid { display: grid; grid-template-columns: 1.3fr 1fr; gap: 18px; align-items: start; }
.card { background: #fff; border: 1px solid var(--line); border-radius: 16px; box-shadow: 0 1px 2px rgba(16,24,40,.04); padding: 22px 24px; }
.phead { display: flex; align-items: center; gap: 16px; padding-bottom: 18px; border-bottom: 1px solid var(--line2); }
.avatar { width: 60px; height: 60px; flex: none; border-radius: 16px; background: linear-gradient(135deg, var(--g2), var(--g1)); color: #fff; font-size: 24px; font-weight: 600; display: flex; align-items: center; justify-content: center; }
.pname { font-size: 18px; font-weight: 600; color: var(--t1); }
.pmeta { margin-top: 4px; font-size: 13px; color: var(--t3); }
.srow { display: flex; align-items: center; justify-content: space-between; margin: 18px 0 14px; }
.stitle { font-size: 15px; font-weight: 600; color: var(--t1); }
.basic { display: grid; grid-template-columns: 1fr 1fr; gap: 14px 24px; }
.brow { display: flex; justify-content: space-between; gap: 12px; padding-bottom: 11px; border-bottom: 1px solid #F5F6F8; }
.bl { font-size: 13px; color: var(--t4); flex: none; }
.bv { font-size: 13.5px; color: var(--t1); text-align: right; }
.masktag { display: inline-flex; align-items: center; gap: 4px; height: 22px; padding: 0 8px; border-radius: 6px; background: var(--warn-bg); color: var(--warn-fg); font-size: 11.5px; font-weight: 500; }
.sens { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 14px; background: #F9FAFB; border: 1px solid var(--line2); border-radius: 10px; }
.eye { all: unset; cursor: pointer; flex: none; display: inline-flex; align-items: center; gap: 5px; font-size: 12.5px; font-weight: 500; color: var(--pri); }
.eye:hover { color: var(--pri-h); }
.eye:disabled { opacity: .5; cursor: not-allowed; }
.idcard { padding: 16px; border-radius: 12px; background: linear-gradient(135deg, var(--pri-50), #ffffff); border: 1px solid var(--pri-100); }
.idlbl { font-size: 11.5px; color: var(--t4); }
.idval { font-size: 13px; color: var(--t1); margin-top: 2px; }
.approw { display: flex; align-items: center; gap: 11px; padding: 11px 0; border-bottom: 1px solid #F4F5F7; }
.atag { flex: none; display: inline-flex; align-items: center; height: 22px; padding: 0 8px; border-radius: 6px; font-size: 11.5px; font-weight: 500; }
.atitle { font-size: 13.5px; color: var(--t1); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.linkbtn { all: unset; cursor: pointer; font-size: 12.5px; font-weight: 600; color: var(--pri); }
.bindform { margin-bottom: 12px; padding: 14px; background: #F9FAFB; border: 1px solid var(--line2); border-radius: 11px; }
.prow { display: flex; align-items: center; gap: 12px; padding: 12px 14px; border: 1px solid var(--line); border-radius: 11px; }
.pav { width: 36px; height: 36px; flex: none; border-radius: 10px; background: var(--pri-50); color: var(--pri); font-size: 14px; font-weight: 600; display: flex; align-items: center; justify-content: center; }
@media (max-width: 900px) { .grid { grid-template-columns: 1fr; } .basic { grid-template-columns: 1fr; } }
</style>
