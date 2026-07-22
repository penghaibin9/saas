<template>
  <BasePortalLayout title="公共组件预览" subtitle="商业化底座验收" :menus="[]" active-key="">
    <section class="gallery">
      <!-- 顶部说明 -->
      <header class="g-intro">
        <h1 class="g-intro__title">公共组件商业化底座 · 预览与验收</h1>
        <p class="g-intro__desc">
          这是全系统公共组件预览页。<strong>后续业务页面（学工 / 教务 / 毕设 / 实习 / 迎新）必须优先调用这里的组件</strong>，
          不允许每个页面各写一套。下方按 9 组展示，每个组件都有一个高校业务示例。
        </p>
        <div class="g-legend">
          <span class="g-tag g-tag--partial">partial 部分完成</span>
          <span class="g-tag g-tag--backend">后端负责</span>
          <span class="g-tag g-tag--alias">统一别名</span>
          <span class="g-legend__hint">partial=UI 就绪但业务能力未接后端/库；后端负责=展示/交互层，真实能力由后端；别名=复用既有组件统一命名。</span>
        </div>
      </header>

      <!-- ========== 第一组：权限 / 审计 / 安全 ========== -->
      <details class="g-group" open>
        <summary class="g-group__sum">第一组 · 权限 / 审计 / 安全（3）</summary>
        <div class="g-grid">
          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppPermissionButton</span><span class="g-tag g-tag--backend">越权后端拦截</span></div>
            <p class="cmp__ctx">学生无权限操作「导师分配」→ 置灰并提示；有权限才可点。</p>
            <div class="cmp__demo cmp__demo--row">
              <AppPermissionButton :allowed="false" reason="学生无「导师分配」权限">分配导师</AppPermissionButton>
              <AppPermissionButton :allowed="true" @click="onDemoClick('分配导师')">分配导师</AppPermissionButton>
              <AppPermissionButton :allowed="true" variant="danger" @click="onDemoClick('删除批次')">删除批次</AppPermissionButton>
              <AppPermissionButton :allowed="true" :loading="true">提交中</AppPermissionButton>
            </div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppSensitiveText</span><span class="g-tag g-tag--backend">查看明文写审计</span></div>
            <p class="cmp__ctx">学生身份证 / 手机号 / 学号 / 姓名脱敏，点「查看」由调用方写审计。</p>
            <div class="cmp__demo">
              <div class="kv"><span>手机号</span><AppSensitiveText type="phone" value="13512346867" revealable @reveal="onDemoClick('查看手机号-写审计')" /></div>
              <div class="kv"><span>身份证</span><AppSensitiveText type="idcard" value="430102200601011234" revealable @reveal="onDemoClick('查看身份证-写审计')" /></div>
              <div class="kv"><span>姓名</span><AppSensitiveText type="name" value="李明" code="S2026-000188" /></div>
            </div>
          </div>

          <div class="cmp cmp--wide">
            <div class="cmp__head"><span class="cmp__name">AppAuditTrail</span><span class="g-tag g-tag--backend">展示后端真实审计</span></div>
            <p class="cmp__ctx">开题材料审核操作留痕（成功 / 越权拒绝按语义色区分）。</p>
            <div class="cmp__demo"><AppAuditTrail :records="demoAuditRecords" /></div>
          </div>
        </div>
      </details>

      <!-- ========== 第二组：导出 / 附件 / 确认 ========== -->
      <details class="g-group" open>
        <summary class="g-group__sum">第二组 · 导出 / 附件 / 确认（5）</summary>
        <div class="g-grid">
          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppExportButton</span><span class="g-tag g-tag--partial">导出走后端</span></div>
            <p class="cmp__ctx">导出毕业设计学生台账；演示环境未接后端，点击真实提示失败（不伪造成功）。</p>
            <div class="cmp__demo cmp__demo--row">
              <AppExportButton :export-fn="demoExportFn">导出学生台账</AppExportButton>
              <AppExportButton :export-fn="demoExportFn" :has-permission="false">无权限导出</AppExportButton>
            </div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppExportConfirm</span><span class="g-tag g-tag--partial">导出审计后端</span></div>
            <p class="cmp__ctx">导出前安全确认：必填导出用途，写入审计。</p>
            <div class="cmp__demo"><AppButton @click="showExport = true">导出学生台账（弹确认）</AppButton></div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppConfirmDialog</span></div>
            <p class="cmp__ctx">退回开题材料：必填退回原因 + 可勾选通知学生。</p>
            <div class="cmp__demo"><AppButton variant="danger" @click="showReturn = true">退回材料（弹确认）</AppButton></div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppFilePreview</span></div>
            <p class="cmp__ctx">开题报告附件预览入口（只展示与派发事件）。</p>
            <div class="cmp__demo">
              <AppFilePreview :files="previewFiles" @preview="onDemoClick('预览附件')" @download="onDemoClick('下载附件')" />
            </div>
          </div>

          <div class="cmp cmp--wide">
            <div class="cmp__head"><span class="cmp__name">AppFileList</span><span class="g-tag g-tag--partial">上传未接文件中心</span></div>
            <p class="cmp__ctx">附件清单：含上传中 / 失败 / 敏感（下载写审计）等状态。</p>
            <div class="cmp__demo">
              <AppFileList :files="demoFiles" removable @preview="onDemoClick('预览')" @download="onDemoClick('下载-写审计')" @remove="onDemoClick('移除')" />
            </div>
          </div>
        </div>
      </details>

      <!-- ========== 第三组：批量 / 审批 / 流程 / 待办 ========== -->
      <details class="g-group" open>
        <summary class="g-group__sum">第三组 · 批量 / 审批 / 流程 / 待办（5）</summary>
        <div class="g-grid">
          <div class="cmp cmp--wide">
            <div class="cmp__head"><span class="cmp__name">AppBatchActionBar</span></div>
            <p class="cmp__ctx">批量催交开题材料：勾选后浮出操作条（导出 / 分配 / 删除）。</p>
            <div class="cmp__demo">
              <div class="cmp__demo--row" style="margin-bottom: 8px">
                <AppButton @click="batchCount = Math.min(batchCount + 3, 42)">+ 选中 3 项</AppButton>
                <AppButton variant="ghost" @click="batchCount = 0">清空</AppButton>
                <span class="cmp__note">当前选中 {{ batchCount }} 项</span>
              </div>
              <AppBatchActionBar :count="batchCount" :total="42" :actions="batchActions" :float="false"
                @action="onBatchAction" @clear="batchCount = 0" @select-all="batchCount = 42" />
            </div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppApprovalPanel</span><span class="g-tag g-tag--backend">流转由审批引擎</span></div>
            <p class="cmp__ctx">审核开题材料：通过 / 退回修改 / 驳回（退回驳回必填意见）。</p>
            <div class="cmp__demo">
              <AppApprovalPanel title="开题材料审核" status="PENDING_APPROVE" current-node="导师审核" current-handler="陈老师"
                :history="demoApprovalHistory" :can-approve="true" :can-return="true" :can-reject="true"
                @approve="onApprove" @return="onApprove" @reject="onApprove" />
            </div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppWorkflowTimeline</span><span class="g-tag g-tag--backend">流转由后端</span></div>
            <p class="cmp__ctx">毕业设计流程进度：提交 → 预审 → 审批（进行中）→ 复核 → 归档。</p>
            <div class="cmp__demo"><AppWorkflowTimeline :nodes="demoWfNodes" :current-index="2" /></div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppTodoPanel</span></div>
            <p class="cmp__ctx">工作台我的待办（优先级 / 逾期 / 操作按钮）。</p>
            <div class="cmp__demo"><AppTodoPanel :items="demoTodos" show-more @open="onDemoClick('打开待办')" @action="onDemoClick('处理待办')" @more="onDemoClick('查看全部')" /></div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppNotificationPanel</span></div>
            <p class="cmp__ctx">消息通知（未读高亮 + 全部已读）。</p>
            <div class="cmp__demo"><AppNotificationPanel :items="demoNotifs" @open="onDemoClick('打开消息')" @read-all="markAllRead" /></div>
          </div>
        </div>
      </details>

      <!-- ========== 第四组：页面骨架 ========== -->
      <details class="g-group" open>
        <summary class="g-group__sum">第四组 · 页面骨架（10）</summary>
        <div class="g-grid">
          <div class="cmp cmp--wide">
            <div class="cmp__head"><span class="cmp__name">AppPageShell</span><span class="g-tag g-tag--alias">= ModulePageShell</span></div>
            <p class="cmp__ctx">页面外壳：标题 + 当前角色 + 数据范围 + 水印容器。</p>
            <div class="cmp__demo cmp__box">
              <AppPageShell title="毕业设计中心" subtitle="2026 届（春）" role-name="毕设管理员" data-scope-name="信息工程学院" :watermark="false">
                <div class="cmp__slot-hint">页面内容区（slot）</div>
              </AppPageShell>
            </div>
          </div>

          <div class="cmp cmp--wide">
            <div class="cmp__head"><span class="cmp__name">AppModuleHero</span><span class="g-tag g-tag--alias">= ModuleHero</span></div>
            <p class="cmp__ctx">看板头部概览条：关键胶囊 + 指标 + 状态机人数轨道。</p>
            <div class="cmp__demo">
              <AppModuleHero title="毕设看板 · 2026 届" subtitle="信息工程学院"
                :chips="['毕设管理员', '本院范围', '选题开放中']"
                :stats="heroStats" :flow="heroFlow" />
            </div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppPageHeader</span></div>
            <p class="cmp__ctx">通用页面标题区。</p>
            <div class="cmp__demo cmp__box"><AppPageHeader title="选题管理" subtitle="学生在开放期内选题，导师确认后入池" /></div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppSectionHeader</span><span class="g-tag g-tag--alias">= ui/SectionHeader</span></div>
            <p class="cmp__ctx">区块标题（序号 + 标题 + 副标题）。</p>
            <div class="cmp__demo cmp__box"><AppSectionHeader index="1" title="开题材料" subtitle="需上传任务书、开题报告" /></div>
          </div>

          <div class="cmp cmp--wide">
            <div class="cmp__head"><span class="cmp__name">AppSectionCard</span></div>
            <p class="cmp__ctx">区块卡片（标题 + 帮助 + 可折叠 + 页脚）。</p>
            <div class="cmp__demo">
              <AppSectionCard title="选题统计" help="按当前批次口径统计" collapsible>
                <template #header-extra><AppButton variant="ghost">导出</AppButton></template>
                这里是区块内容。
                <template #footer><span class="cmp__note">数据更新于 09:00</span></template>
              </AppSectionCard>
            </div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppToolbar</span><span class="g-tag g-tag--alias">= ModuleToolbar</span></div>
            <p class="cmp__ctx">列表顶部操作栏（含禁用+原因）。</p>
            <div class="cmp__demo cmp__box">
              <AppToolbar :actions="toolbarActions" hint="共 128 条" @action="onDemoClick" />
            </div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppActionBar</span></div>
            <p class="cmp__ctx">操作按钮行（左右分组对齐）。</p>
            <div class="cmp__demo cmp__box">
              <AppActionBar align="between">
                <template #left><span class="cmp__note">已选 3 人</span></template>
                <AppButton variant="ghost">取消</AppButton>
                <AppButton variant="primary">确定分配</AppButton>
              </AppActionBar>
            </div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppStickyFooter</span></div>
            <p class="cmp__ctx">吸底操作条（内容滚动时常驻）。</p>
            <div class="cmp__demo cmp__scrollbox">
              <div style="padding: 12px">向下滚动，页脚吸底 ↓<div style="height: 120px" /></div>
              <AppStickyFooter>
                <template #info><span class="cmp__note">3 处未保存</span></template>
                <AppButton variant="ghost">取消</AppButton>
                <AppButton variant="primary">保存</AppButton>
              </AppStickyFooter>
            </div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppDrawerLayout</span></div>
            <p class="cmp__ctx">抽屉内部布局（标题 + 滚动体 + 页脚）。</p>
            <div class="cmp__demo cmp__box" style="height: 240px; padding: 0">
              <AppDrawerLayout title="学生详情" subtitle="S2026-000188 · 李明" @close="onDemoClick('关闭抽屉')">
                这里是抽屉内容，超出会滚动。
                <template #footer><AppActionBar><AppButton variant="ghost">关闭</AppButton><AppButton variant="primary">保存</AppButton></AppActionBar></template>
              </AppDrawerLayout>
            </div>
          </div>

          <div class="cmp cmp--wide">
            <div class="cmp__head"><span class="cmp__name">AppResponsiveGrid</span></div>
            <p class="cmp__ctx">响应式栅格（按容器宽度自动换行）。</p>
            <div class="cmp__demo">
              <AppResponsiveGrid :min-col-width="150">
                <AppMetricCard v-for="n in 4" :key="n" :title="`指标 ${n}`" :value="n * 32" unit="人" />
              </AppResponsiveGrid>
            </div>
          </div>
        </div>
      </details>

      <!-- ========== 第五组：表单组件 ========== -->
      <details class="g-group" open>
        <summary class="g-group__sum">第五组 · 表单组件（12）</summary>
        <div class="cmp cmp--full">
          <div class="cmp__head"><span class="cmp__name">AppForm / AppFormItem / AppFormSection / 各控件 / AppSubmitBar</span></div>
          <p class="cmp__ctx">开题材料审核表单：一站式展示全部表单控件（含校验、必填、帮助、错误态）。</p>
          <div class="cmp__demo">
            <AppForm ref="demoForm" :model="formModel" :rules="formRules" label-width="96px">
              <AppFormSection title="基本信息" description="题目与分类">
                <AppFormItem label="题目名称" prop="title">
                  <template #default="{ status }"><AppTextInput v-model="formModel.title" :status="status" placeholder="请输入题目名称" clearable /></template>
                </AppFormItem>
                <AppResponsiveGrid :min-col-width="240" gap="0 16px">
                  <AppFormItem label="学分" prop="credit">
                    <AppNumberInput v-model="formModel.credit" :min="0" :max="10" :step="0.5" :precision="1" />
                  </AppFormItem>
                  <AppFormItem label="课题类型" prop="type">
                    <AppSelect v-model="formModel.type" :options="typeOptions" />
                  </AppFormItem>
                </AppResponsiveGrid>
                <AppFormItem label="难度" prop="level">
                  <AppRadioGroup v-model="formModel.level" :options="levelOptions" />
                </AppFormItem>
                <AppFormItem label="标签" prop="tags">
                  <AppMultiSelect v-model="formModel.tags" :options="tagOptions" searchable placeholder="可多选（校级 / 创新 / 校企合作…）" />
                </AppFormItem>
                <AppFormItem label="面向专业" prop="majors">
                  <AppCheckboxGroup v-model="formModel.majors" :options="majorCheckOptions" />
                </AppFormItem>
              </AppFormSection>

              <AppFormSection title="审核" description="结论与意见">
                <AppFormItem label="审核结论" prop="result">
                  <template #default="{ status }"><AppSelect v-model="formModel.result" :status="status" :options="resultOptions" /></template>
                </AppFormItem>
                <AppFormItem label="审核意见" prop="comment" hint="退回时必填，便于学生修改">
                  <AppTextarea v-model="formModel.comment" :rows="2" :maxlength="200" show-count />
                </AppFormItem>
                <AppFormItem label="备注（富文本）" prop="rich">
                  <template #label>备注 <span class="g-tag g-tag--partial">partial·需后端XSS清洗</span></template>
                  <AppRichTextEditor v-model="formModel.rich" placeholder="支持加粗 / 列表等基础排版…" />
                </AppFormItem>
              </AppFormSection>

              <AppSubmitBar :loading="formBusy" submit-text="提交审核" show-reset
                @submit="submitForm" @cancel="onDemoClick('取消')" @reset="resetForm" />
            </AppForm>
          </div>
        </div>
      </details>

      <!-- ========== 第六组：高校业务选择器 ========== -->
      <details class="g-group" open>
        <summary class="g-group__sum">第六组 · 高校业务选择器（42，统一适配器已接入教务与学工中心）</summary>
        <div class="cmp cmp--full">
          <p class="cmp__ctx">
            <span class="g-tag g-tag--ok">implemented</span>
            统一 UI、搜索、编辑回显与数据适配：业务页只声明实体类型和上下文 query，不再各写搜索函数。
            <strong>可见的师生 / 组织 / 批次必须由后端按数据范围返回，前端不放大范围。</strong>
          </p>
          <AppResponsiveGrid class="cmp__demo" :min-col-width="230">
            <div><label class="fld">学生 AppStudentPicker</label><AppStudentPicker v-model="pk.stu" :options="stuOptions" /></div>
            <div><label class="fld">教师 AppTeacherPicker（多选）</label><AppTeacherPicker v-model="pk.tea" multiple :options="teaOptions" /></div>
            <div><label class="fld">导师 AppMentorPicker</label><AppMentorPicker v-model="pk.mentor" :options="teaOptions" /></div>
            <div><label class="fld">班级 AppClassPicker</label><AppClassPicker v-model="pk.klass" :options="classOptions" /></div>
            <div><label class="fld">专业 AppMajorPicker</label><AppMajorPicker v-model="pk.major" :options="majorOptions" /></div>
            <div><label class="fld">学院 AppCollegePicker</label><AppCollegePicker v-model="pk.college" :options="collegeOptions" /></div>
            <div><label class="fld">课程 AppCoursePicker</label><AppCoursePicker v-model="pk.course" :options="courseOptions" /></div>
            <div><label class="fld">角色 AppRolePicker</label><AppRolePicker v-model="pk.role" :options="roleOptions" /></div>
            <div><label class="fld">学校/租户 AppTenantPicker</label><AppTenantPicker v-model="pk.tenant" :options="tenantOptions" /></div>
            <div><label class="fld">企业 AppCompanyPicker</label><AppCompanyPicker v-model="pk.company" :options="companyOptions" /></div>
            <div><label class="fld">岗位 AppPositionPicker</label><AppPositionPicker v-model="pk.position" :options="positionOptions" /></div>
            <div><label class="fld">批次 AppBatchPicker</label><AppBatchPicker v-model="pk.batch" :options="batchOptions" /></div>
            <div><label class="fld">业务学期 AppTermEntityPicker</label><AppTermEntityPicker v-model="pk.termEntity" :options="termEntityOptions" /></div>
            <div><label class="fld">学期码 AppTermCodePicker</label><AppTermCodePicker v-model="pk.termCode" :options="termCodeOptions" /></div>
            <div><label class="fld">教学任务 AppTeachingTaskPicker</label><AppTeachingTaskPicker v-model="pk.teachingTask" :options="taskOptions" /></div>
            <div><label class="fld">教学班 AppTeachingClassPicker</label><AppTeachingClassPicker v-model="pk.teachingClass" :options="classOptions" /></div>
            <div><label class="fld">教室 AppClassroomPicker</label><AppClassroomPicker v-model="pk.classroom" :options="roomOptions" /></div>
            <div><label class="fld">实训室 AppLabPicker</label><AppLabPicker v-model="pk.lab" :options="labOptions" /></div>
            <div><label class="fld">设备 AppEquipmentPicker</label><AppEquipmentPicker v-model="pk.equipment" :options="equipmentOptions" /></div>
            <div><label class="fld">节次 AppTimeSlotPicker</label><AppTimeSlotPicker v-model="pk.timeSlot" :options="timeSlotOptions" /></div>
            <div><label class="fld">课表批次 AppScheduleBatchPicker</label><AppScheduleBatchPicker v-model="pk.scheduleBatch" :options="batchOptions" /></div>
            <div><label class="fld">成绩任务 AppGradeTaskPicker</label><AppGradeTaskPicker v-model="pk.gradeTask" :options="taskOptions" /></div>
            <div><label class="fld">成绩记录 AppGradeRecordPicker</label><AppGradeRecordPicker v-model="pk.gradeRecord" :options="studentGradeOptions" /></div>
            <div><label class="fld">毕业批次 AppGraduationBatchPicker</label><AppGraduationBatchPicker v-model="pk.graduationBatch" :options="batchOptions" /></div>
            <div><label class="fld">注册批次 AppRegistrationBatchPicker</label><AppRegistrationBatchPicker v-model="pk.registrationBatch" :options="batchOptions" /></div>
            <div><label class="fld">考试批次 AppExamBatchPicker</label><AppExamBatchPicker v-model="pk.examBatch" :options="batchOptions" /></div>
            <div><label class="fld">培养方案 AppProgramPicker</label><AppProgramPicker v-model="pk.program" :options="programOptions" /></div>
            <div><label class="fld">选课批次 AppSelectionBatchPicker</label><AppSelectionBatchPicker v-model="pk.selectionBatch" :options="batchOptions" /></div>
            <div><label class="fld">补考批次 AppMakeupBatchPicker</label><AppMakeupBatchPicker v-model="pk.makeupBatch" :options="batchOptions" /></div>
            <div><label class="fld">归档批次 AppArchiveBatchPicker</label><AppArchiveBatchPicker v-model="pk.archiveBatch" :options="batchOptions" /></div>
            <div><label class="fld">风险责任人 AppRiskOwnerPicker</label><AppRiskOwnerPicker v-model="pk.riskOwner" :options="riskOwnerOptions" /></div>
            <div><label class="fld">困难认定批次 AppAidBatchPicker</label><AppAidBatchPicker v-model="pk.aidBatch" :options="aidBatchOptions" /></div>
            <div><label class="fld">资助项目 AppFundingProjectPicker</label><AppFundingProjectPicker v-model="pk.fundingProject" :options="fundingProjectOptions" /></div>
            <div><label class="fld">资助批次 AppFundingBatchPicker</label><AppFundingBatchPicker v-model="pk.fundingBatch" :options="fundingBatchOptions" /></div>
            <div><label class="fld">学生归档批次 AppStudentArchiveBatchPicker</label><AppStudentArchiveBatchPicker v-model="pk.studentArchiveBatch" :options="studentArchiveBatchOptions" /></div>
            <div><label class="fld">辅导员考评周期 AppCounselorAssessmentPeriodPicker</label><AppCounselorAssessmentPeriodPicker v-model="pk.assessmentPeriod" :options="assessmentPeriodOptions" /></div>
            <div><label class="fld">宿舍楼栋 AppDormBuildingPicker</label><AppDormBuildingPicker v-model="pk.dormBuilding" :options="dormBuildingOptions" /></div>
            <div><label class="fld">宿舍房间 AppDormRoomPicker</label><AppDormRoomPicker v-model="pk.dormRoom" :options="dormRoomOptions" /></div>
            <div><label class="fld">宿舍床位 AppDormBedPicker</label><AppDormBedPicker v-model="pk.dormBed" :options="dormBedOptions" /></div>
            <div><label class="fld">学年 AppAcademicYearPicker</label><AppAcademicYearPicker v-model="pk.year" /></div>
            <div><label class="fld">学期 AppTermPicker</label><AppTermPicker v-model="pk.term" /></div>
            <div class="span2"><label class="fld">组织级联 AppOrgCascader（学院→专业→班级）</label><AppOrgCascader v-model="pk.org" :data="orgTree" /></div>
          </AppResponsiveGrid>
        </div>
      </details>

      <!-- ========== 第七组：数据展示 / 结果页 ========== -->
      <details class="g-group" open>
        <summary class="g-group__sum">第七组 · 数据展示 / 结果页（12）</summary>
        <div class="g-grid">
          <div class="cmp cmp--wide">
            <div class="cmp__head"><span class="cmp__name">AppStatusTag / AppRiskTag / AppBadge</span></div>
            <p class="cmp__ctx">业务状态 / 风险等级 / 计数徽标。</p>
            <div class="cmp__demo tag-row">
              <AppStatusTag v-for="s in statuses" :key="s" :status="s" :dot="s === 'REVIEWING'" />
              <AppRiskTag v-for="r in riskLevels" :key="r" :level="r" />
              <AppBadge type="success">已通过</AppBadge>
              <AppBadge :count="8" type="danger" />
              <AppBadge dot type="warning" />
            </div>
          </div>

          <div class="cmp cmp--wide">
            <div class="cmp__head"><span class="cmp__name">AppMetricCard</span></div>
            <p class="cmp__ctx">指标卡（趋势 / 下钻 / loading 骨架）。</p>
            <AppResponsiveGrid class="cmp__demo" :min-col-width="150">
              <AppMetricCard title="在读学生" :value="12480" unit="人" trend-type="up" trend-quality="good" trend-label="+32" />
              <AppMetricCard title="高风险" :value="18" unit="人" accent="risk" trend-type="up" trend-quality="bad" trend-label="需处理" drillable @drill="onDemoClick('下钻')" />
              <AppMetricCard title="待审批" :value="7" unit="项" accent="warning" />
              <AppMetricCard title="加载中" value="—" :loading="true" />
            </AppResponsiveGrid>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppQuickFilterChips</span></div>
            <p class="cmp__ctx">快捷筛选（全部 / 待审 / 已通过 + 计数）。</p>
            <div class="cmp__demo"><AppQuickFilterChips v-model="quick" :options="quickOptions" /></div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppSearchBox</span></div>
            <p class="cmp__ctx">搜索框（防抖 + 清空 + 回车）。</p>
            <div class="cmp__demo"><AppSearchBox v-model="search" placeholder="按学号 / 姓名搜索" @search="onDemoClick('搜索：' + $event)" /></div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppProgressBar</span></div>
            <p class="cmp__ctx">进度条（提交率 / 完成率，自动配色）。</p>
            <div class="cmp__demo" style="display: grid; gap: 10px">
              <AppProgressBar :value="92" status="auto" />
              <AppProgressBar :value="61" status="auto" />
              <AppProgressBar :value="28" status="auto" striped />
            </div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppColumnConfig</span></div>
            <p class="cmp__ctx">表格列显示/顺序配置（配合 DataTable）。</p>
            <div class="cmp__demo"><AppColumnConfig v-model:columns="columns" /></div>
          </div>

          <div class="cmp cmp--wide">
            <div class="cmp__head"><span class="cmp__name">AppDescriptionList</span></div>
            <p class="cmp__ctx">学生毕设详情键值表。</p>
            <div class="cmp__demo"><AppDescriptionList :items="descItems" :columns="2" bordered /></div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppPagination</span></div>
            <p class="cmp__ctx">分页器（页码 + 每页条数）。</p>
            <div class="cmp__demo"><AppPagination :total="128" :page="page" :page-size="20" @update:page="page = $event" /></div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppChartCard</span><span class="g-tag g-tag--partial">未接图表库</span></div>
            <p class="cmp__ctx">图表卡外壳（真实图表由调用方在 slot 渲染）。</p>
            <div class="cmp__demo"><AppChartCard title="各专业选题分布" :min-height="120"><div class="mock-bars"><i v-for="(h, i) in [70, 45, 90, 55, 30]" :key="i" :style="{ height: h + '%' }" /></div></AppChartCard></div>
          </div>

          <div class="cmp cmp--wide">
            <div class="cmp__head"><span class="cmp__name">AppOperationResult</span></div>
            <p class="cmp__ctx">Excel 导入完成结果页（成功 / 失败统计 + 下载错误行）。</p>
            <div class="cmp__demo">
              <AppOperationResult status="success" title="Excel 导入完成" description="学生名单已导入，失败行可下载核对。"
                :stats="[{ label: '成功', value: 120, type: 'success' }, { label: '失败', value: 3, type: 'danger' }]">
                <template #actions><AppButton>下载错误行 Excel</AppButton></template>
              </AppOperationResult>
            </div>
          </div>
        </div>
      </details>

      <!-- ========== 第八组：体验增强 ========== -->
      <details class="g-group" open>
        <summary class="g-group__sum">第八组 · 体验增强（9）</summary>
        <div class="g-grid">
          <div class="cmp cmp--wide">
            <div class="cmp__head"><span class="cmp__name">AppWatermark</span></div>
            <p class="cmp__ctx">带水印的学生台账（学校名 + 用户 + 时间，防截屏留痕）。</p>
            <div class="cmp__demo">
              <AppWatermark :text="['示范职业学院', '张老师 · 2026-07-09']" class="cmp__box" style="height: 120px">
                <div class="cmp__slot-hint">学生台账内容区</div>
              </AppWatermark>
            </div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppPrintButton</span></div>
            <p class="cmp__ctx">打印学生归档清单（触发浏览器打印）。</p>
            <div class="cmp__demo"><AppPrintButton label="打印归档清单" @print="onDemoClick('打印')" /></div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppKeyboardShortcut</span></div>
            <p class="cmp__ctx">快捷键（⌘K 打开搜索）。</p>
            <div class="cmp__demo"><AppKeyboardShortcut keys="ctrl+k" label="打开搜索" @trigger="onDemoClick('快捷键 ⌘K')" /></div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppAvatarGroup</span></div>
            <p class="cmp__ctx">答辩组成员头像组（溢出 +N）。</p>
            <div class="cmp__demo"><AppAvatarGroup :avatars="avatarList" :max="4" /></div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppQRCode</span><span class="g-tag g-tag--partial">未接二维码库</span></div>
            <p class="cmp__ctx">二维码占位（真实出图由后端 / 引库）。</p>
            <div class="cmp__demo"><AppQRCode value="https://demo/stu/S2026-000188" :size="96" label="学生报到码" show-value /></div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppStepGuide</span></div>
            <p class="cmp__ctx">首次进入模块的新手引导。</p>
            <div class="cmp__demo"><AppButton variant="primary" @click="guide = true">开始新手引导</AppButton></div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppCopyableText</span></div>
            <p class="cmp__ctx">可复制文本（学号 / 订单号）。</p>
            <div class="cmp__demo"><AppCopyableText value="S2026-000188" @copied="onDemoClick('已复制学号')" /></div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppHelpTooltip / AppFieldHint</span></div>
            <p class="cmp__ctx">帮助气泡 + 字段提示。</p>
            <div class="cmp__demo">
              <div class="kv"><span>综合测评 <AppHelpTooltip content="综合测评 = 学业70% + 素质30%，学期末结算。" /></span><span>92.5</span></div>
              <AppFieldHint type="hint" text="请输入 11 位手机号。" />
              <AppFieldHint type="error" text="手机号格式不正确。" />
              <AppFieldHint type="success" text="校验通过。" />
            </div>
          </div>
        </div>
      </details>

      <!-- ========== 第九组：其它既有基础组件 ========== -->
      <details class="g-group">
        <summary class="g-group__sum">第九组 · 其它既有基础组件（全局态 / 提示 / 步骤 / 时间线 / 日期）</summary>
        <div class="g-grid">
          <div class="cmp cmp--wide">
            <div class="cmp__head"><span class="cmp__name">AppGlobalState</span></div>
            <p class="cmp__ctx">页面级全局状态（就绪 / 加载 / 空 / 错误 / 无权限 / 离线…）。</p>
            <div class="cmp__demo">
              <div class="tag-row" style="margin-bottom: 10px">
                <button v-for="s in globalStates" :key="s" class="dev-chip" :class="{ 'is-active': currentState === s }" @click="currentState = s">{{ s }}</button>
              </div>
              <AppGlobalState :state="currentState" error-code="DEMO_500" @retry="currentState = 'ready'">
                <div class="cmp__slot-hint">业务内容已就绪</div>
              </AppGlobalState>
            </div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppInlineAlert</span></div>
            <p class="cmp__ctx">内联提示（材料需补充）。</p>
            <div class="cmp__demo">
              <AppInlineAlert type="warning" title="材料需要补充" description="开题报告页码不完整，请补充后重新提交。" />
            </div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppStepBar</span></div>
            <p class="cmp__ctx">步骤条（选题 → 开题 → 中期 → 答辩 → 归档）。</p>
            <div class="cmp__demo"><AppStepBar :steps="stepItems" :current="2" /></div>
          </div>

          <div class="cmp">
            <div class="cmp__head"><span class="cmp__name">AppTimeline</span></div>
            <p class="cmp__ctx">通用时间线（流程 / 操作记录）。</p>
            <div class="cmp__demo"><AppTimeline :items="timelineItems" /></div>
          </div>

          <div class="cmp cmp--wide">
            <div class="cmp__head"><span class="cmp__name">日期时间组件族（AppDatePicker / AppTimePicker / RangePicker / DeadlinePicker）</span></div>
            <p class="cmp__ctx">公共日期底座。</p>
            <AppResponsiveGrid class="cmp__demo" :min-col-width="200">
              <div><label class="fld">日期</label><AppDatePicker v-model="date1" /></div>
              <div><label class="fld">时间</label><AppTimePicker v-model="time1" /></div>
              <div><label class="fld">日期范围</label><AppDateRangePicker v-model="dateRange" /></div>
              <div><label class="fld">截止时间</label><AppDeadlinePicker v-model="deadline" /></div>
            </AppResponsiveGrid>
          </div>
        </div>
      </details>

      <p class="dev-back"><router-link to="/">← 返回产品概览首页</router-link></p>
    </section>

    <!-- 弹层 -->
    <AppConfirmDialog v-model:visible="showReturn" danger title="确认退回" content="退回后将生成学生待办和消息，学生修改后可重新提交。"
      confirm-text="确认退回" require-reason reason-label="退回原因" show-notify @confirm="showReturn = false" />
    <AppExportConfirm v-model:visible="showExport" module-name="毕业设计学生台账" :row-count="128" scope-label="信息工程学院" @confirm="onExportConfirm" />
    <AppStepGuide v-model="guide" :steps="guideSteps" @finish="onDemoClick('引导完成')" @skip="onDemoClick('跳过引导')" />
  </BasePortalLayout>
