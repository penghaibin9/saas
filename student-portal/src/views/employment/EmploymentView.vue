<template>
  <div class="sp-page">
    <nav class="sp-tabs">
      <button v-for="t in tabs" :key="t.key" class="sp-tab" :class="{ 'is-active': tab === t.key }" @click="tab = t.key">{{ t.label }}</button>
    </nav>

    <StateBlock v-if="loading" type="loading" text="正在加载就业信息…" />
    <StateBlock v-else-if="error" type="error" :text="error" />
    <template v-else>
      <!-- 我的就业 -->
      <template v-if="tab === 'overview'">
        <section class="sp-card" style="margin-bottom:16px">
          <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:20px;flex-wrap:wrap">
            <div>
              <div style="font-size:18px;font-weight:600">我的就业进度</div>
              <div class="sp-muted" style="margin-top:8px">按学校要求完成生源核对与去向登记，是顺利办理离校手续的前提。</div>
            </div>
            <span class="statepill" :class="{ warn: !isSigned }"><span class="dot" />{{ destText() }}</span>
          </div>
          <FlowSteps :steps="flowSteps" style="margin-top:22px" />
        </section>
        <section class="sp-card">
          <div class="sp-panel__head">就业信息</div>
          <dl class="desc">
            <div><dt>去向类型</dt><dd>{{ destText() }}</dd></div>
            <div><dt>单位</dt><dd>{{ my.companyName || '—' }}</dd></div>
            <div><dt>岗位</dt><dd>{{ my.jobTitle || '—' }}</dd></div>
            <div><dt>材料审核</dt><dd><StatusTag :text="matText()" :tone="my.materialStatus==='APPROVED'?'success':'warn'" /></dd></div>
            <div><dt>去向核验</dt><dd><StatusTag :text="verifyText()" :tone="my.verifyStatus==='VERIFIED'?'success':'warn'" /></dd></div>
            <div><dt>帮扶级别</dt><dd>{{ helpText() }}</dd></div>
          </dl>
          <p v-if="my.materialStatus === 'APPROVED' && my.verifyStatus !== 'VERIFIED'" class="sp-muted" style="margin-top:14px">
            材料已通过审核，但学校尚未完成<strong>去向核验</strong>；两者是相互独立的两步，核验完成后本页才会显示「已核验」。
          </p>
        </section>
        <section class="sp-card">
          <div class="sp-panel__head">就业政策与提醒</div>
          <div style="display:flex;flex-direction:column;gap:10px;font-size:13px;color:var(--t2);line-height:1.7">
            <div>· 请及时完成「生源核对」，信息将用于报到证与档案转递。</div>
            <div>· 已签约 / 已升学同学请在「去向登记」中更新状态并上传材料。</div>
            <div>· 就业去向未登记将影响离校手续办理。</div>
          </div>
        </section>
      </template>

      <!-- 生源核对 -->
      <template v-else-if="tab === 'source'">
        <section class="sp-card" style="max-width:720px">
          <div class="sp-panel__head">生源信息核对</div>
          <dl class="desc">
            <div><dt>姓名</dt><dd>{{ studentName }}</dd></div>
            <div><dt>就业单位</dt><dd>{{ my.companyName || '待登记' }}</dd></div>
            <div><dt>岗位</dt><dd>{{ my.jobTitle || '待登记' }}</dd></div>
            <div><dt>去向类型</dt><dd>{{ destText() }}</dd></div>
          </dl>
          <p class="sp-muted" style="margin-top:14px">生源信息来自学籍档案，如有误请在「我的档案 · 申请更正联系方式」发起更正；确认无误后在「去向登记」提交去向。</p>
        </section>
      </template>

      <!-- 去向登记 -->
      <template v-else-if="tab === 'destination'">
        <section class="sp-card" style="max-width:760px">
          <div class="sp-panel__head">就业去向登记</div>
          <StateBlock v-if="optionsError" type="error" :text="optionsError" />
          <template v-else>
            <div class="sp-fieldlabel">去向类型</div>
            <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px">
              <button v-for="d in destTypes" :key="d.code" class="chipbtn" :class="{ on: form.destinationType === d.code }" @click="form.destinationType = d.code">{{ d.label }}</button>
            </div>
            <div class="two">
              <div v-if="needsCompany"><div class="sp-fieldlabel">{{ companyLabel }}</div><input v-model.trim="form.companyName" class="sp-inp" :placeholder="companyLabel" /></div>
              <div><div class="sp-fieldlabel">岗位/职务</div><input v-model.trim="form.jobTitle" class="sp-inp" placeholder="岗位（可选）" /></div>
              <div><div class="sp-fieldlabel">所在城市</div><ChinaRegionPicker v-model="form.city" /></div>
              <div><div class="sp-fieldlabel">联系电话</div><input v-model.trim="form.contact" class="sp-inp" placeholder="联系方式（可选）" /></div>
            </div>
            <p v-if="requiredMaterials.length" class="sp-muted" style="margin-top:12px">
              该去向需提交：{{ requiredMaterials.map((m) => m.label).join('、') }}。请在提交后按学校通知上传材料。
            </p>
          </template>
          <div class="sp-fieldlabel" style="margin-top:14px">备注</div>
          <textarea v-model.trim="form.remark" class="sp-inp" placeholder="补充说明（可选）" />
          <div style="display:flex;gap:10px;margin-top:16px">
            <button class="sp-btn sp-btn--ghost" :disabled="busy" @click="printDoc">打印去向登记表</button>
            <button class="sp-btn" :disabled="busy || !form.destinationType || !!optionsError" @click="submit">提交登记</button>
          </div>
        </section>
      </template>

      <!-- 签约材料 -->
      <template v-else-if="tab === 'contract'">
        <section class="sp-card" style="max-width:820px">
          <div class="sp-panel__head">签约材料</div>
          <StateBlock v-if="!(my.materials||[]).length" type="empty" text="暂无签约材料，请在去向登记时上传" />
          <AutoTable v-else :rows="my.materials" :columns="MATERIAL_COLS" />
          <button class="sp-btn sp-btn--ghost" :disabled="busy" style="margin-top:16px" @click="printDoc">打印就业协议书</button>
        </section>
        <section class="sp-card" style="max-width:820px">
          <div class="sp-panel__head">就业回访</div>
          <AutoTable :rows="my.followUps" :columns="FOLLOW_UP_COLS" empty="暂无回访记录" />
        </section>
      </template>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import AutoTable from '../../components/AutoTable.vue'
