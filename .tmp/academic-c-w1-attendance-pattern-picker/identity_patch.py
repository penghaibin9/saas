from pathlib import Path

path = Path("miniapp/src/pages/teacher/academic-affairs/attendance.vue")
text = path.read_text(encoding="utf-8")

old = '''      form: { teachingTaskId: '', classId: '', sessionDate: '', slotNo: '', sessionType: '' },\n'''
new = '''      form: { teachingTaskId: '', classId: '', sessionDate: '', slotNo: '', scheduleItemId: '', sessionType: '' },\n'''
if old not in text:
    raise SystemExit("form scheduleItemId anchor missing")
text = text.replace(old, new, 1)

old = '''      this.form.teachingTaskId = task ? task.teachingTaskId : ''\n      this.form.classId = task ? task.classId : ''\n      this.patternIndex = -1\n      this.form.slotNo = ''\n'''
new = '''      this.form.teachingTaskId = task ? task.teachingTaskId : ''\n      this.form.classId = task ? task.classId : ''\n      this.patternIndex = -1\n      this.form.slotNo = ''\n      this.form.scheduleItemId = ''\n'''
if old not in text:
    raise SystemExit("applyTask scheduleItem reset anchor missing")
text = text.replace(old, new, 1)

old = '''      this.patternIndex = patternIndex\n      this.form.sessionDate = seed.sessionDate\n      this.form.slotNo = String(this.formalPatterns[patternIndex].slotNo)\n'''
new = '''      this.patternIndex = patternIndex\n      this.form.sessionDate = seed.sessionDate\n      this.form.slotNo = String(this.formalPatterns[patternIndex].slotNo)\n      this.form.scheduleItemId = String(this.formalPatterns[patternIndex].scheduleItemId || '')\n'''
if old not in text:
    raise SystemExit("deep-link scheduleItem assignment anchor missing")
text = text.replace(old, new, 1)

old = '''      this.patternIndex = Number(event.detail.value)\n      const pattern = this.formalPatterns[this.patternIndex]\n      this.form.slotNo = pattern ? String(pattern.slotNo) : ''\n'''
new = '''      this.patternIndex = Number(event.detail.value)\n      const pattern = this.formalPatterns[this.patternIndex]\n      this.form.slotNo = pattern ? String(pattern.slotNo) : ''\n      this.form.scheduleItemId = pattern ? String(pattern.scheduleItemId || '') : ''\n'''
if old not in text:
    raise SystemExit("pattern picker scheduleItem assignment anchor missing")
text = text.replace(old, new, 1)

old = '''        sessionDate: this.form.sessionDate,\n        slotNo: Number(this.form.slotNo),\n        sessionType: this.form.sessionType || undefined\n'''
new = '''        sessionDate: this.form.sessionDate,\n        slotNo: Number(this.form.slotNo),\n        scheduleItemId: this.form.scheduleItemId || undefined,\n        sessionType: this.form.sessionType || undefined\n'''
if old not in text:
    raise SystemExit("create payload scheduleItem anchor missing")
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
