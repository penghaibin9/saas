/**
 * 甯姪涓績娴佺▼鍥剧礌鏉愮储寮曘€?
 *
 * 姣忎竴寮犲浘閮藉綊灞炰簬宸叉湁甯姪鏉＄洰锛屼笉棰濆鍒涘缓瀛ょ珛鐩綍锛涗氦浜掑紡 HTML 浠嶆槸姝ｆ枃锛?
 * PNG 鐢ㄤ簬蹇€熸壂璇汇€佺Щ鍔ㄧ鏌ョ湅鍜屽湪鏂扮獥鍙ｄ腑鏀惧ぇ銆?
 */
const asset = (module, filename) => `/help/images/${module}/${filename}`

const gallery = {
  'aa-v3-teaching-task': [{ title: '寮€璇惧噯澶囧浘瑙?, src: asset('academic-affairs', 'academic-affairs-teaching-preparation-map-preview.png'), primary: true }],
  'aa-v3-schedule': [{ title: '鎺掕銆侀€夎涓庤皟鍋滆鍥捐В', src: asset('academic-affairs', 'academic-affairs-schedule-selection-map-preview.png'), primary: true }],
  'aa-card-exam-arrangement': [{ title: '鑰冨姟缁勭粐涓庡紓甯稿垎娴佸浘瑙?, src: asset('academic-affairs', 'academic-affairs-exam-map-preview.png'), primary: true }],
  'aa-card-grade-review-publish': [
    { title: '鎴愮哗鍙戝竷銆佽ˉ鑰冧笌棰勮鍥捐В', src: asset('academic-affairs', 'academic-affairs-grade-warning-map-preview.png'), primary: true },
    { title: '鎴愮哗娴佺▼锛堟墜鏈洪槄璇伙級', src: asset('academic-affairs', 'academic-affairs-grade-warning-map-mobile.png'), mobile: true }
  ],
  'aa-v3-graduation-qualification': [{ title: '瀛︾睄銆佹敞鍐屼笌姣曚笟璧勬牸鍥捐В', src: asset('academic-affairs', 'academic-affairs-student-graduation-map-preview.png'), primary: true }],
  'aa-v3-program-course': [
    { title: '鏁欏姟鍏ㄦ櫙鎬昏', src: asset('academic-affairs', 'academic-affairs-relationship-overview-preview.png'), primary: true },
    { title: '鏁欏姟鍏ㄦ櫙鎬昏锛堟墜鏈洪槄璇伙級', src: asset('academic-affairs', 'academic-affairs-relationship-overview-mobile.png'), mobile: true },
    { title: '鏁欏淇濋殰銆佽川閲忎笌褰掓。鍥捐В', src: asset('academic-affairs', 'academic-affairs-quality-archive-map-preview.png') }
  ],

  'gd-v3-batch-setup': [
    { title: '姣曚笟璁捐妯″潡鍏ㄦ櫙鍥?, src: asset('graduation', 'graduation-detailed-final-preview.png'), primary: true },
    { title: '姣曚笟璁捐鎿嶄綔鎬昏鍥?, src: asset('graduation', 'graduation-design-preview.png') },
    { title: '鏃╂湡鍥捐В鑽夋', src: asset('graduation', 'graduation-detailed-preview.png'), archive: true },
    { title: '鍥捐В杩唬绋?, src: asset('graduation', 'graduation-detailed-preview-v2.png'), archive: true }
  ],
  'gd-v2-topic-selection': [
    { title: '閫夐銆佸甯堛€佷换鍔′功涓庡紑棰樺浘瑙?, src: asset('graduation', 'graduation-topic-proposal-map-preview.png'), primary: true },
    { title: '閫夐娴佺▼锛堟墜鏈洪槄璇伙級', src: asset('graduation', 'graduation-topic-proposal-map-mobile.png'), mobile: true }
  ],
  'gd-v3-guidance-midterm': [{ title: '杩囩▼鎸囧涓庝腑鏈熸鏌ュ浘瑙?, src: asset('graduation', 'graduation-guidance-midterm-map-preview.png'), primary: true }],
  'gd-v2-defense': [{ title: '鎴愭灉銆佺瓟杈╀笌鎴愮哗鍥捐В', src: asset('graduation', 'graduation-final-defense-map-preview.png'), primary: true }],
  'gd-v3-archive': [{ title: '鎴愮哗寮傝銆侀闄╀笌褰掓。鍥捐В', src: asset('graduation', 'graduation-score-risk-archive-map-preview.png'), primary: true }],

  'in-v3-batch-lifecycle': [
    { title: '宀椾綅瀹炰範妯″潡鍏ㄦ櫙鍥?, src: asset('internship', 'internship-module-map-preview.png'), primary: true },
    { title: '宀椾綅瀹炰範鎿嶄綔鎬昏鍥?, src: asset('internship', 'internship-detailed-preview.png') },
    { title: '宀椾綅瀹炰範鎬昏锛堟墜鏈洪槄璇伙級', src: asset('internship', 'internship-detailed-mobile-preview.png'), mobile: true }
  ],
  'in-v3-onboard-compliance': [
    { title: '鎵规銆佸矖浣嶃€佸尮閰嶄笌涓婂矖鍥捐В', src: asset('internship', 'internship-start-onboarding-map-preview.png'), primary: true },
    { title: '涓婂矖娴佺▼锛堟墜鏈洪槄璇伙級', src: asset('internship', 'internship-start-onboarding-map-mobile.png'), mobile: true }
  ],
  'in-v2-teacher-process': [{ title: '鎵撳崱銆佹姤鍛婁笌鎸囧宸¤鍥捐В', src: asset('internship', 'internship-daily-guidance-map-preview.png'), primary: true }],
  'in-v3-risk-incident': [{ title: '椋庨櫓銆佽皟宀椾笌鏁存敼鍗曞浘瑙?, src: asset('internship', 'internship-risk-change-map-preview.png'), primary: true }],
  'in-v3-archive': [{ title: '璇勪环銆佸綊妗ｄ笌灏变笟杞寲鍥捐В', src: asset('internship', 'internship-score-archive-map-preview.png'), primary: true }],

  'sa-v3-leave-lifecycle': [
    { title: '瀛﹀伐鍏ㄦ櫙鎬昏', src: asset('student-affairs', 'sa-overview-preview.png'), primary: true },
    { title: '瀛﹀伐鍏ㄦ櫙鎬昏锛堟墜鏈洪槄璇伙級', src: asset('student-affairs', 'sa-overview-mobile.png'), mobile: true },
    { title: '瀛﹀伐涓績鎿嶄綔鎬昏鍥?, src: asset('student-affairs', 'student-affairs-preview.png') }
  ],
  'sa-v3-discipline': [
    { title: '杩庢柊涓庡湪鏍℃湇鍔″浘瑙?, src: asset('student-affairs', 'sa-campus-preview.png'), primary: true },
    { title: '杩庢柊涓庡湪鏍℃湇鍔★紙鎵嬫満闃呰锛?, src: asset('student-affairs', 'sa-campus-mobile.png'), mobile: true }
  ],
  'sa-v3-care-risk': [{ title: '椋庨櫓棰勮涓庡叧鐖卞缃浘瑙?, src: asset('student-affairs', 'sa-risk-preview.png'), primary: true }],
  'sa-v3-aid-funding': [{ title: '璧勫姪鎴愰暱涓庢。妗堟矇娣€鍥捐В', src: asset('student-affairs', 'sa-growth-preview.png'), primary: true }]
}

export function getHelpVisualGallery(id) {
  return gallery[id] || []
}

