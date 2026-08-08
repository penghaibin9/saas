<template>
  <main class="public-help">
    <header class="ph-hero">
      <div class="ph-hero__inner">
        <p class="ph-eyebrow">跃科 SaaS · 自助服务</p>
        <h1>帮助中心</h1>
        <p>按你的角色和问题查操作步骤。这里是只读帮助页，不需要管理端登录，也不会绕过任何业务权限。</p>
      </div>
    </header>

    <div class="ph-shell">
      <section class="ph-controls" aria-label="帮助筛选">
        <label class="ph-search">
          <span>搜索帮助</span>
          <input v-model.trim="query" type="search" placeholder="例如：实习打卡、请假退回、成绩录入" autocomplete="off" />
        </label>
        <label>
          <span>我的角色</span>
          <select v-model="role">
            <option v-for="item in roleOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
        </label>
        <label>
          <span>业务分类</span>
          <select v-model="category">
            <option value="all">全部分类</option>
            <option v-for="item in categories" :key="item.value" :value="item.value">{{ item.label }}（{{ item.count }}）</option>
          </select>
        </label>
      </section>

      <article v-if="currentEntry" class="ph-article">
        <button type="button" class="ph-back" @click="closeTopic">← 返回帮助列表</button>
        <div class="ph-badges">
          <span>{{ currentEntry.typeLabel }}</span>
          <span>{{ currentEntry.category }}</span>
          <span v-if="currentItem.platforms?.length">{{ currentItem.platforms.join('、') }}</span>
        </div>
        <h2>{{ currentEntry.title }}</h2>
        <p class="ph-summary">{{ currentEntry.summary }}</p>

        <section v-if="currentItem.entry || currentItem.mobilePath" class="ph-entry">
          <strong>常见入口</strong>
          <span>{{ currentItem.entry || '从对应业务模块进入' }}</span>
          <small v-if="currentItem.mobilePath">小程序页面：{{ currentItem.mobilePath }}</small>
        </section>

        <section v-if="currentItem.prerequisites?.length" class="ph-section">
          <h3>操作前准备</h3>
          <ul><li v-for="(item, index) in currentItem.prerequisites" :key="index">{{ stringify(item) }}</li></ul>
        </section>

        <section v-if="currentItem.steps?.length" class="ph-section">
          <h3>{{ currentEntry.type === 'flow' ? '业务流转' : '操作步骤' }}</h3>
          <ol class="ph-steps">
            <li v-for="(step, index) in currentItem.steps" :key="index">
              <span>{{ index + 1 }}</span>
              <div>
                <strong v-if="step && typeof step === 'object' && step.name">{{ step.name }}</strong>
                <p>{{ step && typeof step === 'object' && step.detail ? step.detail : stringify(step) }}</p>
              </div>
            </li>
          </ol>
        </section>

        <section v-if="currentItem.fields?.length" class="ph-section">
          <h3>需要填写或确认</h3>
          <ul><li v-for="(item, index) in currentItem.fields" :key="index">{{ stringify(item) }}</li></ul>
        </section>

        <section v-if="currentItem.successCriteria?.length" class="ph-section ph-section--success">
          <h3>完成后的正确结果</h3>
          <ul><li v-for="(item, index) in currentItem.successCriteria" :key="index">{{ stringify(item) }}</li></ul>
        </section>

        <section v-if="currentItem.warnings?.length" class="ph-section ph-section--warning">
          <h3>重要提醒</h3>
          <ul><li v-for="(item, index) in currentItem.warnings" :key="index">{{ stringify(item) }}</li></ul>
        </section>

        <section v-if="currentItem.troubleshooting?.length" class="ph-section">
          <h3>异常排查</h3>
          <ol><li v-for="(item, index) in currentItem.troubleshooting" :key="index">{{ stringify(item) }}</li></ol>
        </section>

        <section v-if="currentItem.faq?.length" class="ph-section">
          <h3>常见问题</h3>
          <details v-for="(item, index) in currentItem.faq" :key="index" class="ph-faq">
            <summary>{{ item.q || item.question || stringify(item) }}</summary>
            <p v-if="item.a || item.answer">{{ item.a || item.answer }}</p>
          </details>
        </section>

        <section v-if="currentItem.related?.length" class="ph-section">
          <h3>相关入口</h3>
          <ul><li v-for="(item, index) in currentItem.related" :key="index">{{ item.label || stringify(item) }}</li></ul>
        </section>
      </article>

      <template v-else>
        <section class="ph-heading">
          <div>
            <p class="ph-eyebrow">{{ query || category !== 'all' ? '搜索结果' : '高频任务' }}</p>
            <h2>{{ query || category !== 'all' ? `找到 ${results.length} 项帮助` : '从常用事项开始' }}</h2>
          </div>
          <p>帮助内容只解释怎么操作；是否能看到数据、能否执行按钮，仍以登录后的权限和数据范围为准。</p>
        </section>

        <div v-if="displayEntries.length" class="ph-grid">
          <button v-for="entry in displayEntries" :key="entry.id" type="button" class="ph-card" @click="openTopic(entry.id)">
            <span>{{ entry.typeLabel }} · {{ entry.category }}</span>
            <strong>{{ entry.title }}</strong>
            <p>{{ entry.summary }}</p>
          </button>
        </div>

        <section v-else class="ph-empty">
          <strong>没有找到匹配内容</strong>
          <p>换一个更接近业务动作的关键词，例如“请假”“退回”“打卡”“成绩”“选课”；也可以清除分类后查看当前角色的高频任务。</p>
          <button type="button" @click="resetSearch">查看当前角色高频帮助</button>
        </section>
      </template>

      <footer class="ph-footer">
        <span>同一帮助内容同时服务 PC 与小程序，避免两套说明长期漂移。</span>
      </footer>
    </div>
  </main>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  HELP_ROLE_OPTIONS,
  getHelpCategories,
  getHelpEntry,
  getPriorityHelp,
  searchHelpCenter
} from '@/config/helpCenterModel'

