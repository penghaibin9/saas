from pathlib import Path

path = Path("miniapp/src/pages/teacher/academic-affairs/attendance.vue")
text = path.read_text(encoding="utf-8")

old = '''          <picker mode="date" :value="form.sessionDate" @change="onDateChange">\n            <view class="at__input at__date">{{ form.sessionDate || '选择考勤日期（必填）' }}</view>\n          </picker>\n'''
new = '''          <picker mode="date" :value="form.sessionDate" @change="onDateChange">\n            <view class="at__input at__date">{{ form.sessionDate || '选择考勤日期（必填）' }}</view>\n          </picker>\n          <text v-if="selectedPattern" class="at__source-note">所选节次来自当前正式课表；具体日期仍以校历、调课与补课实时校验为准。</text>\n'''
if old not in text:
    raise SystemExit("calendar authority note anchor missing")
text = text.replace(old, new, 1)

old = '''    formalPatternLabels() {\n      return this.formalPatterns.map((pattern) => {\n        const parity = pattern.weekParity === 'ODD' ? '单周' : pattern.weekParity === 'EVEN' ? '双周' : '每周'\n        return `周${pattern.weekday} · 第${pattern.slotNo}节 · ${pattern.startWeek}-${pattern.endWeek}周 ${parity}`\n      })\n    },\n'''
new = '''    formalPatternLabels() {\n      const weekdayLabels = ['', '一', '二', '三', '四', '五', '六', '日']\n      return this.formalPatterns.map((pattern) => {\n        const parity = pattern.weekParity === 'ODD' ? '单周' : pattern.weekParity === 'EVEN' ? '双周' : '每周'\n        const weekday = weekdayLabels[Number(pattern.weekday)] || String(pattern.weekday || '?')\n        return `周${weekday} · 第${pattern.slotNo}节 · ${pattern.startWeek}-${pattern.endWeek}周 ${parity}`\n      })\n    },\n'''
if old not in text:
    raise SystemExit("weekday label anchor missing")
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