</template>

<script>
import {
  AppPageHeader, AppStatusTag, AppRiskTag, AppMetricCard, AppSensitiveText, AppGlobalState,
  AppConfirmDialog, AppExportConfirm, AppInlineAlert, AppStepBar, AppTimeline, AppFilePreview,
  AppPermissionButton, AppAuditTrail, AppFileList, AppBatchActionBar, AppApprovalPanel,
  AppExportButton, AppWorkflowTimeline, AppTodoPanel, AppNotificationPanel, AppCopyableText,
  AppHelpTooltip, AppFieldHint, AppPageShell, AppModuleHero, AppToolbar, AppSectionHeader,
  AppSectionCard, AppActionBar, AppStickyFooter, AppResponsiveGrid, AppDrawerLayout,
  AppForm, AppFormItem, AppFormSection, AppTextInput, AppNumberInput, AppTextarea, AppSelect,
  AppMultiSelect, AppRadioGroup, AppCheckboxGroup, AppSubmitBar, AppRichTextEditor,
  AppStudentPicker, AppTeacherPicker, AppMentorPicker, AppClassPicker, AppMajorPicker,
  AppCollegePicker, AppCoursePicker, AppRolePicker, AppTenantPicker, AppCompanyPicker,
  AppPositionPicker, AppBatchPicker, AppOrgCascader, AppAcademicYearPicker, AppTermPicker,
  AppTermEntityPicker, AppTermCodePicker, AppTeachingTaskPicker, AppTeachingClassPicker,
  AppClassroomPicker, AppLabPicker, AppEquipmentPicker, AppTimeSlotPicker, AppScheduleBatchPicker, AppGradeTaskPicker, AppGradeRecordPicker,
  AppGraduationBatchPicker, AppRegistrationBatchPicker, AppExamBatchPicker, AppProgramPicker,
  AppSelectionBatchPicker, AppMakeupBatchPicker, AppArchiveBatchPicker,
  AppRiskOwnerPicker, AppAidBatchPicker, AppFundingProjectPicker, AppFundingBatchPicker,
  AppStudentArchiveBatchPicker, AppCounselorAssessmentPeriodPicker, AppDormBuildingPicker, AppDormRoomPicker, AppDormBedPicker,
  AppPagination, AppSearchBox, AppQuickFilterChips, AppProgressBar, AppDescriptionList,
  AppOperationResult, AppColumnConfig, AppChartCard, AppWatermark, AppPrintButton,
  AppAvatarGroup, AppStepGuide, AppKeyboardShortcut, AppQRCode,
  AppDatePicker, AppTimePicker, AppDateRangePicker, AppDeadlinePicker
} from '@/components/common'
import { AppBadge, AppButton } from '@/components/ui'
import { toast } from '@/utils/toast'
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'

