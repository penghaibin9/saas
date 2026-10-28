-- 跃科岗位实习管理平台 Standalone baseline

-- source: main@adea054e2fd59cc0b83bbdb22f10ec98a8e2fd8c

SET NAMES utf8mb4;

CREATE TABLE t_archive_manifest (
	module_code VARCHAR(64) NOT NULL, 
	archive_type VARCHAR(64) NOT NULL, 
	target_type VARCHAR(40) NOT NULL, 
	target_id VARCHAR(64) NOT NULL, 
	revision INTEGER NOT NULL, 
	status VARCHAR(30) NOT NULL COMMENT 'PREPARED/FROZEN/PACKAGED/SUPERSEDED/REVOKED/ABORTED', 
	rule_version VARCHAR(64), 
	manifest_sha256 VARCHAR(64), 
	package_file_id BIGINT, 
	created_by_name VARCHAR(100), 
	frozen_at DATETIME, 
	revoked_at DATETIME, 
	revoked_by VARCHAR(100), 
	revoke_reason VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_archive_manifest_revision UNIQUE (tenant_id, module_code, archive_type, target_type, target_id, revision)
);

CREATE INDEX ix_archive_manifest_target ON t_archive_manifest (tenant_id, module_code, target_type, target_id, status);

CREATE INDEX ix_t_archive_manifest_manifest_sha256 ON t_archive_manifest (manifest_sha256);

CREATE INDEX ix_t_archive_manifest_module_code ON t_archive_manifest (module_code);

CREATE INDEX ix_t_archive_manifest_package_file_id ON t_archive_manifest (package_file_id);

CREATE INDEX ix_t_archive_manifest_target_id ON t_archive_manifest (target_id);

CREATE INDEX ix_t_archive_manifest_tenant_id ON t_archive_manifest (tenant_id);

CREATE TABLE t_archive_manifest_item (
	manifest_id BIGINT NOT NULL, 
	material_code VARCHAR(100) NOT NULL, 
	asset_id BIGINT NOT NULL, 
	version_id BIGINT NOT NULL, 
	file_object_id BIGINT NOT NULL, 
	file_name_snapshot VARCHAR(300) NOT NULL, 
	size_snapshot BIGINT, 
	sha256_snapshot VARCHAR(64), 
	review_status VARCHAR(40), 
	scan_result VARCHAR(30) NOT NULL, 
	uploader_snapshot VARCHAR(100), 
	submitted_at_snapshot DATETIME, 
	sort_no INTEGER NOT NULL, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_archive_manifest_item_version UNIQUE (tenant_id, manifest_id, version_id, material_code)
);

CREATE INDEX ix_archive_manifest_item_order ON t_archive_manifest_item (tenant_id, manifest_id, sort_no, id);

CREATE INDEX ix_t_archive_manifest_item_asset_id ON t_archive_manifest_item (asset_id);

CREATE INDEX ix_t_archive_manifest_item_file_object_id ON t_archive_manifest_item (file_object_id);

CREATE INDEX ix_t_archive_manifest_item_manifest_id ON t_archive_manifest_item (manifest_id);

CREATE INDEX ix_t_archive_manifest_item_tenant_id ON t_archive_manifest_item (tenant_id);

CREATE INDEX ix_t_archive_manifest_item_version_id ON t_archive_manifest_item (version_id);

