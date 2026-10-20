<template>
  <view class="page-wrap">
    <MobilePrivacyGate />
    <MobileNavBar title="实习档案" variant="brand" show-back :before-back="beforeLeave" :fallback-url="returnUrl" />
    <view class="page-pad profile-wrap">
      <MobileGlobalState :state="state" :description="error" @retry="reload">
        <template v-if="state === 'ready'">
          <view class="card"><text class="heading">准备好这次投递材料</text><text class="hint">档案由本人维护。保存后须返回原招聘季重新预览、确认投递，已提交的历史材料不会被改写。</text><text v-if="completeness" class="hint">当前材料完成度 {{ completeness.percent }}%</text><text v-for="(item, i) in completeness?.blockers || []" :key="i" class="warning">{{ item.message || item.label || item }}</text><text v-if="readWarning" class="warning">{{ readWarning }}</text></view>
          <view class="card"><text class="heading">学校信息</text><text class="hint">来自学校学生档案，如有错误请联系学校核对。</text><view v-for="item in schoolFields" :key="item.key" class="fact"><text>{{ item.label }}</text><text>{{ school[item.key] || '尚未填写' }}</text></view></view>
          <view class="card"><text class="heading">我的介绍</text>
            <label v-for="field in textFields" :key="field.key" class="field"><text>{{ field.label }}</text><textarea v-model="draft[field.key]" :maxlength="field.max" :disabled="busy || !!itemDraft" :placeholder="field.placeholder" /></label>
            <label class="field"><text>技能标签（逗号分隔）</text><input v-model="draft.skills" :disabled="busy || !!itemDraft" maxlength="500" placeholder="如 PLC、设备点检" /></label>
            <label class="field"><text>期望地点（逗号分隔）</text><input v-model="draft.locations" :disabled="busy || !!itemDraft" maxlength="500" placeholder="如 长沙、株洲" /></label>
            <picker mode="date" :value="draft.availableFrom" :disabled="busy || !!itemDraft" @change="draft.availableFrom = $event.detail.value"><view class="date-field">可到岗日期：{{ draft.availableFrom || '请选择' }}</view></picker>
            <button class="primary" :disabled="busy || uncertain || !!itemDraft || !profileDirty" @click="saveProfile">保存介绍</button>
          </view>
          <view class="card"><text class="heading">实践与证明材料</text><text class="hint">补充你实际承担的工作、项目成果与证明附件。学校来源的记录仅可查看。</text><text v-if="profileDirty" class="warning">请先保存上方介绍，再编辑材料。</text>
            <view v-for="item in items" :key="item.id" class="entry"><text class="heading">{{ item.title }}</text><text class="hint">{{ typeLabel(item.itemType) }} · {{ item.organization || '本人提供' }}</text><text class="copy">{{ item.description }}</text><button v-for="(id, i) in item.fileIds || []" :key="id" @click="openFile(id)">查看附件 {{ i + 1 }}</button><view v-if="item.sourceType === 'STUDENT_ENTERED'" class="actions"><button :disabled="busy || uncertain || profileDirty || !!itemDraft" @click="editItem(item)">编辑</button><button :disabled="busy || uncertain || profileDirty || !!itemDraft" @click="removeItem(item)">删除</button></view></view>
            <button v-if="!itemDraft" :disabled="busy || uncertain || profileDirty" @click="editItem()">添加实践或证明</button>
            <view v-else class="entry"><text class="heading">{{ itemDraft.id ? '编辑材料' : '新增材料' }}</text><picker :range="itemTypes.map(x => x.label)" :value="itemTypeIndex" :disabled="busy" @change="itemDraft.itemType = itemTypes[Number($event.detail.value)].value"><view class="date-field">类别：{{ typeLabel(itemDraft.itemType) }}</view></picker><label class="field"><text>名称</text><input v-model="itemDraft.title" :disabled="busy" maxlength="200" placeholder="项目或证明名称" /></label><label class="field"><text>组织或发证单位</text><input v-model="itemDraft.organization" :disabled="busy" maxlength="200" /></label><label class="field"><text>我做了什么</text><textarea v-model="itemDraft.description" :disabled="busy" maxlength="4000" placeholder="说明承担的工作和成果" /></label><text v-for="file in pendingFiles" :key="file.id" class="hint">{{ file.name }}（保存材料后关联）</text><button :disabled="busy" @click="upload">添加证明附件</button><view class="actions"><button :disabled="busy" @click="cancelItem">取消</button><button class="primary" :disabled="busy || uncertain || !itemDraft.title.trim()" @click="saveItem">保存材料</button></view></view>
          </view>
          <MobileInlineAlert v-if="actionError" type="warning" :description="actionError" />
          <button v-if="uncertain" :disabled="busy" @click="reload">重新读取，核对保存结果</button>
          <view class="card"><text class="heading">核对企业可见材料</text><button :disabled="busy || profileDirty || !!itemDraft || uncertain" @click="loadPreview">查看本次材料预览</button><text v-if="previewError" class="warning">{{ previewError }}</text><template v-if="preview"><view v-for="field in preview.sharedFields || []" :key="field.key" class="entry"><text class="hint">{{ field.label }}</text><text class="copy">{{ display(field.value) }}</text></view><view v-for="item in preview.profileSnapshot?.items || []" :key="item.id" class="entry"><text class="heading">{{ item.title }}</text><text class="copy">{{ item.description }}</text></view><text class="hint">联系方式按返回投递确认页选择的共享范围处理。</text></template></view>
          <button :disabled="busy" @click="returnToSelection">返回原招聘季投递</button>
        </template>
      </MobileGlobalState>
    </view>
  </view>
