"""选课域历史兼容入口。

正式批次、课程、学生选退课、名单锁定和人工调整已收口到
``academic_affairs_selection_service``。本文件仅保留旧导入路径，不再修改 core Service。
"""
from __future__ import annotations

from . import academic_affairs_selection_service as _canonical

_legacy = _canonical

create_batch = _canonical.create_batch
publish_batch = _canonical.publish_batch
open_batch = _canonical.open_batch
close_batch = _canonical.close_batch
save_rule = _canonical.save_rule
add_course = _canonical.add_course
update_course = _canonical.update_course
cancel_course = _canonical.cancel_course
student_courses = _canonical.student_courses
student_enroll = _canonical.student_enroll
student_drop = _canonical.student_drop
my_selections = _canonical.my_selections
student_reselect_guide = _canonical.student_reselect_guide
lock_batch = _canonical.lock_batch
adjust_record = _canonical.adjust_record
archive_batch = _canonical.archive_batch
run_time_tick = _canonical.run_time_tick


def __getattr__(name):
    return getattr(_canonical, name)