CREATE TABLE t_attendance_exception (
	internship_id BIGINT NOT NULL, 
	exception_type VARCHAR(50) NOT NULL COMMENT 'OUT_OF_RANGE/MOCK_LOCATION/MISSING', 
	exception_date DATETIME NOT NULL, 
	distance_km FLOAT COMMENT '偏离距离(km)', 
	gps_accuracy FLOAT COMMENT '定位精度(m)', 
	device_risk_flag VARCHAR(50) COMMENT 'normal/is_mock', 
	address VARCHAR(300), 
	student_note VARCHAR(1000) COMMENT '学生说明', 
	streak_days INTEGER NOT NULL COMMENT '连续异常天数', 
	status VARCHAR(50) NOT NULL COMMENT 'PENDING_HANDLE/COMPLETED', 
	handle_action VARCHAR(50) COMMENT 'REASONABLE/ABNORMAL/TO_RISK', 
	handle_comment VARCHAR(500), 
	handled_by_name VARCHAR(100), 
	handled_at DATETIME, 
	appeal_status VARCHAR(30) COMMENT 'PENDING/ACCEPTED/REJECTED', 
	appeal_note VARCHAR(1000) COMMENT '学生异常申诉说明', 
	appeal_file_id VARCHAR(64) COMMENT '申诉凭证文件', 
	appealed_at DATETIME, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_t_attendance_exception_internship_id ON t_attendance_exception (internship_id);

CREATE INDEX ix_t_attendance_exception_tenant_id ON t_attendance_exception (tenant_id);

CREATE TABLE t_audit_outbox (
	event_id VARCHAR(64) NOT NULL, 
	event_type VARCHAR(100) NOT NULL, 
	payload_json JSON NOT NULL, 
	status VARCHAR(20) NOT NULL COMMENT 'PENDING/PROCESSING/PROCESSED/RETRY_WAIT/DEAD', 
	retry_count INTEGER NOT NULL, 
	next_retry_at DATETIME, 
	processed_at DATETIME, 
	last_error VARCHAR(1000), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_audit_outbox_event UNIQUE (tenant_id, event_id)
);

CREATE INDEX ix_t_audit_outbox_event_type ON t_audit_outbox (event_type);

CREATE INDEX ix_t_audit_outbox_tenant_id ON t_audit_outbox (tenant_id);

CREATE TABLE t_class (
	major_id BIGINT NOT NULL, 
	class_name VARCHAR(200) NOT NULL, 
	grade VARCHAR(20) COMMENT '年级，如 2024', 
	counselor_id BIGINT COMMENT '辅导员 user_id', 
	head_teacher_id BIGINT COMMENT '班主任 user_id', 
	status VARCHAR(50) NOT NULL, 
	remark VARCHAR(500), 
	class_code VARCHAR(50) COMMENT '班级编号', 
	capacity INTEGER COMMENT '编制人数（教学任务班级容量校验）', 
	graduate_year VARCHAR(20) COMMENT '应毕业年份，如 2027', 
	class_status VARCHAR(50) NOT NULL COMMENT '班级状态 NORMAL 在读 / GRADUATED 已毕业 / DISBANDED 已解散', 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_t_class_major_id ON t_class (major_id);

CREATE INDEX ix_t_class_tenant_id ON t_class (tenant_id);

CREATE TABLE t_college (
	college_name VARCHAR(200) NOT NULL, 
	code VARCHAR(50), 
	status VARCHAR(50) NOT NULL, 
	remark VARCHAR(500), 
	short_name VARCHAR(100) COMMENT '学院简称', 
	sort_order INTEGER NOT NULL COMMENT '展示排序（升序）', 
	secretary_id BIGINT COMMENT '教学秘书 user_id（orgs 教学秘书绑定）', 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_t_college_tenant_id ON t_college (tenant_id);

CREATE TABLE t_emp_company (
	name VARCHAR(200) NOT NULL, 
	credit_code VARCHAR(50), 
	industry VARCHAR(100), 
	nature VARCHAR(50), 
	city VARCHAR(50), 
	contact_person VARCHAR(100), 
	contact_phone_encrypted VARCHAR(500), 
	cooperation_level VARCHAR(50), 
	status VARCHAR(50) NOT NULL, 
	disable_reason VARCHAR(500), 
	hired_count INTEGER NOT NULL, 
	region VARCHAR(100) COMMENT '省市/地区', 
	address VARCHAR(300) COMMENT '详细地址', 
	scale VARCHAR(50) COMMENT '规模：微/小/中/大型', 
	source VARCHAR(50) COMMENT '来源 SELF_BUILT/SCHOOL_ENTERPRISE/STUDENT_SELF/RECOMMENDED', 
	coop_status VARCHAR(50) NOT NULL COMMENT '企业库合作状态机 PENDING/ACTIVE/REJECTED/SUSPENDED/BLACKLIST/ARCHIVED', 
	qualification_status VARCHAR(50) NOT NULL COMMENT '资质核验 UNREVIEWED/PASSED/FAILED', 
	blacklist BOOL NOT NULL, 
	blacklist_reason VARCHAR(500), 
	review_by VARCHAR(100), 
	review_at DATETIME, 
	review_comment VARCHAR(500), 
	access_valid_until DATETIME COMMENT '实习企业准入有效期', 
	intern_count INTEGER NOT NULL COMMENT '累计接收实习生数', 
	remark VARCHAR(500), 
	archived_at DATETIME, 
	archived_by VARCHAR(100), 
	logo_file_id VARCHAR(64), 
	cover_file_id VARCHAR(64), 
	short_name VARCHAR(100), 
	short_intro VARCHAR(500), 
	website VARCHAR(300), 
	main_business TEXT, 
	established_year INTEGER, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_t_emp_company_coop_status ON t_emp_company (coop_status);

CREATE INDEX ix_t_emp_company_credit_code ON t_emp_company (credit_code);

CREATE INDEX ix_t_emp_company_tenant_id ON t_emp_company (tenant_id);

CREATE TABLE t_excel_import_job (
	module_key VARCHAR(64) NOT NULL COMMENT '模块 key', 
	biz_type VARCHAR(64) NOT NULL COMMENT '业务类型', 
	file_name VARCHAR(255) COMMENT '上传文件名', 
	file_sha256 VARCHAR(64) COMMENT 'Original upload SHA-256', 
	dry_run_sha256 VARCHAR(64) COMMENT 'Dry-run result SHA-256', 
	preview_token_sha256 VARCHAR(64) COMMENT 'Preview token SHA-256', 
	batch_scope VARCHAR(500) COMMENT 'Import batch scope snapshot', 
	data_scope_snapshot JSON COMMENT 'Actor data scope snapshot', 
	template_version VARCHAR(32) NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	total_rows INTEGER NOT NULL, 
	valid_rows INTEGER NOT NULL, 
	invalid_rows INTEGER NOT NULL, 
	success_rows INTEGER NOT NULL, 
	failed_rows INTEGER NOT NULL, 
	expected_success_rows INTEGER NOT NULL, 
	error_file_key VARCHAR(255) COMMENT '错误行文件句柄（预留）', 
	operator_id BIGINT COMMENT '操作人 ID', 
	operator_name VARCHAR(100) COMMENT '操作人姓名', 
	started_at DATETIME COMMENT '开始校验时间', 
	finished_at DATETIME COMMENT '结束时间', 
	confirm_at DATETIME COMMENT '确认导入时间', 
	remark VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_t_excel_import_job_biz_type ON t_excel_import_job (biz_type);

CREATE INDEX ix_t_excel_import_job_module_key ON t_excel_import_job (module_key);

CREATE INDEX ix_t_excel_import_job_status ON t_excel_import_job (status);

CREATE INDEX ix_t_excel_import_job_tenant_id ON t_excel_import_job (tenant_id);

CREATE TABLE t_file_asset (
	asset_code VARCHAR(180) NOT NULL, 
	title VARCHAR(300) NOT NULL, 
	category_code VARCHAR(80) NOT NULL, 
	owner_type VARCHAR(30) NOT NULL, 
	owner_id VARCHAR(64), 
	current_version_id BIGINT, 
	lifecycle_status VARCHAR(30) NOT NULL COMMENT 'ACTIVE/LOCKED/ARCHIVED/DELETED', 
	version_count INTEGER NOT NULL, 
	sensitivity_level VARCHAR(30) NOT NULL, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_file_asset_code UNIQUE (tenant_id, asset_code)
);

CREATE INDEX ix_file_asset_category ON t_file_asset (tenant_id, category_code, lifecycle_status);

CREATE INDEX ix_file_asset_owner ON t_file_asset (tenant_id, owner_type, owner_id);

CREATE INDEX ix_t_file_asset_category_code ON t_file_asset (category_code);

CREATE INDEX ix_t_file_asset_current_version_id ON t_file_asset (current_version_id);

CREATE INDEX ix_t_file_asset_owner_id ON t_file_asset (owner_id);

CREATE INDEX ix_t_file_asset_tenant_id ON t_file_asset (tenant_id);

CREATE TABLE t_file_binding (
	file_id BIGINT NOT NULL, 
	biz_type VARCHAR(50) NOT NULL, 
	biz_id VARCHAR(64) NOT NULL, 
	relation_type VARCHAR(40) NOT NULL, 
	subject_type VARCHAR(30) NOT NULL, 
	subject_id VARCHAR(64), 
	batch_id VARCHAR(64), 
	version_no INTEGER NOT NULL, 
	is_current BOOL NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	scope_json JSON, 
	asset_id BIGINT, 
	version_id BIGINT, 
	module_code VARCHAR(64), 
	student_id BIGINT, 
	college_id BIGINT, 
	class_id BIGINT, 
	data_scope_snapshot_json JSON, 
	invalidated_at DATETIME, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_file_binding_relation UNIQUE (tenant_id, file_id, biz_type, biz_id, relation_type), 
	CONSTRAINT uk_file_binding_version_relation UNIQUE (tenant_id, version_id, module_code, biz_type, biz_id, relation_type)
);

CREATE INDEX ix_file_binding_asset_current ON t_file_binding (tenant_id, asset_id, version_id, is_current);

CREATE INDEX ix_file_binding_batch ON t_file_binding (tenant_id, batch_id);

CREATE INDEX ix_file_binding_business ON t_file_binding (tenant_id, biz_type, biz_id, is_current);

CREATE INDEX ix_file_binding_subject ON t_file_binding (tenant_id, subject_type, subject_id);

CREATE INDEX ix_t_file_binding_asset_id ON t_file_binding (asset_id);

CREATE INDEX ix_t_file_binding_class_id ON t_file_binding (class_id);

CREATE INDEX ix_t_file_binding_college_id ON t_file_binding (college_id);

CREATE INDEX ix_t_file_binding_file_id ON t_file_binding (file_id);

CREATE INDEX ix_t_file_binding_module_code ON t_file_binding (module_code);

CREATE INDEX ix_t_file_binding_student_id ON t_file_binding (student_id);

CREATE INDEX ix_t_file_binding_tenant_id ON t_file_binding (tenant_id);

CREATE INDEX ix_t_file_binding_version_id ON t_file_binding (version_id);

CREATE TABLE t_file_job (
	job_type VARCHAR(40) NOT NULL, 
	file_id BIGINT, 
	dedupe_key VARCHAR(160) NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	attempts INTEGER NOT NULL, 
	max_attempts INTEGER NOT NULL, 
	available_at DATETIME NOT NULL, 
	locked_at DATETIME, 
	locked_by VARCHAR(120), 
	last_error TEXT, 
	payload_json JSON, 
	result_json JSON, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_file_job_dedupe UNIQUE (tenant_id, dedupe_key)
);

CREATE INDEX ix_file_job_claim ON t_file_job (job_type, status, available_at, locked_at);

CREATE INDEX ix_t_file_job_file_id ON t_file_job (file_id);

CREATE INDEX ix_t_file_job_status ON t_file_job (status);

CREATE INDEX ix_t_file_job_tenant_id ON t_file_job (tenant_id);

CREATE TABLE t_file_object (
	file_key VARCHAR(500) NOT NULL COMMENT '兼容存储 key', 
	file_name VARCHAR(300) NOT NULL, 
	ext VARCHAR(20), 
	mime_type VARCHAR(100), 
	size_bytes BIGINT, 
	sha256 VARCHAR(64), 
	biz_type VARCHAR(50), 
	biz_id VARCHAR(64), 
	owner_user_id BIGINT, 
	visibility VARCHAR(30) NOT NULL, 
	security_level VARCHAR(30) NOT NULL, 
	status VARCHAR(50) NOT NULL, 
	remark VARCHAR(500), 
	storage_backend VARCHAR(30) NOT NULL, 
	storage_zone VARCHAR(30) NOT NULL, 
	bucket_name VARCHAR(150), 
	object_key VARCHAR(500), 
	etag VARCHAR(128), 
	legacy_file_key VARCHAR(500), 
	storage_migrated_at DATETIME, 
	storage_verified_at DATETIME, 
	retention_until DATETIME, 
	legal_hold BOOL NOT NULL, 
	deleted_at DATETIME, 
	upload_source VARCHAR(30) NOT NULL, 
	scan_required BOOL NOT NULL, 
	scan_status VARCHAR(30) NOT NULL, 
	scan_attempts INTEGER NOT NULL, 
	scan_engine VARCHAR(50), 
	scan_engine_version VARCHAR(120), 
	scan_signature_version VARCHAR(120), 
	scan_last_error TEXT, 
	scanned_at DATETIME, 
	available_at DATETIME, 
	rejected_at DATETIME, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_file_object_scan_queue ON t_file_object (tenant_id, scan_required, scan_status, created_at);

CREATE INDEX ix_file_retention_cleanup ON t_file_object (tenant_id, legal_hold, is_deleted, retention_until, id);

CREATE INDEX ix_file_storage_migration ON t_file_object (tenant_id, storage_backend, storage_migrated_at, id);

CREATE INDEX ix_file_storage_object ON t_file_object (storage_backend, bucket_name, object_key);

CREATE INDEX ix_t_file_object_biz_id ON t_file_object (biz_id);

CREATE INDEX ix_t_file_object_owner_user_id ON t_file_object (owner_user_id);

CREATE INDEX ix_t_file_object_scan_required ON t_file_object (scan_required);

CREATE INDEX ix_t_file_object_scan_status ON t_file_object (scan_status);

CREATE INDEX ix_t_file_object_sha256 ON t_file_object (sha256);

CREATE INDEX ix_t_file_object_tenant_id ON t_file_object (tenant_id);

CREATE TABLE t_file_retention_policy (
	policy_code VARCHAR(100) NOT NULL, 
	module_code VARCHAR(64), 
	biz_type VARCHAR(80), 
	storage_zone VARCHAR(30), 
	retention_days INTEGER NOT NULL, 
	cleanup_action VARCHAR(30) NOT NULL, 
	priority INTEGER NOT NULL, 
	is_active BOOL NOT NULL, 
	description VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_file_retention_policy_code UNIQUE (tenant_id, policy_code)
);

CREATE INDEX ix_file_retention_policy_match ON t_file_retention_policy (tenant_id, is_active, module_code, biz_type, storage_zone, priority);

CREATE INDEX ix_t_file_retention_policy_tenant_id ON t_file_retention_policy (tenant_id);

CREATE TABLE t_file_scan_record (
	file_id BIGINT NOT NULL, 
	attempt INTEGER NOT NULL, 
	engine VARCHAR(50) NOT NULL, 
	engine_version VARCHAR(120), 
	signature_version VARCHAR(120), 
	result VARCHAR(30) NOT NULL, 
	threat_name VARCHAR(300), 
	started_at DATETIME NOT NULL, 
	completed_at DATETIME, 
	error_code VARCHAR(80), 
	error_message TEXT, 
	details_json JSON, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_file_scan_record_attempt UNIQUE (tenant_id, file_id, attempt)
);

CREATE INDEX ix_file_scan_record_result ON t_file_scan_record (tenant_id, result, created_at);

CREATE INDEX ix_t_file_scan_record_file_id ON t_file_scan_record (file_id);

CREATE INDEX ix_t_file_scan_record_tenant_id ON t_file_scan_record (tenant_id);

CREATE TABLE t_file_upload_session (
	session_key VARCHAR(64) NOT NULL, 
	file_id BIGINT, 
	status VARCHAR(30) NOT NULL, 
	source VARCHAR(30) NOT NULL, 
	file_name VARCHAR(300), 
	expected_size BIGINT, 
	received_size BIGINT NOT NULL, 
	expires_at DATETIME, 
	completed_at DATETIME, 
	metadata_json JSON, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_file_upload_session_key UNIQUE (tenant_id, session_key)
);

CREATE INDEX ix_file_upload_session_status ON t_file_upload_session (tenant_id, status, created_at);

CREATE INDEX ix_t_file_upload_session_file_id ON t_file_upload_session (file_id);

CREATE INDEX ix_t_file_upload_session_tenant_id ON t_file_upload_session (tenant_id);

CREATE TABLE t_file_version (
	asset_id BIGINT NOT NULL, 
	file_object_id BIGINT NOT NULL, 
	version_no INTEGER NOT NULL, 
	source_channel VARCHAR(40) NOT NULL, 
	uploader_user_id VARCHAR(64), 
	uploader_name_snapshot VARCHAR(100), 
	submit_comment VARCHAR(500), 
	status VARCHAR(30) NOT NULL COMMENT 'UPLOADED/SCANNING/READY/SUBMITTED/APPROVED/REJECTED/INVALIDATED/ARCHIVED', 
	is_current BOOL NOT NULL, 
	submitted_at DATETIME, 
	invalidated_at DATETIME, 
	invalidated_by VARCHAR(100), 
	invalid_reason VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_file_version_no UNIQUE (tenant_id, asset_id, version_no), 
	CONSTRAINT uk_file_version_object UNIQUE (tenant_id, asset_id, file_object_id)
);

CREATE INDEX ix_file_version_current ON t_file_version (tenant_id, asset_id, is_current, status);

CREATE INDEX ix_t_file_version_asset_id ON t_file_version (asset_id);

CREATE INDEX ix_t_file_version_file_object_id ON t_file_version (file_object_id);

CREATE INDEX ix_t_file_version_is_current ON t_file_version (is_current);

CREATE INDEX ix_t_file_version_tenant_id ON t_file_version (tenant_id);

CREATE TABLE t_internship_agreement (
	internship_id BIGINT NOT NULL, 
	student_id BIGINT NOT NULL, 
	template_id BIGINT COMMENT '→ 模板库', 
	batch_id BIGINT, 
	enterprise_name VARCHAR(200), 
	position_name VARCHAR(100), 
	student_confirm_status VARCHAR(20) NOT NULL COMMENT 'PENDING/CONFIRMED/REJECTED', 
	student_confirm_at DATETIME, 
	enterprise_confirm_status VARCHAR(20) NOT NULL, 
	enterprise_confirm_at DATETIME, 
	enterprise_confirm_by VARCHAR(50) COMMENT '记录企业签署的经办人', 
	school_confirm_status VARCHAR(20) NOT NULL, 
	school_confirm_at DATETIME, 
	school_confirm_by VARCHAR(50), 
	status VARCHAR(30) NOT NULL COMMENT 'DRAFT/PENDING_STUDENT/PENDING_ENTERPRISE/PENDING_SCHOOL/EFFECTIVE/REJECTED/VOIDED/ARCHIVED', 
	reject_reason VARCHAR(500), 
	file_id VARCHAR(64) COMMENT '签署扫描件 file_id（文件中心）', 
	source_type VARCHAR(30) COMMENT 'ENTERPRISE_ONLINE/SCHOOL_RECORDED/FILE_EVIDENCE/IMPORTED/SYSTEM_GENERATED/LEGACY_UNKNOWN', 
	recorded_by_user_id VARCHAR(64), 
	recorded_by_name VARCHAR(100), 
	recorded_at DATETIME, 
	source_file_id VARCHAR(64), 
	enterprise_contact_id BIGINT, 
	source_remark VARCHAR(500), 
	esign_status VARCHAR(20) NOT NULL COMMENT '电子签章预留 NONE/PENDING/SIGNED', 
	rendered_body TEXT COMMENT '生成时模板变量渲染快照', 
	esign_provider VARCHAR(30) NOT NULL COMMENT '电子签渠道 INTERNAL/第三方', 
	esign_initiated_at DATETIME, 
	esign_initiated_by VARCHAR(50), 
	esign_student_at DATETIME, 
	esign_enterprise_at DATETIME, 
	esign_school_at DATETIME, 
	remark VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_t_internship_agreement_batch_id ON t_internship_agreement (batch_id);

CREATE INDEX ix_t_internship_agreement_internship_id ON t_internship_agreement (internship_id);

CREATE INDEX ix_t_internship_agreement_status ON t_internship_agreement (status);

CREATE INDEX ix_t_internship_agreement_student_id ON t_internship_agreement (student_id);

CREATE INDEX ix_t_internship_agreement_template_id ON t_internship_agreement (template_id);

CREATE INDEX ix_t_internship_agreement_tenant_id ON t_internship_agreement (tenant_id);

CREATE TABLE t_internship_agreement_template (
	name VARCHAR(200) NOT NULL COMMENT '模板名称', 
	category VARCHAR(50) COMMENT '协议类型：三方/顶岗/安全责任书等', 
	template_version VARCHAR(32) NOT NULL COMMENT '模板版本号', 
	scope_college_ids JSON COMMENT '适用学院ID列表', 
	scope_major_ids JSON COMMENT '适用专业ID列表', 
	scope_grades JSON COMMENT '适用年级列表，如[''2024级'']', 
	scope_batch_ids JSON COMMENT '适用实习批次ID列表', 
	body TEXT COMMENT '模板正文（可含 {{变量}} 占位）', 
	variables JSON COMMENT '变量说明 [{key,label,example}]，如 studentName/companyName/positionName/internPeriod', 
	is_default BOOL NOT NULL COMMENT '是否默认模板（同租户同类型唯一）', 
	status VARCHAR(32) NOT NULL, 
	remark VARCHAR(500), 
	enabled_at DATETIME, 
	disabled_at DATETIME, 
	archived_at DATETIME, 
	archived_by VARCHAR(100), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_t_internship_agreement_template_status ON t_internship_agreement_template (status);

CREATE INDEX ix_t_internship_agreement_template_tenant_id ON t_internship_agreement_template (tenant_id);

CREATE TABLE t_internship_application (
	record_id BIGINT COMMENT 'N-1/legacy physical record key; NULL for V3 campaign rows', 
	campaign_record_id BIGINT COMMENT '→ t_internship_record.id; V3 campaign namespace', 
	student_id BIGINT NOT NULL, 
	batch_id BIGINT, 
	campaign_id BIGINT COMMENT '→ t_internship_recruitment_campaign.id；旧入口/自主实习为 NULL', 
	application_type VARCHAR(32) NOT NULL, 
	volunteer_no INTEGER NOT NULL, 
	position_id BIGINT, 
	company_name VARCHAR(200), 
	position_name VARCHAR(100), 
	work_address VARCHAR(300), 
	contact_name VARCHAR(100), 
	contact_phone VARCHAR(64), 
	evidence_file_id VARCHAR(64), 
	application_note VARCHAR(500), 
	application_statement TEXT COMMENT '该志愿岗位专属申请说明', 
	material_snapshot_id BIGINT COMMENT '→ t_internship_application_material_snapshot.id', 
	status VARCHAR(32) NOT NULL, 
	submitted_at DATETIME, 
	reviewed_by_name VARCHAR(100), 
	reviewed_at DATETIME, 
	review_comment VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_intern_application_record_volunteer UNIQUE (tenant_id, record_id, volunteer_no), 
	CONSTRAINT uk_intern_application_campaign_record_volunteer UNIQUE (tenant_id, campaign_record_id, campaign_id, volunteer_no)
);

CREATE INDEX ix_t_internship_application_application_type ON t_internship_application (application_type);

CREATE INDEX ix_t_internship_application_batch_id ON t_internship_application (batch_id);

CREATE INDEX ix_t_internship_application_campaign_id ON t_internship_application (campaign_id);

CREATE INDEX ix_t_internship_application_campaign_record_id ON t_internship_application (campaign_record_id);

CREATE INDEX ix_t_internship_application_material_snapshot_id ON t_internship_application (material_snapshot_id);

CREATE INDEX ix_t_internship_application_position_id ON t_internship_application (position_id);

CREATE INDEX ix_t_internship_application_record_id ON t_internship_application (record_id);

CREATE INDEX ix_t_internship_application_status ON t_internship_application (status);

CREATE INDEX ix_t_internship_application_student_id ON t_internship_application (student_id);

CREATE INDEX ix_t_internship_application_tenant_id ON t_internship_application (tenant_id);

CREATE TABLE t_internship_application_material_snapshot (
	volunteer_group_id BIGINT NOT NULL COMMENT '→ t_internship_volunteer_group.id（M4）', 
	student_id BIGINT NOT NULL COMMENT '→ t_student_profile.id', 
	campaign_id BIGINT NOT NULL COMMENT '→ t_internship_recruitment_campaign.id', 
	batch_id BIGINT NOT NULL COMMENT '→ t_internship_batch.id', 
	submission_version INTEGER NOT NULL, 
	profile_version INTEGER NOT NULL, 
	profile_snapshot_json JSON NOT NULL, 
	school_fact_snapshot_json JSON NOT NULL, 
	attachment_file_ids_json JSON, 
	material_policy_snapshot_json JSON, 
	consent_version VARCHAR(80) NOT NULL, 
	consent_at DATETIME NOT NULL, 
	contact_sharing_policy JSON NOT NULL, 
	snapshot_hash VARCHAR(64) NOT NULL, 
	generated_profile_pdf_file_id BIGINT, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_intern_material_snapshot_submission UNIQUE (tenant_id, volunteer_group_id, submission_version)
);

CREATE INDEX ix_intern_material_snapshot_campaign_student ON t_internship_application_material_snapshot (tenant_id, campaign_id, student_id);

CREATE INDEX ix_intern_material_snapshot_group_version ON t_internship_application_material_snapshot (tenant_id, volunteer_group_id, submission_version);

CREATE INDEX ix_intern_material_snapshot_student_created ON t_internship_application_material_snapshot (tenant_id, student_id, created_at);

CREATE INDEX ix_t_internship_application_material_snapshot_snapshot_hash ON t_internship_application_material_snapshot (snapshot_hash);

CREATE INDEX ix_t_internship_application_material_snapshot_tenant_id ON t_internship_application_material_snapshot (tenant_id);

CREATE TABLE t_internship_archive (
	internship_id BIGINT NOT NULL, 
	student_id BIGINT NOT NULL, 
	batch_id BIGINT, 
	completeness INTEGER NOT NULL COMMENT '材料完整度 0-100', 
	missing_items VARCHAR(500) COMMENT '缺失材料清单', 
	material_snapshot JSON COMMENT '归档材料快照', 
	snapshot_version INTEGER, 
	status VARCHAR(20) NOT NULL COMMENT 'ARCHIVED/REVOKED', 
	package_file_id VARCHAR(64) COMMENT '归档包 file_id', 
	previous_record_status VARCHAR(20) COMMENT '归档前实习记录状态，撤销时恢复', 
	package_invalidated_at DATETIME COMMENT '撤销归档时标记既有归档包失效', 
	revoked_by_name VARCHAR(50), 
	revoked_at DATETIME, 
	revoke_reason VARCHAR(500), 
	force_reason VARCHAR(500), 
	force_evidence_file_ids JSON, 
	force_bypassed_items JSON, 
	force_rule_version VARCHAR(64), 
	force_approved_role VARCHAR(50), 
	force_approved_by VARCHAR(100), 
	archived_by_name VARCHAR(50), 
	archived_at DATETIME, 
	remark VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_internship_archive_record UNIQUE (tenant_id, internship_id)
);

CREATE INDEX ix_t_internship_archive_batch_id ON t_internship_archive (batch_id);

CREATE INDEX ix_t_internship_archive_internship_id ON t_internship_archive (internship_id);

CREATE INDEX ix_t_internship_archive_student_id ON t_internship_archive (student_id);

CREATE INDEX ix_t_internship_archive_tenant_id ON t_internship_archive (tenant_id);

CREATE TABLE t_internship_audit_trail (
	target_id BIGINT NOT NULL, 
	target_type VARCHAR(50) NOT NULL COMMENT 'RECORD/EXCEPTION/REPORT/RISK/BATCH', 
	action VARCHAR(100) NOT NULL, 
	operator_name VARCHAR(100), 
	detail_json JSON, 
	occurred_at DATETIME NOT NULL, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_t_internship_audit_trail_target_id ON t_internship_audit_trail (target_id);

CREATE INDEX ix_t_internship_audit_trail_tenant_id ON t_internship_audit_trail (tenant_id);

CREATE TABLE t_internship_batch (
	batch_name VARCHAR(200) NOT NULL, 
	batch_no VARCHAR(100) NOT NULL, 
	academic_year VARCHAR(20) COMMENT '学年，如 2025-2026', 
	term VARCHAR(20) COMMENT '学期', 
	start_date DATETIME COMMENT '实习起', 
	end_date DATETIME COMMENT '实习止', 
	signup_start_date DATETIME COMMENT '报名/资格确认窗口起', 
	signup_end_date DATETIME COMMENT '报名/资格确认窗口止', 
	planned_count INTEGER NOT NULL COMMENT '计划实习人数', 
	status VARCHAR(50) NOT NULL COMMENT 'DRAFT/RUNNING/CLOSED/ARCHIVED/VOIDED', 
	stage_config JSON COMMENT '阶段/时间轴 [{code,name,startDate,endDate}]', 
	rules_config JSON COMMENT '规则配置 {checkin/weeklyReport/guidance/evaluation/score}', 
	rules_version INTEGER NOT NULL COMMENT '已生效规则版本', 
	compliance_template_id BIGINT COMMENT '启用时冻结的合规模板', 
	compliance_template_version INTEGER COMMENT '启用时冻结的合规模板版本', 
	previous_status VARCHAR(50), 
	last_transition_at DATETIME, 
	last_transition_by VARCHAR(100), 
	transition_reason VARCHAR(500), 
	archive_status VARCHAR(50) NOT NULL COMMENT 'NOT_ARCHIVED/ARCHIVED', 
	archived_at DATETIME, 
	archived_by VARCHAR(100), 
	archive_batch_no VARCHAR(100), 
	remark VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_intern_batch_no UNIQUE (tenant_id, batch_no)
);

CREATE INDEX ix_t_internship_batch_tenant_id ON t_internship_batch (tenant_id);

CREATE TABLE t_internship_batch_participant (
	batch_id BIGINT NOT NULL, 
	student_id BIGINT NOT NULL COMMENT '= t_student_profile.id', 
	source VARCHAR(30) NOT NULL COMMENT 'SCOPE 规则圈定 / MANUAL 人工补录', 
	snapshot_student_no VARCHAR(50), 
	snapshot_name VARCHAR(100), 
	snapshot_class_name VARCHAR(100), 
	snapshot_college_name VARCHAR(100), 
	internship_id BIGINT COMMENT '冻结时创建/命中的 t_internship_record.id', 
	status VARCHAR(30) NOT NULL COMMENT 'ACTIVE 在册 / REMOVED 已移出（保留行以便追溯）', 
	remove_reason VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_intern_participant UNIQUE (tenant_id, batch_id, student_id)
);

CREATE INDEX ix_intern_participant_batch ON t_internship_batch_participant (tenant_id, batch_id, is_deleted);

CREATE INDEX ix_t_internship_batch_participant_batch_id ON t_internship_batch_participant (batch_id);

CREATE INDEX ix_t_internship_batch_participant_internship_id ON t_internship_batch_participant (internship_id);

CREATE INDEX ix_t_internship_batch_participant_student_id ON t_internship_batch_participant (student_id);

CREATE INDEX ix_t_internship_batch_participant_tenant_id ON t_internship_batch_participant (tenant_id);

CREATE TABLE t_internship_batch_plan (
	batch_id BIGINT NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	objectives TEXT COMMENT '实习目标', 
	content TEXT COMMENT '计划正文', 
	tasks_json JSON COMMENT '任务清单', 
	status VARCHAR(20) NOT NULL COMMENT 'DRAFT/PUBLISHED', 
	published_at DATETIME, 
	published_by_name VARCHAR(50), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_intern_batch_plan UNIQUE (tenant_id, batch_id)
);

CREATE INDEX ix_t_internship_batch_plan_batch_id ON t_internship_batch_plan (batch_id);

CREATE INDEX ix_t_internship_batch_plan_tenant_id ON t_internship_batch_plan (tenant_id);

CREATE TABLE t_internship_batch_scope_rule (
	batch_id BIGINT NOT NULL, 
	rule_json JSON COMMENT 'ScopeRule.to_dict()：collegeIds/majorIds/classIds/studentIds/grades + exclude*', 
	last_preview_count INTEGER NOT NULL COMMENT '最近一次预览命中人数（仅供页面显示）', 
	last_preview_at DATETIME, 
	frozen_at DATETIME COMMENT '冻结时间；非空表示名单已生成', 
	frozen_by VARCHAR(100), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_intern_scope_batch UNIQUE (tenant_id, batch_id)
);

CREATE INDEX ix_t_internship_batch_scope_rule_batch_id ON t_internship_batch_scope_rule (batch_id);

CREATE INDEX ix_t_internship_batch_scope_rule_tenant_id ON t_internship_batch_scope_rule (tenant_id);

CREATE TABLE t_internship_campaign_enterprise (
	campaign_id BIGINT NOT NULL COMMENT '→ t_internship_recruitment_campaign.id', 
	company_id BIGINT NOT NULL COMMENT '→ t_emp_company.id', 
	status VARCHAR(20) NOT NULL COMMENT 'ACCEPTED/DECLINED/INVITED/REVOKED/SUSPENDED', 
	invite_source VARCHAR(30) NOT NULL COMMENT 'MANUAL/PUBLIC_REQUEST/REUSE', 
	invited_by_user_id BIGINT, 
	invited_at DATETIME, 
	accepted_at DATETIME, 
	declined_at DATETIME, 
	revoked_at DATETIME, 
	revoke_reason VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_intern_campaign_enterprise UNIQUE (tenant_id, campaign_id, company_id)
);

CREATE INDEX ix_intern_campaign_enterprise_campaign_status ON t_internship_campaign_enterprise (tenant_id, campaign_id, status, is_deleted);

CREATE INDEX ix_intern_campaign_enterprise_company_status ON t_internship_campaign_enterprise (tenant_id, company_id, status, is_deleted);

CREATE INDEX ix_t_internship_campaign_enterprise_tenant_id ON t_internship_campaign_enterprise (tenant_id);

CREATE TABLE t_internship_change_request (
	internship_id BIGINT NOT NULL, 
	active_pending_internship_id BIGINT GENERATED ALWAYS AS (CASE WHEN is_deleted = 0 AND status = 'PENDING' THEN internship_id ELSE NULL END) STORED COMMENT '仅待审核时等于 internship_id，用于唯一索引；其余为 NULL', 
	student_id BIGINT NOT NULL, 
	change_type VARCHAR(30) NOT NULL COMMENT '变更类型', 
	reason VARCHAR(500) NOT NULL, 
	target_enterprise_id BIGINT, 
	target_position_id BIGINT, 
	target_enterprise_name VARCHAR(200), 
	target_position_name VARCHAR(100), 
	record_version_snapshot INTEGER NOT NULL COMMENT '申请时实习主记录版本', 
	status VARCHAR(20) NOT NULL COMMENT 'PENDING/APPROVED/REJECTED', 
	review_comment VARCHAR(500), 
	reviewed_by_name VARCHAR(50), 
	reviewed_at DATETIME, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_ix_change_active_pending UNIQUE (tenant_id, active_pending_internship_id)
);

CREATE INDEX ix_t_internship_change_request_internship_id ON t_internship_change_request (internship_id);

CREATE INDEX ix_t_internship_change_request_student_id ON t_internship_change_request (student_id);

CREATE INDEX ix_t_internship_change_request_target_enterprise_id ON t_internship_change_request (target_enterprise_id);

CREATE INDEX ix_t_internship_change_request_target_position_id ON t_internship_change_request (target_position_id);

CREATE INDEX ix_t_internship_change_request_tenant_id ON t_internship_change_request (tenant_id);

CREATE TABLE t_internship_checkin (
	internship_id BIGINT NOT NULL, 
	checkin_date VARCHAR(10) NOT NULL COMMENT 'YYYY-MM-DD', 
	checkin_at DATETIME NOT NULL, 
	lat FLOAT, 
	lng FLOAT, 
	address VARCHAR(300), 
	result VARCHAR(30) NOT NULL COMMENT 'RECORDED/NORMAL/OUT_OF_RANGE/NO_LOCATION/LOW_ACCURACY/LOCATION_UNCERTAIN/MOCK_LOCATION', 
	note VARCHAR(500) COMMENT '学生备注', 
	gps_accuracy FLOAT COMMENT '定位精度(m)', 
	device_risk_flag VARCHAR(30) COMMENT 'not_available/mock/rooted（客户端 normal 不作为可信证明）', 
	distance_m FLOAT COMMENT '距岗位围栏中心距离(m)', 
	evidence_file_id VARCHAR(64) COMMENT '打卡凭证文件', 
	idempotency_key VARCHAR(100) COMMENT '客户端幂等键', 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_internship_checkin_day UNIQUE (tenant_id, internship_id, checkin_date)
);

CREATE INDEX ix_t_internship_checkin_internship_id ON t_internship_checkin (internship_id);

CREATE INDEX ix_t_internship_checkin_tenant_id ON t_internship_checkin (tenant_id);

CREATE TABLE t_internship_communication_log (
	enterprise_id BIGINT NOT NULL COMMENT '关联企业 t_emp_company', 
	internship_id BIGINT COMMENT '可选关联实习记录', 
	student_id BIGINT, 
	position_id BIGINT COMMENT '可选关联岗位', 
	communication_type VARCHAR(20) NOT NULL COMMENT 'PHONE/WECHAT/EMAIL/ONSITE/MEETING/ENTERPRISE_FEEDBACK', 
	direction VARCHAR(20) NOT NULL COMMENT 'SCHOOL 学校发起 / ENTERPRISE 企业发起', 
	contact_id BIGINT COMMENT '企业联系人 id', 
	contact_name_snapshot VARCHAR(50) COMMENT '联系人姓名快照', 
	advisor_name VARCHAR(50) COMMENT '经办教师（owner scope 本人指导学生）', 
	occurred_at DATETIME COMMENT '沟通时间', 
	summary TEXT COMMENT '沟通摘要', 
	result VARCHAR(1000) COMMENT '沟通结果', 
	follow_up_required BOOL NOT NULL, 
	follow_up_due_at DATETIME, 
	follow_up_owner_id BIGINT, 
	follow_up_done BOOL NOT NULL, 
	file_id VARCHAR(64) COMMENT '附件 file_id 预留', 
	status VARCHAR(20) NOT NULL COMMENT 'NORMAL/VOIDED', 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_t_internship_communication_log_enterprise_id ON t_internship_communication_log (enterprise_id);

CREATE INDEX ix_t_internship_communication_log_internship_id ON t_internship_communication_log (internship_id);

CREATE INDEX ix_t_internship_communication_log_status ON t_internship_communication_log (status);

CREATE INDEX ix_t_internship_communication_log_student_id ON t_internship_communication_log (student_id);

CREATE INDEX ix_t_internship_communication_log_tenant_id ON t_internship_communication_log (tenant_id);

CREATE TABLE t_internship_complaint (
	complaint_no VARCHAR(40) COMMENT '投诉编号', 
	source VARCHAR(20) NOT NULL COMMENT 'STUDENT/PARENT/ENTERPRISE/TEACHER/ANONYMOUS/REGULATOR', 
	target_type VARCHAR(20) COMMENT 'ENTERPRISE/POSITION/STUDENT/TEACHER/OTHER', 
	enterprise_id BIGINT, 
	position_id BIGINT, 
	student_id BIGINT, 
	internship_id BIGINT COMMENT '投诉明确关联的实习主记录；禁止按最新记录猜测', 
	batch_id BIGINT, 
	category VARCHAR(50) COMMENT '投诉分类', 
	severity VARCHAR(20) NOT NULL COMMENT 'LOW/MEDIUM/HIGH', 
	content TEXT COMMENT '投诉内容', 
	evidence_file_id VARCHAR(64), 
	complainant_contact_encrypted VARCHAR(500) COMMENT '投诉人联系方式(敏感,Fernet密文)', 
	complainant_contact_hash VARCHAR(64) COMMENT '投诉人联系方式HMAC检索摘要', 
	confidential_level VARCHAR(20) NOT NULL COMMENT 'NORMAL/CONFIDENTIAL', 
	status VARCHAR(20) NOT NULL COMMENT 'RECEIVED/ACCEPTED/INVESTIGATING/RESOLVED/REJECTED/WITHDRAWN/CLOSED', 
	accepted_by_name VARCHAR(50) COMMENT '受理人', 
	owner_name VARCHAR(50) COMMENT '责任人', 
	accept_deadline VARCHAR(10) COMMENT '受理期限 YYYY-MM-DD', 
	resolve_deadline VARCHAR(10) COMMENT '办结期限 YYYY-MM-DD', 
	conclusion TEXT COMMENT '结论/处理意见', 
	followup_result TEXT COMMENT '回访结果', 
	risk_id BIGINT COMMENT '转风险单 → t_risk_record', 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_t_internship_complaint_batch_id ON t_internship_complaint (batch_id);

CREATE INDEX ix_t_internship_complaint_complainant_contact_hash ON t_internship_complaint (complainant_contact_hash);

CREATE INDEX ix_t_internship_complaint_complaint_no ON t_internship_complaint (complaint_no);

CREATE INDEX ix_t_internship_complaint_enterprise_id ON t_internship_complaint (enterprise_id);

CREATE INDEX ix_t_internship_complaint_internship_id ON t_internship_complaint (internship_id);

CREATE INDEX ix_t_internship_complaint_risk_id ON t_internship_complaint (risk_id);

CREATE INDEX ix_t_internship_complaint_status ON t_internship_complaint (status);

CREATE INDEX ix_t_internship_complaint_student_id ON t_internship_complaint (student_id);

CREATE INDEX ix_t_internship_complaint_tenant_id ON t_internship_complaint (tenant_id);

CREATE TABLE t_internship_compliance_exemption (
	internship_id BIGINT NOT NULL, 
	active_pending_internship_id BIGINT GENERATED ALWAYS AS (CASE WHEN is_deleted = 0 AND status = 'PENDING_REVIEW' THEN internship_id ELSE NULL END) STORED COMMENT '仅待审核时等于 internship_id，用于唯一索引；其余为 NULL', 
	batch_id BIGINT, 
	check_code VARCHAR(64) NOT NULL, 
	reason VARCHAR(1000) NOT NULL, 
	evidence_file_ids JSON, 
	valid_from DATETIME, 
	valid_until DATETIME, 
	status VARCHAR(20) NOT NULL COMMENT 'DRAFT/PENDING_REVIEW/APPROVED/REJECTED/EXPIRED/REVOKED', 
	approved_by_name VARCHAR(100), 
	approved_at DATETIME, 
	requested_by_name VARCHAR(100), 
	requested_by_user_id VARCHAR(64), 
	reviewed_by_name VARCHAR(100), 
	reviewed_at DATETIME, 
	rule_version VARCHAR(64), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_ix_exempt_active_pending UNIQUE (tenant_id, active_pending_internship_id, check_code)
);

CREATE INDEX ix_ix_exempt_intern ON t_internship_compliance_exemption (tenant_id, internship_id, check_code, is_deleted);

CREATE INDEX ix_t_internship_compliance_exemption_batch_id ON t_internship_compliance_exemption (batch_id);

CREATE INDEX ix_t_internship_compliance_exemption_internship_id ON t_internship_compliance_exemption (internship_id);

CREATE INDEX ix_t_internship_compliance_exemption_tenant_id ON t_internship_compliance_exemption (tenant_id);

CREATE TABLE t_internship_compliance_template (
	template_code VARCHAR(64) NOT NULL, 
	template_name VARCHAR(200) NOT NULL, 
	template_version INTEGER NOT NULL, 
	status VARCHAR(20) NOT NULL COMMENT 'DRAFT/ACTIVE/RETIRED', 
	config JSON COMMENT '合规规则 JSON', 
	effective_at DATETIME, 
	approved_by_name VARCHAR(100), 
	approved_at DATETIME, 
	change_reason VARCHAR(500), 
	remark VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_ix_compliance_tpl_ver UNIQUE (tenant_id, template_code, template_version)
);

CREATE INDEX ix_t_internship_compliance_template_template_code ON t_internship_compliance_template (template_code);

CREATE INDEX ix_t_internship_compliance_template_tenant_id ON t_internship_compliance_template (tenant_id);

CREATE TABLE t_internship_consent (
	internship_id BIGINT NOT NULL, 
	batch_id BIGINT, 
	student_id BIGINT NOT NULL, 
	consent_type VARCHAR(20) NOT NULL COMMENT 'STUDENT/GUARDIAN', 
	applicable BOOL NOT NULL, 
	participant_name VARCHAR(100), 
	participant_relation VARCHAR(50), 
	identity_masked VARCHAR(64), 
	contact_masked VARCHAR(64), 
	content_version VARCHAR(64), 
	content_snapshot TEXT, 
	content_hash VARCHAR(64), 
	delivery_channel VARCHAR(40), 
	message_id BIGINT, 
	delivered_at DATETIME, 
	viewed_at DATETIME, 
	confirmed_at DATETIME, 
	confirmation_method VARCHAR(40), 
	device_digest VARCHAR(128), 
	client_ip_digest VARCHAR(128), 
	confirmed_by_user_id VARCHAR(64), 
	confirmed_student_id BIGINT, 
	guardian_token_hash VARCHAR(64), 
	guardian_token_expires_at DATETIME, 
	guardian_token_used_at DATETIME, 
	guardian_token_revoked_at DATETIME, 
	file_id VARCHAR(64), 
	status VARCHAR(30) NOT NULL COMMENT 'NOT_APPLICABLE/MISSING/PENDING/VALID/REJECTED/EXPIRED/SUPERSEDED/REVOKED', 
	revoked_at DATETIME, 
	revoke_reason VARCHAR(500), 
	rule_version VARCHAR(64), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_ix_consent_intern ON t_internship_consent (tenant_id, internship_id, consent_type, is_deleted);

CREATE INDEX ix_t_internship_consent_batch_id ON t_internship_consent (batch_id);

CREATE INDEX ix_t_internship_consent_content_hash ON t_internship_consent (content_hash);

CREATE INDEX ix_t_internship_consent_internship_id ON t_internship_consent (internship_id);

CREATE INDEX ix_t_internship_consent_student_id ON t_internship_consent (student_id);

CREATE INDEX ix_t_internship_consent_tenant_id ON t_internship_consent (tenant_id);

CREATE TABLE t_internship_emergency_plan (
	company_id BIGINT, 
	batch_id BIGINT, 
	plan_name VARCHAR(200) NOT NULL, 
	responsible_person VARCHAR(100), 
	emergency_contact VARCHAR(100), 
	backup_contact VARCHAR(100), 
	hospital_or_support VARCHAR(300), 
	response_steps TEXT, 
	valid_from DATETIME, 
	valid_until DATETIME, 
	file_ids JSON, 
	status VARCHAR(30) NOT NULL COMMENT 'DRAFT/PENDING_REVIEW/APPROVED/EXPIRED', 
	reviewed_by_name VARCHAR(100), 
	reviewed_at DATETIME, 
	rule_version VARCHAR(64), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_ix_emerg_company ON t_internship_emergency_plan (tenant_id, company_id, is_deleted);

CREATE INDEX ix_t_internship_emergency_plan_batch_id ON t_internship_emergency_plan (batch_id);

CREATE INDEX ix_t_internship_emergency_plan_company_id ON t_internship_emergency_plan (company_id);

CREATE INDEX ix_t_internship_emergency_plan_tenant_id ON t_internship_emergency_plan (tenant_id);

CREATE TABLE t_internship_enterprise_access_grant (
	member_id BIGINT NOT NULL COMMENT '→ t_internship_enterprise_member.id', 
	company_id BIGINT NOT NULL COMMENT '→ t_emp_company.id', 
	grant_type VARCHAR(30) NOT NULL COMMENT 'INTERNSHIP_COLLAB/RECRUITMENT', 
	campaign_id BIGINT COMMENT 'RECRUITMENT grant → t_internship_recruitment_campaign.id', 
	batch_id BIGINT COMMENT '招聘/实习协同所属 t_internship_batch.id', 
	valid_from DATETIME NOT NULL, 
	valid_until DATETIME NOT NULL, 
	status VARCHAR(20) NOT NULL COMMENT 'ACTIVE/EXPIRED/REVOKED', 
	revoked_at DATETIME, 
	revoked_by_user_id BIGINT, 
	revoke_reason VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_intern_enterprise_access_grant UNIQUE (tenant_id, member_id, grant_type, campaign_id, batch_id)
);

CREATE INDEX ix_intern_enterprise_grant_company_validity ON t_internship_enterprise_access_grant (tenant_id, company_id, status, valid_until);

CREATE INDEX ix_intern_enterprise_grant_member_validity ON t_internship_enterprise_access_grant (tenant_id, member_id, status, valid_until);

CREATE INDEX ix_t_internship_enterprise_access_grant_tenant_id ON t_internship_enterprise_access_grant (tenant_id);

CREATE TABLE t_internship_enterprise_application_decision (
	application_id BIGINT NOT NULL, 
	volunteer_group_id BIGINT NOT NULL, 
	campaign_id BIGINT NOT NULL, 
	batch_id BIGINT NOT NULL, 
	company_id BIGINT NOT NULL, 
	position_id BIGINT NOT NULL, 
	material_snapshot_id BIGINT NOT NULL, 
	submission_version INTEGER NOT NULL, 
	decision_status VARCHAR(30) NOT NULL COMMENT 'PENDING/INTERESTED/INTERVIEW/ACCEPT_INTENT/REJECTED', 
	effect_status VARCHAR(20) NOT NULL COMMENT 'ACTIVE/EXPIRED/SUPERSEDED/CONSUMED', 
	valid_until DATETIME, 
	superseded_reason VARCHAR(500), 
	interview_at DATETIME, 
	interview_note VARCHAR(1000), 
	decision_reason VARCHAR(1000), 
	decided_by_member_id BIGINT, 
	decided_by_user_id BIGINT, 
	decided_at DATETIME, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_intern_enterprise_decision_app_snapshot UNIQUE (tenant_id, application_id, material_snapshot_id)
);

CREATE INDEX ix_intern_enterprise_decision_application ON t_internship_enterprise_application_decision (tenant_id, application_id, is_deleted);

CREATE INDEX ix_intern_enterprise_decision_company_campaign_status ON t_internship_enterprise_application_decision (tenant_id, company_id, campaign_id, decision_status, is_deleted);

CREATE INDEX ix_intern_enterprise_decision_effect ON t_internship_enterprise_application_decision (tenant_id, volunteer_group_id, effect_status, valid_until, is_deleted);

CREATE INDEX ix_t_internship_enterprise_application_decision_tenant_id ON t_internship_enterprise_application_decision (tenant_id);

CREATE TABLE t_internship_enterprise_contact (
	company_id BIGINT NOT NULL, 
	contact_type VARCHAR(50) NOT NULL COMMENT 'CONTACT 联系人 / MENTOR 企业导师', 
	name VARCHAR(100) NOT NULL, 
	title VARCHAR(100) COMMENT '职务', 
	phone_encrypted VARCHAR(500), 
	email VARCHAR(200), 
	is_primary BOOL NOT NULL, 
	remark VARCHAR(500), 
	status VARCHAR(50) NOT NULL COMMENT 'ACTIVE/INACTIVE', 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_t_internship_enterprise_contact_company_id ON t_internship_enterprise_contact (company_id);

CREATE INDEX ix_t_internship_enterprise_contact_tenant_id ON t_internship_enterprise_contact (tenant_id);

CREATE TABLE t_internship_enterprise_eval (
	internship_id BIGINT NOT NULL, 
	student_id BIGINT NOT NULL, 
	batch_id BIGINT, 
	position_name VARCHAR(100), 
	mentor_name VARCHAR(50) COMMENT '企业导师姓名', 
	attendance_score INTEGER NOT NULL COMMENT '出勤 0-100', 
	skill_score INTEGER NOT NULL COMMENT '技能 0-100', 
	attitude_score INTEGER NOT NULL COMMENT '态度 0-100', 
	collaboration_score INTEGER NOT NULL COMMENT '协作 0-100', 
	safety_score INTEGER NOT NULL COMMENT '安全纪律 0-100', 
	overall_comment TEXT COMMENT '综合评语', 
	recommend_hire BOOL NOT NULL COMMENT '是否建议录用', 
	source VARCHAR(20) NOT NULL COMMENT 'ENTERPRISE/SCHOOL_RECORDED', 
	source_type VARCHAR(30) COMMENT 'ENTERPRISE_ONLINE/SCHOOL_RECORDED/FILE_EVIDENCE/IMPORTED/SYSTEM_GENERATED/LEGACY_UNKNOWN', 
	recorded_by_user_id VARCHAR(64), 
	recorded_by_name VARCHAR(100), 
	recorded_at DATETIME, 
	source_file_id VARCHAR(64), 
	enterprise_contact_id BIGINT, 
	placement_snapshot_id BIGINT COMMENT '评价提交时的正式安置快照；旧安置评价不得作用于新岗位', 
	enterprise_id BIGINT COMMENT '评价提交时的企业主键快照', 
	position_id BIGINT COMMENT '评价提交时的岗位主键快照', 
	source_remark VARCHAR(500), 
	submit_status VARCHAR(20) NOT NULL COMMENT 'DRAFT/SUBMITTED', 
	school_review_status VARCHAR(20) NOT NULL COMMENT 'PENDING/APPROVED/RETURNED', 
	school_review_comment VARCHAR(500), 
	reviewed_by_name VARCHAR(50), 
	reviewed_at DATETIME, 
	file_id VARCHAR(64) COMMENT '企业签署评价扫描件 file_id', 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_t_internship_enterprise_eval_batch_id ON t_internship_enterprise_eval (batch_id);

CREATE INDEX ix_t_internship_enterprise_eval_enterprise_id ON t_internship_enterprise_eval (enterprise_id);

CREATE INDEX ix_t_internship_enterprise_eval_internship_id ON t_internship_enterprise_eval (internship_id);

CREATE INDEX ix_t_internship_enterprise_eval_placement_snapshot_id ON t_internship_enterprise_eval (placement_snapshot_id);

CREATE INDEX ix_t_internship_enterprise_eval_position_id ON t_internship_enterprise_eval (position_id);

CREATE INDEX ix_t_internship_enterprise_eval_student_id ON t_internship_enterprise_eval (student_id);

CREATE INDEX ix_t_internship_enterprise_eval_tenant_id ON t_internship_enterprise_eval (tenant_id);

CREATE TABLE t_internship_enterprise_inspection (
	company_id BIGINT NOT NULL, 
	batch_id BIGINT, 
	inspection_type VARCHAR(30) NOT NULL COMMENT 'ONSITE/REMOTE/DOCUMENT', 
	inspection_required BOOL NOT NULL, 
	inspection_date DATETIME, 
	inspectors VARCHAR(200), 
	workplace_address VARCHAR(300), 
	safety_condition VARCHAR(500), 
	accommodation_condition VARCHAR(500), 
	mentor_condition VARCHAR(500), 
	remuneration_condition VARCHAR(500), 
	conclusion VARCHAR(1000), 
	risk_items TEXT, 
	rectification_items TEXT, 
	file_ids JSON, 
	valid_until DATETIME, 
	status VARCHAR(30) NOT NULL COMMENT 'DRAFT/SUBMITTED/APPROVED/REJECTED/EXPIRED', 
	review_comment VARCHAR(500), 
	reviewed_by_name VARCHAR(100), 
	reviewed_at DATETIME, 
	rule_version VARCHAR(64), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_ix_ent_insp_tenant_company ON t_internship_enterprise_inspection (tenant_id, company_id, is_deleted);

CREATE INDEX ix_t_internship_enterprise_inspection_batch_id ON t_internship_enterprise_inspection (batch_id);

CREATE INDEX ix_t_internship_enterprise_inspection_company_id ON t_internship_enterprise_inspection (company_id);

CREATE INDEX ix_t_internship_enterprise_inspection_tenant_id ON t_internship_enterprise_inspection (tenant_id);

CREATE TABLE t_internship_enterprise_member (
	company_id BIGINT NOT NULL COMMENT '→ t_emp_company.id', 
	user_id BIGINT NOT NULL COMMENT '→ t_user.id', 
	contact_id BIGINT COMMENT '可对齐 t_internship_enterprise_contact.id', 
	member_role VARCHAR(30) NOT NULL COMMENT 'COMPANY_ADMIN/HR/MENTOR', 
	status VARCHAR(20) NOT NULL COMMENT 'ACTIVE/DISABLED/INVITED', 
	is_primary BOOL NOT NULL, 
	invited_phone_hash VARCHAR(128), 
	invite_token_hash VARCHAR(128), 
	invite_expires_at DATETIME, 
	invited_at DATETIME, 
	accepted_at DATETIME, 
	last_active_at DATETIME, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_intern_enterprise_member UNIQUE (tenant_id, company_id, user_id)
);

CREATE INDEX ix_intern_enterprise_member_company_status ON t_internship_enterprise_member (tenant_id, company_id, status, is_deleted);

CREATE INDEX ix_intern_enterprise_member_user_status ON t_internship_enterprise_member (tenant_id, user_id, status, is_deleted);

CREATE INDEX ix_t_internship_enterprise_member_tenant_id ON t_internship_enterprise_member (tenant_id);

CREATE TABLE t_internship_evidence_package (
	package_type VARCHAR(20) NOT NULL COMMENT 'STUDENT/BATCH/ENTERPRISE/ARCHIVE', 
	batch_id BIGINT, 
	target_id BIGINT NOT NULL COMMENT 'internshipId/batchId/companyId', 
	package_version INTEGER NOT NULL, 
	package_file_id VARCHAR(64), 
	package_sha256 VARCHAR(64), 
	package_size_bytes BIGINT, 
	manifest_json JSON, 
	included_items JSON, 
	missing_items JSON, 
	rule_version VARCHAR(64), 
	metric_version VARCHAR(64), 
	generated_by_name VARCHAR(100), 
	generated_at DATETIME, 
	status VARCHAR(30) NOT NULL COMMENT 'READY/READY_WITH_MISSING/FAILED/INVALIDATED/LEGACY_SUMMARY', 
	invalidated_at DATETIME, 
	invalidated_by_name VARCHAR(100), 
	invalidation_reason VARCHAR(500), 
	row_count INTEGER NOT NULL, 
	file_count INTEGER NOT NULL, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_ix_evpkg_target_version UNIQUE (tenant_id, package_type, target_id, package_version)
);

CREATE INDEX ix_ix_evpkg_target ON t_internship_evidence_package (tenant_id, package_type, target_id, is_deleted);

CREATE INDEX ix_t_internship_evidence_package_batch_id ON t_internship_evidence_package (batch_id);

CREATE INDEX ix_t_internship_evidence_package_package_sha256 ON t_internship_evidence_package (package_sha256);

CREATE INDEX ix_t_internship_evidence_package_tenant_id ON t_internship_evidence_package (tenant_id);

CREATE TABLE t_internship_final_score (
	internship_id BIGINT NOT NULL, 
	student_id BIGINT NOT NULL, 
	batch_id BIGINT, 
	score_config_id BIGINT COMMENT '核算时的评分配置快照 id', 
	score_config_version INTEGER COMMENT '核算时的评分配置版本', 
	checkin_score INTEGER COMMENT '打卡分 0-100', 
	weekly_score INTEGER COMMENT '周报分 0-100', 
	monthly_score INTEGER COMMENT '月报/总结分 0-100', 
	enterprise_score INTEGER COMMENT '企业评价分 0-100（可自动取企业评价均分）', 
	school_score INTEGER COMMENT '学校/指导教师评分 0-100', 
	w_checkin INTEGER NOT NULL COMMENT '权重快照', 
	w_weekly INTEGER NOT NULL, 
	w_monthly INTEGER NOT NULL, 
	w_enterprise INTEGER NOT NULL, 
	w_school INTEGER NOT NULL, 
	total_score FLOAT COMMENT '加权总分', 
	pass_line FLOAT NOT NULL, 
	is_pass BOOL NOT NULL, 
	incomplete BOOL NOT NULL COMMENT '是否缺项', 
	incomplete_reason VARCHAR(300) COMMENT '缺哪几项', 
	status VARCHAR(20) NOT NULL COMMENT 'PENDING_CALC/PENDING_REVIEW/PENDING_PUBLISH/PUBLISHED/WITHDRAWN/ARCHIVED', 
	reviewed_by_name VARCHAR(50), 
	reviewed_at DATETIME, 
	published_by_name VARCHAR(50), 
	published_at DATETIME, 
	remark VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_internship_final_score_record UNIQUE (tenant_id, internship_id)
);

CREATE INDEX ix_t_internship_final_score_batch_id ON t_internship_final_score (batch_id);

CREATE INDEX ix_t_internship_final_score_internship_id ON t_internship_final_score (internship_id);

CREATE INDEX ix_t_internship_final_score_score_config_id ON t_internship_final_score (score_config_id);

CREATE INDEX ix_t_internship_final_score_student_id ON t_internship_final_score (student_id);

CREATE INDEX ix_t_internship_final_score_tenant_id ON t_internship_final_score (tenant_id);

CREATE TABLE t_internship_guidance (
	internship_id BIGINT NOT NULL, 
	student_id BIGINT NOT NULL, 
	advisor_name VARCHAR(50) COMMENT '指导教师', 
	method VARCHAR(20) NOT NULL COMMENT 'ONLINE/PHONE/ONSITE/ENTERPRISE_FEEDBACK/VIDEO', 
	topic VARCHAR(200) COMMENT '指导主题', 
	content TEXT COMMENT '指导内容', 
	problem_type VARCHAR(50) COMMENT '问题类型', 
	suggestion VARCHAR(1000) COMMENT '处理建议', 
	next_follow_date VARCHAR(10) COMMENT '下次跟进日期 YYYY-MM-DD', 
	to_risk BOOL NOT NULL COMMENT '是否形成风险', 
	notify_counselor BOOL NOT NULL COMMENT '是否通知辅导员', 
	file_id VARCHAR(64) COMMENT '附件 file_id 预留（文件中心）', 
	status VARCHAR(20) NOT NULL COMMENT 'NORMAL/VOIDED', 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_t_internship_guidance_internship_id ON t_internship_guidance (internship_id);

CREATE INDEX ix_t_internship_guidance_student_id ON t_internship_guidance (student_id);

CREATE INDEX ix_t_internship_guidance_tenant_id ON t_internship_guidance (tenant_id);

CREATE TABLE t_internship_incident (
	incident_no VARCHAR(64) NOT NULL, 
	batch_id BIGINT, 
	internship_id BIGINT, 
	company_id BIGINT, 
	student_id BIGINT, 
	risk_id BIGINT COMMENT '联动 RiskRecord.id', 
	incident_type VARCHAR(50) NOT NULL, 
	severity VARCHAR(20) NOT NULL COMMENT 'LOW/MEDIUM/HIGH/CRITICAL', 
	occurred_at DATETIME, 
	location VARCHAR(300), 
	summary TEXT, 
	injury_flag BOOL NOT NULL, 
	affected_persons VARCHAR(500), 
	reported_by_name VARCHAR(100), 
	reported_at DATETIME, 
	emergency_action TEXT, 
	guardian_notified_at DATETIME, 
	school_notified_at DATETIME, 
	enterprise_notified_at DATETIME, 
	external_reported_at DATETIME, 
	status VARCHAR(30) NOT NULL COMMENT 'REPORTED/EMERGENCY_HANDLING/INVESTIGATING/RECTIFYING/PENDING_REVIEW/CLOSED', 
	investigation_conclusion TEXT, 
	responsibility_conclusion TEXT, 
	rectification_plan TEXT, 
	rectification_deadline DATETIME, 
	closed_at DATETIME, 
	closed_by_name VARCHAR(100), 
	file_ids JSON, 
	idempotency_key VARCHAR(80), 
	rule_version VARCHAR(64), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_ix_incident_no UNIQUE (tenant_id, incident_no), 
	CONSTRAINT uk_ix_incident_idem UNIQUE (tenant_id, idempotency_key)
);

CREATE INDEX ix_ix_incident_batch ON t_internship_incident (tenant_id, batch_id, is_deleted);

CREATE INDEX ix_t_internship_incident_batch_id ON t_internship_incident (batch_id);

CREATE INDEX ix_t_internship_incident_company_id ON t_internship_incident (company_id);

CREATE INDEX ix_t_internship_incident_idempotency_key ON t_internship_incident (idempotency_key);

CREATE INDEX ix_t_internship_incident_internship_id ON t_internship_incident (internship_id);

CREATE INDEX ix_t_internship_incident_student_id ON t_internship_incident (student_id);

CREATE INDEX ix_t_internship_incident_tenant_id ON t_internship_incident (tenant_id);

CREATE TABLE t_internship_insurance (
	internship_id BIGINT NOT NULL, 
	student_id BIGINT NOT NULL, 
	policy_no VARCHAR(100) COMMENT '保单号', 
	insurer_name VARCHAR(200) COMMENT '承保机构', 
	coverage_type VARCHAR(100) COMMENT '险种', 
	effective_date VARCHAR(10) COMMENT '生效日 YYYY-MM-DD', 
	expiry_date VARCHAR(10) COMMENT '失效日 YYYY-MM-DD', 
	file_id VARCHAR(64) COMMENT '保单扫描件 file_id', 
	status VARCHAR(30) NOT NULL COMMENT 'NOT_SUBMITTED/SUBMITTED/VERIFIED/REJECTED', 
	submitted_at DATETIME, 
	verify_comment VARCHAR(500), 
	verified_by_name VARCHAR(50), 
	verified_at DATETIME, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_intern_insurance UNIQUE (tenant_id, internship_id)
);

CREATE INDEX ix_t_internship_insurance_internship_id ON t_internship_insurance (internship_id);

CREATE INDEX ix_t_internship_insurance_student_id ON t_internship_insurance (student_id);

CREATE INDEX ix_t_internship_insurance_tenant_id ON t_internship_insurance (tenant_id);

CREATE TABLE t_internship_intention (
	record_id BIGINT NOT NULL COMMENT '→ t_internship_record.id', 
	active_record_id BIGINT GENERATED ALWAYS AS (CASE WHEN is_deleted = 0 AND status IN ('DRAFT', 'SUBMITTED') THEN record_id ELSE NULL END) STORED COMMENT '仅进行中（DRAFT/SUBMITTED）时等于 record_id，用于唯一索引；其余为 NULL', 
	student_id BIGINT NOT NULL COMMENT '→ t_student_profile.id', 
	batch_id BIGINT, 
	preferred_city VARCHAR(100), 
	preferred_industry VARCHAR(100), 
	preferred_company_id BIGINT, 
	preferred_position_id BIGINT, 
	intention_note VARCHAR(500), 
	status VARCHAR(32) NOT NULL, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_ix_intention_active UNIQUE (tenant_id, active_record_id)
);

CREATE INDEX ix_t_internship_intention_batch_id ON t_internship_intention (batch_id);

CREATE INDEX ix_t_internship_intention_preferred_company_id ON t_internship_intention (preferred_company_id);

CREATE INDEX ix_t_internship_intention_preferred_position_id ON t_internship_intention (preferred_position_id);

CREATE INDEX ix_t_internship_intention_record_id ON t_internship_intention (record_id);

CREATE INDEX ix_t_internship_intention_status ON t_internship_intention (status);

CREATE INDEX ix_t_internship_intention_student_id ON t_internship_intention (student_id);

CREATE INDEX ix_t_internship_intention_tenant_id ON t_internship_intention (tenant_id);

CREATE TABLE t_internship_leave (
	internship_id BIGINT NOT NULL, 
	active_pending_internship_id BIGINT GENERATED ALWAYS AS (CASE WHEN is_deleted = 0 AND status = 'PENDING' THEN internship_id ELSE NULL END) STORED COMMENT '仅待审批时等于 internship_id，用于唯一索引；其余为 NULL', 
	student_id BIGINT NOT NULL, 
	leave_type VARCHAR(20) NOT NULL COMMENT 'SICK 病假 / PERSONAL 事假 / OTHER 其他', 
	start_date VARCHAR(10) NOT NULL COMMENT '起 YYYY-MM-DD', 
	end_date VARCHAR(10) NOT NULL COMMENT '止 YYYY-MM-DD', 
	days FLOAT NOT NULL COMMENT '请假天数', 
	reason VARCHAR(500) NOT NULL COMMENT '请假事由', 
	status VARCHAR(20) NOT NULL COMMENT 'PENDING/APPROVED/REJECTED/WITHDRAWN', 
	apply_by_name VARCHAR(50) COMMENT '申请人（学生）', 
	review_by_name VARCHAR(50) COMMENT '审批人', 
	review_at DATETIME, 
	review_comment VARCHAR(500), 
	file_id VARCHAR(64) COMMENT '证明附件 file_id（文件中心）', 
	returned_at DATETIME COMMENT 'Actual return-from-leave time', 
	return_note VARCHAR(500) COMMENT 'Student return note', 
	return_file_id VARCHAR(64) COMMENT 'Return evidence file id', 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_ix_leave_active_pending UNIQUE (tenant_id, active_pending_internship_id)
);

CREATE INDEX ix_t_internship_leave_internship_id ON t_internship_leave (internship_id);

CREATE INDEX ix_t_internship_leave_student_id ON t_internship_leave (student_id);

CREATE INDEX ix_t_internship_leave_tenant_id ON t_internship_leave (tenant_id);

CREATE TABLE t_internship_makeup (
	internship_id BIGINT NOT NULL, 
	active_pending_internship_id BIGINT GENERATED ALWAYS AS (CASE WHEN is_deleted = 0 AND status = 'PENDING' THEN internship_id ELSE NULL END) STORED COMMENT '仅待审核时等于 internship_id，用于唯一索引；其余为 NULL', 
	student_id BIGINT NOT NULL, 
	checkin_date VARCHAR(10) NOT NULL COMMENT '补卡日期 YYYY-MM-DD', 
	makeup_type VARCHAR(20) NOT NULL COMMENT 'MISSING 缺卡 / OUT_OF_RANGE 超范围补录', 
	reason VARCHAR(500) NOT NULL COMMENT '补卡事由', 
	status VARCHAR(20) NOT NULL COMMENT 'PENDING/APPROVED/REJECTED/WITHDRAWN', 
	apply_by_name VARCHAR(50) COMMENT '申请人（学生）', 
	review_by_name VARCHAR(50) COMMENT '审批人', 
	review_at DATETIME, 
	review_comment VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_ix_makeup_active_pending UNIQUE (tenant_id, active_pending_internship_id, checkin_date)
);

CREATE INDEX ix_t_internship_makeup_internship_id ON t_internship_makeup (internship_id);

CREATE INDEX ix_t_internship_makeup_student_id ON t_internship_makeup (student_id);

CREATE INDEX ix_t_internship_makeup_tenant_id ON t_internship_makeup (tenant_id);

CREATE TABLE t_internship_match (
	record_id BIGINT NOT NULL, 
	student_id BIGINT NOT NULL, 
	position_id BIGINT NOT NULL, 
	company_id BIGINT NOT NULL, 
	match_type VARCHAR(32) NOT NULL, 
	score INTEGER NOT NULL, 
	major_hit BOOL NOT NULL, 
	enterprise_hit BOOL NOT NULL, 
	conflict_flag BOOL NOT NULL, 
	conflict_reason VARCHAR(500), 
	status VARCHAR(32) NOT NULL, 
	confirmed_by VARCHAR(100), 
	confirmed_at DATETIME, 
	remark VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_t_internship_match_company_id ON t_internship_match (company_id);

CREATE INDEX ix_t_internship_match_match_type ON t_internship_match (match_type);

CREATE INDEX ix_t_internship_match_position_id ON t_internship_match (position_id);

CREATE INDEX ix_t_internship_match_record_id ON t_internship_match (record_id);

CREATE INDEX ix_t_internship_match_status ON t_internship_match (status);

CREATE INDEX ix_t_internship_match_student_id ON t_internship_match (student_id);

CREATE INDEX ix_t_internship_match_tenant_id ON t_internship_match (tenant_id);

CREATE TABLE t_internship_placement_snapshot (
	record_id BIGINT NOT NULL, 
	placement_seq INTEGER NOT NULL, 
	snapshot_version INTEGER NOT NULL, 
	application_id BIGINT, 
	enterprise_decision_id BIGINT, 
	campaign_id BIGINT, 
	batch_id BIGINT NOT NULL, 
	company_id BIGINT NOT NULL, 
	position_id BIGINT NOT NULL, 
	company_name VARCHAR(200) NOT NULL, 
	company_credit_code VARCHAR(50), 
	position_title VARCHAR(200) NOT NULL, 
	position_category VARCHAR(50), 
	work_location VARCHAR(200), 
	work_address VARCHAR(300), 
	work_content TEXT, 
	major_requirement VARCHAR(200), 
	grade_requirement VARCHAR(100), 
	salary_range VARCHAR(50), 
	subsidy VARCHAR(50), 
	remuneration_type VARCHAR(30), 
	remuneration_amount FLOAT, 
	remuneration_cycle VARCHAR(30), 
	daily_hours FLOAT, 
	weekly_hours FLOAT, 
	shift_type VARCHAR(30), 
	night_shift BOOL, 
	overtime_allowed BOOL, 
	rest_days VARCHAR(50), 
	rest_days_per_week FLOAT, 
	accommodation_provided BOOL, 
	meal_provided BOOL, 
	hazardous_flag BOOL, 
	special_equipment VARCHAR(200), 
	prohibited_reason VARCHAR(500), 
	enterprise_mentor_name VARCHAR(100), 
	rights_status VARCHAR(30), 
	rights_rule_version VARCHAR(64), 
	rights_checked_at DATETIME, 
	position_version INTEGER NOT NULL, 
	position_updated_at DATETIME, 
	snapshot_json JSON NOT NULL, 
	snapshot_hash VARCHAR(64) NOT NULL, 
	snapshot_sha256 VARCHAR(64) NOT NULL, 
	placement_at DATETIME NOT NULL, 
	captured_at DATETIME NOT NULL, 
	captured_by_user_id BIGINT, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_intern_placement_snapshot_seq UNIQUE (tenant_id, record_id, placement_seq)
);

CREATE INDEX ix_intern_placement_snapshot_position_time ON t_internship_placement_snapshot (tenant_id, position_id, placement_at);

CREATE INDEX ix_intern_placement_snapshot_record_time ON t_internship_placement_snapshot (tenant_id, record_id, placement_at);

CREATE INDEX ix_t_internship_placement_snapshot_snapshot_sha256 ON t_internship_placement_snapshot (snapshot_sha256);

CREATE INDEX ix_t_internship_placement_snapshot_tenant_id ON t_internship_placement_snapshot (tenant_id);

CREATE TABLE t_internship_plan_ack (
	plan_id BIGINT NOT NULL, 
	internship_id BIGINT NOT NULL, 
	student_id BIGINT NOT NULL, 
	status VARCHAR(20) NOT NULL COMMENT 'PENDING/ACKNOWLEDGED', 
	acknowledged_at DATETIME, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_intern_plan_ack UNIQUE (tenant_id, internship_id, plan_id)
);

CREATE INDEX ix_t_internship_plan_ack_internship_id ON t_internship_plan_ack (internship_id);

CREATE INDEX ix_t_internship_plan_ack_plan_id ON t_internship_plan_ack (plan_id);

CREATE INDEX ix_t_internship_plan_ack_student_id ON t_internship_plan_ack (student_id);

CREATE INDEX ix_t_internship_plan_ack_tenant_id ON t_internship_plan_ack (tenant_id);

CREATE TABLE t_internship_plan_task_progress (
	plan_id BIGINT NOT NULL, 
	internship_id BIGINT NOT NULL, 
	student_id BIGINT NOT NULL, 
	task_sort_order INTEGER NOT NULL COMMENT '任务序号', 
	task_name VARCHAR(100) NOT NULL, 
	status VARCHAR(20) NOT NULL COMMENT 'NOT_STARTED/SUBMITTED/APPROVED/RETURNED', 
	student_note VARCHAR(500), 
	evidence_file_id VARCHAR(64), 
	submitted_at DATETIME, 
	reviewed_by_name VARCHAR(50), 
	reviewed_at DATETIME, 
	review_comment VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_intern_plan_task_prog UNIQUE (tenant_id, internship_id, plan_id, task_sort_order)
);

CREATE INDEX ix_t_internship_plan_task_progress_internship_id ON t_internship_plan_task_progress (internship_id);

CREATE INDEX ix_t_internship_plan_task_progress_plan_id ON t_internship_plan_task_progress (plan_id);

CREATE INDEX ix_t_internship_plan_task_progress_student_id ON t_internship_plan_task_progress (student_id);

CREATE INDEX ix_t_internship_plan_task_progress_tenant_id ON t_internship_plan_task_progress (tenant_id);

CREATE TABLE t_internship_position (
	company_id BIGINT NOT NULL COMMENT '→ t_emp_company.id', 
	company_name VARCHAR(200) COMMENT '冗余展示名', 
	batch_id BIGINT COMMENT '→ t_internship_batch.id', 
	campaign_id BIGINT COMMENT '→ t_internship_recruitment_campaign.id；历史岗位保持 NULL', 
	source_type VARCHAR(30) NOT NULL COMMENT 'SCHOOL/ENTERPRISE', 
	title VARCHAR(200) NOT NULL, 
	category VARCHAR(50) COMMENT '岗位类别', 
	major_requirement VARCHAR(200) COMMENT '专业要求', 
	grade_requirement VARCHAR(100) COMMENT '年级要求', 
	work_location VARCHAR(200) COMMENT '工作地点', 
	geofence_lat FLOAT COMMENT '岗位围栏中心纬度', 
	geofence_lng FLOAT COMMENT '岗位围栏中心经度', 
	geofence_radius_m INTEGER COMMENT '岗位围栏半径(米)', 
	salary_range VARCHAR(50) COMMENT '薪资区间', 
	subsidy VARCHAR(50) COMMENT '补贴', 
	headcount INTEGER NOT NULL COMMENT '岗位容量', 
	allocated_count INTEGER NOT NULL COMMENT '已分配人数（最终落岗 Authority 写入）', 
	mentor_contact_id BIGINT, 
	mentor_name VARCHAR(100), 
	risk_flag BOOL NOT NULL, 
	risk_note VARCHAR(500), 
	daily_hours FLOAT, 
	weekly_hours FLOAT, 
	shift_type VARCHAR(30), 
	night_shift BOOL, 
	overtime_allowed BOOL, 
	rest_days VARCHAR(50), 
	rest_days_per_week FLOAT, 
	remuneration_type VARCHAR(30), 
	remuneration_amount FLOAT, 
	remuneration_cycle VARCHAR(30), 
	accommodation_provided BOOL, 
	meal_provided BOOL, 
	hazardous_flag BOOL, 
	special_equipment VARCHAR(200), 
	work_content TEXT, 
	work_address VARCHAR(300), 
	prohibited_reason VARCHAR(500), 
	rights_status VARCHAR(30), 
	rights_checked_at DATETIME, 
	rights_rule_version VARCHAR(64), 
	status VARCHAR(50) NOT NULL, 
	remark VARCHAR(500), 
	publish_at DATETIME, 
	archived_at DATETIME, 
	archived_by VARCHAR(100), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_intern_position_campaign_catalog ON t_internship_position (tenant_id, campaign_id, status, company_id, is_deleted);

CREATE INDEX ix_t_internship_position_batch_id ON t_internship_position (batch_id);

CREATE INDEX ix_t_internship_position_campaign_id ON t_internship_position (campaign_id);

CREATE INDEX ix_t_internship_position_company_id ON t_internship_position (company_id);

CREATE INDEX ix_t_internship_position_mentor_contact_id ON t_internship_position (mentor_contact_id);

CREATE INDEX ix_t_internship_position_status ON t_internship_position (status);

CREATE INDEX ix_t_internship_position_tenant_id ON t_internship_position (tenant_id);

CREATE TABLE t_internship_process_report (
	internship_id BIGINT NOT NULL, 
	report_type VARCHAR(20) NOT NULL COMMENT '报告类型 MONTHLY/SUMMARY 等', 
	period_key VARCHAR(20) NOT NULL COMMENT '周期键，如 2026-03', 
	content TEXT, 
	word_count INTEGER NOT NULL, 
	submitted_at DATETIME, 
	status VARCHAR(50) NOT NULL COMMENT 'PENDING_REVIEW/APPROVED/RETURNED', 
	review_action VARCHAR(50), 
	review_comment VARCHAR(500), 
	reviewed_by_name VARCHAR(100), 
	reviewed_at DATETIME, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_intern_process_report UNIQUE (tenant_id, internship_id, report_type, period_key)
);

CREATE INDEX ix_t_internship_process_report_internship_id ON t_internship_process_report (internship_id);

CREATE INDEX ix_t_internship_process_report_tenant_id ON t_internship_process_report (tenant_id);

CREATE TABLE t_internship_record (
	student_id BIGINT NOT NULL COMMENT '= t_student_profile.id', 
	batch_id BIGINT COMMENT '实习批次；应用层强制非空，历史 NULL 待人工映射后由迁移改 NOT NULL', 
	enterprise_name VARCHAR(200) COMMENT '实习单位（冗余展示）', 
	position_name VARCHAR(100) COMMENT '岗位（冗余展示）', 
	advisor_name VARCHAR(100) COMMENT '校内指导教师', 
	enterprise_mentor_name VARCHAR(100) COMMENT '企业导师（冗余展示）', 
	advisor_user_id BIGINT COMMENT '校内指导教师 t_user.id', 
	enterprise_id BIGINT COMMENT '→ t_emp_company.id', 
	position_id BIGINT COMMENT '→ t_internship_position.id', 
	mentor_contact_id BIGINT COMMENT '→ t_internship_enterprise_contact.id', 
	eligibility_status VARCHAR(50) NOT NULL COMMENT '实习资格 PENDING/QUALIFIED/UNQUALIFIED', 
	destination_type VARCHAR(50) NOT NULL COMMENT '实习去向 ASSIGNED/SELF_ARRANGED/EXEMPTED/NONE', 
	status VARCHAR(50) NOT NULL COMMENT 'PREPARING/READY/ONBOARD/ASSESSING/ARCHIVED', 
	risk_level VARCHAR(50) NOT NULL COMMENT 'NONE/LOW/MEDIUM/HIGH', 
	intern_start_date DATETIME, 
	intern_end_date DATETIME, 
	insurance_info VARCHAR(200) COMMENT '实习保险', 
	agreement_info VARCHAR(200) COMMENT '三方协议状态', 
	remark VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	current_placement_snapshot_id BIGINT COMMENT '→ t_internship_placement_snapshot.id', 
	PRIMARY KEY (id), 
	CONSTRAINT uk_intern_stu_batch UNIQUE (tenant_id, student_id, batch_id)
);

CREATE INDEX ix_intern_tenant_student_active ON t_internship_record (tenant_id, student_id, is_deleted);

CREATE INDEX ix_t_internship_record_advisor_user_id ON t_internship_record (advisor_user_id);

CREATE INDEX ix_t_internship_record_batch_id ON t_internship_record (batch_id);

CREATE INDEX ix_t_internship_record_enterprise_id ON t_internship_record (enterprise_id);

CREATE INDEX ix_t_internship_record_position_id ON t_internship_record (position_id);

CREATE INDEX ix_t_internship_record_student_id ON t_internship_record (student_id);

CREATE INDEX ix_t_internship_record_tenant_id ON t_internship_record (tenant_id);

CREATE TABLE t_internship_recruitment_campaign (
	batch_id BIGINT NOT NULL COMMENT '→ t_internship_batch.id', 
	campaign_code VARCHAR(100) NOT NULL, 
	campaign_name VARCHAR(200) NOT NULL, 
	round_no INTEGER NOT NULL, 
	status VARCHAR(20) NOT NULL COMMENT 'DRAFT/OPEN/FROZEN/CLOSED/ARCHIVED', 
	invite_start_at DATETIME, 
	invite_end_at DATETIME, 
	position_submit_start_at DATETIME, 
	position_submit_end_at DATETIME, 
	student_select_start_at DATETIME, 
	student_select_end_at DATETIME, 
	enterprise_decision_start_at DATETIME, 
	enterprise_decision_end_at DATETIME, 
	school_confirm_start_at DATETIME, 
	school_confirm_end_at DATETIME, 
	enterprise_access_end_at DATETIME, 
	enterprise_confirm_required BOOL NOT NULL, 
	application_material_policy_json JSON, 
	teacher_confirm_sla_hours INTEGER NOT NULL COMMENT '企业 ACCEPT_INTENT 后学校确认 SLA；冻结范围 1-168 小时', 
	remark VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_intern_recruit_campaign_code UNIQUE (tenant_id, campaign_code), 
	CONSTRAINT uk_intern_recruit_campaign_round UNIQUE (tenant_id, batch_id, round_no)
);

CREATE INDEX ix_intern_recruit_campaign_batch_status ON t_internship_recruitment_campaign (tenant_id, batch_id, status, is_deleted);

CREATE INDEX ix_intern_recruit_campaign_select_window ON t_internship_recruitment_campaign (tenant_id, status, student_select_start_at, student_select_end_at);

CREATE INDEX ix_t_internship_recruitment_campaign_tenant_id ON t_internship_recruitment_campaign (tenant_id);

CREATE TABLE t_internship_remuneration_record (
	internship_id BIGINT NOT NULL, 
	batch_id BIGINT, 
	position_id BIGINT, 
	agreed_amount FLOAT, 
	agreed_cycle VARCHAR(30) COMMENT 'MONTHLY/WEEKLY/DAILY/ONCE', 
	actual_paid_amount FLOAT, 
	paid_at DATETIME, 
	proof_file_id VARCHAR(64), 
	status VARCHAR(30) NOT NULL COMMENT 'AGREED/PARTIAL/PAID/DISCREPANCY/UNCONFIRMED', 
	discrepancy VARCHAR(500), 
	student_confirmed_at DATETIME, 
	rule_version VARCHAR(64), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_t_internship_remuneration_record_batch_id ON t_internship_remuneration_record (batch_id);

CREATE INDEX ix_t_internship_remuneration_record_internship_id ON t_internship_remuneration_record (internship_id);

CREATE INDEX ix_t_internship_remuneration_record_position_id ON t_internship_remuneration_record (position_id);

CREATE INDEX ix_t_internship_remuneration_record_tenant_id ON t_internship_remuneration_record (tenant_id);

CREATE TABLE t_internship_safety_completion (
	internship_id BIGINT NOT NULL, 
	batch_id BIGINT, 
	student_id BIGINT NOT NULL, 
	course_id BIGINT NOT NULL, 
	course_version VARCHAR(40) NOT NULL, 
	course_content_snapshot TEXT, 
	course_content_hash VARCHAR(64), 
	started_at DATETIME, 
	completed_at DATETIME, 
	studied_minutes INTEGER NOT NULL, 
	submitted_at DATETIME, 
	answer_snapshot JSON, 
	attempt_count INTEGER NOT NULL, 
	score INTEGER, 
	passed BOOL NOT NULL, 
	commitment_confirmed BOOL NOT NULL, 
	commitment_at DATETIME, 
	commitment_content_hash VARCHAR(64), 
	commitment_device_digest VARCHAR(128), 
	evidence_file_id VARCHAR(64), 
	review_mode VARCHAR(30) NOT NULL COMMENT 'ONLINE_QUIZ/TEACHER_REVIEW', 
	reviewed_by_name VARCHAR(100), 
	reviewed_by_user_id VARCHAR(64), 
	reviewed_at DATETIME, 
	status VARCHAR(30) NOT NULL COMMENT 'PENDING/PASSED/FAILED/EXPIRED', 
	rule_version VARCHAR(64), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_ix_safety_completion UNIQUE (tenant_id, internship_id, course_id)
);

CREATE INDEX ix_t_internship_safety_completion_batch_id ON t_internship_safety_completion (batch_id);

CREATE INDEX ix_t_internship_safety_completion_course_id ON t_internship_safety_completion (course_id);

CREATE INDEX ix_t_internship_safety_completion_internship_id ON t_internship_safety_completion (internship_id);

CREATE INDEX ix_t_internship_safety_completion_student_id ON t_internship_safety_completion (student_id);

CREATE INDEX ix_t_internship_safety_completion_tenant_id ON t_internship_safety_completion (tenant_id);

CREATE TABLE t_internship_safety_course (
	batch_id BIGINT, 
	title VARCHAR(200) NOT NULL, 
	course_version VARCHAR(40) NOT NULL, 
	required_minutes INTEGER NOT NULL, 
	passing_score INTEGER NOT NULL, 
	max_attempts INTEGER NOT NULL, 
	require_commitment BOOL NOT NULL, 
	content_snapshot TEXT, 
	material_file_ids JSON, 
	status VARCHAR(20) NOT NULL COMMENT 'DRAFT/ACTIVE/RETIRED', 
	effective_at DATETIME, 
	retired_at DATETIME, 
	rule_version VARCHAR(64), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_t_internship_safety_course_batch_id ON t_internship_safety_course (batch_id);

CREATE INDEX ix_t_internship_safety_course_tenant_id ON t_internship_safety_course (tenant_id);

CREATE TABLE t_internship_score_config (
	batch_id BIGINT, 
	active_scope_key VARCHAR(80) COMMENT 'ACTIVE 配置唯一作用域；历史 RETIRED 置空', 
	checkin_weight INTEGER NOT NULL COMMENT '打卡权重', 
	weekly_weight INTEGER NOT NULL COMMENT '周报权重', 
	monthly_weight INTEGER NOT NULL COMMENT '月报/总结权重', 
	enterprise_weight INTEGER NOT NULL COMMENT '企业评价权重', 
	school_weight INTEGER NOT NULL COMMENT '学校/教师评价权重', 
	pass_line FLOAT NOT NULL COMMENT '及格线', 
	status VARCHAR(20) NOT NULL, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_intern_score_cfg_active_scope UNIQUE (tenant_id, active_scope_key)
);

CREATE INDEX ix_t_internship_score_config_active_scope_key ON t_internship_score_config (active_scope_key);

CREATE INDEX ix_t_internship_score_config_batch_id ON t_internship_score_config (batch_id);

CREATE INDEX ix_t_internship_score_config_tenant_id ON t_internship_score_config (tenant_id);

CREATE TABLE t_internship_special_filing (
	internship_id BIGINT NOT NULL, 
	batch_id BIGINT, 
	student_id BIGINT NOT NULL, 
	filing_type VARCHAR(40) NOT NULL COMMENT 'CROSS_PROVINCE/CROSS_CITY/OVERSEAS/HIGH_RISK/NIGHT_SHIFT/SPECIAL_TRADE/MINOR/REMOTE/OTHER', 
	applicable BOOL NOT NULL, 
	trigger_reason VARCHAR(500), 
	destination_region VARCHAR(200), 
	work_address VARCHAR(300), 
	risk_description TEXT, 
	student_application TEXT, 
	guardian_consent_required BOOL NOT NULL, 
	college_review_by VARCHAR(100), 
	college_review_at DATETIME, 
	college_comment VARCHAR(500), 
	school_review_by VARCHAR(100), 
	school_review_at DATETIME, 
	school_comment VARCHAR(500), 
	regulator_filing_no VARCHAR(100), 
	status VARCHAR(30) NOT NULL COMMENT 'NOT_REQUIRED/DRAFT/PENDING_COLLEGE/PENDING_SCHOOL/APPROVED/REJECTED/WITHDRAWN/EXPIRED/SUPERSEDED', 
	requested_by_name VARCHAR(100), 
	requested_by_user_id VARCHAR(64), 
	reviewed_by_name VARCHAR(100), 
	reviewed_at DATETIME, 
	approved_by_name VARCHAR(100), 
	approved_at DATETIME, 
	valid_until DATETIME, 
	file_ids JSON, 
	rule_version VARCHAR(64), 
	superseded_by_id BIGINT, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_ix_filing_intern ON t_internship_special_filing (tenant_id, internship_id, is_deleted);

CREATE INDEX ix_t_internship_special_filing_batch_id ON t_internship_special_filing (batch_id);

CREATE INDEX ix_t_internship_special_filing_internship_id ON t_internship_special_filing (internship_id);

CREATE INDEX ix_t_internship_special_filing_student_id ON t_internship_special_filing (student_id);

CREATE INDEX ix_t_internship_special_filing_tenant_id ON t_internship_special_filing (tenant_id);

CREATE TABLE t_internship_student_eval (
	internship_id BIGINT NOT NULL, 
	student_id BIGINT NOT NULL, 
	batch_id BIGINT, 
	self_summary TEXT COMMENT '实习总结', 
	self_harvest TEXT COMMENT '学习收获', 
	self_problem TEXT COMMENT '存在问题', 
	advisor_opinion VARCHAR(1000) COMMENT '指导教师意见', 
	mentor_opinion VARCHAR(1000) COMMENT '企业导师意见', 
	submit_status VARCHAR(20) NOT NULL COMMENT 'DRAFT/SUBMITTED', 
	submitted_at DATETIME, 
	school_review_status VARCHAR(20) NOT NULL COMMENT 'PENDING/APPROVED/RETURNED', 
	school_review_comment VARCHAR(500), 
	reviewed_by_name VARCHAR(50), 
	reviewed_at DATETIME, 
	file_id VARCHAR(64) COMMENT '鉴定表扫描件 file_id', 
	enterprise_rating INTEGER COMMENT '对企业评分 1-5', 
	position_rating INTEGER COMMENT '对岗位评分 1-5', 
	enterprise_feedback VARCHAR(1000) COMMENT '对企业评价意见', 
	position_feedback VARCHAR(1000) COMMENT '对岗位评价意见', 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_t_internship_student_eval_batch_id ON t_internship_student_eval (batch_id);

CREATE INDEX ix_t_internship_student_eval_internship_id ON t_internship_student_eval (internship_id);

CREATE INDEX ix_t_internship_student_eval_student_id ON t_internship_student_eval (student_id);

CREATE INDEX ix_t_internship_student_eval_tenant_id ON t_internship_student_eval (tenant_id);

CREATE TABLE t_internship_student_profile (
	student_id BIGINT NOT NULL COMMENT '→ t_student_profile.id', 
	profile_version INTEGER NOT NULL, 
	headline VARCHAR(120), 
	self_intro TEXT, 
	strengths TEXT, 
	available_from DATE, 
	available_until DATE, 
	expected_locations_json JSON, 
	skill_tags_json JSON, 
	resume_template_code VARCHAR(50) NOT NULL, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_intern_student_profile UNIQUE (tenant_id, student_id)
);

CREATE INDEX ix_intern_student_profile_student ON t_internship_student_profile (tenant_id, student_id, is_deleted);

CREATE INDEX ix_t_internship_student_profile_tenant_id ON t_internship_student_profile (tenant_id);

CREATE TABLE t_internship_student_profile_item (
	profile_id BIGINT NOT NULL COMMENT '→ t_internship_student_profile.id', 
	item_type VARCHAR(30) NOT NULL COMMENT 'SKILL_EVIDENCE/CERTIFICATE/PROJECT/PRACTICE/AWARD/PORTFOLIO', 
	title VARCHAR(200) NOT NULL, 
	organization VARCHAR(200), 
	description TEXT, 
	start_date DATE, 
	end_date DATE, 
	level VARCHAR(100), 
	source_type VARCHAR(30) NOT NULL COMMENT 'STUDENT_ENTERED/SCHOOL_FACT', 
	source_ref_type VARCHAR(80), 
	source_ref_id VARCHAR(100), 
	verification_status VARCHAR(30) NOT NULL COMMENT 'UNVERIFIED/VERIFIED/NOT_REQUIRED', 
	sort_order INTEGER NOT NULL, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_intern_profile_item_source ON t_internship_student_profile_item (tenant_id, source_ref_type, source_ref_id, is_deleted);

CREATE INDEX ix_intern_profile_item_type ON t_internship_student_profile_item (tenant_id, profile_id, item_type, is_deleted);

CREATE INDEX ix_t_internship_student_profile_item_tenant_id ON t_internship_student_profile_item (tenant_id);

CREATE TABLE t_internship_visit (
	internship_id BIGINT NOT NULL, 
	student_id BIGINT NOT NULL, 
	advisor_name VARCHAR(50) COMMENT '巡访教师', 
	enterprise_name VARCHAR(200), 
	visit_at DATETIME COMMENT '巡访时间', 
	method VARCHAR(20) NOT NULL COMMENT 'ONSITE/ONLINE/PHONE', 
	enterprise_feedback VARCHAR(1000) COMMENT '企业反馈', 
	student_feedback VARCHAR(1000) COMMENT '学生反馈', 
	safety_issue VARCHAR(500) COMMENT '安全隐患', 
	rectify_require VARCHAR(500) COMMENT '整改要求', 
	rectify_deadline VARCHAR(10) COMMENT '整改截止 YYYY-MM-DD', 
	rectify_status VARCHAR(20) NOT NULL COMMENT 'NONE/PENDING/DONE', 
	monthly_report TEXT COMMENT '巡访月报', 
	file_id VARCHAR(64) COMMENT '附件 file_id 预留', 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_t_internship_visit_internship_id ON t_internship_visit (internship_id);

CREATE INDEX ix_t_internship_visit_student_id ON t_internship_visit (student_id);

CREATE INDEX ix_t_internship_visit_tenant_id ON t_internship_visit (tenant_id);

CREATE TABLE t_internship_visit_plan (
	batch_id BIGINT COMMENT '关联批次', 
	college_id BIGINT, 
	enterprise_id BIGINT COMMENT '巡访企业', 
	enterprise_name VARCHAR(200), 
	owner_name VARCHAR(50) COMMENT '计划负责人（owner scope）', 
	collaborators VARCHAR(500) COMMENT '协同人员（姓名，逗号分隔）', 
	student_scope TEXT COMMENT '覆盖学生范围（学号/姓名快照）', 
	plan_date VARCHAR(10) COMMENT '计划日期 YYYY-MM-DD', 
	time_window VARCHAR(50) COMMENT '时间窗', 
	method VARCHAR(20) NOT NULL COMMENT 'ONSITE/ONLINE/PHONE', 
	location VARCHAR(200) COMMENT '巡访地点', 
	objective TEXT COMMENT '目标与检查清单', 
	status VARCHAR(20) NOT NULL COMMENT 'DRAFT/PUBLISHED/IN_PROGRESS/COMPLETED/CANCELLED/OVERDUE', 
	plan_type VARCHAR(20) NOT NULL COMMENT 'VISIT 正式 / UNPLANNED 临时巡访补录', 
	remind_at DATETIME COMMENT '提醒时间', 
	visit_id BIGINT COMMENT '实际巡访记录 id（关联执行）', 
	completed_at DATETIME, 
	cancel_reason VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_t_internship_visit_plan_batch_id ON t_internship_visit_plan (batch_id);

CREATE INDEX ix_t_internship_visit_plan_college_id ON t_internship_visit_plan (college_id);

CREATE INDEX ix_t_internship_visit_plan_enterprise_id ON t_internship_visit_plan (enterprise_id);

CREATE INDEX ix_t_internship_visit_plan_status ON t_internship_visit_plan (status);

CREATE INDEX ix_t_internship_visit_plan_tenant_id ON t_internship_visit_plan (tenant_id);

CREATE TABLE t_internship_volunteer_group (
	record_id BIGINT NOT NULL COMMENT '→ t_internship_record.id', 
	student_id BIGINT NOT NULL COMMENT '→ t_student_profile.id', 
	batch_id BIGINT NOT NULL COMMENT '→ t_internship_batch.id', 
	campaign_id BIGINT NOT NULL COMMENT '→ t_internship_recruitment_campaign.id', 
	status VARCHAR(30) NOT NULL COMMENT 'DRAFT/SUBMITTED/LOCKED/NEEDS_REVISION/APPROVED/CLOSED', 
	submission_version INTEGER NOT NULL, 
	current_material_snapshot_id BIGINT COMMENT '→ t_internship_application_material_snapshot.id', 
	submitted_at DATETIME, 
	locked_application_id BIGINT COMMENT '触发当前 LOCKED 的 canonical InternshipApplication.id', 
	locked_at DATETIME, 
	locked_by_decision_id BIGINT COMMENT '最近触发 LOCKED 的 EnterpriseApplicationDecision；历史 Decision 不删除', 
	teacher_confirm_deadline DATETIME, 
	approved_at DATETIME, 
	revision_requested_at DATETIME, 
	revision_reason VARCHAR(500), 
	released_at DATETIME, 
	release_reason VARCHAR(500), 
	released_by_user_id BIGINT, 
	unlock_requested_at DATETIME, 
	unlock_request_reason VARCHAR(500), 
	contact_consent_revoked_at DATETIME, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_intern_volunteer_group_record_campaign UNIQUE (tenant_id, record_id, campaign_id)
);

CREATE INDEX ix_intern_volunteer_group_campaign_deadline ON t_internship_volunteer_group (tenant_id, campaign_id, status, teacher_confirm_deadline, is_deleted);

CREATE INDEX ix_intern_volunteer_group_record_status ON t_internship_volunteer_group (tenant_id, record_id, status, is_deleted);

CREATE INDEX ix_intern_volunteer_group_student_status ON t_internship_volunteer_group (tenant_id, student_id, campaign_id, status, is_deleted);

CREATE INDEX ix_t_internship_volunteer_group_tenant_id ON t_internship_volunteer_group (tenant_id);

CREATE TABLE t_major (
	college_id BIGINT NOT NULL, 
	major_name VARCHAR(200) NOT NULL, 
	code VARCHAR(50), 
	status VARCHAR(50) NOT NULL, 
	remark VARCHAR(500), 
	education_years INTEGER NOT NULL COMMENT '学制（年），默认3', 
	training_level VARCHAR(50) COMMENT '培养层次 SECONDARY/HIGHER/FIVE_YEAR 等', 
	enroll_status VARCHAR(50) NOT NULL COMMENT '招生状态 ENROLLING 招生中 / STOPPED 停招', 
	direction VARCHAR(200) COMMENT '专业方向（可空）', 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_t_major_college_id ON t_major (college_id);

CREATE INDEX ix_t_major_tenant_id ON t_major (tenant_id);

CREATE TABLE t_message_attachment (
	campaign_id BIGINT NOT NULL, 
	file_id BIGINT NOT NULL, 
	sort_no INTEGER NOT NULL, 
	file_name_snapshot VARCHAR(200), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_msg_attach_campaign ON t_message_attachment (tenant_id, campaign_id, sort_no);

CREATE INDEX ix_t_message_attachment_campaign_id ON t_message_attachment (campaign_id);

CREATE INDEX ix_t_message_attachment_tenant_id ON t_message_attachment (tenant_id);

CREATE TABLE t_message_audience (
	campaign_id BIGINT NOT NULL, 
	audience_type VARCHAR(30) NOT NULL COMMENT 'ALL_STUDENT/ALL_STAFF/ALL_USERS/COLLEGE/MAJOR/GRADE/ADMIN_CLASS/TEACHING_CLASS/ROLE/PERSON', 
	include_or_exclude VARCHAR(10) NOT NULL COMMENT 'INCLUDE/EXCLUDE', 
	target_id BIGINT, 
	target_code VARCHAR(64), 
	include_children BOOL NOT NULL, 
	rule_json JSON, 
	rule_version VARCHAR(20) NOT NULL, 
	resolved_count INTEGER, 
	resolved_at DATETIME, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_audience_campaign ON t_message_audience (tenant_id, campaign_id, id);

CREATE INDEX ix_t_message_audience_campaign_id ON t_message_audience (campaign_id);

CREATE INDEX ix_t_message_audience_tenant_id ON t_message_audience (tenant_id);

CREATE TABLE t_message_campaign (
	title VARCHAR(200) NOT NULL, 
	content_plain TEXT NOT NULL, 
	content_html TEXT, 
	summary VARCHAR(200), 
	category VARCHAR(30) NOT NULL COMMENT 'ANNOUNCEMENT/BUSINESS/REMINDER/EMERGENCY', 
	priority VARCHAR(20) NOT NULL COMMENT 'NORMAL/IMPORTANT/EMERGENCY', 
	status VARCHAR(30) NOT NULL COMMENT 'DRAFT/PENDING_REVIEW/RETURNED/REJECTED/APPROVED/SCHEDULED/PUBLISHING/PUBLISHED/PARTIAL_FAILED/WITHDRAWN/EXPIRED', 
	source_kind VARCHAR(20) NOT NULL COMMENT 'HUMAN/BUSINESS_EVENT/PLATFORM', 
	source_module VARCHAR(50), 
	source_biz_type VARCHAR(50), 
	source_biz_id BIGINT, 
	content_mode VARCHAR(20) NOT NULL COMMENT 'SHARED/PER_RECIPIENT', 
	template_id BIGINT, 
	template_version VARCHAR(30), 
	sender_user_id BIGINT NOT NULL, 
	sender_context_id VARCHAR(64), 
	sender_org_id BIGINT, 
	sender_name_snapshot VARCHAR(100), 
	sender_role_snapshot VARCHAR(64), 
	org_name_snapshot VARCHAR(200), 
	publish_mode VARCHAR(20) NOT NULL COMMENT 'IMMEDIATE/SCHEDULED', 
	scheduled_at DATETIME, 
	published_at DATETIME, 
	effective_at DATETIME, 
	expire_at DATETIME, 
	require_ack BOOL NOT NULL, 
	pinned BOOL NOT NULL, 
	emergency BOOL NOT NULL, 
	action_key VARCHAR(80), 
	action_params_json JSON, 
	workflow_instance_id BIGINT, 
	recipient_count INTEGER NOT NULL, 
	delivered_count INTEGER NOT NULL, 
	read_count INTEGER NOT NULL, 
	ack_count INTEGER NOT NULL, 
	failure_count INTEGER NOT NULL, 
	content_version INTEGER NOT NULL, 
	idempotency_key VARCHAR(80), 
	audience_fingerprint VARCHAR(80), 
	supersedes_campaign_id BIGINT, 
	withdrawn_at DATETIME, 
	withdrawn_by BIGINT, 
	withdraw_reason VARCHAR(500), 
	channels_json JSON, 
	remark VARCHAR(500), 
	ack_deadline_at DATETIME, 
	delivery_mode VARCHAR(20) NOT NULL COMMENT 'SYNC/ASYNC' DEFAULT 'ASYNC', 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_campaign_tenant_idem UNIQUE (tenant_id, idempotency_key)
);

CREATE INDEX ix_campaign_tenant_org_created ON t_message_campaign (tenant_id, sender_org_id, created_at, id);

CREATE INDEX ix_campaign_tenant_status_sched ON t_message_campaign (tenant_id, status, scheduled_at, id);

CREATE INDEX ix_t_message_campaign_sender_user_id ON t_message_campaign (sender_user_id);

CREATE INDEX ix_t_message_campaign_tenant_id ON t_message_campaign (tenant_id);

CREATE TABLE t_message_channel_delivery (
	campaign_id BIGINT NOT NULL, 
	channel VARCHAR(20) NOT NULL, 
	receiver_user_id BIGINT NOT NULL, 
	status VARCHAR(20) NOT NULL COMMENT 'PENDING/PROCESSING/RETRY_WAIT/SENT/SKIPPED/DEAD', 
	attempt_count INTEGER NOT NULL, 
	next_retry_at DATETIME, 
	locked_by VARCHAR(80), 
	locked_at DATETIME, 
	lease_expires_at DATETIME, 
	last_error_code VARCHAR(80), 
	last_error_message_safe VARCHAR(200), 
	provider_request_id VARCHAR(120), 
	sent_at DATETIME, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_msg_channel_delivery_receiver UNIQUE (tenant_id, campaign_id, channel, receiver_user_id)
);

CREATE INDEX ix_msg_channel_delivery_campaign ON t_message_channel_delivery (tenant_id, campaign_id, channel, status);

CREATE INDEX ix_msg_channel_delivery_claim ON t_message_channel_delivery (tenant_id, status, next_retry_at, id);

CREATE INDEX ix_msg_channel_delivery_lease ON t_message_channel_delivery (tenant_id, status, lease_expires_at, id);

CREATE INDEX ix_t_message_channel_delivery_campaign_id ON t_message_channel_delivery (campaign_id);

CREATE INDEX ix_t_message_channel_delivery_receiver_user_id ON t_message_channel_delivery (receiver_user_id);

CREATE INDEX ix_t_message_channel_delivery_tenant_id ON t_message_channel_delivery (tenant_id);

CREATE TABLE t_message_delivery_job (
	campaign_id BIGINT NOT NULL, 
	cursor_start INTEGER NOT NULL, 
	batch_size INTEGER NOT NULL, 
	status VARCHAR(20) NOT NULL COMMENT 'PENDING/PROCESSING/SUCCEEDED/RETRY_WAIT/DEAD', 
	attempt_count INTEGER NOT NULL, 
	next_retry_at DATETIME, 
	locked_by VARCHAR(80), 
	locked_at DATETIME, 
	lease_expires_at DATETIME, 
	last_error_code VARCHAR(80), 
	recipient_slice_json JSON, 
	written_count INTEGER NOT NULL, 
	remark VARCHAR(500) COMMENT 'worker notes', 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_msg_delivery_job_campaign_cursor UNIQUE (tenant_id, campaign_id, cursor_start)
);

CREATE INDEX ix_msg_delivery_job_status_retry ON t_message_delivery_job (status, next_retry_at, id);

CREATE INDEX ix_t_message_delivery_job_campaign_id ON t_message_delivery_job (campaign_id);

CREATE INDEX ix_t_message_delivery_job_tenant_id ON t_message_delivery_job (tenant_id);

CREATE TABLE t_message_event_outbox (
	event_code VARCHAR(80) NOT NULL, 
	source_module VARCHAR(50) NOT NULL, 
	source_biz_type VARCHAR(50) NOT NULL, 
	source_biz_id BIGINT NOT NULL, 
	payload_json JSON, 
	recipient_refs_json JSON, 
	dedup_key VARCHAR(120) NOT NULL, 
	status VARCHAR(20) NOT NULL COMMENT 'PENDING/PROCESSING/SUCCEEDED/RETRY_WAIT/DEAD', 
	attempt_count INTEGER NOT NULL, 
	next_retry_at DATETIME, 
	last_error_code VARCHAR(80), 
	locked_by VARCHAR(80), 
	locked_at DATETIME, 
	lease_expires_at DATETIME, 
	occurred_at DATETIME NOT NULL, 
	processed_at DATETIME, 
	campaign_id BIGINT, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_outbox_tenant_dedup UNIQUE (tenant_id, dedup_key)
);

CREATE INDEX ix_outbox_status_retry ON t_message_event_outbox (status, next_retry_at, id);

CREATE INDEX ix_t_message_event_outbox_event_code ON t_message_event_outbox (event_code);

CREATE INDEX ix_t_message_event_outbox_tenant_id ON t_message_event_outbox (tenant_id);

CREATE TABLE t_permission (
	permission_code VARCHAR(200) NOT NULL COMMENT '模块:资源:动作，如 student:profile:export', 
	permission_name VARCHAR(200) NOT NULL, 
	module_code VARCHAR(50), 
	action VARCHAR(50) COMMENT '17 个动作枚举之一（§4.3）', 
	created_at DATETIME NOT NULL, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_permission_code UNIQUE (permission_code)
);

CREATE TABLE t_risk_record (
	internship_id BIGINT NOT NULL, 
	risk_code VARCHAR(50) NOT NULL COMMENT '如 INT-R07', 
	risk_title VARCHAR(200) NOT NULL, 
	risk_level VARCHAR(50) NOT NULL COMMENT 'HIGH/MEDIUM/LOW', 
	source_module VARCHAR(50) NOT NULL COMMENT 'system/manual/complaint/internship_leave', 
	source_type VARCHAR(50) COMMENT '来源单据类型，如 COMPLAINT/LEAVE', 
	source_id BIGINT COMMENT '来源单据主键', 
	source_version INTEGER COMMENT '创建风险时来源单据版本', 
	owner_name VARCHAR(100) COMMENT '跟进责任人', 
	deadline_at DATETIME, 
	status VARCHAR(50) NOT NULL COMMENT 'PENDING_HANDLE/PROCESSING/RESOLVED/CLOSED', 
	last_follow_at DATETIME, 
	last_follow_note VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_risk_source UNIQUE (tenant_id, source_type, source_id, risk_code)
);

CREATE INDEX ix_risk_source ON t_risk_record (tenant_id, source_type, source_id);

CREATE INDEX ix_t_risk_record_internship_id ON t_risk_record (internship_id);

CREATE INDEX ix_t_risk_record_source_id ON t_risk_record (source_id);

CREATE INDEX ix_t_risk_record_source_type ON t_risk_record (source_type);

CREATE INDEX ix_t_risk_record_tenant_id ON t_risk_record (tenant_id);

CREATE TABLE t_role (
	role_code VARCHAR(50) NOT NULL COMMENT '如 COUNSELOR/COLLEGE_ADMIN', 
	role_name VARCHAR(100) NOT NULL, 
	role_type VARCHAR(50) COMMENT 'SYSTEM/CUSTOM，TODO 以 11 中心为准', 
	status VARCHAR(50) NOT NULL, 
	remark VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_tenant_role_code UNIQUE (tenant_id, role_code)
);

CREATE INDEX ix_t_role_tenant_id ON t_role (tenant_id);

CREATE TABLE t_role_permission (
	role_id BIGINT NOT NULL, 
	permission_id BIGINT NOT NULL, 
	status VARCHAR(50) NOT NULL, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_role_permission UNIQUE (tenant_id, role_id, permission_id)
);

CREATE INDEX ix_t_role_permission_permission_id ON t_role_permission (permission_id);

CREATE INDEX ix_t_role_permission_role_id ON t_role_permission (role_id);

CREATE INDEX ix_t_role_permission_tenant_id ON t_role_permission (tenant_id);

CREATE TABLE t_student_account_link (
	student_id BIGINT NOT NULL COMMENT '= t_student_profile.id（学籍身份，永久不变）', 
	user_id BIGINT NOT NULL COMMENT '= t_user.id（登录账号）', 
	link_status VARCHAR(20) NOT NULL COMMENT 'ACTIVE/SUSPENDED/REVOKED/MERGED', 
	bound_login_name VARCHAR(100) COMMENT '建立绑定时的登录名快照，仅供追溯，不作为查询键', 
	bound_student_no VARCHAR(50) COMMENT '建立绑定时的学号快照，仅供追溯，不作为查询键', 
	source VARCHAR(30) NOT NULL COMMENT '来源：IDENTITY_IMPORT/MANUAL/BACKFILL（历史 login_name==student_no 回填）', 
	bound_at DATETIME COMMENT '绑定时间', 
	unbound_at DATETIME COMMENT '解绑/暂停时间', 
	remark VARCHAR(500) COMMENT '备注（换绑原因等）', 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_sal_tenant_student_status UNIQUE (tenant_id, student_id, link_status), 
	CONSTRAINT uk_sal_tenant_user_status UNIQUE (tenant_id, user_id, link_status)
);

CREATE INDEX ix_sal_tenant_student_status ON t_student_account_link (tenant_id, student_id, link_status);

CREATE INDEX ix_sal_tenant_user_status ON t_student_account_link (tenant_id, user_id, link_status);

CREATE INDEX ix_t_student_account_link_link_status ON t_student_account_link (link_status);

CREATE INDEX ix_t_student_account_link_student_id ON t_student_account_link (student_id);

CREATE INDEX ix_t_student_account_link_tenant_id ON t_student_account_link (tenant_id);

CREATE INDEX ix_t_student_account_link_user_id ON t_student_account_link (user_id);

CREATE TABLE t_student_contact (
	student_id BIGINT NOT NULL COMMENT '= t_student_profile.id', 
	contact_type VARCHAR(50) NOT NULL COMMENT 'PHONE/EMAIL/HOME_ADDRESS/GUARDIAN_PHONE/EMERGENCY_PHONE', 
	contact_value_encrypted VARCHAR(500) COMMENT '敏感：联系值密文', 
	contact_value_hash VARCHAR(128), 
	contact_name VARCHAR(100) COMMENT '联系人姓名（紧急联系人/监护人）', 
	verified_status VARCHAR(50) NOT NULL COMMENT 'UNVERIFIED/VERIFIED/EXPIRED', 
	is_primary BOOL NOT NULL, 
	remark VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_contact_tenant_student_type_active ON t_student_contact (tenant_id, student_id, contact_type, is_deleted);

CREATE INDEX ix_t_student_contact_contact_value_hash ON t_student_contact (contact_value_hash);

CREATE INDEX ix_t_student_contact_student_id ON t_student_contact (student_id);

CREATE INDEX ix_t_student_contact_tenant_id ON t_student_contact (tenant_id);

CREATE TABLE t_student_import_batch (
	batch_no VARCHAR(100) NOT NULL COMMENT '批次号', 
	file_id BIGINT COMMENT '上传文件 t_file_object.id', 
	total_rows BIGINT, 
	success_rows BIGINT, 
	error_rows BIGINT, 
	status VARCHAR(50) NOT NULL COMMENT 'UPLOADED/DRY_RUN_PASSED/DRY_RUN_FAILED/CONFIRMED/WRITING/SUCCESS/FAILED/ROLLED_BACK', 
	remark VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_t_student_import_batch_tenant_id ON t_student_import_batch (tenant_id);

CREATE TABLE t_student_parent_link (
	student_id BIGINT NOT NULL COMMENT '= t_student_profile.id（被查看学生）', 
	student_no VARCHAR(50) NOT NULL COMMENT '学号（冗余，便于家长侧解析）', 
	guardian_name VARCHAR(100) NOT NULL COMMENT '家长/监护人姓名', 
	relation VARCHAR(20) NOT NULL COMMENT '关系：FATHER/MOTHER/GUARDIAN/OTHER/PARENT', 
	guardian_phone_encrypted VARCHAR(500) NOT NULL COMMENT '敏感：家长手机号（照既有约定存值，读时脱敏）', 
	guardian_phone_hash VARCHAR(128) NOT NULL COMMENT '手机号 hash：家长验证码登录/查重匹配', 
	visible_scopes JSON COMMENT '授权可见范围：ACADEMIC_GRADE/FEE_AID_STATUS/CAMPUS_ALERT/CAREER_PROGRESS', 
	link_status VARCHAR(20) NOT NULL COMMENT 'ACTIVE/REVOKED', 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_t_student_parent_link_guardian_phone_hash ON t_student_parent_link (guardian_phone_hash);

CREATE INDEX ix_t_student_parent_link_link_status ON t_student_parent_link (link_status);

CREATE INDEX ix_t_student_parent_link_student_id ON t_student_parent_link (student_id);

CREATE INDEX ix_t_student_parent_link_student_no ON t_student_parent_link (student_no);

CREATE INDEX ix_t_student_parent_link_tenant_id ON t_student_parent_link (tenant_id);

CREATE TABLE t_student_profile (
	student_no VARCHAR(50) NOT NULL COMMENT '学号（租户内永久唯一；作废后同号仅可复活原主档）', 
	real_name VARCHAR(100) NOT NULL COMMENT '姓名（冻结册：非敏感）；建索引:审批/巡访/迁移期姓名兜底查询消全表扫描', 
	gender VARCHAR(10), 
	id_card_encrypted VARCHAR(500) COMMENT '敏感：身份证密文（id_card）', 
	id_card_hash VARCHAR(128) COMMENT '身份证 hash（查重）', 
	college_id BIGINT, 
	major_id BIGINT, 
	class_id BIGINT, 
	grade VARCHAR(20), 
	current_stage VARCHAR(50) NOT NULL COMMENT '生命周期阶段（冻结册 §5.1 枚举）', 
	student_status VARCHAR(50) NOT NULL COMMENT '学生状态（§5.2：NORMAL/MERGED/RECYCLED 等）', 
	data_quality_status VARCHAR(50) COMMENT '数据质量状态', 
	enroll_date DATETIME, 
	status VARCHAR(50) NOT NULL COMMENT 'TODO：与 student_status 口径以 01 中心为准', 
	remark VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_tenant_student_no UNIQUE (tenant_id, student_no)
);

CREATE INDEX ix_student_tenant_active_id ON t_student_profile (tenant_id, is_deleted, id);

CREATE INDEX ix_student_tenant_class_active_id ON t_student_profile (tenant_id, class_id, is_deleted, id);

CREATE INDEX ix_student_tenant_college_active_id ON t_student_profile (tenant_id, college_id, is_deleted, id);

CREATE INDEX ix_student_tenant_major_active_id ON t_student_profile (tenant_id, major_id, is_deleted, id);

CREATE INDEX ix_t_student_profile_class_id ON t_student_profile (class_id);

CREATE INDEX ix_t_student_profile_college_id ON t_student_profile (college_id);

CREATE INDEX ix_t_student_profile_id_card_hash ON t_student_profile (id_card_hash);

CREATE INDEX ix_t_student_profile_major_id ON t_student_profile (major_id);

CREATE INDEX ix_t_student_profile_real_name ON t_student_profile (real_name);

CREATE INDEX ix_t_student_profile_tenant_id ON t_student_profile (tenant_id);

CREATE TABLE t_student_stage_event (
	student_id BIGINT NOT NULL, 
	from_stage VARCHAR(50), 
	to_stage VARCHAR(50) NOT NULL, 
	reason VARCHAR(500), 
	source_module VARCHAR(50), 
	occurred_at DATETIME NOT NULL, 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	PRIMARY KEY (id)
);

CREATE INDEX ix_t_student_stage_event_student_id ON t_student_stage_event (student_id);

CREATE INDEX ix_t_student_stage_event_tenant_id ON t_student_stage_event (tenant_id);

CREATE TABLE t_teacher_student_scope (
	teacher_key VARCHAR(64) NOT NULL COMMENT '教师标识：登录名或 userId', 
	teacher_name VARCHAR(64) COMMENT '教师姓名（冗余，便于排查）', 
	role_code VARCHAR(32) COMMENT '生效角色（COUNSELOR/GD_MENTOR/...）；空=全部角色', 
	scope_type VARCHAR(16) NOT NULL COMMENT 'CLASS/COLLEGE/MAJOR/STUDENT/ADVISOR', 
	ref_value VARCHAR(128) COMMENT '班级名/学院名/专业名/学号；ADVISOR 可空', 
	status VARCHAR(16) NOT NULL, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_t_teacher_student_scope_teacher_key ON t_teacher_student_scope (teacher_key);

CREATE INDEX ix_t_teacher_student_scope_tenant_id ON t_teacher_student_scope (tenant_id);

CREATE TABLE t_tenant (
	tenant_code VARCHAR(50) NOT NULL COMMENT '租户编码（学校唯一标识）', 
	school_name VARCHAR(200) NOT NULL COMMENT '学校全称', 
	short_name VARCHAR(100) COMMENT '学校简称', 
	region_code VARCHAR(50) COMMENT '省市区编码', 
	deploy_mode VARCHAR(30) NOT NULL COMMENT 'SAAS/PRIVATE', 
	db_mode VARCHAR(30) NOT NULL COMMENT '一期恒 SHARED（行级隔离）', 
	db_name VARCHAR(100) COMMENT '仅后期私有化预留，一期 NULL', 
	status VARCHAR(50) NOT NULL COMMENT 'PROVISIONING/ACTIVE/SUSPENDED/ARCHIVED', 
	contact_name VARCHAR(100), 
	contact_phone_encrypted VARCHAR(500) COMMENT '敏感：联系人电话密文（§17.2）', 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_tenant_code UNIQUE (tenant_code)
);

CREATE TABLE t_tenant_brand_config (
	tenant_id BIGINT NOT NULL COMMENT '租户ID', 
	platform_name VARCHAR(200) COMMENT '平台名称（顶栏主名称）', 
	platform_subtitle VARCHAR(200), 
	browser_title VARCHAR(200), 
	logo_light_file_id BIGINT, 
	logo_dark_file_id BIGINT, 
	favicon_file_id BIGINT, 
	badge_file_id BIGINT COMMENT '校徽', 
	login_bg_file_id BIGINT, 
	campus_line_file_id BIGINT COMMENT '校园线稿/主楼', 
	primary_color VARCHAR(20) COMMENT '品牌主色，如 #2563EB', 
	secondary_color VARCHAR(20), 
	default_theme VARCHAR(50) COMMENT 'academy_blue/business_blue/eye_green/mono/gray', 
	motto VARCHAR(200) COMMENT '校训', 
	watermark_text VARCHAR(200) COMMENT '页面水印文案', 
	config_json JSON COMMENT '其余可扩展品牌项（PG 落地为 JSONB）', 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_tenant_brand UNIQUE (tenant_id)
);

CREATE TABLE t_tenant_storage_quota (
	total_quota_bytes BIGINT NOT NULL, 
	warning_percent INTEGER NOT NULL, 
	hard_limit_enabled BOOL NOT NULL, 
	module_quota_json JSON, 
	description VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_tenant_storage_quota UNIQUE (tenant_id)
);

CREATE INDEX ix_t_tenant_storage_quota_tenant_id ON t_tenant_storage_quota (tenant_id);

CREATE INDEX ix_tenant_storage_quota_enabled ON t_tenant_storage_quota (tenant_id, hard_limit_enabled, is_deleted);

CREATE TABLE t_unified_message (
	receiver_id BIGINT NOT NULL, 
	source_module VARCHAR(50), 
	source_biz_id BIGINT, 
	title VARCHAR(500) NOT NULL, 
	content VARCHAR(2000), 
	message_type VARCHAR(50) COMMENT 'ANNOUNCEMENT/BUSINESS/REMINDER/EMERGENCY/SYSTEM/TODO_NOTICE', 
	status VARCHAR(50) NOT NULL COMMENT 'UNREAD/READ', 
	read_at DATETIME, 
	remark VARCHAR(500), 
	campaign_id BIGINT, 
	receiver_user_id BIGINT, 
	receiver_type VARCHAR(20) COMMENT 'STUDENT/STAFF/UNKNOWN', 
	receiver_context_key VARCHAR(64) NOT NULL COMMENT 'GLOBAL=个人全局；非空身份键=仅该激活身份可见' DEFAULT 'GLOBAL', 
	priority VARCHAR(20) COMMENT 'NORMAL/IMPORTANT/EMERGENCY', 
	category VARCHAR(30) COMMENT 'ALL/EMERGENCY/ANNOUNCEMENT/BUSINESS/TODO/SYSTEM', 
	delivered_at DATETIME, 
	ack_at DATETIME, 
	require_ack BOOL NOT NULL, 
	action_key VARCHAR(80), 
	action_params_json JSON, 
	expire_at DATETIME, 
	content_version INTEGER NOT NULL, 
	delivery_status VARCHAR(20) COMMENT 'PENDING/DELIVERED/FAILED', 
	rendered_title VARCHAR(500), 
	rendered_content_plain TEXT, 
	sender_org_name_snapshot VARCHAR(200), 
	pinned BOOL NOT NULL, 
	withdrawn_at DATETIME, 
	withdraw_reason VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_msg_campaign_receiver_ctx UNIQUE (tenant_id, campaign_id, receiver_user_id, receiver_context_key)
);

CREATE INDEX ix_msg_tenant_receiver_active_id ON t_unified_message (tenant_id, receiver_id, is_deleted, id);

CREATE INDEX ix_msg_tenant_receiver_unread ON t_unified_message (tenant_id, receiver_id, is_deleted, status);

CREATE INDEX ix_msg_tenant_user_ctx_status_created ON t_unified_message (tenant_id, receiver_user_id, receiver_context_key, status, created_at, id);

CREATE INDEX ix_t_unified_message_campaign_id ON t_unified_message (campaign_id);

CREATE INDEX ix_t_unified_message_receiver_id ON t_unified_message (receiver_id);

CREATE INDEX ix_t_unified_message_receiver_user_id ON t_unified_message (receiver_user_id);

CREATE INDEX ix_t_unified_message_tenant_id ON t_unified_message (tenant_id);

CREATE TABLE t_unified_todo (
	source_module VARCHAR(50) NOT NULL, 
	source_biz_type VARCHAR(100), 
	source_biz_id BIGINT NOT NULL, 
	todo_type VARCHAR(100) NOT NULL, 
	assignee_id BIGINT NOT NULL, 
	student_id BIGINT, 
	title VARCHAR(500) NOT NULL, 
	status VARCHAR(50) NOT NULL COMMENT 'PENDING/DONE/CANCELLED', 
	due_at DATETIME, 
	completed_at DATETIME COMMENT 'TP-W02：真实完成时间；只在 status 变为 DONE 时写，与 updated_at（任何编辑都会动）区分', 
	remark VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_todo_dedup UNIQUE (tenant_id, source_module, source_biz_id, todo_type, assignee_id)
);

CREATE INDEX ix_t_unified_todo_assignee_id ON t_unified_todo (assignee_id);

CREATE INDEX ix_t_unified_todo_student_id ON t_unified_todo (student_id);

CREATE INDEX ix_t_unified_todo_tenant_id ON t_unified_todo (tenant_id);

CREATE INDEX ix_todo_tenant_assignee_status_id ON t_unified_todo (tenant_id, assignee_id, is_deleted, status, id);

CREATE INDEX ix_todo_tenant_student_status_id ON t_unified_todo (tenant_id, student_id, is_deleted, status, id);

CREATE TABLE t_user (
	login_name VARCHAR(100) NOT NULL COMMENT '工号/学号/手机号登录名', 
	real_name VARCHAR(100) NOT NULL, 
	password_hash VARCHAR(200) NOT NULL COMMENT 'bcrypt（TODO P1/P2 接真实口令体系）', 
	user_type VARCHAR(50) NOT NULL COMMENT 'SCHOOL_ADMIN/TEACHER/STUDENT/ENTERPRISE_MENTOR/GUARDIAN/PLATFORM_OP', 
	phone_encrypted VARCHAR(500) COMMENT '敏感：手机号密文', 
	phone_hash VARCHAR(128) COMMENT '手机号不可逆 hash（查重/匹配）', 
	status VARCHAR(50) NOT NULL COMMENT 'ACTIVE/DISABLED/LOCKED', 
	must_change_password BOOL NOT NULL, 
	credential_version BIGINT NOT NULL COMMENT '认证凭据安全版本；改密/绑定/撤销时递增' DEFAULT '0', 
	last_login_at DATETIME, 
	wx_openid VARCHAR(64) COMMENT '微信 openid（legacy 单账号绑定；新绑定以 t_wx_account_binding 为准）', 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_tenant_login UNIQUE (tenant_id, login_name)
);

CREATE INDEX ix_t_user_phone_hash ON t_user (phone_hash);

CREATE INDEX ix_t_user_tenant_id ON t_user (tenant_id);

CREATE INDEX ix_t_user_user_type ON t_user (user_type);

CREATE UNIQUE INDEX ix_t_user_wx_openid ON t_user (wx_openid);

CREATE TABLE t_user_role (
	user_id BIGINT NOT NULL, 
	role_id BIGINT NOT NULL, 
	status VARCHAR(50) NOT NULL, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_user_role UNIQUE (tenant_id, user_id, role_id)
);

CREATE INDEX ix_t_user_role_role_id ON t_user_role (role_id);

CREATE INDEX ix_t_user_role_tenant_id ON t_user_role (tenant_id);

CREATE INDEX ix_t_user_role_user_id ON t_user_role (user_id);

CREATE TABLE t_weekly_report (
	internship_id BIGINT NOT NULL, 
	week_number INTEGER NOT NULL, 
	work_content VARCHAR(2000) COMMENT '本周工作', 
	harvest_content VARCHAR(2000) COMMENT '学习收获', 
	plan_content VARCHAR(2000) COMMENT '下周计划', 
	word_count INTEGER NOT NULL, 
	report_version INTEGER NOT NULL COMMENT '版本号，重交自增', 
	risk_flag VARCHAR(50) COMMENT '内容风险标记', 
	submitted_at DATETIME, 
	status VARCHAR(50) NOT NULL COMMENT 'PENDING_REVIEW/APPROVED/RETURNED/OVERDUE', 
	review_action VARCHAR(50) COMMENT 'APPROVE/RETURN', 
	review_comment VARCHAR(500), 
	reviewed_by_name VARCHAR(100), 
	reviewed_at DATETIME, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_weekly_report_week UNIQUE (tenant_id, internship_id, week_number)
);

CREATE INDEX ix_t_weekly_report_internship_id ON t_weekly_report (internship_id);

CREATE INDEX ix_t_weekly_report_tenant_id ON t_weekly_report (tenant_id);

CREATE TABLE t_workflow_definition (
	workflow_code VARCHAR(100) NOT NULL, 
	workflow_name VARCHAR(200) NOT NULL, 
	source_module VARCHAR(60) NOT NULL, 
	source_biz_type VARCHAR(100) NOT NULL, 
	definition_version VARCHAR(30) NOT NULL, 
	status VARCHAR(30) NOT NULL COMMENT 'PENDING_CONFIRMATION/ENABLED/DISABLED', 
	policy_confirmed BOOL NOT NULL DEFAULT '0', 
	policy_confirmed_by BIGINT, 
	policy_confirmed_at DATETIME, 
	timeout_hours INTEGER NOT NULL, 
	allow_transfer BOOL NOT NULL, 
	allow_reject BOOL NOT NULL, 
	allow_withdraw BOOL NOT NULL, 
	starter_role_codes_json JSON NOT NULL, 
	cc_role_codes_json JSON NOT NULL, 
	policy_snapshot_json JSON NOT NULL, 
	source_profile VARCHAR(50) NOT NULL, 
	installed_project_id BIGINT NOT NULL, 
	description VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_workflow_definition_code UNIQUE (tenant_id, workflow_code)
);

CREATE INDEX ix_t_workflow_definition_installed_project_id ON t_workflow_definition (installed_project_id);

CREATE INDEX ix_t_workflow_definition_status ON t_workflow_definition (status);

CREATE INDEX ix_t_workflow_definition_tenant_id ON t_workflow_definition (tenant_id);

CREATE TABLE t_workflow_instance (
	workflow_code VARCHAR(100) NOT NULL COMMENT '流程编码', 
	source_module VARCHAR(50) NOT NULL COMMENT '来源模块（student/gd/intern/...）', 
	source_biz_type VARCHAR(100) NOT NULL, 
	source_biz_id BIGINT NOT NULL, 
	applicant_id BIGINT NOT NULL COMMENT '申请人 user_id', 
	title VARCHAR(500), 
	status VARCHAR(50) NOT NULL COMMENT 'RUNNING/APPROVED/REJECTED/RETURNED/CANCELLED（TODO 以 11 中心为准）', 
	current_node VARCHAR(100), 
	remark VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_t_workflow_instance_applicant_id ON t_workflow_instance (applicant_id);

CREATE INDEX ix_t_workflow_instance_source_biz_id ON t_workflow_instance (source_biz_id);

CREATE INDEX ix_t_workflow_instance_tenant_id ON t_workflow_instance (tenant_id);

CREATE TABLE t_workflow_node_definition (
	workflow_definition_id BIGINT NOT NULL, 
	node_code VARCHAR(100) NOT NULL, 
	node_name VARCHAR(150) NOT NULL, 
	sequence_no INTEGER NOT NULL, 
	approver_role_code VARCHAR(50) NOT NULL, 
	assignee_strategy VARCHAR(40) NOT NULL, 
	data_scope_code VARCHAR(40) NOT NULL, 
	timeout_hours INTEGER NOT NULL, 
	condition_json JSON NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_workflow_node_definition_code UNIQUE (tenant_id, workflow_definition_id, node_code)
);

CREATE INDEX ix_t_workflow_node_definition_tenant_id ON t_workflow_node_definition (tenant_id);

CREATE INDEX ix_t_workflow_node_definition_workflow_definition_id ON t_workflow_node_definition (workflow_definition_id);

CREATE TABLE t_workflow_task (
	instance_id BIGINT NOT NULL, 
	node_code VARCHAR(100), 
	assignee_id BIGINT NOT NULL COMMENT '审批人 user_id', 
	status VARCHAR(50) NOT NULL COMMENT 'PENDING/APPROVED/REJECTED/TRANSFERRED/CANCELLED', 
	action_reason VARCHAR(500) COMMENT '驳回/退回原因（≥5 字，§1.4）', 
	acted_at DATETIME, 
	deadline_at DATETIME, 
	remark VARCHAR(500), 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_t_workflow_task_assignee_id ON t_workflow_task (assignee_id);

CREATE INDEX ix_t_workflow_task_instance_id ON t_workflow_task (instance_id);

CREATE INDEX ix_t_workflow_task_tenant_id ON t_workflow_task (tenant_id);

CREATE TABLE t_wx_account_binding (
	wx_openid VARCHAR(64) NOT NULL, 
	user_id BIGINT NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	last_used_at DATETIME, 
	id BIGINT NOT NULL AUTO_INCREMENT, 
	tenant_id BIGINT NOT NULL COMMENT '租户(学校)ID，行级隔离', 
	updated_at DATETIME NOT NULL, 
	updated_by BIGINT, 
	is_deleted BOOL NOT NULL COMMENT '逻辑删除', 
	version INTEGER NOT NULL COMMENT '乐观锁', 
	created_at DATETIME NOT NULL, 
	created_by BIGINT, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_wx_openid_tenant UNIQUE (tenant_id, wx_openid)
);

CREATE INDEX ix_t_wx_account_binding_tenant_id ON t_wx_account_binding (tenant_id);

CREATE INDEX ix_t_wx_account_binding_user_id ON t_wx_account_binding (user_id);

CREATE INDEX ix_t_wx_account_binding_wx_openid ON t_wx_account_binding (wx_openid);

CREATE INDEX ix_wx_binding_tenant_user_active ON t_wx_account_binding (tenant_id, user_id, is_deleted, status);
