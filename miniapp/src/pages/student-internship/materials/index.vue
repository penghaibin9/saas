<template>
  <view class="internship-surface mobile-page mobile-student page-wrap materials-page">
    <MobileNavBar title="实习材料" show-back :fallback-url="'/pages/student-internship/index' + (context.batchId ? '?batchId=' + encodeURIComponent(context.batchId) : '')" />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="context.batchId">
        <view class="mat__batch"><text>{{ batchName || '当前实习批次' }}</text><button v-if="items.length > 1" class="mobile-control mat__switch" :aria-expanded="requirementMenuOpen" :disabled="!!busyId || !!scanningId" @click="requirementMenuOpen = !requirementMenuOpen">切换要求</button></view>
        <view v-if="requirementMenuOpen" class="card mat__choices" role="group" aria-label="选择材料要求"><button class="mobile-control" v-for="(choice,index) in items" :key="choice.id" :aria-pressed="activeItem?.id === choice.id" @click="chooseRequirement(index)">{{ choice.materialName }}</button></view>
        <MobileInlineAlert v-if="historyMode" type="info" description="历史实习材料仅可查看，不再提交或修改。" />
        <MobileGlobalState v-if="!items.length" state="empty" title="当前批次暂无材料任务" description="等待学校发布收件要求。" />
        <view v-for="item in displayedItems" :key="item.id" class="mat__object">
          <view class="card mat mat__identity"><view class="row-between">
            <view class="flex-1">
              <text class="t-md t-bold">{{ item.materialName }}</text>
              <text class="mat__code">{{ item.isRequired ? '必交材料' : '选交材料' }}</text>
            </view>
            <MobileStatusTag :label="!historyMode && item.submission?.status === 'RETURNED' ? '待补正' : statusLabel(item)" :type="statusTone(item)" />
          </view>
          <view v-if="item.submission?.reviewComment" class="mat__review" :class="{ 'mat__review--done': item.submission.status !== 'RETURNED' }"><text class="t-bold">{{ item.submission.status === 'RETURNED' ? '老师退回意见' : '审核意见' }}</text><text>{{ item.submission.reviewComment }}</text></view>
          <text class="mat__desc">{{ materialNextStep(item) }}</text></view>

          <view class="card mat">
            <view class="mat__template"><MobileShellIcon name="file-text" /><view class="flex-1"><button class="mobile-control mat__details-toggle" :aria-expanded="requirementsOpen" @click="requirementsOpen = !requirementsOpen">要求与模板</button><text class="mat__hash">{{ item.minFiles === item.maxFiles ? '需交' + item.minFiles + '份' : '需交' + item.minFiles + '～' + item.maxFiles + '份' }} · 查看格式要求</text></view><button v-if="item.template" class="mobile-control btn btn-ghost" :disabled="!!busyId" @click="downloadTemplate(item)">下载模板</button></view>
            <view v-if="requirementsOpen" class="mat__facts"><text>允许格式：{{ item.allowedFormatLabel }}</text><text v-if="item.description">{{ item.description }}</text><text>截止时间：{{ item.dueAt ? fmt(item.dueAt) : '未设置' }}</text><text v-if="item.template">模板：{{ item.template.fileName || '学校模板' }} · 第{{ item.template.versionNo }}版</text></view>
          </view>

          <view v-if="canSubmit(item)" class="card mat mat__upload">
            <view class="row-between"><text class="mat__upload-title">{{ item.submission?.status === 'RETURNED' ? '本次重交' : '提交材料' }}</text><text class="mat__count">{{ pending(item.id).length }} / {{ item.maxFiles }} 份</text></view>
            <view v-for="(file, index) in visibleFiles(pending(item.id), item.id + ':pending')" :key="file.fileId" class="mat__pending">
              <MobileShellIcon :name="fileIcon(file.fileName)" />
              <view class="flex-1"><text class="mat__file-name">{{ file.fileName }}</text><text class="mat__hash" :class="{ 'mat__safe': file.readyForBusiness }">{{ file.statusText }}</text></view>
              <button class="mobile-control" :disabled="!!busyId || !!scanningId" @click="removePending(item.id, index)">移除</button>
            </view>
            <button v-if="pending(item.id).length > 4" class="mobile-control mat__expand" :aria-expanded="!!expandedFiles[item.id + ':pending']" @click="toggleFiles(item.id + ':pending')">{{ expandedFiles[item.id + ':pending'] ? '收起文件' : '展开全部' + pending(item.id).length + '份' }}</button>
            <text v-if="materialErrors[String(item.id)]" class="mat__review">{{ materialErrors[String(item.id)] }}</text>
            <view v-if="pending(item.id).length" class="mat__scan" :class="{ 'mat__scan--ready': pendingReady(item) }"><MobileShellIcon :name="pendingReady(item) ? 'check' : 'shield-exclamation'" :tone="pendingReady(item) ? 'teal' : 'amber'" plain /><text>{{ pendingReady(item) ? pending(item.id).length + '份文件安全检查均已完成' : '文件安全可用后才能提交，已选文件会保留。' }}</text></view>
            <view class="mat__actions">
              <button v-if="pending(item.id).length < item.maxFiles" class="mobile-control btn btn-ghost" :disabled="!!busyId || !!scanningId" @click="pick(item)">{{ busyId === item.id ? '上传中…' : '添加文件' }}</button>
              <button v-if="pending(item.id).length" class="mobile-control mat__expand" :disabled="!!busyId || !!scanningId" @click="refreshPending(item)">{{ scanningId===String(item.id) ? '读取中…' : '读取扫描结果' }}</button>
            </view>
          </view>
          <view v-if="item.submission" class="card mat mat__submission">
            <button class="mobile-control mat__details-toggle" :aria-expanded="!canSubmit(item) || !!previousOpen[item.id]" @click="previousOpen = { ...previousOpen, [item.id]: !previousOpen[item.id] }">{{ canSubmit(item) ? '查看上次提交 · ' : '最近一次提交 · ' }}{{ item.submission.statusLabel }}</button>
            <template v-if="!canSubmit(item) || previousOpen[item.id]">
              <view v-for="file in visibleFiles(item.submission.files, item.id + ':submitted')" :key="file.slotNo" class="mat__file-row"><MobileShellIcon :name="fileIcon(file.fileName)" /><view class="flex-1"><text class="mat__file-name">{{ file.fileName || ('第' + file.slotNo + '份材料') }}</text><text class="mat__hash">第{{ file.versionNo }}版 · {{ file.statusText }}</text></view><button class="mobile-control mat__preview" @click="preview(file.fileId)">查看</button></view>
              <button v-if="item.submission.files.length > 4" class="mobile-control mat__expand" :aria-expanded="!!expandedFiles[item.id + ':submitted']" @click="toggleFiles(item.id + ':submitted')">{{ expandedFiles[item.id + ':submitted'] ? '收起文件' : '展开全部' + item.submission.files.length + '份' }}</button>
            </template>
          </view>
        </view>
      </view>
    </MobileGlobalState>
    <MobileSafeAreaBar v-if="state === 'ready' && activeItem && canSubmit(activeItem)"><view class="mat__submit-bar"><text>{{ activeItem.submission?.status === 'RETURNED' ? '将按原单重新提交，历史版本保留。' : '提交后交指导教师审核，可在本页查看结果。' }}</text><button class="mobile-control btn btn-primary" :disabled="!!busyId || !!scanningId || !pendingReady(activeItem)" @click="submit(activeItem)">{{ busyId ? '处理中…' : activeItem.submission?.status === 'RETURNED' ? '重新提交审核' : '提交审核' }}</button></view></MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { chooseSingleFile, openBusinessFile, uploadBusinessFile } from '@/services/fileApi'
