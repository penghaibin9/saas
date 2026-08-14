import { defineStore } from 'pinia'
import { enterpriseInternshipApi } from '../services/enterpriseInternshipApi'

export const useEnterpriseContextStore = defineStore('enterpriseContext', {
  state: () => ({ schoolName:'', companyName:'', memberName:'', memberRole:'', campaign:null, loading:false, error:'' }),
  actions: {
    async load(){
      if (this.loading) return
      this.loading = true; this.error = ''
      try {
        const data = await enterpriseInternshipApi.context()
        this.schoolName=data?.schoolName||data?.school_name||''
        this.companyName=data?.companyName||data?.company_name||''
        this.memberName=data?.memberName||data?.member_name||''
        this.memberRole=data?.memberRole||data?.member_role||''
        this.campaign=data?.campaign||null
      } catch (error) { this.error=error?.message||'企业上下文加载失败' }
      finally { this.loading=false }
    },
  },
})
