import { defineStore } from 'pinia'
import { enterpriseInternshipApi } from '../services/enterpriseInternshipApi'
import { getSelectedCampaignId } from '../services/request'

export const useEnterpriseContextStore = defineStore('enterpriseContext', {
  state: () => ({ schoolName:'', companyName:'', memberName:'', memberRole:'', campaign:null, capabilities:{recruitmentWrite:false}, contextReady:false, loading:false, error:'' }),
  getters:{
    historyMode:(state)=>['CLOSED','ARCHIVED'].includes(String(state.campaign?.status||'')),
    recruitmentWritable:(state)=>state.contextReady&&state.capabilities?.recruitmentWrite===true&&!['CLOSED','ARCHIVED'].includes(String(state.campaign?.status||'')),
  },
  actions: {
    async load(){
      if(this.loading)return
      const campaignId=getSelectedCampaignId()
      if(!campaignId){this.contextReady=false;this.capabilities={recruitmentWrite:false};this.error='尚未选择招聘季，请先从企业登录后的招聘季列表进入。';return}
      this.loading=true;this.error='';this.contextReady=false;this.capabilities={recruitmentWrite:false}
      try{
        const authContext=await enterpriseInternshipApi.context(campaignId)
        this.memberRole=authContext?.memberRole||''
        this.campaign={id:authContext?.campaignId||campaignId,status:'OPEN'}
        this.capabilities={recruitmentWrite:authContext?.capabilities?.recruitmentWrite===true,internshipCollab:authContext?.capabilities?.internshipCollab===true}
        this.contextReady=true
        const [campaignResult,companyResult]=await Promise.allSettled([enterpriseInternshipApi.campaigns(),enterpriseInternshipApi.company()])
        if(campaignResult.status==='fulfilled'){
          const rows=Array.isArray(campaignResult.value)?campaignResult.value:(campaignResult.value?.items||[])
          const current=rows.find(item=>String(item.id||item.campaignId)===String(campaignId))
          if(current)this.campaign={...current,id:current.id||current.campaignId}
        }
        if(companyResult.status==='fulfilled')this.companyName=companyResult.value?.name||companyResult.value?.companyName||''
      }catch(error){this.contextReady=false;this.capabilities={recruitmentWrite:false};this.error=error?.message||'企业上下文加载失败'}finally{this.loading=false}
    },
  },
})
