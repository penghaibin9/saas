import { defineStore } from 'pinia'
import { enterpriseInternshipApi, setEnterpriseApiContext } from '../services/enterpriseInternshipApi'
import { getSelectedCampaignId } from '../services/request'

const APPLICATION_ROLES = new Set(['COMPANY_ADMIN','HR'])

function campaignFromAuthContext(authContext,campaignId){
  const campaign={id:authContext?.campaignId||campaignId}
  if(authContext?.campaignName)campaign.campaignName=authContext.campaignName
  if(authContext?.campaignStatus)campaign.status=authContext.campaignStatus
  if(authContext?.batchId)campaign.batchId=authContext.batchId
  if(authContext?.phaseLabel)campaign.phaseLabel=authContext.phaseLabel
  if(authContext?.currentDeadlineAt)campaign.currentDeadlineAt=authContext.currentDeadlineAt
  if(authContext?.enterpriseDecisionDeadline)campaign.enterpriseDecisionDeadline=authContext.enterpriseDecisionDeadline
  return campaign
}
function campaignRows(data){return Array.isArray(data)?data:(Array.isArray(data?.items)?data.items:[])}
function findCampaign(data,campaignId){return campaignRows(data).find(item=>String(item.id||item.campaignId)===String(campaignId))||null}

export const useEnterpriseContextStore=defineStore('enterpriseContext',{
  state:()=>({schoolName:'',companyName:'',memberName:'',memberRole:'',campaign:null,contextMode:'NONE',capabilities:{recruitmentWrite:false,internshipCollab:false},contextReady:false,loading:false,error:''}),
  getters:{
    historyMode:(state)=>['CLOSED','ARCHIVED'].includes(String(state.campaign?.status||'')),
    recruitmentContextReady:(state)=>state.contextReady&&state.contextMode==='RECRUITMENT',
    recruitmentWritable:(state)=>state.contextReady&&state.contextMode==='RECRUITMENT'&&state.capabilities?.recruitmentWrite===true&&!['CLOSED','ARCHIVED'].includes(String(state.campaign?.status||'')),
    internshipCollabReady:(state)=>state.contextReady&&state.capabilities?.internshipCollab===true&&Number(state.campaign?.batchId)>0,
    applicationViewAllowed:(state)=>state.contextReady&&state.contextMode==='RECRUITMENT'&&APPLICATION_ROLES.has(String(state.memberRole||'').toUpperCase()),
    applicationReviewAllowed:(state)=>state.contextReady&&state.contextMode==='RECRUITMENT'&&APPLICATION_ROLES.has(String(state.memberRole||'').toUpperCase()),
  },
  actions:{
    async load(){
      if(this.loading)return
      const campaignId=getSelectedCampaignId()
      if(!campaignId){this.contextReady=false;this.contextMode='NONE';this.capabilities={recruitmentWrite:false,internshipCollab:false};this.campaign=null;setEnterpriseApiContext('NONE',0);this.error='尚未选择招聘季，请先从企业登录后的招聘季列表进入。';return}
      this.loading=true;this.error='';this.contextReady=false;this.contextMode='NONE';this.capabilities={recruitmentWrite:false,internshipCollab:false};this.campaign=null;setEnterpriseApiContext('NONE',0)
      try{
        const campaigns=await enterpriseInternshipApi.campaigns()
        const selected=findCampaign(campaigns,campaignId)
        const selectedBatchId=Number(selected?.batchId||0)
        if(selected)this.campaign={...selected,id:selected.id||selected.campaignId||campaignId}

        let authContext=null,mode='NONE',recruitmentError=null
        try{authContext=await enterpriseInternshipApi.context(campaignId);mode='RECRUITMENT'}catch(error){recruitmentError=error}
        if(!authContext&&Number.isInteger(selectedBatchId)&&selectedBatchId>0){
          try{authContext=await enterpriseInternshipApi.collaborationContext(selectedBatchId);mode='COLLABORATION'}catch{/* fail closed below */}
        }
        if(!authContext)throw recruitmentError||new Error('当前企业没有可用的招聘或实习协同授权')

        this.contextMode=mode
        this.memberRole=authContext?.memberRole||''
        const fromAuth=campaignFromAuthContext(authContext,campaignId)
        this.campaign={...(this.campaign||{}),...fromAuth,id:(this.campaign?.id||fromAuth.id||campaignId)}
        if(!this.campaign?.batchId&&selectedBatchId>0)this.campaign.batchId=String(selectedBatchId)
        const serverCapabilities={recruitmentWrite:authContext?.capabilities?.recruitmentWrite===true,internshipCollab:authContext?.capabilities?.internshipCollab===true}
        this.capabilities={recruitmentWrite:mode==='RECRUITMENT'&&serverCapabilities.recruitmentWrite,internshipCollab:serverCapabilities.internshipCollab}
        if(!Number(this.campaign?.batchId))this.capabilities={...this.capabilities,internshipCollab:false}
        this.contextReady=true
        setEnterpriseApiContext(mode,this.campaign?.batchId)

        // UX gates mirror server permissions only. Every backend request still revalidates member,
        // tenant, company, campaign/batch and active Grant scope before returning or mutating data.
        try{const company=await enterpriseInternshipApi.company();this.companyName=company?.name||company?.companyName||''}catch{this.companyName=''}
      }catch(error){
        this.contextReady=false;this.contextMode='NONE';this.capabilities={recruitmentWrite:false,internshipCollab:false};this.campaign=null;setEnterpriseApiContext('NONE',0);this.error=error?.message||'企业上下文加载失败'
      }finally{this.loading=false}
    },
  },
})