import fileSdk from '@/services/fileSdk'
import { normalizeFileReadiness, filesReadyForBusiness, refreshFileReadiness, materialRequirementView, allowedFormatText } from '@/services/fileReadiness.mjs'
import { normalizeError } from '@/services/request'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { toast } from '@/utils/nav'
import { releasePreview } from '@/services/reportMedia.mjs'

export default {
  data() {
    return {
      state: 'loading',
      context: { batchId: '', internshipId: '' },
      items: [],
      batchName: '', selectedRequirementId: '', historyMode: false, requirementsOpen: false, requirementMenuOpen: false, expandedFiles: {}, previousOpen: {},
      pendingByRequirement: {},
      busyId: '', requestSeq:0, generation:currentSessionGeneration(), hidden:false, requestedBatchId:'', scanningId:'', materialErrors:{}, scanSequence:0
    }
  },
  computed: {
    activeItem() { return this.items.find(item => String(item.id) === this.selectedRequirementId) || (!this.historyMode && (this.items.find(item => item.submission?.status === 'RETURNED') || this.items.find(item => !item.submission || ['DRAFT','WITHDRAWN'].includes(item.submission.status)))) || this.items[0] || null },
    displayedItems() { return this.activeItem ? [this.activeItem] : [] },
    requirementNames() { return this.items.map(item => item.materialName) },
    requirementIndex() { return Math.max(0, this.items.findIndex(item => String(item.id) === String(this.activeItem?.id))) }
  },
  onLoad(options={}) { this.requestedBatchId=String(options.batchId || '');this.selectedRequirementId=String(options.requirementId || '');this.load() },
  onShow() {const wasHidden=this.hidden;this.hidden=false;if(this.generation!==currentSessionGeneration()){this.pendingByRequirement={};this.items=[];this.context={batchId:'',internshipId:''};this.load()}else if(wasHidden && this.state==='loading')return this.load()},
  onHide() {this.hidden=true;this.scanSequence++;this.scanningId=''},
  onUnload() {this.hidden=true;this.requestSeq++;this.scanSequence++},
  onPullDownRefresh() { this.load(() => uni.stopPullDownRefresh()) },
  methods: {
    chooseRequirement(index) { this.selectRequirement({ detail:{ value:index } });this.requirementMenuOpen=false },
    selectRequirement(event) { if (this.busyId || this.scanningId) return; const item = this.items[Number(event.detail.value)]; if (item) { this.selectedRequirementId = String(item.id); this.requirementsOpen = false } },
    visibleFiles(files = [], key) { return this.expandedFiles[key] ? files : files.slice(0, 4) },
    toggleFiles(key) { this.expandedFiles = { ...this.expandedFiles, [key]: !this.expandedFiles[key] } },
    fileIcon(name = '') { return /\.(zip|rar)$/i.test(name) ? 'folder' : 'file-text' },
    materialNextStep(item) { if (this.historyMode) return '当前为历史实习，材料仅供查阅。'; return ({ RETURNED:'请按老师意见补正，仍交指导教师审核。', SUBMITTED:'已提交，等待指导教师审核。', APPROVED:'指导教师已审核通过，材料版本已保留。' })[item.submission?.status] || '按学校要求上传材料，提交后可在本页查看审核结果。' },
    fmt(value) { return String(value || '').slice(0, 16).replace('T', ' ') },
    shortHash(value) { const text = String(value || ''); return text ? text.slice(0, 10) + '…' : '—' },
    pending(id) { return this.pendingByRequirement[String(id)] || [] },
    pendingReady(item) {const files=this.pending(item.id);return files.length>=Number(item.minFiles || 0) && files.length<=Number(item.maxFiles || 1) && filesReadyForBusiness(files)},
    current(seq,generation,allowHidden=false) {return seq===this.requestSeq && generation===currentSessionGeneration() && (!this.hidden || allowHidden)},
    async refreshPending(item) {
      if(this.busyId || this.scanningId) return
      const key=String(item.id),files=this.pending(key),seq=this.requestSeq,generation=this.generation,sequence=++this.scanSequence
      const current=()=>this.current(seq,generation) && sequence===this.scanSequence && this.pending(key)===files
      this.scanningId=key;this.materialErrors={...this.materialErrors,[key]:''}
      try {const updated=await refreshFileReadiness(files,id=>fileSdk.metadata(id),current);if(updated)this.pendingByRequirement={...this.pendingByRequirement,[key]:updated}}
      catch {if(current()){this.pendingByRequirement={...this.pendingByRequirement,[key]:files.map(file=>({...file,readyForBusiness:false,statusText:'扫描结果未能读取，材料已保留'}))};this.materialErrors={...this.materialErrors,[key]:'扫描结果读取失败，材料已保留，请重新读取'}}}
      finally {if(sequence===this.scanSequence)this.scanningId=''}
    },
    statusLabel(item) {
      if (item.isLate && !item.submission) return '已逾期未交'
      return item.submission?.statusLabel || '未提交'
    },
    statusTone(item) {
      const status = item.submission?.status
      if (status === 'APPROVED') return 'success'
      if (status === 'RETURNED') return 'warning'
      if (item.isLate) return 'danger'
      if (status === 'SUBMITTED') return 'warning'
      return 'default'
    },
    canSubmit(item) {
      if (this.historyMode) return false
      const status = item.submission?.status
      return !status || status === 'RETURNED' || status === 'DRAFT' || status === 'WITHDRAWN'
    },
    async load(done) {
      const seq=++this.requestSeq,generation=currentSessionGeneration();if(this.generation!==generation){this.pendingByRequirement={};this.expandedFiles={};this.previousOpen={};this.selectedRequirementId='';this.requirementsOpen=false;this.requirementMenuOpen=false}this.generation=generation
      this.scanSequence++;this.scanningId='';this.busyId='';this.items=[]
      this.state = 'loading'
      try {
        const dashboard = await studentApi.getInternship(this.requestedBatchId)
        if(!this.current(seq,generation))return
        this.batchName=dashboard.batch || '';this.historyMode=!!dashboard.historyMode
        const next={batchId:String(dashboard?.batchId || ''),internshipId:String(dashboard?.recordId || '')}
        if(next.batchId!==this.context.batchId || next.internshipId!==this.context.internshipId){this.pendingByRequirement={};this.materialErrors={};this.requirementMenuOpen=false}
        this.context=next
        if (!this.context.batchId || !this.context.internshipId) {
          this.items = []
          this.state = 'ready'
          return
        }
        const rows = await studentApi.getInternshipMaterialRequirements(this.context.batchId, this.context.internshipId)
        if(!this.current(seq,generation))return
        this.items = (Array.isArray(rows) ? rows : rows?.items || []).map(item=>({...materialRequirementView(item),allowedFormatLabel:allowedFormatText(item.allowedExtensions)}))
        this.selectedRequirementId=String(this.activeItem?.id || '')
        this.state = 'ready'
      } catch (e) {
        if(!this.current(seq,generation))return
        this.items = []
        const shown = normalizeError(e)
        this.state = shown.pageState || 'error'
        toast(shown.text)
      } finally { if (done) done() }
    },
    async downloadTemplate(item) {
      if (!item.template || this.busyId || this.hidden || this.generation!==currentSessionGeneration()) return
      const seq=this.requestSeq,generation=this.generation
      this.busyId = item.id
      try {
        const downloaded = await studentApi.downloadInternshipMaterialTemplate(
          item.id, this.context.batchId, this.context.internshipId, item.template.versionId)
        if(!this.current(seq,generation)){releasePreview(downloaded?.tempFilePath);return}
        if (!downloaded?.tempFilePath) return toast('模板下载失败')
        if (typeof document !== 'undefined') {
          const link=document.createElement('a')
          try {
            link.href=downloaded.tempFilePath
            link.download=String(item.template.fileName || '学校材料模板').replace(/[\\/:*?"<>|]/g,'_')
            document.body.appendChild(link);link.click()
          } finally {link.remove();setTimeout(()=>releasePreview(downloaded.tempFilePath),1000)}
          return
        }
        uni.openDocument({
          filePath: downloaded.tempFilePath,
          fileType: String(item.template.fileName || '').split('.').pop().toLowerCase() || undefined,
          showMenu: true,
          fail: () => {if(this.current(seq,generation))toast('模板已下载，但当前设备无法直接预览')}
        })
      } catch (e) {if(this.current(seq,generation))toast('模板下载未完成，请重试')}
      finally {if(seq===this.requestSeq)this.busyId = ''}
    },
    async preview(fileId) {
      if(this.hidden || this.generation!==currentSessionGeneration())return
      try { await openBusinessFile(fileId) }
      catch (e) { toast('材料暂时无法打开，请重新读取后重试') }
    },
    async pick(item) {
      if (this.busyId || this.pending(item.id).length >= Number(item.maxFiles || 1)) return
      if(this.hidden || this.generation!==currentSessionGeneration() || !this.canSubmit(item))return
      const seq=this.requestSeq,generation=this.generation
      this.busyId = item.id
      try {
        const file = await chooseSingleFile()
        if (!file || !this.current(seq,generation,true)) return
        const ext = String(file.name || '').split('.').pop().toLowerCase()
        const allowed = item.allowedExtensions || []
        if (allowed.length && !allowed.includes(ext)) return toast('文件格式不符合学校要求')
        const uploaded = await uploadBusinessFile(file, { bizType: 'INTERNSHIP_CUSTOM_MATERIAL' })
        if(!this.current(seq,generation,true))return
        if(!uploaded?.fileId)throw Error('材料上传结果未能核对')
        const key = String(item.id)
        const normalized=normalizeFileReadiness({...uploaded,fileName:uploaded.fileName || file.name || '材料文件'})
        this.pendingByRequirement = {
          ...this.pendingByRequirement,
          [key]: [...this.pending(key), normalized]
        }
        toast(normalized.readyForBusiness?'材料安全可用':'文件已接收，请读取安全扫描结果')
      } catch (e) {if(this.current(seq,generation,true))this.materialErrors={...this.materialErrors,[String(item.id)]:'材料上传未完成，已选材料保留，请重试'}}
      finally {if(seq===this.requestSeq)this.busyId = ''}
    },
    removePending(id, index) {
      if(this.busyId)return
      const key = String(id)
      const next = [...this.pending(key)]
      next.splice(index, 1)
      this.pendingByRequirement = { ...this.pendingByRequirement, [key]: next }
    },
    async submit(item) {
      if (this.busyId || this.scanningId || this.hidden || this.generation!==currentSessionGeneration() || !this.canSubmit(item)) return
      const files = this.pending(item.id)
      const min = Number(item.minFiles || 0)
      const max = Number(item.maxFiles || 1)
      if (files.length < min || files.length > max) return toast(`请上传 ${min}～${max} 份材料`)
      if(!filesReadyForBusiness(files)){this.materialErrors={...this.materialErrors,[String(item.id)]:'材料尚未安全可用，请读取扫描结果或移除后重新上传'};return}
      const seq=this.requestSeq,generation=this.generation
      this.busyId = item.id
      try {
        await studentApi.submitInternshipMaterial(item.id, {
          ...this.context,
          fileIds: files.map((file) => String(file.fileId)),
          expectedVersion:item.submission?.version ?? 0,
          comment: item.submission?.status === 'RETURNED' ? '按审核意见重新提交' : '学生提交'
        })
        if(!this.current(seq,generation))return
        this.pendingByRequirement = { ...this.pendingByRequirement, [String(item.id)]: [] }
        toast('材料已提交审核')
        await this.load()
      } catch (e) {if(this.current(seq,generation))this.materialErrors={...this.materialErrors,[String(item.id)]:normalizeError(e).text+'；材料已保留，请重新读取原任务核对'}}
      finally {if(seq===this.requestSeq)this.busyId = ''}
    }
  }
}
</script>

<style scoped>
.materials-page{font-size:var(--font-size-md);padding-bottom:calc(136px + var(--safe-area-bottom))}
.materials-page :deep(.page-pad){width:100%;max-width:760px;margin:0 auto;box-sizing:border-box;gap:var(--space-4)}
.mat__batch{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);font-size:var(--font-size-md);color:var(--text-secondary);line-height:1.6}
.mat__batch>text{min-width:0;overflow-wrap:anywhere}.mat__switch{display:flex;align-items:center;min-height:44px;margin:0;padding:0 var(--space-2);border:0;background:transparent;color:var(--brand-primary);font-size:var(--font-size-base)}.mat__switch::after{border:0}
.mat__choices{display:flex;flex-direction:column;padding:var(--space-2)}.mat__choices>button{min-height:44px;width:100%;margin:0;padding:var(--space-3);line-height:1.6;text-align:left;border:0;background:var(--bg-card);color:var(--text-primary);font-size:var(--font-size-md)}.mat__choices>button[aria-pressed=true]{background:var(--primary-50);color:var(--brand-primary)}.mat__choices>button::after{border:0}
.mat__object{display:flex;flex-direction:column;gap:var(--space-3)}.mat{display:flex;flex-direction:column;gap:var(--space-3);padding:var(--space-4)}
.mat__identity .t-md{font-size:var(--font-size-lg);line-height:1.5}.mat__identity .row-between{align-items:flex-start;gap:var(--space-3)}
.mat__code,.mat__desc,.mat__hash{display:block;color:var(--text-secondary);font-size:var(--font-size-base);line-height:1.6;overflow-wrap:anywhere}
.mat__code{margin-top:var(--space-1)}.mat__facts{display:flex;flex-direction:column;gap:var(--space-2);padding-top:var(--space-3);border-top:1px solid var(--border-light);font-size:var(--font-size-base);line-height:1.7;color:var(--text-secondary)}
.mat__template,.mat__file-row,.mat__pending{display:flex;align-items:center;gap:var(--space-3)}
.mat__template .btn{flex-shrink:0;padding:0 var(--space-3);margin:0;font-size:var(--font-size-base)}
.mat__details-toggle{min-height:44px;margin:0;padding:0;text-align:left;line-height:1.5;font-size:var(--font-size-md);font-weight:var(--font-weight-semibold);border:0;background:transparent;color:var(--text-primary)}
.mat__details-toggle::after,.mat__expand::after,.mat__preview::after,.mat__pending button::after{border:0}
.mat__file-row,.mat__pending{padding:var(--space-3) 0;border-bottom:1px solid var(--border-light)}
.mat__file-name{display:block;font-size:var(--font-size-md);line-height:1.6;color:var(--text-primary);font-weight:var(--font-weight-medium);overflow-wrap:anywhere}
.mat__preview,.mat__pending button{flex-shrink:0;display:flex;align-items:center;justify-content:center;min-height:44px;min-width:44px;margin:0;padding:0 var(--space-1);border:0;background:transparent;color:var(--brand-primary);font-size:var(--font-size-base)}
.mat__upload-title{font-size:var(--font-size-xl);font-weight:var(--font-weight-semibold);line-height:1.5}.mat__count{font-size:var(--font-size-md);color:var(--text-secondary)}
.mat__review{display:flex;flex-direction:column;gap:var(--space-2);padding:var(--space-3);border-radius:var(--radius-md);background:var(--warning-50);color:var(--warning-700);font-size:var(--font-size-md);line-height:1.7;white-space:pre-wrap;overflow-wrap:anywhere}
.mat__review--done{background:var(--info-50);color:var(--text-secondary)}
.mat__expand{display:flex;align-items:center;justify-content:center;min-height:44px;margin:0;padding:0 var(--space-2);border:0;background:transparent;color:var(--brand-primary);font-size:var(--font-size-md);line-height:1.5}
.mat__scan{display:flex;align-items:center;gap:var(--space-2);padding:var(--space-3);background:var(--warning-50);border-radius:var(--radius-md);font-size:var(--font-size-base);line-height:1.6;color:var(--warning-700)}
.mat__scan--ready{background:var(--success-50);color:var(--success-700)}.mat__safe{color:var(--success-700)}
.mat__actions{display:flex;align-items:center;gap:var(--space-2);flex-wrap:wrap}.mat__actions .btn{margin:0}
.mat__submit-bar{width:100%;max-width:728px;margin:auto;display:flex;flex-direction:column;gap:var(--space-2)}
.mat__submit-bar>text{font-size:var(--font-size-sm);line-height:1.6;color:var(--text-secondary)}.mat__submit-bar>.btn{width:100%;margin:0;min-height:44px;box-sizing:border-box}
</style>
