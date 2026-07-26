from .base import authorize_student_action


def authorize(db, student, action="view"):
    return authorize_student_action(
        db, student, action=f"risk.{action}", permission_code=f"graduationDesign.risk.{action}",
    )
