/** 商用对标流程 · 学生端进度与导航 */
const NAV = {
  taskbook: '/pages/taskbook/taskbook',
  topicround: '/pages/topicround/topicround',
  parentconsent: '/pages/parentconsent/parentconsent',
  appraisal: '/pages/appraisal/appraisal',
  plagiarism: '/pages/plagiarism/plagiarism',
  internscore: '/pages/internscore/internscore',
  employment: '/pages/employment/employment',
  teachervisit: '/pages/teachervisit/teachervisit',
  urgehub: '/pages/urgehub/urgehub',
  reviewhub: '/pages/review/review',
  riskcomplaint: '/pages/risk/risk',
  asgchange: '/pages/assignment-change/assignment-change',
  insurancehub: '/pages/insurances/insurances',
  quality: '/pages/quality/quality',
  checkins: '/pages/checkin/checkin',
  agreements: '/pages/agreement/agreement',
  'gd-home': '/pages/topics/topics',
  'gd-achievements': '/pages/achievements/achievements'
};

function buildFlowSteps(bm) {
  if (!bm) return [];
  return [
    { key: 'taskbook', label: '任务书', url: NAV.taskbook, done: bm.taskBook === 'confirmed', pending: bm.taskBook === 'pending_confirm' || bm.taskBook === 'missing' },
    { key: 'topicround', label: '选题互选', url: NAV.topicround, done: !!bm.topicChoiceSubmitted, pending: !!(bm.topicRound && !bm.topicChoiceSubmitted) },
    { key: 'parentconsent', label: '家长知情', url: NAV.parentconsent, done: bm.parentConsent === 'approved', pending: ['missing', 'pending', 'rejected'].indexOf(bm.parentConsent) >= 0 },
    { key: 'appraisal', label: '实习鉴定', url: NAV.appraisal, done: bm.appraisal === 'approved', pending: ['missing', 'pending', 'rejected'].indexOf(bm.appraisal) >= 0 },
    { key: 'plagiarism', label: '查重检测', url: NAV.plagiarism, done: !!bm.plagiarismDone, pending: !bm.plagiarismDone },
    { key: 'internscore', label: '实习考评', url: NAV.internscore, done: bm.internScore === 'published', pending: bm.internScore === 'computed' || bm.internScore === 'none' },
    { key: 'employment', label: '就业去向', url: NAV.employment, done: bm.employment === 'filled', pending: bm.employment === 'missing' }
  ];
}

module.exports = { NAV, buildFlowSteps };