</template>

<script>
import { internshipSelectionApi } from '@/services/internshipSelectionApi'
import { chooseSingleFile, uploadBusinessFile, openBusinessFile } from '@/services/fileApi'
import { selectionScope, selectionScopePath } from '../../../../../shared/internshipSelectionScope.mjs'

const base = '/pages/student-internship/profile/index'
const itemTypes = [{value:'PROJECT',label:'项目'},{value:'PRACTICE',label:'实践经历'},{value:'CERTIFICATE',label:'技能证书'},{value:'AWARD',label:'获奖'},{value:'PORTFOLIO',label:'作品'},{value:'SKILL_EVIDENCE',label:'技能证明'}]
const cleanList = value => value.split(/[,，、]/).map(x => x.trim()).filter(Boolean)
export default {
  data: () => ({ scope: {}, scopeError: '', state: 'loading', error: '', actionError: '', readWarning: '', completeness: null, school: {}, draft: {}, baseline: '', version: 0, items: [], itemDraft: null, pendingFiles: [], busy: false, uncertain: false, sequence: 0, preview: null, previewError: '', itemTypes,
    schoolFields: [{key:'realName',label:'姓名'},{key:'studentNo',label:'学号'},{key:'majorName',label:'专业'},{key:'className',label:'班级'}],
    textFields: [{key:'selfIntro',label:'自我介绍',max:1000,placeholder:'介绍专业学习经历和实习目标'},{key:'strengths',label:'个人优势',max:1000,placeholder:'说明技能、经验与擅长的工作'}] }),
  computed: {
    api() { return internshipSelectionApi.forScope(this.scope) },
    returnUrl() { return selectionScopePath('/pages/student-internship/enterprises/index', this.scope) },
    profileDirty() { return this.baseline !== '' && JSON.stringify(this.draft) !== this.baseline },
    itemTypeIndex() { return Math.max(0, itemTypes.findIndex(x => x.value === this.itemDraft?.itemType)) }
  },
  onLoad(query) { this.applyQuery(query || {}) },
  onUnload() { this.sequence++ },
  watch: { draft: { deep: true, handler() { this.preview = null } }, '$route.fullPath'() { if (this.$route?.path === base) this.applyQuery(this.$route.query || {}) } },
  methods: {
    applyQuery(query) { this.sequence++; this.preview = null; this.itemDraft = null; this.busy = false; try { this.scope = selectionScope(query); this.scopeError = '';  return this.load() } catch (e) { this.scopeError = e.message; this.state = 'error'; this.error = e.message } },
    accept(data) { const p = data.profile || {}; this.version = p.profileVersion || 0; this.school = data.schoolFacts || {}; this.items = data.items || []; this.draft = { selfIntro: p.selfIntro || '', strengths: p.strengths || '', skills: (p.skillTags || []).join('，'), locations: (p.expectedLocations || []).join('，'), availableFrom: p.availableFrom || '' }; this.baseline = JSON.stringify(this.draft) },
    async load() { if (this.scopeError) { this.state = 'error'; this.error = this.scopeError; return }; const seq = ++this.sequence; this.state = 'loading'; this.error = ''; this.actionError = ''; this.uncertain = false; this.preview = null; this.itemDraft = null; this.pendingFiles = []; try { const data = await this.api.profile(); if (seq !== this.sequence) return; this.accept(data); this.state = 'ready'; await this.loadCompleteness(seq) } catch (e) { if (seq === this.sequence) { this.state = 'error'; this.error = e.message } } },
    async loadCompleteness(seq) { this.completeness = null; this.readWarning = ''; try { const data = await this.api.profileCompleteness(); if (seq === this.sequence) this.completeness = data } catch (e) { if (seq === this.sequence) this.readWarning = e.message || '暂无法核对本轮材料要求，可先维护本人档案。' } },
    ask(content) { return new Promise(resolve => uni.showModal({ title: '核对操作', content, success: result => resolve(!!result.confirm), fail: () => resolve(false) })) },
    async beforeLeave() { if (this.busy) return false; return !(this.profileDirty || this.itemDraft) || await this.ask('尚有未保存的内容，确定离开？') },
    async returnToSelection() { if (await this.beforeLeave()) uni.redirectTo({url: this.returnUrl}) },
    async reload() { if (await this.beforeLeave()) await this.load() },
    async mutate(task) { if (this.busy || this.uncertain) return; const seq = this.sequence; this.busy = true; this.actionError = ''; this.preview = null; try { const data = await task(); if (seq !== this.sequence) return; this.accept(data); this.itemDraft = null; this.pendingFiles = []; await this.loadCompleteness(seq) } catch (e) { if (seq === this.sequence) { this.uncertain = true; this.actionError = `${e.message || '保存未完成'}。请先重新读取并核对结果，避免重复添加。` } } finally { if (seq === this.sequence) this.busy = false } },
    saveProfile() { if (this.itemDraft || !this.profileDirty) return; const api = this.api; const data = {expectedProfileVersion:this.version,selfIntro:this.draft.selfIntro.trim(),strengths:this.draft.strengths.trim(),skillTags:cleanList(this.draft.skills),expectedLocations:cleanList(this.draft.locations),availableFrom:this.draft.availableFrom || null}; return this.mutate(() => api.updateProfile(data)) },
    editItem(item) { if (this.busy || this.profileDirty || this.uncertain || this.itemDraft || (item && item.sourceType !== 'STUDENT_ENTERED')) return; this.itemDraft = {id:item?.id || '',itemType:item?.itemType || 'PRACTICE',title:item?.title || '',organization:item?.organization || '',description:item?.description || ''}; this.pendingFiles = [] },
    async cancelItem() { if (!this.busy && await this.ask('放弃本次材料编辑？已保存的材料仍保留。')) { this.itemDraft = null; this.pendingFiles = [] } },
    saveItem() { if (!this.itemDraft?.title.trim()) return; const api = this.api; const {id,...data} = this.itemDraft; data[id ? 'appendFileIds' : 'fileIds'] = this.pendingFiles.map(x => x.id); return this.mutate(() => id ? api.updateProfileItem(id,data) : api.createProfileItem(data)) },
    async removeItem(item) { if (this.busy || this.profileDirty || this.itemDraft || this.uncertain || item.sourceType !== 'STUDENT_ENTERED') return; const seq = this.sequence; const api = this.api; if (await this.ask(`删除“${item.title}”？历史投递材料仍保留。`) && seq === this.sequence) await this.mutate(() => api.deleteProfileItem(item.id)) },
    async upload() { if (this.busy || !this.itemDraft) return; const seq = this.sequence; this.busy = true; try { const file = await chooseSingleFile(); if (!file || seq !== this.sequence) return; const result = await uploadBusinessFile(file,{bizType:'TEMP_PRIVATE'}); if (seq !== this.sequence) return; const id = result.fileId || result.id; if (!id) throw new Error('附件上传未返回文件标识'); this.pendingFiles.push({id:String(id),name:result.fileName || file.name || '证明附件'}) } catch (e) { if (seq === this.sequence) this.actionError = e.message || '附件上传未完成' } finally { if (seq === this.sequence) this.busy = false } },
    async openFile(id) { try { await openBusinessFile(id) } catch (e) { this.actionError = e.message || '附件暂无法打开' } },
    async loadPreview() { if (this.busy || this.profileDirty || this.itemDraft || this.uncertain) return; const seq = this.sequence; this.busy = true; this.preview = null; this.previewError = ''; try { const data = await this.api.profilePreview(); if (seq === this.sequence) this.preview = data } catch (e) { if (seq === this.sequence) this.previewError = e.message || '预览未完成' } finally { if (seq === this.sequence) this.busy = false } },
    typeLabel(value) { return itemTypes.find(x => x.value === value)?.label || '材料' },
    display(value) { return Array.isArray(value) ? value.join('、') : value || '未填写' }
  }
}
</script>

