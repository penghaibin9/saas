<template>
  <view class="school-service" :class="{ 'is-compact': compact, 'is-expanded': expanded }">
    <button v-if="compact" class="school-service-toggle" :aria-expanded="expanded" @click="expanded=!expanded">{{ expanded ? '收起帮助' : '咨询与帮助' }}</button>
    <view v-else class="school-service-head" @click="expanded=!expanded"><view class="school-service-brand"><image v-if="logoUrl" :src="logoUrl" class="school-service-logo" mode="aspectFit" aria-label="学校校徽" @error="logoFailed"/><text>{{ config?.brand?.platformName || '学校实习服务' }}</text></view><text>{{ expanded ? '收起' : '咨询与帮助' }}</text></view>
    <text v-if="logoError && (!compact || expanded)" class="school-service-line">{{ logoError }}</text>
    <view v-if="expanded">
      <image v-if="compact && logoUrl" :src="logoUrl" class="school-service-logo" mode="aspectFit" aria-label="学校校徽" @error="logoFailed" />
      <text v-if="error" class="school-service-line">{{ error }}</text>
      <button v-if="error" size="mini" @click="load">重新读取</button>
      <template v-else-if="config"><text class="school-service-line">{{ config.brand.schoolName }}</text><text class="school-service-line">{{ config.service.reminderText }}</text><text class="school-service-line">咨询电话：{{ config.service.contactPhone || '学校尚未配置' }}</text><text v-if="config.service.supervisionPhone" class="school-service-line">监督电话：{{ config.service.supervisionPhone }}</text><text v-if="config.service.responsibleName" class="school-service-line">承办人：{{ config.service.responsibleName }}</text><view v-for="item in config.service.faq" :key="item.question"><text class="school-service-question">{{ item.question }}</text><text class="school-service-line">{{ item.answer }}</text></view></template>
    </view>
  </view>
</template>
<script>
import { realRequest } from '@/services/request'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import fileSdk from '@/services/fileSdk'
import { loadReportMedia, releasePreview } from '@/services/reportMedia.mjs'
export default {
  props:{compact:{type:Boolean,default:false}},
  data:()=>({config:null,error:'',logoUrl:'',logoError:'',expanded:false,sequence:0}),
  mounted(){this.load()},beforeUnmount(){this.sequence++;this.clearLogo()},
  methods:{
    clearLogo(){releasePreview(this.logoUrl);this.logoUrl=''},
    logoFailed(){this.clearLogo();this.logoError='学校校徽暂时无法读取，学校服务仍可使用。'},
    async load(){
      const run=++this.sequence,generation=currentSessionGeneration(),current=()=>run===this.sequence && generation===currentSessionGeneration()
      this.error='';this.config=null;this.logoError='';this.clearLogo()
      try{
        const result=await realRequest('/system/school-service');if(!current())return;this.config=result
        if(result.brand?.logoFileId){
          try{
            const logo=await loadReportMedia({fileId:result.brand.logoFileId},fileSdk,current)
            if(!logo)return
            if(logo.kind!=='image'){releasePreview(logo.url);throw new Error('校徽类型无效')}
            if(current())this.logoUrl=logo.url;else releasePreview(logo.url)
          }catch{if(current())this.logoFailed()}
        }
      }catch{if(current())this.error='学校服务暂时无法读取，请重试'}
    }
  }
}
</script>
<style scoped>.school-service{margin:12px 16px;padding:14px;border:1px solid #dbe5f0;background:#fff;border-radius:10px}.school-service-head{display:flex;align-items:center;justify-content:space-between;gap:12px;font-size:12px;color:#275eab}.school-service-brand{display:flex;align-items:center;gap:8px;min-width:0}.school-service-logo{width:32px;height:32px;flex-shrink:0}.school-service-head>text{flex-shrink:0}.school-service-line{display:block;font-size:13px;color:#475569;line-height:1.8;margin-top:8px}.school-service-question{display:block;font-size:13px;font-weight:600;margin-top:14px}.school-service.is-compact{margin:0 16px 8px;padding:0;border:0;background:transparent}.school-service.is-compact.is-expanded{padding:12px;border:1px solid var(--border-base);background:var(--bg-card)}.school-service-toggle{display:block;width:auto;min-height:var(--touch-target-min);margin:0 0 0 auto;padding:0 8px;border:0;background:transparent;color:var(--text-link);font-size:var(--font-size-sm);line-height:var(--touch-target-min)}.school-service-toggle::after{border:0}</style>