export default {
  name: 'ComponentDevPreview',
  components: {
    BasePortalLayout, AppBadge, AppButton,
    AppPageHeader, AppStatusTag, AppRiskTag, AppMetricCard, AppSensitiveText, AppGlobalState,
    AppConfirmDialog, AppExportConfirm, AppInlineAlert, AppStepBar, AppTimeline, AppFilePreview,
    AppPermissionButton, AppAuditTrail, AppFileList, AppBatchActionBar, AppApprovalPanel,
    AppExportButton, AppWorkflowTimeline, AppTodoPanel, AppNotificationPanel, AppCopyableText,
    AppHelpTooltip, AppFieldHint, AppPageShell, AppModuleHero, AppToolbar, AppSectionHeader,
    AppSectionCard, AppActionBar, AppStickyFooter, AppResponsiveGrid, AppDrawerLayout,
    AppForm, AppFormItem, AppFormSection, AppTextInput, AppNumberInput, AppTextarea, AppSelect,
    AppMultiSelect, AppRadioGroup, AppCheckboxGroup, AppSubmitBar, AppRichTextEditor,
    AppStudentPicker, AppTeacherPicker, AppMentorPicker, AppClassPicker, AppMajorPicker,
    AppCollegePicker, AppCoursePicker, AppRolePicker, AppTenantPicker, AppCompanyPicker,
    AppPositionPicker, AppBatchPicker, AppOrgCascader, AppAcademicYearPicker, AppTermPicker,
    AppTermEntityPicker, AppTermCodePicker, AppTeachingTaskPicker, AppTeachingClassPicker,
    AppClassroomPicker, AppLabPicker, AppEquipmentPicker, AppTimeSlotPicker, AppScheduleBatchPicker, AppGradeTaskPicker, AppGradeRecordPicker,
    AppGraduationBatchPicker, AppRegistrationBatchPicker, AppExamBatchPicker, AppProgramPicker,
    AppSelectionBatchPicker, AppMakeupBatchPicker, AppArchiveBatchPicker,
    AppRiskOwnerPicker, AppAidBatchPicker, AppFundingProjectPicker, AppFundingBatchPicker,
    AppStudentArchiveBatchPicker, AppCounselorAssessmentPeriodPicker, AppDormBuildingPicker, AppDormRoomPicker, AppDormBedPicker,
    AppPagination, AppSearchBox, AppQuickFilterChips, AppProgressBar, AppDescriptionList,
    AppOperationResult, AppColumnConfig, AppChartCard, AppWatermark, AppPrintButton,
    AppAvatarGroup, AppStepGuide, AppKeyboardShortcut, AppQRCode,
    AppDatePicker, AppTimePicker, AppDateRangePicker, AppDeadlinePicker
  },
  data() {
    return {
      showReturn: false, showExport: false, guide: false,
      currentState: 'ready',
      batchCount: 0,
      formBusy: false,
      page: 1, quick: '', search: '',
      date1: '', time1: '', dateRange: [], deadline: '',
      formModel: { title: '', credit: 2, type: '', level: '2', tags: [], majors: [], result: '', comment: '', rich: '' },
      formRules: {
        title: [{ required: true, message: '请输入题目名称', min: 4 }],
        result: [{ required: true, message: '请选择审核结论' }]
      },
      pk: { stu: '', tea: [], mentor: '', klass: '', major: '', college: '', course: '', role: '', tenant: '', company: '', position: '', batch: '', org: [], year: '', term: '', termEntity: '', termCode: '', teachingTask: '', teachingClass: '', classroom: '', lab: '', equipment: '', timeSlot: '', scheduleBatch: '', gradeTask: '', gradeRecord: '', graduationBatch: '', registrationBatch: '', examBatch: '', program: '', selectionBatch: '', makeupBatch: '', archiveBatch: '', riskOwner: '', aidBatch: '', fundingProject: '', fundingBatch: '', studentArchiveBatch: '', assessmentPeriod: '', dormBuilding: '', dormRoom: '', dormBed: '' },
      termEntityOptions: [{ label: '2026—2027 第1学期', value: 'term-1' }, { label: '2026—2027 第2学期', value: 'term-2' }],
      termCodeOptions: [{ label: '2026—2027 第1学期', value: '2026-1' }, { label: '2026—2027 第2学期', value: '2026-2' }],
      taskOptions: [{ label: '数据结构 · 软件2301 · 陈静', value: 'task-1' }, { label: '操作系统 · 计算机2302 · 赵磊', value: 'task-2' }],
      roomOptions: [{ label: '实训楼 A301', value: 'room-1' }, { label: '教学楼 B205', value: 'room-2' }],
      labOptions: [{ label: '网络实训室（48工位）', value: 'lab-1' }, { label: '智能制造实训室（36工位）', value: 'lab-2' }],
      equipmentOptions: [{ label: '数控车床 · SB-2026-001', value: 'equipment-1' }, { label: '教学投影仪 · SB-2026-002', value: 'equipment-2' }],
      timeSlotOptions: [{ label: '第 1 节 · 08:00-08:45', value: 'slot-1' }, { label: '第 2 节 · 08:55-09:40', value: 'slot-2' }],
      riskOwnerOptions: [{ label: '张老师', value: 'owner-1', desc: '心理中心' }, { label: '李老师', value: 'owner-2', desc: '学工处' }],
      aidBatchOptions: [{ label: '2026 年困难认定批次', value: 'aid-1', desc: '2026-2027 · OPEN' }],
      fundingProjectOptions: [{ label: '国家励志奖学金', value: 'fund-project-1', desc: 'SCHOLARSHIP · ACTIVE' }],
      fundingBatchOptions: [{ label: '2026-2027 · 国家励志奖学金', value: 'fund-batch-1', desc: 'OPEN' }],
      studentArchiveBatchOptions: [{ label: '2026 届学生归档', value: 'archive-1', desc: '2026 · COLLECTING' }],
      assessmentPeriodOptions: [{ label: '2026 年春季学期考评', value: 'period-1', desc: 'DRAFT' }],
      dormBuildingOptions: [{ label: '1 号学生公寓', value: 'building-1', desc: '空床 12' }],
      dormRoomOptions: [{ label: '302 宿舍', value: 'dorm-room-1', desc: '3 层 · 空床 1' }],
      dormBedOptions: [{ label: '3 号床', value: 'bed-3', desc: '空床' }],
      studentGradeOptions: [{ label: '李明 · S2026-0001 · 82分', value: 'grade-1' }, { label: '王芳 · S2026-0002 · 91分', value: 'grade-2' }],
      programOptions: [{ label: '软件技术2026级培养方案', value: 'program-1' }, { label: '大数据技术2026级培养方案', value: 'program-2' }],
      columns: [
        { key: 'no', label: '学号', visible: true, required: true },
        { key: 'name', label: '姓名', visible: true },
        { key: 'class', label: '班级', visible: true },
        { key: 'mentor', label: '导师', visible: true },
        { key: 'topic', label: '题目', visible: false },
        { key: 'status', label: '状态', visible: true }
      ],
      // —— 选项 ——
      levelOptions: [{ label: '较易', value: '1' }, { label: '适中', value: '2' }, { label: '较难', value: '3' }],
      typeOptions: [{ label: '工程设计', value: 'eng' }, { label: '理论研究', value: 'theory' }, { label: '应用开发', value: 'app' }],
      resultOptions: [{ label: '通过', value: 'pass' }, { label: '退回修改', value: 'return' }, { label: '驳回', value: 'reject' }],
      tagOptions: [{ label: '校级', value: 'sch' }, { label: '创新创业', value: 'inno' }, { label: '校企合作', value: 'coop' }, { label: '真实课题', value: 'real' }],
      majorCheckOptions: [{ label: '计算机应用', value: 'm1' }, { label: '软件技术', value: 'm2' }, { label: '大数据', value: 'm3' }],
      quickOptions: [{ label: '全部', value: '', count: 128 }, { label: '待审', value: 'p', count: 12 }, { label: '已通过', value: 'a', count: 96 }, { label: '已驳回', value: 'r', count: 20 }],
      stuOptions: [
        { label: '李明（S2026-0001）', value: 's1', desc: '计算机2301' },
        { label: '王芳（S2026-0002）', value: 's2', desc: '计算机2301' },
        { label: '张伟（S2026-0003）', value: 's3', desc: '软件2302' }
      ],
      teaOptions: [{ label: '陈静 老师（T0012）', value: 't1' }, { label: '赵磊 老师（T0033）', value: 't2' }, { label: '孙悦 老师（T0041）', value: 't3' }],
      classOptions: [{ label: '计算机2301', value: 'k1' }, { label: '计算机2302', value: 'k2' }, { label: '软件2301', value: 'k3' }],
      majorOptions: [{ label: '计算机应用技术', value: 'm1' }, { label: '软件技术', value: 'm2' }, { label: '大数据技术', value: 'm3' }],
      collegeOptions: [{ label: '信息工程学院', value: 'c1' }, { label: '经济管理学院', value: 'c2' }],
      courseOptions: [{ label: '数据结构（C0021）', value: 'co1' }, { label: '操作系统（C0033）', value: 'co2' }],
      roleOptions: [{ label: '毕设管理员', value: 'r1' }, { label: '毕设导师', value: 'r2' }, { label: '答辩秘书', value: 'r3' }],
      tenantOptions: [{ label: '示范职业学院', value: 'te1' }, { label: '实验中学', value: 'te2' }],
      companyOptions: [{ label: '××科技有限公司', value: 'cp1' }, { label: '××软件股份', value: 'cp2' }],
      positionOptions: [{ label: '前端开发实习', value: 'p1' }, { label: '测试实习', value: 'p2' }],
      batchOptions: [{ label: '2026 届毕业设计（春）', value: 'b1' }, { label: '2025 届毕业设计（春）', value: 'b2' }],
      orgTree: [
        { label: '信息工程学院', value: 'c1', children: [
          { label: '计算机应用技术', value: 'm1', children: [{ label: '计算机2301', value: 'k1' }, { label: '计算机2302', value: 'k2' }] },
          { label: '软件技术', value: 'm2', children: [{ label: '软件2301', value: 'k3' }] }
        ] },
        { label: '经济管理学院', value: 'c2', children: [{ label: '会计', value: 'm3', children: [{ label: '会计2301', value: 'k4' }] }] }
      ],
      toolbarActions: [
        { key: 'add', label: '新增题目', variant: 'primary' },
        { key: 'imp', label: '导入 Excel' },
        { key: 'del', label: '删除', disabled: true, disabledReason: '无删除权限' }
      ],
      batchActions: [{ key: 'export', label: '批量导出', icon: '⬇' }, { key: 'urge', label: '批量催交' }, { key: 'delete', label: '批量删除', danger: true }],
      heroStats: [
        { label: '毕设学生', value: 128 },
        { label: '已选题', value: 96, trend: '75%', trendQuality: 'good' },
        { label: '待审核', value: 12, trend: '需处理', trendQuality: 'bad' }
      ],
      heroFlow: [
        { label: '选题', value: 128, active: true }, { label: '开题', value: 96 }, { label: '中期', value: 40 }, { label: '答辩', value: 0 }, { label: '归档', value: 0 }
      ],
      avatarList: [{ name: '王芳' }, { name: '李明' }, { name: '张伟' }, { name: '陈静' }, { name: '赵磊' }, { name: '孙悦' }],
      previewFiles: [
        { id: 1, name: '任务书.pdf', type: 'pdf', size: '182KB', uploadedAt: '06-20' },
        { id: 2, name: '开题报告.docx', type: 'word', size: '96KB', uploadedAt: '06-21' }
      ],
      demoFiles: [
        { id: 1, name: '开题报告.pdf', size: 348160, uploadedAt: '2026-06-20', uploader: '李同学', status: 'done' },
        { id: 2, name: '困难认定材料.jpg', size: 1258291, uploadedAt: '2026-06-21', sensitive: true, status: 'done' },
        { id: 3, name: '实习周报.docx', size: 51200, status: 'uploading', progress: 62 },
        { id: 4, name: '成绩单.xlsx', size: 20480, status: 'error' }
      ],
      descItems: [
        { label: '学号', value: 'S2026-000188' }, { label: '姓名', value: '李明' },
        { label: '班级', value: '计算机2301' }, { label: '导师', value: '陈静' },
        { label: '题目', value: '基于 Vue 的教务管理系统设计', span: 2 }
      ],
      stepItems: [{ title: '选题' }, { title: '开题' }, { title: '中期' }, { title: '答辩' }, { title: '归档' }],
      timelineItems: [
        { title: '提交开题', time: '06-20 09:12', operator: '李明', type: 'primary' },
        { title: '导师通过', time: '06-21 10:03', operator: '陈静', status: 'APPROVED', type: 'success' }
      ],
      guideSteps: [
        { title: '欢迎使用毕业设计中心', description: '这里集中管理选题、导师分配、开题、过程检查、答辩与归档。' },
        { title: '先选择批次', description: '大部分操作都以「毕业设计批次」为范围，请先在顶部选择当前批次。' },
        { title: '按角色办事', description: '导师、评阅、答辩秘书看到的入口不同，系统按你的角色与数据范围展示。' }
      ],
      demoApprovalHistory: [
        { id: 1, node: '学生提交', result: '已提交', handler: '李同学', at: '2026-06-20 09:12' },
        { id: 2, node: '班主任预审', result: '已通过', handler: '王老师', at: '2026-06-20 10:03', comment: '情况属实，同意上报。' }
      ],
      demoAuditRecords: [
        { id: 1, action: '导出学生名单', actor: '张老师', actorRole: '辅导员', reason: '学院例会名单核对', ip: '10.12.3.44', at: '2026-06-22 14:20', result: '成功' },
        { id: 2, action: '查看完整手机号', actor: '李老师', actorRole: '资助老师', reason: '奖助电话核实', ip: '10.12.3.88', at: '2026-06-22 15:01', result: '成功' },
        { id: 3, action: '尝试跨班级查看', actor: '赵老师', actorRole: '专业课教师', ip: '10.12.4.10', at: '2026-06-22 16:30', result: '越权拒绝' }
      ],
      demoWfNodes: [
        { name: '学生提交', result: '已提交', handler: '李同学', at: '06-20 09:12' },
        { name: '班主任预审', result: '已通过', handler: '王老师', at: '06-20 10:03' },
        { name: '辅导员审批', result: '审批中', handler: '张老师' },
        { name: '学院复核', handler: '待处理' },
        { name: '归档' }
      ],
      demoTodos: [
        { id: 1, title: '3 份请假单待审批', meta: '计算机2301班', tag: '请假', priority: 'high', actionText: '去审批' },
        { id: 2, title: '困难认定材料待复核', meta: '2 人', at: '今天', overdue: true, actionText: '去处理' },
        { id: 3, title: '毕设中期检查提醒', meta: '本周截止', priority: 'normal' }
      ],
      demoNotifs: [
        { id: 1, title: '成绩发布审批已通过', desc: '《数据结构》期末成绩已通过教务处审核并发布。', at: '10 分钟前', read: false, type: 'success' },
        { id: 2, title: '高风险预警：出勤异常', desc: '张三近 7 天缺勤 3 次，请及时谈话。', at: '1 小时前', read: false, type: 'danger' },
        { id: 3, title: '待你审批：调停课申请', at: '昨天', read: true, type: 'approval' }
      ],
      statuses: ['DRAFT', 'PENDING_REVIEW', 'REVIEWING', 'APPROVED', 'RETURNED', 'REJECTED', 'OVERDUE', 'ARCHIVED'],
      riskLevels: ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'],
      globalStates: ['ready', 'loading', 'empty', 'error', 'forbidden', 'offline', 'readonly', 'noLicense']
    }
  },
  methods: {
    onDemoClick(label) { toast.success(`触发：${label}`) },
    onBatchAction(a) { toast.success(`批量动作：${a.label}（对 ${this.batchCount} 项）`) },
    onApprove(payload) { toast.success(`审批已提交${payload && payload.reason ? '：' + payload.reason : ''}`) },
    markAllRead() { this.demoNotifs = this.demoNotifs.map((m) => ({ ...m, read: true })); toast.success('已全部标为已读') },
    onExportConfirm() { this.showExport = false; toast.error('演示环境未接后端导出接口') },
    resetForm() { this.formModel = { title: '', credit: 2, type: '', level: '2', tags: [], majors: [], result: '', comment: '', rich: '' }; this.$refs.demoForm.clearValidate() },
    async submitForm() {
      const { valid, firstInvalid } = await this.$refs.demoForm.validate()
      if (!valid) { toast.error(`请检查表单：${firstInvalid}`); return }
      this.formBusy = true
      setTimeout(() => { this.formBusy = false; toast.success('审核已提交（演示）') }, 600)
    },
    // 演示环境：不接后端，真实返回失败，绝不伪造导出成功
    async demoExportFn() { return { code: 1, message: '演示环境未接后端导出接口' } }
  }
}
</script>

