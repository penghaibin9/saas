<template>
  <aside class="academic-context" aria-label="教务学业导航">
    <div class="academic-context__head">
      <span>当前模块</span>
      <strong>教务学业</strong>
      <p>按真实路由切换，不改变原业务页面、接口或状态。</p>
    </div>

    <label class="academic-context__search">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-3-3" />
      </svg>
      <input v-model.trim="keyword" placeholder="搜索教务事项" />
    </label>

    <nav class="academic-context__groups">
      <section v-for="group in visibleGroups" :key="group.label" class="academic-context__group">
        <h3>{{ group.label }}</h3>
        <button
          v-for="item in group.items"
          :key="item.path"
          type="button"
          class="academic-context__item"
          :class="{ 'is-active': isActive(item.path) }"
          :title="item.label"
          @click="router.push(item.path)"
        >
          <span>{{ item.label }}</span>
          <em v-if="item.tag">{{ item.tag }}</em>
        </button>
      </section>
    </nav>
  </aside>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const keyword = ref('')

const groups = [
  {
    label: '教务工作台',
    items: [{ path: '/academic', label: '教务总览', tag: '首页' }]
  },
  {
    label: '注册与安排',
    items: [
      { path: '/academic/registration', label: '学期注册' },
      { path: '/academic/schedule', label: '我的课表' },
      { path: '/academic/selection', label: '网上选课' },
      { path: '/academic/attendance', label: '课堂考勤' },
      { path: '/academic/calendar', label: '校历' }
    ]
  },
  {
    label: '成绩与考试',
    items: [
      { path: '/academic/grades', label: '我的成绩', tag: '高频' },
      { path: '/academic/evaluation', label: '学生评教' },
      { path: '/academic/recheck', label: '成绩复查' },
      { path: '/academic/exam', label: '考试与缓考' },
      { path: '/academic/makeup', label: '补考重修' },
      { path: '/academic/clearance', label: '清考结果' }
    ]
  },
  {
    label: '培养与毕业',
    items: [
      { path: '/academic/status', label: '学籍与异动' },
      { path: '/academic/credits', label: '学分修读' },
      { path: '/academic/warning', label: '学业预警' },
      { path: '/academic/textbook', label: '教材领用' },
      { path: '/academic/level-exam', label: '等级考试' },
      { path: '/academic/major-split', label: '专业分流' },
      { path: '/academic/recognition', label: '成绩认定' },
      { path: '/academic/graduation', label: '毕业资格自查' }
    ]
  },
  {
    label: '兼容入口',
    items: [{ path: '/academic/all', label: '全部旧功能', tag: '低频' }]
  }
]

const visibleGroups = computed(() => {
  const query = keyword.value.toLowerCase()
  if (!query) return groups
  return groups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => item.label.toLowerCase().includes(query))
    }))
    .filter((group) => group.items.length)
})

function isActive(path) {
  return route.path === path
}
</script>

<style scoped>
.academic-context {
  position: sticky;
  top: 0;
  align-self: start;
  width: 208px;
  max-height: calc(100vh - 116px);
  overflow-y: auto;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: linear-gradient(180deg, var(--surface, #fff) 0%, color-mix(in srgb, var(--pri) 2%, var(--surface, #fff)) 100%);
  box-shadow: 0 8px 24px rgba(31,48,86,.06);
}
.academic-context::-webkit-scrollbar { width: 5px; }
.academic-context::-webkit-scrollbar-thumb { border-radius: 5px; background: var(--line); }
.academic-context__head {
  padding: 14px;
  border: 1px solid var(--pri-100);
  border-radius: 13px;
  background: linear-gradient(135deg, var(--pri-50), color-mix(in srgb, var(--pri) 3%, var(--surface, #fff)));
}
.academic-context__head > span {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--pri-text, var(--pri));
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .1em;
}
.academic-context__head > span::before {
  content: "";
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--pri);
  box-shadow: 0 0 0 3px var(--pri-100);
}
.academic-context__head strong { display: block; margin-top: 7px; color: var(--t1); font-size: 19px; line-height: 1.2; }
.academic-context__head p { margin: 7px 0 0; color: var(--t3); font-size: 11.5px; line-height: 1.55; }
.academic-context__search {
  height: 40px;
  margin: 12px 2px 8px;
  padding: 0 11px;
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--surface, #fff);
  color: var(--t4);
  transition: border-color .15s ease, box-shadow .15s ease;
}
.academic-context__search:focus-within { border-color:var(--pri); box-shadow:0 0 0 3px var(--pri-50); }
.academic-context__search svg { width: 15px; height: 15px; flex: none; }
.academic-context__search input { width: 100%; border: 0; outline: 0; background: transparent; color: var(--t1); font-size: 12px; }
.academic-context__groups { padding-bottom: 4px; }
.academic-context__group h3 {
  margin: 16px 7px 7px;
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--t2);
  font-size: 12px;
  font-weight: 750;
  line-height: 1.2;
}
.academic-context__group h3::before {
  content: "";
  width: 3px;
  height: 13px;
  flex: none;
  border-radius: 3px;
  background: var(--pri);
}
.academic-context__group h3::after {
  content: "";
  height: 1px;
  flex: 1;
  background: var(--line2);
}
.academic-context__group:first-child h3 { margin-top: 10px; }
.academic-context__item {
  width: 100%;
  min-height: 38px;
  padding: 7px 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border: 1px solid transparent;
  border-radius: 9px;
  background: transparent;
  color: var(--t2);
  cursor: pointer;
  font-size: 12.5px;
  text-align: left;
  transition: background .15s ease, border-color .15s ease, color .15s ease, transform .15s ease;
}
.academic-context__item:hover {
  border-color: var(--pri-100);
  background: var(--pri-50);
  color: var(--pri-text, var(--pri));
  transform: translateX(2px);
}
.academic-context__item.is-active {
  border-color: color-mix(in srgb, var(--pri) 22%, var(--line));
  background: linear-gradient(90deg, var(--pri-100), var(--pri-50));
  color: var(--pri-text, var(--pri));
  font-weight: 750;
  box-shadow: 0 5px 14px rgba(var(--sp-primary-rgb),.10);
}
.academic-context__item em {
  flex: none;
  padding: 2px 7px;
  border: 1px solid var(--pri-100);
  border-radius: 8px;
  background: var(--surface, #fff);
  color: var(--pri-text, var(--pri));
  font-size: 9px;
  font-style: normal;
}

@media (max-width: 1180px) {
  .academic-context { width: 196px; }
}
@media (max-width: 820px) {
  .academic-context {
    position: static;
    width: 100%;
    max-height: none;
    padding: 10px;
  }
  .academic-context__head,
  .academic-context__search,
  .academic-context__group h3 { display: none; }
  .academic-context__groups { display: flex; gap: 7px; overflow-x: auto; }
  .academic-context__group { display: flex; gap: 7px; flex: none; }
  .academic-context__item { width: auto; min-width: max-content; min-height: 36px; padding: 0 12px; }
}
</style>
