from .base import authorize_student_action


def authorize(db, student, action="manage"):
    code = "graduationDesign.student.view" if action == "view" else "graduationDesign.student.manage"
    return authorize_student_action(db, student, action=f"student.{action}", permission_code=code)