<style scoped>
.gallery {
  max-width: 1100px;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
/* 顶部说明 */
.g-intro {
  padding: var(--space-5);
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-md);
  background: var(--primary-25, var(--primary-50));
}
.g-intro__title { margin: 0 0 var(--space-2); font-size: var(--font-size-xl); color: var(--text-primary); }
.g-intro__desc { margin: 0 0 var(--space-3); font-size: var(--font-size-sm); color: var(--text-secondary); line-height: var(--line-height-base); }
.g-legend { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-2); }
.g-legend__hint { font-size: var(--font-size-xs); color: var(--text-tertiary); }
/* 标签 */
.g-tag {
  display: inline-flex; align-items: center; height: 18px; padding: 0 var(--space-2);
  border-radius: var(--radius-full); font-size: 11px; font-weight: var(--font-weight-medium); white-space: nowrap;
}
.g-tag--partial { background: var(--warning-50); color: var(--warning-700); border: 1px solid var(--warning-100); }
.g-tag--ok { background: var(--success-50); color: var(--success-700); border: 1px solid var(--success-100); }
.g-tag--backend { background: var(--info-50); color: var(--info-700); border: 1px solid var(--info-100); }
.g-tag--alias { background: var(--gray-100); color: var(--text-secondary); border: 1px solid var(--border-light); }
/* 分组 */
.g-group {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  box-shadow: var(--shadow-card);
  overflow: hidden;
}
.g-group__sum {
  cursor: pointer;
  padding: var(--space-4) var(--space-5);
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  background: var(--bg-subtle);
  list-style: none;
  display: flex; align-items: center; gap: var(--space-2);
}
.g-group__sum::before { content: '▸'; color: var(--text-tertiary); transition: transform 0.15s; }
.g-group[open] > .g-group__sum::before { transform: rotate(90deg); }
.g-group__sum::-webkit-details-marker { display: none; }
.g-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5);
}
/* 组件卡 */
.cmp {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  padding: var(--space-4);
  background: var(--bg-card);
  min-width: 0;
}
.cmp--wide { grid-column: span 2; }
.cmp--full { grid-column: 1 / -1; }
.cmp__head { display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-1); flex-wrap: wrap; }
.cmp__name { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: var(--font-size-sm); font-weight: var(--font-weight-semibold); color: var(--primary-700); }
.cmp__ctx { margin: 0 0 var(--space-3); font-size: var(--font-size-xs); color: var(--text-tertiary); line-height: 1.5; }
.cmp__demo { min-width: 0; }
.cmp__demo--row { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: center; }
.cmp__note { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.cmp__box { border: 1px dashed var(--border-base); border-radius: var(--radius-base); padding: var(--space-3); }
.cmp__slot-hint { padding: var(--space-4); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); }
.cmp__scrollbox { height: 180px; overflow-y: auto; border: 1px dashed var(--border-base); border-radius: var(--radius-base); position: relative; display: flex; flex-direction: column; }
/* 表单示例内字段栅格 */
.fld { display: block; font-size: var(--font-size-xs); color: var(--text-secondary); margin-bottom: var(--space-1); }
.span2 { grid-column: span 2; }
.kv { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); font-size: var(--font-size-sm); color: var(--text-secondary); padding: var(--space-1) 0; }
.tag-row { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: center; }
.dev-chip {
  height: 28px; padding: 0 var(--space-3); border: 1px solid var(--border-base);
  border-radius: var(--radius-full); background: var(--bg-card); cursor: pointer; font-size: var(--font-size-xs); color: var(--text-secondary);
}
.dev-chip.is-active { border-color: var(--primary-100); background: var(--primary-50); color: var(--primary-700); }
/* 图表卡 mock */
.mock-bars { display: flex; align-items: flex-end; gap: var(--space-3); height: 100px; padding: var(--space-2); }
.mock-bars i { flex: 1; background: linear-gradient(180deg, var(--primary-400, var(--primary-500)), var(--primary-600)); border-radius: var(--radius-sm) var(--radius-sm) 0 0; }
.dev-back { margin-top: var(--space-2); font-size: var(--font-size-sm); }
.dev-back a { color: var(--primary-600); text-decoration: none; }
@media (max-width: 860px) {
  .g-grid { grid-template-columns: 1fr; }
  .cmp--wide, .cmp--full { grid-column: 1 / -1; }
}
</style>
