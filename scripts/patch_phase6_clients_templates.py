#!/usr/bin/env python3
# One-time fail-closed patcher for Stage 6 template and miniapp client integration.
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_exact(path: str, old: str, new: str, marker: str) -> bool:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if marker in text:
        return False
    if old not in text:
        raise SystemExit(f"refusing to patch changed source: {path}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")
    return True


def append_once(path: str, content: str, marker: str) -> bool:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if marker in text:
        return False
    target.write_text(text.rstrip() + "\n\n" + content.strip() + "\n", encoding="utf-8")
    return True


def main() -> None:
    changed: list[str] = []
    catalog = "backend/app/modules/graduation/services/graduation_material_catalog_service.py"
    router = "backend/app/modules/graduation/routers/graduation_material_center.py"
    frontend_api = "frontend/src/modules/graduation/api/graduation-material-center.api.js"
    frontend_view = "frontend/src/modules/graduation/views/GraduationMaterialCenterView.vue"
    mini_sdk = "miniapp/src/services/fileSdk.js"
    student_api = "miniapp/src/services/studentApi.js"
    teacher_api = "miniapp/src/services/teacherApi.js"
    student_page = "miniapp/src/pages/student/graduation/index.vue"
    teacher_page = "miniapp/src/pages/teacher/graduation-guide/index.vue"

    old = '''        template_ids = {int(row.template_id) for row in policies}
        templates = {int(row.id): row for row in db.scalars(select(GraduationTemplate).where(
            GraduationTemplate.tenant_id == _tid(), GraduationTemplate.id.in_(template_ids or {-1}),
            GraduationTemplate.is_deleted.is_(False),
        )).all()}
'''
    new = '''        templates = {int(row.id): row for row in db.scalars(select(GraduationTemplate).where(
            GraduationTemplate.tenant_id == _tid(),
            GraduationTemplate.is_deleted.is_(False),
        ).order_by(GraduationTemplate.template_type, GraduationTemplate.name)).all()}
'''
    if replace_exact(catalog, old, new, "order_by(GraduationTemplate.template_type, GraduationTemplate.name)"):
        changed.append(catalog)

    old = '''                "majorId": policy.major_id or "", "enabled": bool(policy.enabled),
                "status": policy.status, "effectiveAt": _iso(policy.effective_at),
'''
    new = '''                "majorId": policy.major_id or "", "enabled": bool(policy.enabled),
                "status": policy.status, "version": int(policy.version or 0),
                "effectiveAt": _iso(policy.effective_at),
'''
    replace_exact(catalog, old, new, '"status": policy.status, "version": int(policy.version or 0)')

    old = '''        return {"items": items, "total": len(items)}
'''
    new = '''        return {
            "items": items, "total": len(items),
            "availableTemplates": [{
                "templateId": str(template.id), "templateName": template.name,
                "templateType": template.template_type, "status": template.status,
            } for template in templates.values()],
        }
'''
    target = ROOT / catalog
    text = target.read_text(encoding="utf-8")
    marker = '"availableTemplates": [{'
    if marker not in text:
        index = text.rfind(old)
        if index < 0:
            raise SystemExit(f"refusing to patch changed source: {catalog} template return")
        target.write_text(text[:index] + new + text[index + len(old):], encoding="utf-8")

    status_function = '''
def update_template_policy_status(policy_id: int, enabled: bool, expected_version: int, user: dict) -> dict:
    # 学校自助启停模板；启用前重新执行公共文件安全门和乐观锁。
    role = str((user or {}).get("currentRoleCode") or (user or {}).get("userType") or "").upper()
    permissions = set((user or {}).get("permissions") or [])
    if role not in {"PLATFORM_SUPER_ADMIN", "SCHOOL_ADMIN", "GRADUATION_ADMIN", "GD_GRADE_ADMIN"} \
            and "*" not in permissions and "graduationDesign.template.manage" not in permissions:
        raise not_found("毕业设计模板策略不存在")
    with session() as db:
        policy = db.scalars(select(GraduationTemplateAssetPolicy).where(
            GraduationTemplateAssetPolicy.tenant_id == _tid(),
            GraduationTemplateAssetPolicy.id == int(policy_id),
            GraduationTemplateAssetPolicy.is_deleted.is_(False),
        ).with_for_update()).first()
        if not policy:
            raise not_found("毕业设计模板策略不存在")
        if int(policy.version or 0) != int(expected_version):
            raise AppException("DATA_CONFLICT", "模板策略版本已变化，请刷新后重试")
        if enabled:
            if not policy.current_version_id:
                raise AppException("DATA_CONFLICT", "模板尚未发布文件版本")
            version = db.scalars(select(FileVersion).where(
                FileVersion.tenant_id == _tid(),
                FileVersion.id == int(policy.current_version_id),
                FileVersion.is_current.is_(True),
                FileVersion.is_deleted.is_(False),
            )).first()
            file_obj = db.get(FileObject, int(version.file_object_id)) if version else None
            if not version or not file_obj:
                raise AppException("DATA_CONFLICT", "模板当前文件版本不存在")
            legacy_center._require_file_ready(file_obj)
        policy.enabled = bool(enabled)
        policy.status = "ENABLED" if enabled else "DISABLED"
        policy.effective_at = datetime.utcnow() if enabled else policy.effective_at
        policy.version = int(policy.version or 0) + 1
        db.commit()
        return {
            "policyId": str(policy.id), "templateCode": policy.template_code,
            "enabled": bool(policy.enabled), "status": policy.status,
            "version": int(policy.version or 0), "effectiveAt": _iso(policy.effective_at),
        }
'''
    if append_once(catalog, status_function, "def update_template_policy_status("):
        if catalog not in changed:
            changed.append(catalog)

    old = '''@router.get("/material-center/templates/{template_id}/versions", summary="模板资产版本历史")
def template_versions(template_id: int, user=Depends(get_current_user)):
    return success(center.template_versions(template_id))
'''
    new = '''@router.post("/material-center/templates/policies/{policy_id}/status", summary="启用或停用模板资产策略")
def update_template_status(policy_id: int, body: dict = Body(...), user=Depends(get_current_user)):
    enabled = bool((body or {}).get("enabled"))
    expected = (body or {}).get("expectedVersion")
    if not str(expected or "").isdigit():
        raise AppException("VALIDATION_ERROR", "expectedVersion 不能为空")
    return success(catalog.update_template_policy_status(
        policy_id, enabled, int(expected), user,
    ), message="模板状态已更新")


@router.get("/material-center/templates/{template_id}/versions", summary="模板资产版本历史")
def template_versions(template_id: int, user=Depends(get_current_user)):
    return success(center.template_versions(template_id))
'''
    if replace_exact(router, old, new, 'templates/policies/{policy_id}/status'):
        changed.append(router)

    old = '''  templateVersions(templateId) {
    return request(`/graduation/material-center/templates/${encodeURIComponent(templateId)}/versions`)
  },
'''
    new = '''  setTemplateStatus(policyId, enabled, expectedVersion) {
    return request(`/graduation/material-center/templates/policies/${encodeURIComponent(policyId)}/status`, {
      method: 'POST', data: { enabled, expectedVersion }
    })
  },
  templateVersions(templateId) {
    return request(`/graduation/material-center/templates/${encodeURIComponent(templateId)}/versions`)
  },
'''
    if replace_exact(frontend_api, old, new, "setTemplateStatus(policyId"):
        changed.append(frontend_api)

    old = '''      <section class="gm-panel gm-templates">
        <header class="gm-section-head"><div><strong>模板资产与版本</strong><span>DOCX / PDF / XLSX / PPTX，更新模板只新增 FileVersion</span></div><button class="gm-btn" @click="loadTemplates">刷新模板</button></header>
        <div v-if="!templates.length" class="gm-state">当前批次尚未发布公共模板资产</div>
        <div v-else class="gm-table-wrap"><table><thead><tr><th>模板代码</th><th>模板名称</th><th>范围</th><th>状态</th><th>当前版本</th><th>历史版本</th></tr></thead>
          <tbody><tr v-for="item in templates" :key="item.policyId"><td><code>{{ item.templateCode }}</code></td><td>{{ item.templateName }}</td><td>{{ item.collegeId || '全校' }} / {{ item.majorId || '全部专业' }}</td><td>{{ item.status }}</td><td>{{ item.currentVersionId || '-' }}</td><td>{{ item.versions?.length || 0 }}</td></tr></tbody>
        </table></div>
      </section>
'''
    new = '''      <section class="gm-panel gm-templates">
        <header class="gm-section-head"><div><strong>模板资产与版本</strong><span>学校管理员自助上传、配置变量并启停；更新只新增 FileVersion</span></div><button class="gm-btn" @click="loadTemplates">刷新模板</button></header>
        <form class="gm-template-form" @submit.prevent="publishTemplate">
          <label>模板<select v-model="templateForm.templateId" required><option value="">请选择</option><option v-for="item in templateOptions" :key="item.templateId" :value="item.templateId">{{ item.templateType }} · {{ item.templateName }}</option></select></label>
          <label>模板代码<input v-model.trim="templateForm.templateCode" required placeholder="如 GD_PROPOSAL" /></label>
          <label>学院范围<input v-model.trim="templateForm.collegeId" placeholder="留空为全校" /></label>
          <label>专业范围<input v-model.trim="templateForm.majorId" placeholder="留空为全部专业" /></label>
          <label class="gm-template-form__schema">变量 Schema<textarea v-model="templateForm.variableSchemaText" rows="4" spellcheck="false" /></label>
          <div class="gm-template-form__upload">
            <FileUploader biz-type="GRADUATION_TEMPLATE" :biz-id="templateForm.templateId || 'new'" accept=".docx,.pdf,.xlsx,.pptx" button-text="上传模板新版本" @uploaded="onTemplateUploaded" />
            <span>{{ templateForm.fileName || '尚未上传文件' }}</span>
          </div>
          <button class="gm-btn gm-btn--primary" type="submit" :disabled="templateBusy || !templateForm.fileId">{{ templateBusy ? '发布中…' : '发布模板版本' }}</button>
        </form>
        <div v-if="!templates.length" class="gm-state">当前批次尚未发布公共模板资产</div>
        <div v-else class="gm-table-wrap"><table><thead><tr><th>模板代码</th><th>模板名称</th><th>范围</th><th>状态</th><th>当前版本</th><th>历史版本</th><th>操作</th></tr></thead>
          <tbody><tr v-for="item in templates" :key="item.policyId"><td><code>{{ item.templateCode }}</code></td><td>{{ item.templateName }}</td><td>{{ item.collegeId || '全校' }} / {{ item.majorId || '全部专业' }}</td><td>{{ item.status }}</td><td>{{ item.currentVersionId || '-' }}</td><td>{{ item.versions?.length || 0 }}</td><td><button class="gm-btn" @click="toggleTemplate(item)">{{ item.enabled ? '停用' : '启用' }}</button></td></tr></tbody>
        </table></div>
      </section>
'''
    if replace_exact(frontend_view, old, new, "gm-template-form__schema"):
        changed.append(frontend_view)

    replace_exact(
        frontend_view,
        '''import FileVersionTimeline from '@/components/file/FileVersionTimeline.vue'
import { normalizeFile } from '@/services/file/fileSdk'
''',
        '''import FileVersionTimeline from '@/components/file/FileVersionTimeline.vue'
import FileUploader from '@/components/file/FileUploader.vue'
import { normalizeFile } from '@/services/file/fileSdk'
''',
        "import FileUploader from '@/components/file/FileUploader.vue'",
    )

    replace_exact(
        frontend_view,
        '''const selectedId = ref(''); const templates = ref([]); const exportJob = ref(null)
const page = ref(1); const pageSize = 20; const missingOnly = ref(false)
''',
        '''const selectedId = ref(''); const templates = ref([]); const templateOptions = ref([]); const exportJob = ref(null)
const templateBusy = ref(false)
const templateForm = reactive({
  templateId: '', templateCode: '', collegeId: '', majorId: '', fileId: '', fileName: '',
  variableSchemaText: JSON.stringify({ variables: [{ name: 'studentName', type: 'string' }, { name: 'topicTitle', type: 'string' }] }, null, 2)
})
const page = ref(1); const pageSize = 20; const missingOnly = ref(false)
''',
        "const templateBusy = ref(false)",
    )

    replace_exact(
        frontend_view,
        '''async function loadTemplates() { if (!batchId.value) return; const data = await api.templateCatalog(batchId.value); templates.value = data.items || [] }
''',
        '''async function loadTemplates() {
  if (!batchId.value) return
  const data = await api.templateCatalog(batchId.value)
  templates.value = data.items || []
  templateOptions.value = data.availableTemplates || []
}
function onTemplateUploaded(file) { templateForm.fileId = file.fileId; templateForm.fileName = file.fileName || '' }
async function publishTemplate() {
  templateBusy.value = true; error.value = ''
  try {
    const variableSchema = JSON.parse(templateForm.variableSchemaText || '{}')
    await api.publishTemplateAsset(templateForm.templateId, templateForm.fileId, {
      templateCode: templateForm.templateCode, batchId: batchId.value,
      collegeId: templateForm.collegeId, majorId: templateForm.majorId, variableSchema
    })
    templateForm.fileId = ''; templateForm.fileName = ''
    await loadTemplates()
  } catch (e) { error.value = e instanceof SyntaxError ? '变量 Schema 不是有效 JSON' : (e?.message || '模板发布失败') }
  finally { templateBusy.value = false }
}
async function toggleTemplate(item) {
  try { await api.setTemplateStatus(item.policyId, !item.enabled, item.version); await loadTemplates() }
  catch (e) { error.value = e?.message || '模板状态更新失败' }
}
''',
        "async function toggleTemplate(item)",
    )

    replace_exact(
        frontend_view,
        '''.gm-detail{max-height:1200px;overflow:auto}.gm-group''',
        '''.gm-template-form{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:12px;padding:16px;border-bottom:1px solid #edf1f7}.gm-template-form label{display:grid;gap:5px;color:#526176;font-size:13px}.gm-template-form input,.gm-template-form select,.gm-template-form textarea{border:1px solid #ccd8e8;border-radius:8px;padding:8px;background:#fff}.gm-template-form__schema{grid-column:span 2}.gm-template-form__upload{grid-column:span 3;display:flex;align-items:center;gap:12px;color:#69768b;font-size:13px}
.gm-detail{max-height:1200px;overflow:auto}.gm-group''',
        ".gm-template-form{display:grid",
    )

    if replace_exact(
        mini_sdk,
        '''function fileExtension(fileName) {
  const name = String(fileName || '').toLowerCase()
  const index = name.lastIndexOf('.')
  return index >= 0 ? name.slice(index + 1) : ''
}

export async function openBusinessFile(fileId) {
''',
        '''function fileExtension(fileName) {
  const name = String(fileName || '').toLowerCase()
  const index = name.lastIndexOf('.')
  return index >= 0 ? name.slice(index + 1) : ''
}

function openDownloaded(downloaded, fileName = '') {
  const ext = fileExtension(fileName)
  return new Promise((resolve, reject) => {
    if (['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(ext)) {
      uni.previewImage({ urls: [downloaded.tempFilePath], current: downloaded.tempFilePath, success: resolve, fail: reject })
      return
    }
    uni.openDocument({
      filePath: downloaded.tempFilePath, fileType: ext || undefined, showMenu: true,
      success: resolve,
      fail: (error) => reject({ code: 'PREVIEW_FAILED', message: error?.errMsg || '当前文件无法预览，请在 PC 端查看' })
    })
  })
}

export async function openBusinessFile(fileId) {
''',
        "function openDownloaded(downloaded",
    ):
        changed.append(mini_sdk)

    replace_exact(
        mini_sdk,
        '''  const downloaded = await realDownload(`/files/download/${enc(id)}`)
  const ext = fileExtension(meta.fileName)
  return new Promise((resolve, reject) => {
    if (['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(ext)) {
      uni.previewImage({
        urls: [downloaded.tempFilePath],
        current: downloaded.tempFilePath,
        success: () => resolve(meta),
        fail: (error) => reject({ code: 'PREVIEW_FAILED', message: error?.errMsg || '图片预览失败' })
      })
      return
    }
    uni.openDocument({
      filePath: downloaded.tempFilePath,
      fileType: ext || undefined,
      showMenu: true,
      success: () => resolve(meta),
      fail: (error) => reject({ code: 'PREVIEW_FAILED', message: error?.errMsg || '当前文件无法预览，请在管理端下载查看' })
    })
  })
''',
        '''  const downloaded = await realDownload(`/files/download/${enc(id)}`)
  await openDownloaded(downloaded, meta.fileName)
  return meta
''',
        "await openDownloaded(downloaded, meta.fileName)",
    )

    replace_exact(
        mini_sdk,
        '''  async list({ bizType, bizId }) {
''',
        '''  async openAuthorized({ fileId, ticketPath, openPath, action = 'preview', fileName = '' }) {
    const id = String(fileId || '').trim()
    if (!id) throw { code: 'FILE_REQUIRED', biz: true, message: '附件不存在' }
    const ticket = await realRequest(ticketPath, { method: 'POST', data: { action } })
    const raw = encodeURIComponent(String(ticket?.ticket || ''))
    if (!raw) throw { code: 404001, biz: true, message: '文件票据不存在或已失效' }
    const downloaded = await realDownload(`${openPath}?ticket=${raw}`)
    await openDownloaded(downloaded, fileName)
    return ticket
  },
  async list({ bizType, bizId }) {
''',
        "async openAuthorized({ fileId",
    )

    if replace_exact(
        student_api,
        '''  getGraduation: () => real.enrichGraduation(),
''',
        '''  getGraduation: () => real.enrichGraduation(),
  getGraduationMaterialLibrary: () =>
    realRequest('/mobile/graduation/material-center/library?includeHistory=true'),
  submitGraduationMaterial: (materialCode, body) =>
    realRequest(`/mobile/graduation/material-center/materials/${encodeURIComponent(materialCode)}/submit`, {
      method: 'POST', data: { ...body, clientSurface: 'MP_WEIXIN' }
    }),
''',
        "getGraduationMaterialLibrary",
    ):
        changed.append(student_api)

    if replace_exact(
        teacher_api,
        '''import { mockRequest, realFirst, realFirstStrict } from './request'
''',
        '''import { mockRequest, realFirst, realFirstStrict, realRequest } from './request'
''',
        "realFirstStrict, realRequest",
    ):
        changed.append(teacher_api)

    replace_exact(
        teacher_api,
        '''  getGraduationFinalDetail: (id) => real.gdTeacherFinalDetail(id),
''',
        '''  getGraduationFinalDetail: (id) => real.gdTeacherFinalDetail(id),
  getGraduationMaterialLibrary: (gdStudentId) =>
    realRequest(`/mobile/graduation/material-center/library?gdStudentId=${encodeURIComponent(gdStudentId)}&includeHistory=true`),
  reviewGraduationMaterial: (materialId, body) =>
    realRequest(`/mobile/graduation/material-center/materials/${encodeURIComponent(materialId)}/review`, {
      method: 'POST', data: body
    }),
''',
        "getGraduationMaterialLibrary: (gdStudentId)",
    )

    if replace_exact(
        student_page,
        '''        <!-- 归档 -->
        <view v-if="archive && archive.hasData" id="gd-archive"''',
        '''        <!-- 统一材料库：状态、版本、退回原因和小型材料补交 -->
        <view v-if="materials" id="gd-materials" class="section-head"><text class="section-head__title">材料库</text></view>
        <view v-if="materials" class="card stack-sm">
          <view class="gd__choice-row"><text class="gd__choice-title">18 类材料 · 缺 {{ materialCount('MISSING') }} · 退回 {{ materialCount('RETURNED') }}</text></view>
          <view v-for="m in materials.items || []" :key="m.materialId" class="gd__final-item">
            <view class="gd__choice-row">
              <view class="flex-1"><text class="gd__choice-title">{{ m.materialName }}</text><text class="gd__hint">{{ m.materialCode }} · 当前版本 {{ m.currentVersion?.versionNo || '—' }} · {{ m.currentVersion?.scanStatus || '未上传' }}</text></view>
              <MobileStatusTag :label="m.reviewStatus || m.businessStatus" :type="m.reviewStatus === 'APPROVED' ? 'success' : m.reviewStatus === 'RETURNED' ? 'danger' : 'warning'" />
            </view>
            <MobileInlineAlert v-if="m.rejectReason" type="danger" title="需要重交" :description="m.rejectReason" />
            <view class="gg__actions">
              <button v-if="m.currentVersion?.fileId && (m.currentVersion.allowedActions || []).includes('preview')" class="btn btn-ghost" @click="openMaterial(m)">安全预览</button>
              <button v-if="canMiniSubmit(m)" class="btn btn-primary" :disabled="materialUploadingCode === m.materialCode" @click="submitSmallMaterial(m)">{{ materialUploadingCode === m.materialCode ? '上传中…' : '补交小型材料' }}</button>
              <text v-else-if="isPcOnly(m.materialCode) && ['MISSING','RETURNED'].includes(m.businessStatus)" class="gd__hint">大型论文、作品或源代码请到学生 PC 上传</text>
            </view>
          </view>
        </view>

        <!-- 归档 -->
        <view v-if="archive && archive.hasData" id="gd-archive"''',
        "统一材料库：状态、版本",
    ):
        changed.append(student_page)

    replace_exact(
        student_page,
        '''import { normalizeError, getToken } from '@/services/request'
import { go, toast } from '@/utils/nav'
import { ENV } from '@/config/env'
''',
        '''import { normalizeError } from '@/services/request'
import fileSdk from '@/services/fileSdk'
import { go, toast } from '@/utils/nav'
''',
        "import fileSdk from '@/services/fileSdk'",
    )

    replace_exact(
        student_page,
        '''      defense: null, grade: null, archive: null,
''',
        '''      defense: null, grade: null, archive: null, materials: null, materialUploadingCode: '',
''',
        "materialUploadingCode",
    )

    replace_exact(
        student_page,
        '''      if (this.archive && this.archive.hasData) nav.push({ label: '归档', anchor: 'archive' })
''',
        '''      if (this.materials) nav.push({ label: '材料', anchor: 'materials' })
      if (this.archive && this.archive.hasData) nav.push({ label: '归档', anchor: 'archive' })
''',
        "nav.push({ label: '材料', anchor: 'materials' })",
    )

    replace_exact(
        student_page,
        '''        track('归档', studentApi.getGraduationArchive().then((d) => { this.archive = d }))
''',
        '''        track('归档', studentApi.getGraduationArchive().then((d) => { this.archive = d })),
        track('材料库', studentApi.getGraduationMaterialLibrary().then((d) => { this.materials = d }))
''',
        "studentApi.getGraduationMaterialLibrary()",
    )

    old_upload_start = "    // 附件：选择 → 校验大小/类型 → 真实上传文件中心 → 记录 file_id（提交时随材料一起提交）\n    pickUpload(target) {"
    text = (ROOT / student_page).read_text(encoding="utf-8")
    if "公共 File SDK：统一鉴权刷新" not in text:
        start = text.find(old_upload_start)
        end = text.find("    removeAtt(target, i) {", start)
        if start < 0 or end < 0:
            raise SystemExit(f"refusing to patch changed source: {student_page} upload block")
        new_upload = '''    // 公共 File SDK：统一鉴权刷新、错误处理与上传合同；小程序不承担大型论文/ZIP上传。
    async pickUpload(target) {
      if (this.uploading) return
      // #ifdef MP-WEIXIN
      if (target === 'final') { toast('论文定稿、作品和源代码请使用学生 PC 上传'); return }
      // #endif
      const arr = target === 'prop' ? 'propAtts' : 'finalAtts'
      this.uploading = true
      try {
        const selected = await fileSdk.choose()
        if (!selected) return
        const uploaded = await fileSdk.upload(selected, { bizType: 'GRADUATION_MATERIAL' })
        this[arr].push({ fileId: uploaded.fileId, fileName: uploaded.fileName || selected.name || '附件' })
      } catch (e) { toast(normalizeError(e).text || '上传失败') }
      finally { this.uploading = false }
    },
'''
        (ROOT / student_page).write_text(text[:start] + new_upload + text[end:], encoding="utf-8")

    old_download_start = "    downloadAtt(a) {"
    text = (ROOT / student_page).read_text(encoding="utf-8")
    if "async submitSmallMaterial(material)" not in text:
        start = text.find(old_download_start)
        end = text.find("    submitRectify() {", start)
        if start < 0 or end < 0:
            raise SystemExit(f"refusing to patch changed source: {student_page} download block")
        new_download = '''    async downloadAtt(a) {
      const fileId = a && a.fileId
      if (!fileId) { toast('附件无效'); return }
      try {
        await fileSdk.openAuthorized({
          fileId,
          fileName: a.fileName,
          ticketPath: `/mobile/graduation/material-center/files/${encodeURIComponent(fileId)}/ticket`,
          openPath: `/mobile/graduation/material-center/files/${encodeURIComponent(fileId)}/preview`,
          action: 'preview'
        })
      } catch (e) { toast(normalizeError(e).text || '附件暂不可预览') }
    },
    materialCount(status) { return ((this.materials && this.materials.items) || []).filter((m) => m.businessStatus === status || m.reviewStatus === status).length },
    isPcOnly(code) { return ['THESIS_DRAFT', 'THESIS_FINAL', 'DESIGN_WORK', 'SOURCE_CODE', 'WORK_DESCRIPTION'].includes(code) },
    canMiniSubmit(material) { return !this.isPcOnly(material.materialCode) && ['MISSING', 'RETURNED'].includes(material.businessStatus) },
    async openMaterial(material) { return this.downloadAtt(material.currentVersion || {}) },
    async submitSmallMaterial(material) {
      if (this.materialUploadingCode) return
      this.materialUploadingCode = material.materialCode
      try {
        const selected = await fileSdk.choose()
        if (!selected) return
        if (Number(selected.size || 0) > 8 * 1024 * 1024) { toast('小程序仅支持 8MB 以内材料，请到学生 PC 上传'); return }
        const uploaded = await fileSdk.upload(selected, { bizType: 'GRADUATION_MATERIAL', bizId: material.materialId })
        await studentApi.submitGraduationMaterial(material.materialCode, {
          fileId: uploaded.fileId, expectedVersion: material.version
        })
        uni.showToast({ title: '材料已提交', icon: 'success' })
        this.materials = await studentApi.getGraduationMaterialLibrary()
      } catch (e) { toast(normalizeError(e).text || '材料提交失败') }
      finally { this.materialUploadingCode = '' }
    },
'''
        (ROOT / student_page).write_text(text[:start] + new_download + text[end:], encoding="utf-8")

    if replace_exact(
        teacher_page,
        '''            <view v-if="detail.attachmentsList && detail.attachmentsList.length" class="rv__block">
              <text class="rv__label">材料附件（点击下载）</text>
              <view v-for="a in detail.attachmentsList" :key="a.fileId" class="rv__att" @click="downloadAtt(a)"><text class="rv__att-name">📎 {{ a.fileName }}</text><text class="rv__att-dl">下载</text></view>
            </view>
''',
        '''            <view v-if="detail.currentSafeVersions && detail.currentSafeVersions.length" class="rv__block">
              <text class="rv__label">当前安全版本（审核锁定）</text>
              <view v-for="v in detail.currentSafeVersions" :key="v.versionId" class="rv__att" @click="openVersion(v)">
                <view><text class="rv__att-name">📎 {{ v.fileName }}</text><text class="rv__text">FileVersion {{ v.versionId }} · v{{ v.versionNo }} · {{ v.scanStatus }} · {{ v.reviewStatus || v.status }}</text></view>
                <text class="rv__att-dl">安全预览</text>
              </view>
              <text v-if="!detail.reviewReady" class="rv__warn">文件仍在扫描、已隔离或版本已变化，当前不能审核通过</text>
            </view>
            <view v-else-if="detail.attachmentsList && detail.attachmentsList.length" class="rv__block">
              <text class="rv__label">历史兼容附件</text>
              <view v-for="a in detail.attachmentsList" :key="a.fileId" class="rv__att" @click="openVersion(a)"><text class="rv__att-name">📎 {{ a.fileName }}</text><text class="rv__att-dl">安全预览</text></view>
            </view>
''',
        "当前安全版本（审核锁定）",
    ):
        changed.append(teacher_page)

    replace_exact(
        teacher_page,
        '''import { normalizeError } from '@/services/request'
import { go, toast } from '@/utils/nav'
import { ENV } from '@/config/env'
import { getToken } from '@/services/request'
''',
        '''import { normalizeError } from '@/services/request'
import fileSdk from '@/services/fileSdk'
import { go, toast } from '@/utils/nav'
''',
        "import fileSdk from '@/services/fileSdk'",
    )

    replace_exact(
        teacher_page,
        '''    canAct() { return !this.acting && !!this.detail && this.detailState === 'ready' }
''',
        '''    canAct() {
      const needsSafeVersion = this.reviewKind === 'proposal' || this.reviewKind === 'final'
      return !this.acting && !!this.detail && this.detailState === 'ready'
        && (!needsSafeVersion || this.detail.reviewReady === true)
    }
''',
        "const needsSafeVersion = this.reviewKind",
    )

    text = (ROOT / teacher_page).read_text(encoding="utf-8")
    if "async openVersion(item)" not in text:
        start = text.find("    downloadAtt(a) {")
        end = text.find("    addGuidance(g) {", start)
        if start < 0 or end < 0:
            raise SystemExit(f"refusing to patch changed source: {teacher_page} download block")
        replacement = '''    async openVersion(item) {
      const fileId = item && item.fileId
      if (!fileId) { toast('附件无效'); return }
      try {
        await fileSdk.openAuthorized({
          fileId,
          fileName: item.fileName,
          ticketPath: `/mobile/graduation/material-center/files/${encodeURIComponent(fileId)}/ticket`,
          openPath: `/mobile/graduation/material-center/files/${encodeURIComponent(fileId)}/preview`,
          action: 'preview'
        })
      } catch (e) { toast(normalizeError(e).text || '材料尚未通过安全扫描或无权限') }
    },
    downloadAtt(a) { return this.openVersion(a) },
'''
        (ROOT / teacher_page).write_text(text[:start] + replacement + text[end:], encoding="utf-8")

    print("phase 6 client/template patch complete:", ", ".join(changed) if changed else "already applied")


if __name__ == "__main__":
    main()
