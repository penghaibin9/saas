<template>
  <section v-if="questions.length" id="questions" class="reading-guide" aria-labelledby="reading-guide-title">
    <div class="guide-inner"><header><p>从你的工作开始了解</p><h2 id="reading-guide-title">选型前，先核对这三件事</h2><span>按业务范围浏览原介绍，再通过界面与演示确认具体需求。</span></header>
      <div class="guide-questions"><article v-for="question in questions" :key="question.q"><h3>{{ question.q }}</h3><p>{{ question.a }}</p><a :href="question.href">{{ question.link }} →</a></article></div>
      <nav class="guide-links" aria-label="产品延伸阅读"><a :href="'/news?product='+product.key">阅读与本产品相关的资讯 →</a><RouterLink to="/services/delivery">了解实施服务 →</RouterLink><RouterLink :to="{path:'/contact',query:{product:product.key}}">预约有针对性的演示 →</RouterLink></nav>
    </div>
  </section>
</template>
<script setup>
import { computed } from 'vue'
import { readingQuestions, publicProduct } from '../../services/officialSearchData.js'
const props=defineProps({path:{type:String,required:true}})
const product=computed(()=>publicProduct(props.path))
const questions=computed(()=>readingQuestions(props.path))
</script>
<style scoped>
.reading-guide{background:#fff;color:#172f49;scroll-margin-top:165px;padding:52px 0;border-bottom:1px solid #e2e9f1}.guide-inner{width:min(1280px,calc(100% - 80px));margin:auto}.reading-guide header>p{font-size:13px;font-weight:600;color:#2268df;margin:0 0 12px}.reading-guide h2{font-size:29px;line-height:1.5;margin:0 0 12px}.reading-guide header>span{color:#62768e;font-size:15px;line-height:1.8}.guide-questions{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:32px;margin-top:30px}.guide-questions article{padding-top:20px;border-top:2px solid #d7e4f5}.reading-guide h3{font-size:18px;line-height:1.7;margin:0 0 14px}.guide-questions p{font-size:14px;line-height:1.9;color:#526c85;overflow-wrap:anywhere;margin:0 0 20px}.reading-guide a{font-size:13px;color:#2268df;text-decoration:none;display:inline-block;min-height:44px;padding:10px 0}.guide-links{display:flex;flex-wrap:wrap;gap:12px 30px;margin-top:26px;border-top:1px solid #e2e9f1;padding-top:18px}@media(max-width:720px){.reading-guide{padding:36px 0;scroll-margin-top:145px}.guide-inner{width:calc(100% - 32px)}.reading-guide h2{font-size:25px}.guide-questions{grid-template-columns:1fr;gap:24px}.guide-links{display:grid;gap:0}.guide-questions p{margin-bottom:10px}}
</style>
