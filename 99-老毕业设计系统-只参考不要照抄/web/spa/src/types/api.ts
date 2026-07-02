// 本文件由 openapi/spec.js 自动生成，请勿手改。生成：npm run gen:types
// 与后端 zod 契约一致，用于前端强类型对齐。

export interface ApiResp<T = any> { success: boolean; message?: string; code?: string; data: T; }

export interface LoginReq {
  username: string;
  password: string;
}

export interface RegisterReq {
  username: string;
  password: string;
  real_name: string;
  phone?: string;
  email?: string;
}

export interface StipendCreateReq {
  student_id: number;
  period: string;
  amount?: number;
  base_salary_ref?: number;
  method?: 'bank' | 'cash' | 'wechat' | 'alipay';
}

export interface ProvisionReq {
  code: string;
  name: string;
  plan?: 'trial' | 'standard' | 'pro';
  expire_date?: string;
  region?: string;
  contact_name?: string;
  contact_phone?: string;
}

export interface WfDispatchReq {
  action: string;
  remark?: string;
}

export interface User {
  id?: number;
  username?: string;
  realName?: string;
  role?: number;
  roleName?: string;
  collegeId?: number;
  eeid?: string;
  status?: number;
}

export interface Plan {
  code?: string;
  name?: string;
  price_year?: number;
  max_students?: number;
  max_storage_mb?: number;
  ai_monthly_quota?: number;
}

export interface Tenant {
  code?: string;
  name?: string;
  db_name?: string;
  plan?: string;
  expire_date?: string;
  status?: number;
  max_students?: number;
  ai_monthly_quota?: number;
}

export interface Stipend {
  id?: number;
  student_id?: number;
  period?: string;
  amount?: number;
  base_salary_ref?: number;
  status?: number;
  compliant?: boolean | null;
}

export interface WorkflowState {
  bizType?: string;
  bizId?: number;
  state?: string;
  stateName?: string;
  isEnd?: boolean;
  actions?: {
    action?: string;
    name?: string;
    to_state?: string;
  }[];
}

export interface RiskRadarDim {
  key?: string;
  label?: string;
  value?: number;
}

export interface Error {
  success?: boolean;
  code?: string;
  message?: string;
}

