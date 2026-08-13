/**
 * 帮助中心流程图素材索引。
 *
 * 每一张图都归属于已有帮助条目，不额外创建孤立目录；交互式 HTML 仍是正文，
 * PNG 用于快速扫读、移动端查看和在新窗口中放大。
 */
const asset = (module, filename) => `/help/images/${module}/${filename}`

const gallery = {
  'doc-aa-relationship-overview': [
    { title: '教务全景总览', src: asset('academic-affairs', 'academic-affairs-relationship-overview-preview.png'), primary: true },
    { title: '教务全景总览（手机阅读）', src: asset('academic-affairs', 'academic-affairs-relationship-overview-mobile.png'), mobile: true }
  ],
  'doc-aa-teaching-preparation-map': [{ title: '开课准备图解', src: asset('academic-affairs', 'academic-affairs-teaching-preparation-map-preview.png'), primary: true }],
  'doc-aa-schedule-selection-map': [{ title: '排课、选课与调停课图解', src: asset('academic-affairs', 'academic-affairs-schedule-selection-map-preview.png'), primary: true }],
  'doc-aa-exam-map': [{ title: '考务组织与异常分流图解', src: asset('academic-affairs', 'academic-affairs-exam-map-preview.png'), primary: true }],
  'doc-aa-grade-warning-map': [
    { title: '成绩发布、补考与预警图解', src: asset('academic-affairs', 'academic-affairs-grade-warning-map-preview.png'), primary: true },
    { title: '成绩流程（手机阅读）', src: asset('academic-affairs', 'academic-affairs-grade-warning-map-mobile.png'), mobile: true }
  ],
  'doc-aa-student-graduation-map': [{ title: '学籍、注册与毕业资格图解', src: asset('academic-affairs', 'academic-affairs-student-graduation-map-preview.png'), primary: true }],
  'doc-aa-quality-archive-map': [{ title: '教学保障、质量与归档图解', src: asset('academic-affairs', 'academic-affairs-quality-archive-map-preview.png'), primary: true }],

  'doc-gd-relationship-map': [
    { title: '毕业设计模块全景图', src: asset('graduation', 'graduation-detailed-final-preview.png'), primary: true },
    { title: '早期图解草案', src: asset('graduation', 'graduation-detailed-preview.png'), archive: true },
    { title: '图解迭代稿', src: asset('graduation', 'graduation-detailed-preview-v2.png'), archive: true }
  ],
  'doc-gd-topic-proposal-map': [
    { title: '选题、导师、任务书与开题图解', src: asset('graduation', 'graduation-topic-proposal-map-preview.png'), primary: true },
    { title: '选题流程（手机阅读）', src: asset('graduation', 'graduation-topic-proposal-map-mobile.png'), mobile: true }
  ],
  'doc-gd-guidance-midterm-map': [{ title: '过程指导与中期检查图解', src: asset('graduation', 'graduation-guidance-midterm-map-preview.png'), primary: true }],
  'doc-gd-final-defense-map': [{ title: '成果、答辩与成绩图解', src: asset('graduation', 'graduation-final-defense-map-preview.png'), primary: true }],
  'doc-gd-score-risk-archive-map': [{ title: '成绩异议、风险与归档图解', src: asset('graduation', 'graduation-score-risk-archive-map-preview.png'), primary: true }],
  'doc-gd-overview': [{ title: '毕业设计操作总览图', src: asset('graduation', 'graduation-design-preview.png'), primary: true }],

  'doc-in-relationship-map': [{ title: '岗位实习模块全景图', src: asset('internship', 'internship-module-map-preview.png'), primary: true }],
  'doc-in-start-onboarding-map': [
    { title: '批次、岗位、匹配与上岗图解', src: asset('internship', 'internship-start-onboarding-map-preview.png'), primary: true },
    { title: '上岗流程（手机阅读）', src: asset('internship', 'internship-start-onboarding-map-mobile.png'), mobile: true }
  ],
  'doc-in-daily-guidance-map': [{ title: '打卡、报告与指导巡访图解', src: asset('internship', 'internship-daily-guidance-map-preview.png'), primary: true }],
  'doc-in-risk-change-map': [{ title: '风险、调岗与整改单图解', src: asset('internship', 'internship-risk-change-map-preview.png'), primary: true }],
  'doc-in-score-archive-map': [{ title: '评价、归档与就业转化图解', src: asset('internship', 'internship-score-archive-map-preview.png'), primary: true }],
  'doc-in-overview': [
    { title: '岗位实习操作总览图', src: asset('internship', 'internship-detailed-preview.png'), primary: true },
    { title: '岗位实习总览（手机阅读）', src: asset('internship', 'internship-detailed-mobile-preview.png'), mobile: true }
  ],

  'doc-sa-relationship-overview': [
    { title: '学工全景总览', src: asset('student-affairs', 'sa-overview-preview.png'), primary: true },
    { title: '学工全景总览（手机阅读）', src: asset('student-affairs', 'sa-overview-mobile.png'), mobile: true }
  ],
  'doc-sa-campus-life-map': [
    { title: '迎新与在校服务图解', src: asset('student-affairs', 'sa-campus-preview.png'), primary: true },
    { title: '迎新与在校服务（手机阅读）', src: asset('student-affairs', 'sa-campus-mobile.png'), mobile: true }
  ],
  'doc-sa-risk-care-map': [{ title: '风险预警与关爱处置图解', src: asset('student-affairs', 'sa-risk-preview.png'), primary: true }],
  'doc-sa-growth-archive-map': [{ title: '资助成长与档案沉淀图解', src: asset('student-affairs', 'sa-growth-preview.png'), primary: true }],
  'doc-sa-overview': [{ title: '学工中心操作总览图', src: asset('student-affairs', 'student-affairs-preview.png'), primary: true }]
}

export function getHelpVisualGallery(id) {
  return gallery[id] || []
}
