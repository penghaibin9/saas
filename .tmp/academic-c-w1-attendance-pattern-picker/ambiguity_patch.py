from pathlib import Path

path = Path("miniapp/src/pages/teacher/academic-affairs/attendance.vue")
text = path.read_text(encoding="utf-8")

old = '''      const slotRaw = String(options.slotNo || '').trim()\n      const anySeed = Boolean(taskIdRaw || sessionDate || slotRaw)\n'''
new = '''      const slotRaw = String(options.slotNo || '').trim()\n      const scheduleItemId = String(options.scheduleItemId || '').trim()\n      const anySeed = Boolean(taskIdRaw || sessionDate || slotRaw || scheduleItemId)\n'''
if old not in text:
    raise SystemExit("parse seed scheduleItem anchor missing")
text = text.replace(old, new, 1)

old = '''        teachingTaskId: String(taskId),\n        sessionDate,\n        slotNo: String(slotNo)\n'''
new = '''        teachingTaskId: String(taskId),\n        sessionDate,\n        slotNo: String(slotNo),\n        scheduleItemId\n'''
if old not in text:
    raise SystemExit("seed return anchor missing")
text = text.replace(old, new, 1)

old = '''      const patternIndex = this.formalPatterns.findIndex((pattern) => Number(pattern.slotNo) === Number(seed.slotNo))\n      if (patternIndex < 0) {\n        this.taskSelectionInvalid = true\n        this.applyTask(null)\n        this.form.sessionDate = ''\n        toast('该正式课次节次已不在当前发布课表中')\n        return\n      }\n      this.patternIndex = patternIndex\n'''
new = '''      const matchingPatternIndexes = []\n      this.formalPatterns.forEach((pattern, patternIndex) => {\n        if (Number(pattern.slotNo) === Number(seed.slotNo)) matchingPatternIndexes.push(patternIndex)\n      })\n      let patternIndex = -1\n      if (seed.scheduleItemId) {\n        patternIndex = matchingPatternIndexes.find((candidateIndex) =>\n          String(this.formalPatterns[candidateIndex].scheduleItemId || '') === seed.scheduleItemId)\n        if (patternIndex === undefined) patternIndex = -1\n      } else if (matchingPatternIndexes.length === 1) {\n        patternIndex = matchingPatternIndexes[0]\n      }\n      if (patternIndex < 0) {\n        const ambiguous = !seed.scheduleItemId && matchingPatternIndexes.length > 1\n        this.taskSelectionInvalid = true\n        this.applyTask(null)\n        this.form.sessionDate = ''\n        toast(ambiguous ? '该节次对应多个正式课表项，请从教师今日课次重新进入' : '该正式课次已不在当前发布课表中')\n        return\n      }\n      this.patternIndex = patternIndex\n'''
if old not in text:
    raise SystemExit("seed pattern matching anchor missing")
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