import FlowSteps from '../../components/FlowSteps.vue'
import ChinaRegionPicker from '../../components/ChinaRegionPicker.vue'
import { portalApi } from '../../services/portalApi'
import { useSessionStore } from '../../stores/session'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const session = useSessionStore()
// SP-E10：材料类型/审核状态/回访方式的 label 全部由服务端 canonical 下发
// （typeLabel/statusLabel/wayLabel），本页不再维护第二份业务字典——旧的本地
// MATERIAL_TYPE 就漏了 CONTRACT/ENLIST_PROOF/OTHER，一律显示成"其他就业材料"。
const MATERIAL_COLS = [
  { key: 'typeLabel', label: '材料类型' },
  { key: 'fileName', label: '文件名称' },
  { key: 'statusLabel', label: '审核状态' }
]
const FOLLOW_UP_COLS = [
  { key: 'time', label: '回访时间' },
  { key: 'wayLabel', label: '跟进方式' },
  { key: 'content', label: '回访内容' }
]
const tabs = [
  { key: 'overview', label: '我的就业' }, { key: 'source', label: '生源核对' },
  { key: 'destination', label: '去向登记' }, { key: 'contract', label: '签约材料' }
]
const tab = ref('overview')
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const my = ref({})
const form = reactive({ destinationType: '', companyName: '', jobTitle: '', city: '', contact: '', remark: '' })

// SP-E03/SP-E10：去向类型与状态字典全部由服务端 canonical 下发，本页不再维护
// 任何业务枚举——旧实现硬编码的 FURTHER/MILITARY 与管理端 canonical 的
// FURTHER_STUDY/ENLISTED 根本不是同一套 code，学生提交的去向管理端识别不了；
// 状态字典也漏了 PENDING_VERIFY/SUBMITTED/REVIEWING/RETURNED，界面会直接显示
// 英文原始码。本地只保留 tone（视觉）映射，不解释业务含义。
const options = ref({ destinationTypes: [], verifyStatuses: [], materialStatuses: [], helpLevels: [] })
const optionsError = ref('')

