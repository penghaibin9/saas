import { defineStore } from 'pinia'
import { enterpriseInternshipApi } from '../services/enterpriseInternshipApi'
import { getSelectedCampaignId } from '../services/request'

const APPLICATION_ROLES = new Set(['COMPANY_ADMIN','HR'])

function campaignFromAuthContext(authContext,campaignId){
  const campaign={ id:authContext?.campaignId||campaignId }
  if(authContext?.campaignName)campaign.campaignName=authContext.campaignName
  if(authContext?.campaignStatus)campaign.status=authContext.campaignStatus
  if(authContext?.batchId)campaign.batchId=authContext.batchId
  if(authContext?.phaseLabel)campaign.phaseLabel=authContext.phaseLabel
  if(authContext?.currentDeadlineAt)campaign.currentDeadlineAt=authContext.currentDeadlineAt
  if(authContext?.enterpriseDecisionDeadline)campaign.enterpriseDecisionDeadline=authContext.enterpriseDecisionDeadline
  return campaign
}

export const useEnterpriseContextStore = defineStore('enterpriseContext', {
  state: () => ({ schoolName:'', companyName:'', memberName:'', memberRole:'', campaign:null, capabilities:{recruitmentWrite:false,internshipCollab:false}, contextReady:false, loading:false, error:'' }),
  getters:{
    historyMode:(state)=>['CLOSED','ARCHIVED'].includes(String(state.campaign?.status||'')),
    recruitmentWritable:(state)=>state.contextReady&&state.capabilities?.recruitmentWrite===true&&!['CLOSED','ARCHIVED'].includes(String(state.campaign?.status||'')),
    internshipCollabReady:(state)=>state.contextReady&&state.capabilities?.internshipCollab===true&&Number(state.campaign?.batchId)>0,
    applicationViewAllowed:(state)=>state.contextReady&&APPLICATION_ROLES.has(String(state.memberRole||'').toUpperCase()),
    applicationReviewAllowed:(state)=>state.contextReady&&APPLICATION_ROLES.has(String(state.memberRole||'').toUpperCase()),
  },
  actions: {
    async load(){
      if(this.loading)return
      const campaignId=getSelectedCampaignId()
      if(!campaignId){this.contextReady=false;this.capabilities={recruitmentWrite:false,internshipCollab:false};this.campaign=null;this.error='尚未选择招聘季，请先从企业登录后的招聘季列表进入。';return}
      this.loading=true;this.error='';this.contextReady=false;this.capabilities={recruitmentWrite:false,internshipCollab:false}
      try{
        const authContext=await enterpriseInternshipApi.context(campaignId)
        this.memberRole=authContext?.memberRole||''
        this.campaign=campaignFromAuthContext(authContext,campaignId)
        this.capabilities={
          recruitmentWrite:authContext?.capabilities?.recruitmentWrite===true,
          internshipCollab:authContext?.capabilities?.internshipCollab===true,
        }
        this.contextReady=true
        const [campaignResult,companyResult]=await Promise.allSettled([enterpriseInternshipApi.campaigns(),enterpriseInternshipApi.company()])
        if(campaignResult.status==='fulfilled'){
          const rows=Array.isArray(campaignResult.value)?campaignResult.value:(campaignResult.value?.items||[])
          const current=rows.find(item=>String(item.id||item.campaignId)===String(campaignId))
          if(current)this.campaign={...this.campaign,...current,id:current.id||current.campaignId||this.campaign.id}
        }
        if(companyResult.status==='fulfilled')this.companyName=companyResult.value?.name||companyResult.value?.companyName||''
        if(!Number(this.campaign?.batchId))this.capabilities={...this.capabilities,internshipCollab:false}
      }catch(error){this.contextReady=false;this.capabilities={recruitmentWrite:false,internshipCollab:false};this.campaign=null;this.error=error?.message||'企业上下文加载失败'}finally{this.loading=false}
    },
  },
})
