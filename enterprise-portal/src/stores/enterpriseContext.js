import { defineStore } from 'pinia'
import { enterpriseInternshipApi } from '../services/enterpriseInternshipApi'

export const useEnterpriseContextStore = defineStore('enterpriseContext', {
  state: () => ({ schoolName:'', companyName:'', memberName:'', memberRole:'', campaign:null, capabilities:{}, contextReady:false, loading:false, error:'' }),
  getters:{
    historyMode:(state)=>['CLOSED','ARCHIVED'].includes(String(state.campaign?.status||'')),
    recruitmentWritable:(state)=>state.contextReady && !['CLOSED','ARCHIVED'].includes(String(state.campaign?.status||'')) && state.capabilities?.recruitmentWrite !== false,
  },
  actions: {
    async load(){
      if (this.loading) return
      this.loading = true; this.error = ''; this.contextReady=false
      try {
        const data = await enterpriseInternshipApi.context()
        this.schoolName=data?.schoolName||data?.school_name||''
        this.companyName=data?.companyName||data?.company_name||''
        this.memberName=data?.memberName||data?.member_name||''
        this.memberRole=data?.memberRole||data?.member_role||''
        this.campaign=data?.campaign||null
        this.capabilities=data?.capabilities||{}
        this.contextReady=true
      } catch (error) { this.error=error?.message||'企业上下文加载失败' }
      finally { this.loading=false }
    },
  },
})