const route = useRoute()
const router = useRouter()
const roleOptions = HELP_ROLE_OPTIONS
const allowedRoles = new Set(roleOptions.map((item) => item.value))

const initialRole = String(route.query.role || 'all')
const role = ref(allowedRoles.has(initialRole) ? initialRole : 'all')
const category = ref(String(route.query.category || 'all'))
const query = ref(String(route.query.q || ''))
const topic = ref(String(route.query.topic || ''))

const categories = computed(() => getHelpCategories(role.value))
const currentEntry = computed(() => getHelpEntry(topic.value))
const currentItem = computed(() => currentEntry.value?.item || {})
const results = computed(() => searchHelpCenter(query.value, {
  role: role.value,
  category: category.value,
  limit: 100
}))
const priority = computed(() => getPriorityHelp(role.value, 10))
const displayEntries = computed(() => query.value || category.value !== 'all' ? results.value : priority.value)

watch(role, () => {
  if (category.value !== 'all' && !categories.value.some((item) => item.value === category.value)) category.value = 'all'
  topic.value = ''
})
watch([role, category, query, topic], syncUrl)

function syncUrl() {
  const next = {}
  if (role.value !== 'all') next.role = role.value
  if (category.value !== 'all') next.category = category.value
  if (query.value) next.q = query.value
  if (topic.value) next.topic = topic.value
  if (route.query.source) next.source = route.query.source
  router.replace({ path: '/help', query: next }).catch(() => {})
}

function openTopic(id) {
  topic.value = id
  window.scrollTo({ top: 0, behavior: 'smooth' })
}
function closeTopic() {
  topic.value = ''
}
function resetSearch() {
  query.value = ''
  category.value = 'all'
}
function stringify(value) {
  if (value == null) return ''
  if (typeof value === 'string' || typeof value === 'number') return String(value)
  if (Array.isArray(value)) return value.map(stringify).filter(Boolean).join('、')
  if (value.label) return value.label
  if (value.name && value.detail) return `${value.name}：${value.detail}`
  if (value.name) return value.name
  return Object.values(value).map(stringify).filter(Boolean).join(' · ')
}
</script>

