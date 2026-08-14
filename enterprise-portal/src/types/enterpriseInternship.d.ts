export type CampaignStatus = 'DRAFT'|'OPEN'|'FROZEN'|'CLOSED'|'ARCHIVED'
export type PositionStatus = 'DRAFT'|'PENDING'|'PUBLISHED'|'OFFLINE'|'SUSPENDED'|'FULL'|'RISK'|'ARCHIVED'
export type EnterpriseDecisionStatus = 'INTERESTED'|'INTERVIEW'|'ACCEPT_INTENT'|'REJECTED'
export type EnterpriseDecisionEffectStatus = 'ACTIVE'|'EXPIRED'|'SUPERSEDED'|'CONSUMED'
export type VolunteerGroupStatus = 'DRAFT'|'SUBMITTED'|'LOCKED'|'NEEDS_REVISION'|'APPROVED'|'CLOSED'
export type EnterpriseMemberRole = 'COMPANY_ADMIN'|'HR'|'MENTOR'
export type ContactSharingMode = 'MASKED_ONLY'|'AFTER_INTERVIEW'|'AFTER_ACCEPT_INTENT'|'IMMEDIATE'

export interface EnterpriseCampaignContext {
  id:string|number
  name:string
  status:CampaignStatus
  phaseLabel?:string
  enterpriseDecisionDeadline?:string
  schoolConfirmDeadline?:string
}

export interface EnterpriseContext {
  schoolName:string
  companyName:string
  memberName:string
  memberRole:EnterpriseMemberRole
  campaign?:EnterpriseCampaignContext
  capabilities?:{ recruitmentWrite?:boolean; internshipCollab?:boolean }
}

export interface EnterpriseCompanyEditable {
  logoFileId?:number|null
  coverFileId?:number|null
  shortName?:string
  shortIntro?:string
  website?:string
  mainBusiness?:string
  establishedYear?:number|null
  address?:string
}

export interface EnterprisePositionEditable {
  title:string
  category?:string
  majorRequirement?:string
  gradeRequirement?:string
  workLocation?:string
  headcount:number
  mentorContactId?:number|null
  workContent?:string
  workAddress?:string
  dailyHours?:number|null
  weeklyHours?:number|null
  shiftType?:string
  nightShift?:boolean
  overtimeAllowed?:boolean
  restDaysPerWeek?:number|null
  remunerationType?:string
  remunerationAmount?:number|null
  remunerationCycle?:string
  salaryRange?:string
  subsidy?:string
  accommodationProvided?:boolean
  mealProvided?:boolean
  hazardousFlag?:boolean
  specialEquipment?:string
  prohibitedReason?:string
  remark?:string
}

export interface EnterprisePositionSummary {
  id:string|number
  title:string
  status:PositionStatus
  workLocation?:string
  headcount?:number
  salaryRange?:string
  applicantCount?:number
  acceptIntentCount?:number
  placementCount?:number
  riskFlag?:boolean
  updatedAt?:string
}

export interface ApplicantSummary {
  applicationId:string|number
  name:string
  major?:string
  grade?:string
  positionName:string
  volunteerNo:1|2|3
  skillTags?:string[]
  matchHint?:string
  matchPercent?:number
  appliedAt?:string
  decisionStatus?:EnterpriseDecisionStatus
  decisionEffectStatus?:EnterpriseDecisionEffectStatus
  decisionReason?:string|null
  decisionValidUntil?:string|null
  acceptIntentReleased?:boolean
  volunteerGroupStatus?:VolunteerGroupStatus
}

export interface ApplicationMaterialProjection {
  applicationStatement?:string
  skillTags?:string[]
  projects?:unknown[]
  practices?:unknown[]
  certificates?:unknown[]
  portfolio?:unknown[]
  generatedProfilePdfFileId?:number|null
  contactSharingMode?:ContactSharingMode
}
