<template>
  <div data-academic-page class="sp-page academic-prototype academic-directory">
    <AcademicPrototypeHeader title="全部教务事项" group="全部教务事项" description="查找本人教务服务，进入具体事项办理。" @refresh="search = ''" />
    <div class="stack"><div class="toolbar"><input v-model.trim="search" class="input" type="search" placeholder="搜索本人教务事项" aria-label="搜索本人教务事项" /><button class="btn">查找</button></div>
      <p v-if="!visibleItems.length" class="muted">没有找到匹配的教务事项，请调整关键词。</p>
      <div class="screen-list"><RouterLink v-for="item in visibleItems" :key="item.to" :to="item.to" class="service-btn"><span class="iconbox"><AcademicPrototypeIcon :name="item.icon" /></span><span><strong>{{ item.title }}</strong><small>{{ item.group }}</small></span></RouterLink></div>
    </div>
  </div>
</template>
<script setup>
import { computed, ref } from 'vue'
import AcademicPrototypeHeader from '../../components/academic/AcademicPrototypeHeader.vue'
import AcademicPrototypeIcon from '../../components/academic/AcademicPrototypeIcon.vue'
const search = ref('')
// 目录仅包含本人教务查询与申请，不包含教师管理动作。
const groups = [
  ['学业工作台', [['学业总览', '', 'house']]],
  ['注册与安排', [['学期注册','registration','id-card'],['我的课表','schedule','calendar-days'],['网上选课','selection','book-open'],['课堂考勤','attendance','clipboard-check'],['校历','calendar','calendar-days']]],
  ['成绩与考试', [['我的成绩','grades','chart-column'],['学生评教','evaluation','star'],['成绩复查','recheck','file-circle-question'],['考试与缓考','exam','file-lines'],['补考重修','makeup','arrows-rotate'],['清考结果','clearance','circle-check']]],
  ['培养与毕业', [['学籍与异动','status','address-card'],['学分修读','credits','chart-simple'],['学业预警','warning','triangle-exclamation'],['教材领用','textbook','book'],['等级考试','level-exam','medal'],['专业分流','major-split','code-branch'],['成绩认定','recognition','file-circle-check'],['毕业资格自查','graduation','graduation-cap']]]
]
const items = groups.flatMap(([group, entries]) => entries.map(([title,path,icon]) => ({ title, group, icon, to:'/academic' + (path ? '/' + path : '') })))
const visibleItems = computed(() => items.filter(item => !search.value || (item.title + item.group).includes(search.value)))
</script>
<style src="../../components/academic/studentAcademicPrototype.css"></style>
<style scoped>
.screen-list{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.service-btn{display:flex;gap:12px;padding:16px;background:var(--surface);border:1px solid var(--line);border-radius:9px;text-align:left;align-items:center;color:var(--ink)}.service-btn strong{display:block}.service-btn small{display:block;margin-top:3px}@media(max-width:900px){.screen-list{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){.screen-list{grid-template-columns:1fr}}
</style>
