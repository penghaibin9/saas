from pathlib import Path

path = Path("miniapp/src/pages/teacher/academic-affairs/attendance.vue")
text = path.read_text(encoding="utf-8")

old = '''          <view v-if="selectedTask" class="at__task-note">\n            <text>{{ selectedTask.courseName || '未命名课程' }}</text>\n            <text>{{ selectedTask.className || '未关联班级' }} · {{ selectedTask.termCode || '当前学期' }}</text>\n          </view>\n          <picker mode="date" :value="form.sessionDate" @change="onDateChange">\n            <view class="at__input at__date">{{ form.sessionDate || '选择考勤日期（必填）' }}</view>\n          </picker>\n          <input class="at__input" type="number" v-model="form.slotNo" placeholder="第几节（必填）" placeholder-class="at__ph" />\n'''
new = '''          <view v-if="selectedTask" class="at__task-note">\n            <text>{{ selectedTask.courseName || '未命名课程' }}</text>\n            <text>{{ selectedTask.className || '未关联班级' }} · {{ selectedTask.termCode || '当前学期' }}</text>\n            <text v-if="!selectedTask.formalOccurrenceReady" class="at__source-note">{{ selectedTask.formalScheduleIssue || '当前教学任务尚无可点名的正式课次' }}</text>\n          </view>\n          <picker\n            mode="selector"\n            :range="formalPatternLabels"\n            :value="patternIndex < 0 ? 0 : patternIndex"\n            :disabled="!formalPatterns.length"\n            @change="onPatternPick"\n          >\n            <view class="at__input at__date">{{ selectedPatternLabel || '选择正式上课节次（必填）' }}</view>\n          </picker>\n          <picker mode="date" :value="form.sessionDate" @change="onDateChange">\n            <view class="at__input at__date">{{ form.sessionDate || '选择考勤日期（必填）' }}</view>\n          </picker>\n'''
if old not in text:
    raise SystemExit("template slot input anchor missing")
text = text.replace(old, new, 1)

old = '''      taskOptions: [], taskIndex: 0, taskSelectionInvalid: false, routeSeed: null,\n      form: { teachingTaskId: '', classId: '', sessionDate: '', slotNo: '', sessionType: '' },\n'''
new = '''      taskOptions: [], taskIndex: 0, patternIndex: -1, taskSelectionInvalid: false, routeSeed: null,\n      form: { teachingTaskId: '', classId: '', sessionDate: '', slotNo: '', sessionType: '' },\n'''
if old not in text:
    raise SystemExit("data patternIndex anchor missing")
text = text.replace(old, new, 1)

old = '''    selectedTask() {\n      if (this.taskSelectionInvalid) return null\n      return (this.taskOptions || [])[this.taskIndex] || null\n    },\n    hasValidSlot() {\n      const slot = Number(this.form.slotNo)\n      return Number.isInteger(slot) && slot > 0\n    },\n'''
new = '''    selectedTask() {\n      if (this.taskSelectionInvalid) return null\n      return (this.taskOptions || [])[this.taskIndex] || null\n    },\n    formalPatterns() {\n      return (this.selectedTask && this.selectedTask.formalSchedulePatterns) || []\n    },\n    formalPatternLabels() {\n      return this.formalPatterns.map((pattern) => {\n        const parity = pattern.weekParity === 'ODD' ? '单周' : pattern.weekParity === 'EVEN' ? '双周' : '每周'\n        return `周${pattern.weekday} · 第${pattern.slotNo}节 · ${pattern.startWeek}-${pattern.endWeek}周 ${parity}`\n      })\n    },\n    selectedPattern() {\n      if (this.patternIndex < 0) return null\n      return this.formalPatterns[this.patternIndex] || null\n    },\n    selectedPatternLabel() {\n      if (this.patternIndex < 0) return ''\n      return this.formalPatternLabels[this.patternIndex] || ''\n    },\n    hasValidSlot() {\n      const pattern = this.selectedPattern\n      const slot = Number(this.form.slotNo)\n      return !!pattern && Number.isInteger(slot) && slot > 0 && slot === Number(pattern.slotNo)\n    },\n'''
if old not in text:
    raise SystemExit("computed slot anchor missing")
text = text.replace(old, new, 1)

old = '''      this.taskSelectionInvalid = false\n      this.taskIndex = index\n      this.applyTask(this.taskOptions[index])\n      this.form.sessionDate = seed.sessionDate\n      this.form.slotNo = seed.slotNo\n    },\n    onDateChange(event) { this.form.sessionDate = event.detail.value },\n'''
new = '''      this.taskSelectionInvalid = false\n      this.taskIndex = index\n      this.applyTask(this.taskOptions[index])\n      const patternIndex = this.formalPatterns.findIndex((pattern) => Number(pattern.slotNo) === Number(seed.slotNo))\n      if (patternIndex < 0) {\n        this.taskSelectionInvalid = true\n        this.applyTask(null)\n        this.form.sessionDate = ''\n        toast('该正式课次节次已不在当前发布课表中')\n        return\n      }\n      this.patternIndex = patternIndex\n      this.form.sessionDate = seed.sessionDate\n      this.form.slotNo = String(this.formalPatterns[patternIndex].slotNo)\n    },\n    onDateChange(event) { this.form.sessionDate = event.detail.value },\n'''
if old not in text:
    raise SystemExit("deep-link pattern anchor missing")
text = text.replace(old, new, 1)

old = '''    applyTask(task) {\n      this.form.teachingTaskId = task ? task.teachingTaskId : ''\n      this.form.classId = task ? task.classId : ''\n    },\n'''
new = '''    applyTask(task) {\n      this.form.teachingTaskId = task ? task.teachingTaskId : ''\n      this.form.classId = task ? task.classId : ''\n      this.patternIndex = -1\n      this.form.slotNo = ''\n    },\n'''
if old not in text:
    raise SystemExit("applyTask anchor missing")
text = text.replace(old, new, 1)

old = '''    onTaskPick(event) {\n      this.routeSeed = null\n      this.taskSelectionInvalid = false\n      this.taskIndex = Number(event.detail.value)\n      this.applyTask(this.taskOptions[this.taskIndex])\n    },\n'''
new = '''    onTaskPick(event) {\n      this.routeSeed = null\n      this.taskSelectionInvalid = false\n      this.taskIndex = Number(event.detail.value)\n      this.applyTask(this.taskOptions[this.taskIndex])\n    },\n    onPatternPick(event) {\n      this.patternIndex = Number(event.detail.value)\n      const pattern = this.formalPatterns[this.patternIndex]\n      this.form.slotNo = pattern ? String(pattern.slotNo) : ''\n    },\n'''
if old not in text:
    raise SystemExit("onTaskPick anchor missing")
text = text.replace(old, new, 1)

old = '''        this.taskOptions = ((data && data.items) || []).filter((task) =>\n          ALLOWED_TASK_STATUSES.has(String(task.taskStatus || '').toUpperCase()))\n        this.applyOccurrenceSeed()\n'''
new = '''        this.taskOptions = ((data && data.items) || [])\n          .filter((task) => ALLOWED_TASK_STATUSES.has(String(task.taskStatus || '').toUpperCase()))\n          .sort((left, right) => Number(Boolean(right.formalOccurrenceReady)) - Number(Boolean(left.formalOccurrenceReady)))\n        this.applyOccurrenceSeed()\n'''
if old not in text:
    raise SystemExit("loadTasks ready-sort anchor missing")
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