<style scoped>
.public-help { min-height: 100vh; background: #f6f8fc; color: #172033; font-family: system-ui, -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif; }
.ph-hero { padding: 34px 18px 28px; background: linear-gradient(135deg, #1f5ed6, #367ef2); color: #fff; }
.ph-hero__inner, .ph-shell { width: min(960px, 100%); margin: 0 auto; }
.ph-eyebrow { margin: 0 0 6px; font-size: 12px; font-weight: 700; letter-spacing: .08em; color: inherit; opacity: .78; }
.ph-hero h1 { margin: 0; font-size: clamp(28px, 6vw, 42px); }
.ph-hero p:last-child { max-width: 720px; margin: 10px 0 0; line-height: 1.7; color: rgba(255,255,255,.88); }
.ph-shell { padding: 18px 14px 36px; box-sizing: border-box; }
.ph-controls { display: grid; grid-template-columns: minmax(0, 1.7fr) minmax(150px, .65fr) minmax(180px, .8fr); gap: 10px; padding: 14px; border: 1px solid #e3e8f2; border-radius: 16px; background: #fff; box-shadow: 0 10px 30px rgba(30, 64, 120, .06); }
.ph-controls label { display: grid; gap: 6px; font-size: 12px; color: #667085; }
.ph-controls input, .ph-controls select { width: 100%; height: 40px; box-sizing: border-box; border: 1px solid #dce3ef; border-radius: 10px; padding: 0 11px; background: #fff; color: #172033; font: inherit; outline: none; }
.ph-controls input:focus, .ph-controls select:focus { border-color: #367ef2; box-shadow: 0 0 0 3px rgba(54,126,242,.1); }
.ph-heading { display: flex; justify-content: space-between; gap: 20px; align-items: end; margin: 24px 2px 12px; }
.ph-heading h2 { margin: 0; font-size: 21px; }
.ph-heading > p { max-width: 430px; margin: 0; color: #667085; font-size: 13px; line-height: 1.6; }
.ph-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.ph-card { min-width: 0; text-align: left; padding: 16px; border: 1px solid #e3e8f2; border-radius: 14px; background: #fff; cursor: pointer; color: inherit; font: inherit; }
.ph-card:hover { border-color: #b9cdf7; box-shadow: 0 8px 24px rgba(31,94,214,.08); }
.ph-card > span { display: block; margin-bottom: 8px; color: #367ef2; font-size: 11px; font-weight: 700; }
.ph-card strong { display: block; font-size: 16px; }
.ph-card p { margin: 8px 0 0; color: #667085; font-size: 13px; line-height: 1.6; }
.ph-article { margin-top: 18px; padding: 20px; border: 1px solid #e3e8f2; border-radius: 16px; background: #fff; }
.ph-back { padding: 0; border: 0; background: none; color: #367ef2; cursor: pointer; font: inherit; }
.ph-badges { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 18px; }
.ph-badges span { padding: 4px 8px; border-radius: 999px; background: #eef4ff; color: #275ebf; font-size: 11px; }
.ph-article h2 { margin: 12px 0 0; font-size: clamp(23px, 5vw, 32px); }
.ph-summary { margin: 10px 0 0; color: #5b6578; line-height: 1.75; }
.ph-entry { display: grid; gap: 5px; margin-top: 16px; padding: 13px 14px; border-radius: 12px; background: #f5f8fe; }
.ph-entry strong { font-size: 12px; color: #275ebf; }
.ph-entry span { font-size: 14px; }
.ph-entry small { color: #798397; word-break: break-all; }
.ph-section { margin-top: 22px; padding-top: 18px; border-top: 1px solid #edf0f5; }
.ph-section h3 { margin: 0 0 10px; font-size: 17px; }
.ph-section ul, .ph-section ol { margin: 0; padding-left: 22px; color: #485268; line-height: 1.75; }
.ph-section--warning { padding: 14px; border: 1px solid #f6dca2; border-radius: 12px; background: #fffaf0; }
.ph-section--success { padding: 14px; border: 1px solid #bfe6cf; border-radius: 12px; background: #f3fbf6; }
.ph-steps { list-style: none; padding-left: 0 !important; display: grid; gap: 11px; }
.ph-steps li { display: grid; grid-template-columns: 28px minmax(0,1fr); gap: 10px; align-items: start; }
.ph-steps li > span { display: grid; place-items: center; width: 26px; height: 26px; border-radius: 50%; background: #eef4ff; color: #275ebf; font-size: 12px; font-weight: 700; }
.ph-steps p { margin: 0; }
.ph-faq { padding: 10px 0; border-bottom: 1px solid #edf0f5; }
.ph-faq summary { cursor: pointer; font-weight: 600; }
.ph-faq p { margin: 8px 0 0; color: #5b6578; line-height: 1.7; }
.ph-empty { margin-top: 18px; padding: 28px 18px; text-align: center; border: 1px dashed #cfd8e8; border-radius: 14px; background: #fff; }
.ph-empty p { max-width: 620px; margin: 8px auto 14px; color: #667085; line-height: 1.7; }
.ph-empty button { min-height: 38px; padding: 0 14px; border: 0; border-radius: 9px; background: #367ef2; color: #fff; cursor: pointer; }
.ph-footer { margin-top: 24px; text-align: center; color: #8a94a6; font-size: 12px; }
@media (max-width: 720px) {
  .ph-hero { padding-top: 26px; }
  .ph-controls { grid-template-columns: 1fr; }
  .ph-grid { grid-template-columns: 1fr; }
  .ph-heading { display: block; }
  .ph-heading > p { margin-top: 7px; }
  .ph-article { padding: 16px; }
}
</style>
