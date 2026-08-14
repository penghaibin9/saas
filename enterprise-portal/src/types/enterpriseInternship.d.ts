export type CampaignStatus='DRAFT'|'OPEN'|'FROZEN'|'CLOSED'|'ARCHIVED'
export type PositionStatus='DRAFT'|'PENDING'|'PUBLISHED'|'OFFLINE'
export type EnterpriseDecisionStatus='INTERESTED'|'INTERVIEW'|'ACCEPT_INTENT'|'REJECTED'
export type VolunteerGroupStatus='DRAFT'|'SUBMITTED'|'LOCKED'|'NEEDS_REVISION'|'APPROVED'|'CLOSED'
export interface EnterpriseContext { schoolName:string; companyName:string; memberName:string; memberRole:'COMPANY_ADMIN'|'HR'|'MENTOR'; campaign?:{id:string|number;name:string;status:CampaignStatus;phaseLabel?:string;enterpriseDecisionDeadline?:string;schoolConfirmDeadline?:string} }
export interface EnterprisePositionSummary { id:string|number; name:string; status:PositionStatus; city?:string; headcount?:number; salaryDisplay?:string; applicantCount?:number; acceptIntentCount?:number; placementCount?:number; riskFlag?:boolean; updatedAt?:string }
export interface ApplicantSummary { applicationId:string|number; name:string; major?:string; grade?:string; positionName:string; volunteerNo:1|2|3; skillTags?:string[]; matchHint?:string; matchPercent?:number; appliedAt?:string; decisionStatus?:EnterpriseDecisionStatus; groupStatus?:VolunteerGroupStatus }
