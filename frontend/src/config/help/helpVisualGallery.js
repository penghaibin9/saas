/**
 * 帮助中心流程图素材索引。
 *
 * 每一张图都归属于已有帮助条目，不额外创建孤立目录；交互式 HTML 仍是正文，
 * PNG 用于快速扫读、移动端查看和在新窗口中放大。
 */
const asset = (module, filename) => `/help/images/${module}/${filename}`

const gallery = {
  'aa-v3-teaching-task': [{ title: '开课准备图解', src: asset('academic-affairs', 'academic-affairs-teaching-preparation-map-preview.png'), primary: true }],
  'aa-v3-schedule': [{ title: '排课、选课与调停课图解', src: asset('academic-affairs', 'academic-affairs-schedule-selection-map-preview.png'), primary: true }],
  'aa-card-exam-arrangement': [{ title: '考务组织与异常分流图解', src: asset('academic-affairs', 'academic-affairs-exam-map-preview.png'), primary: true }],
  'aa-card-grade-review-publish': [
    { title: '成绩发布、补考与预警图解', src: asset('academic-affairs', 'academic-affairs-grade-warning-map-preview.png'), primary: true },
    { title: '成绩流程（手机阅读）', src: asset('academic-affairs', 'academic-affairs-grade-warning-map-mobile.png'), mobile: true }
  ],
  'aa-v3-graduation-qualification': [{ title: '学籍、注册与毕业资格图解', src: asset('academic-affairs', 'academic-affairs-student-graduation-map-preview.png'), primary: true }],
  'aa-v3-program-course': [
    { title: '教务全景总览', src: asset('academic-affairs', 'academic-affairs-relationship-overview-preview.png'), primary: true },
    { title: '教务全景总览（手机阅读）', src: asset('academic-affairs', 'academic-affairs-relationship-overview-mobile.png'), mobile: true },
    { title: '教学保障、质量与归档图解', src: asset('academic-affairs', 'academic-affairs-quality-archive-map-preview.png') }
  ],

  'gd-v3-batch-setup': [
    { title: '毕业设计模块全景图', src: asset('graduation', 'graduation-detailed-final-preview.png'), primary: true },
    { title: '毕业设计操作总览图', src: asset('graduation', 'graduation-design-preview.png') },
    { title: '早期图解草案', src: asset('graduation', 'graduation-detailed-preview.png'), archive: true },
    { title: '图解迭代稿', src: asset('graduation', 'graduation-detailed-preview-v2.png'), archive: true }
  ],
  'gd-v2-topic-selection': [
    { title: '选题、导师、任务书与开题图解', src: asset('graduation', 'graduation-topic-proposal-map-preview.png'), primary: true },
    { title: '选题流程（手机阅读）', src: asset('graduation', 'graduation-topic-proposal-map-mobile.png'), mobile: true }
  ],
  'gd-v3-guidance-midterm': [{ title: '过程指导与中期检查图解', src: asset('graduation', 'graduation-guidance-midterm-map-preview.png'), primary: true }],
  'gd-v2-defense': [{ title: '成果、答辩与成绩图解', src: asset('graduation', 'graduation-final-defense-map-preview.png'), primary: true }],
  'gd-v3-archive': [{ title: '成绩异议、风险与归档图解', src: asset('graduation', 'graduation-score-risk-archive-map-preview.png'), primary: true }],

  'in-v3-batch-lifecycle': [
    { title: '岗位实习模块全景图', src: asset('internship', 'internship-module-map-preview.png'), primary: true },
    { title: '岗位实习操作总览图', src: asset('internship', 'internship-detailed-preview.png') },
    { title: '岗位实习总览（手机阅读）', src: asset('internship', 'internship-detailed-mobile-preview.png'), mobile: true }
  ],
  'in-v3-onboard-compliance': [
    { title: '批次、岗位、匹配与上岗图解', src: asset('internship', 'internship-start-onboarding-map-preview.png'), primary: true },
    { title: '上岗流程（手机阅读）', src: asset('internship', 'internship-start-onboarding-map-mobile.png'), mobile: true }
  ],
  'in-v2-teacher-process': [{ title: '打卡、报告与指导巡访图解', src: asset('internship', 'internship-daily-guidance-map-preview.png'), primary: true }],
  'in-v3-risk-incident': [{ title: '风险、调岗与整改单图解', src: asset('internship', 'internship-risk-change-map-preview.png'), primary: true }],
  'in-v3-archive': [{ title: '评价、归档与就业转化图解', src: asset('internship', 'internship-score-archive-map-preview.png'), primary: true }],

  'sa-v3-leave-lifecycle': [
    { title: '学工全景总览', src: asset('student-affairs', 'sa-overview-preview.png'), primary: true },
    { title: '学工全景总览（手机阅读）', src: asset('student-affairs', 'sa-overview-mobile.png'), mobile: true },
    { title: '学工中心操作总览图', src: asset('student-affairs', 'student-affairs-preview.png') }
  ],
  'sa-v3-discipline': [
    { title: '迎新与在校服务图解', src: asset('student-affairs', 'sa-campus-preview.png'), primary: true },
    { title: '迎新与在校服务（手机阅读）', src: asset('student-affairs', 'sa-campus-mobile.png'), mobile: true }
  ],
  'sa-v3-care-risk': [{ title: '风险预警与关爱处置图解', src: asset('student-affairs', 'sa-risk-preview.png'), primary: true }],
  'sa-v3-aid-funding': [{ title: '资助成长与档案沉淀图解', src: asset('student-affairs', 'sa-growth-preview.png'), primary: true }]
}

export function getHelpVisualGallery(id) {
  return gallery[id] || []
}
