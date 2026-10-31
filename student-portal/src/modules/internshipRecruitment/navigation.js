export const INTERNSHIP_TABS = [
  { key: 'overview', label: '我的实习' }, { key: 'notices', label: '通知公告' }, { key: 'consent', label: '知情确认' }, { key: 'agreement', label: '三方协议' },
  { key: 'checkin', label: '每日打卡' }, { key: 'leave', label: '实习请假' },
  { key: 'makeup', label: '补卡申请' }, { key: 'intention', label: '岗位意向' },
  { key: 'application', label: '正式申请' }, { key: 'change', label: '调岗退岗' },
  { key: 'enterprises', label: '企业岗位库' }, { key: 'insurance', label: '实习保险' },
  { key: 'plan', label: '实习计划' }, { key: 'help', label: '实习求助' },
  { key: 'report', label: '实习报告' }, { key: 'eval', label: '实习成绩/自评' },
  { key: 'selection', label: '实习选岗' }, { key: 'profile', label: '实习档案' }, { key: 'safety', label: '安全教育' }, { key: 'materials', label: '实习材料' }
]

export const INTERNSHIP_TAB_GROUPS = [
  { key:'onboard', label:'安排与入岗', keys:['overview','notices','consent','safety','agreement','insurance','plan'] },
  { key:'selection', label:'选岗与申请', keys:['selection','profile','intention','application'] },
  { key:'process', label:'在岗办理', keys:['checkin','leave','makeup','report','materials'] },
  { key:'change-result', label:'变更与结果', keys:['change','help','eval'] }
].map(group => ({...group,tabs:group.keys.map(key => INTERNSHIP_TABS.find(item => item.key === key))}))