const destTypes = computed(() => options.value.destinationTypes || [])
const currentDest = computed(
  () => destTypes.value.find((d) => d.code === form.destinationType) || null
)
// 服务端按去向类型下发 requiredFields：签约要单位、升学要院校、入伍/自由职业不要求，
// 不再是"只有 SIGNED 才显示单位输入框"这种前端自己拍的规则。
const needsCompany = computed(() => (currentDest.value?.requiredFields || []).includes('companyName'))
const companyLabel = computed(() => currentDest.value?.companyLabel || '单位名称')
const requiredMaterials = computed(() => currentDest.value?.requiredMaterials || [])

const studentName = computed(() => session.user?.realName || '同学')
const isSigned = computed(() => my.value.destinationType === 'SIGNED')

// 状态文案一律用服务端下发的 label；服务端没给才回落原始码，绝不本地编译语义。
function destText() { return my.value.destinationLabel || my.value.destinationType || '待登记' }
function verifyText() { return my.value.verifyStatusLabel || my.value.verifyStatus || '—' }
function matText() { return my.value.materialStatusLabel || my.value.materialStatus || '—' }
function helpText() { return my.value.helpLevelLabel || my.value.helpLevel || '—' }

const flowSteps = computed(() => {
  // SP-E09：materialStatus（材料审核）与 verifyStatus（去向核验）是两个独立事实，
  // 进度条按"登记 → 材料 → 核验"的真实先后顺序推进，不再拿去向核验状态去冒充
  // 第一步"生源核对"的完成度（那一步根本没有对应的后端事实）。
  const order = ['去向登记', '材料审核', '去向核验', '离校归档']
  let cur = 0
  if (my.value.destinationType) cur = 1
  if (my.value.materialStatus === 'APPROVED') cur = 2
  if (my.value.verifyStatus === 'VERIFIED') cur = 3
  return order.map((name, i) => ({ name, state: i < cur ? 'done' : i === cur ? 'current' : 'todo' }))
})

async function load() {
  loading.value = true; error.value = ''
  try { my.value = await portalApi.employmentMy() || {} }
  catch (e) { error.value = e?.message || '就业信息加载失败' } finally { loading.value = false }
}
async function loadOptions() {
  // 字典加载失败必须显式报错并禁用提交：没有 canonical 选项时让学生"随便选一个"
  // 提交，等于又回到旧的 code 漂移问题。
  optionsError.value = ''
  try {
    options.value = await portalApi.employmentDestinationOptions() || {}
    if (!form.destinationType && destTypes.value.length) {
      form.destinationType = destTypes.value[0].code
    }
  } catch (e) {
    optionsError.value = e?.message || '去向选项加载失败，暂时无法提交登记'
  }
}
async function submit() {
  if (!form.destinationType) return
  busy.value = true
  try {
    await portalApi.employmentDestination({ ...form })
    // SP-E07：后端此刻只生成了一张待处理的事务申请工单，去向既没入 canonical
    // 台账、更没核验。说"已登记"会让学生以为流程结束。
    ui.notify('去向信息已提交学校核验，请留意审核结果')
    tab.value = 'overview'
    load()
  } catch (e) { ui.notify(e?.message || '提交失败（演示租户为只读）') } finally { busy.value = false }
}
async function printDoc() {
  busy.value = true
  // SP-E08 欠账：后端目前只写打印审计留痕，不产出真实 PDF/fileId，文案如实说明。
  try { await portalApi.employmentDestinationPrint({}); ui.notify('已生成打印留痕（暂未生成可下载文件）') }
  catch (e) { ui.notify(e?.message || '打印失败（演示租户为只读）') } finally { busy.value = false }
}
onMounted(() => { load(); loadOptions() })
</script>

<style scoped>
.statepill { display: inline-flex; align-items: center; gap: 7px; padding: 8px 13px; background: var(--pri-50); border-radius: 9px; color: var(--pri); font-weight: 600; font-size: 13.5px; }
.statepill.warn { background: var(--warn-bg); color: var(--warn-fg); }
.statepill .dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
.desc { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px 24px; margin: 0; }
.desc dt { font-size: 12px; color: var(--t3); margin-bottom: 5px; }
.desc dd { margin: 0; font-size: 14px; color: var(--t1); }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.chipbtn { all: unset; box-sizing: border-box; cursor: pointer; padding: 9px 16px; border-radius: 9px; font-size: 13px; font-weight: 500; background: #fff; color: var(--t1); border: 1px solid var(--line); }
.chipbtn.on { background: var(--pri-50); color: var(--pri); border-color: var(--pri); font-weight: 600; }
@media (max-width: 900px) { .desc { grid-template-columns: 1fr 1fr; } .two { grid-template-columns: 1fr; } }
</style>
