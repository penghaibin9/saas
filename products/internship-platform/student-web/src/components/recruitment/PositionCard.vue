<template>
  <button type="button" class="position-card" :class="{ 'is-selected': selected }" @click="$emit('select', position.id)">
    <div class="position-card__top">
      <strong class="position-card__title">{{ position.title }}</strong>
      <span class="position-card__salary">{{ position.remuneration }}</span>
    </div>
    <div class="position-card__company">
      <span>{{ position.companyName }}</span>
      <span v-if="position.companyVerified" class="verified">学校已核验</span>
    </div>
    <div class="position-card__location">{{ position.workLocation }}</div>
    <div class="position-card__tags">
      <span v-if="position.matchLabel" class="tag tag--match">{{ position.matchLabel }}</span>
      <span v-for="major in visibleMajors" :key="`major-${major}`" class="tag">{{ major }}</span>
      <span v-for="grade in visibleGrades" :key="`grade-${grade}`" class="tag">{{ grade }}</span>
      <span v-if="position.accommodation === true" class="tag">提供住宿</span>
      <span v-if="position.meal === true" class="tag">提供餐食</span>
      <span v-for="benefit in visibleBenefits" :key="`benefit-${benefit}`" class="tag">{{ benefit }}</span>
    </div>
    <div class="position-card__bottom">
      <span>剩余 {{ position.remaining }} 个名额</span>
      <span>{{ publishedText }}</span>
    </div>
  </button>
</template>

<script setup>
import { computed } from 'vue'
import { formatPublishedAt } from '../../modules/internshipRecruitment/positionModel'

const props = defineProps({
  position: { type: Object, required: true },
  selected: { type: Boolean, default: false }
})
defineEmits(['select'])

const visibleMajors = computed(() => (Array.isArray(props.position.majors) ? props.position.majors : []).slice(0, 2))
const visibleGrades = computed(() => (Array.isArray(props.position.grades) ? props.position.grades : []).slice(0, 1))
const visibleBenefits = computed(() => (Array.isArray(props.position.benefits) ? props.position.benefits : []).slice(0, 2))
const publishedText = computed(() => formatPublishedAt(props.position.publishedAt))
</script>

<style scoped>
.position-card { width:100%; padding:15px 16px; border:1px solid #eef0f3; border-radius:10px; background:#fff; text-align:left; cursor:pointer; transition:border-color .15s,box-shadow .15s,background .15s; }
.position-card:hover { border-color:#c6d7ff; box-shadow:0 4px 14px rgba(28,69,135,.06); }
.position-card.is-selected { border-color:#2f6bff; background:#f8fbff; box-shadow:0 0 0 2px rgba(47,107,255,.08); }
.position-card__top { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; }
.position-card__title { color:#1a1a1a; font-size:18px; line-height:1.35; }
.position-card__salary { flex-shrink:0; color:#fa541c; font-size:16px; font-weight:700; }
.position-card__company { display:flex; align-items:center; gap:7px; margin-top:7px; color:#444; font-size:13px; }
.verified { padding:1px 5px; border:1px solid #adc6ff; border-radius:4px; color:#2f6bff; font-size:11px; }
.position-card__location { margin-top:5px; color:#666; font-size:13px; }
.position-card__tags { display:flex; gap:6px; flex-wrap:wrap; margin-top:10px; }
.tag { padding:3px 7px; border-radius:4px; background:#f0f5ff; color:#34527a; font-size:12px; }
.tag--match { color:#234c91; font-weight:600; }
.position-card__bottom { display:flex; justify-content:space-between; gap:10px; margin-top:11px; color:#8c8c8c; font-size:12px; }
</style>