<style scoped>
.profile-wrap{max-width:680px;margin:auto;padding-bottom:calc(24px + env(safe-area-inset-bottom))}.card{margin-bottom:16px}.heading{display:block;font-size:17px;font-weight:600;line-height:1.6;color:var(--text-primary)}.hint,.warning,.copy{display:block;font-size:13px;line-height:1.8;margin-top:8px;overflow-wrap:anywhere}.hint{color:var(--text-secondary)}.warning{color:var(--warning,#956316)}.copy{white-space:pre-wrap;color:var(--text-primary)}.fact{display:flex;justify-content:space-between;gap:16px;margin-top:12px;font-size:14px}.field{display:block;margin-top:20px;font-size:14px}.field input,.field textarea{box-sizing:border-box;width:100%;padding:12px;border:1px solid var(--border-light);border-radius:8px;margin-top:8px;font-size:14px;line-height:1.6}.field textarea{height:130px}.field input{height:46px}.date-field{min-height:48px;padding-top:12px;font-size:14px}.entry{margin-top:18px;padding-top:16px;border-top:1px solid var(--border-light)}button{font-size:14px;min-height:44px;margin-top:12px}.primary{background:var(--brand-primary);color:#fff}.actions{display:flex;gap:12px}.actions button{flex:1}button[disabled]{opacity:.5}
</style>
