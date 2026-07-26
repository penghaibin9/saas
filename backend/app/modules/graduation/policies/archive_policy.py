from .base import authorize_student_action


def authorize(db, student, action="view"):
    return authorize_student_action(
        db, student, action=f"archive.{action}", permission_code=f"graduationDesign.archive.{action}",
    )
