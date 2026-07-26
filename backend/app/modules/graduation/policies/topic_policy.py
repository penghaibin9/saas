from .base import authorize_student_action


def authorize_assignment(db, student):
    return authorize_student_action(
        db, student, action="topic.assign", permission_code="graduationDesign.topic.assign",
        allowed_batch_states=("DRAFT", "ACTIVE", "IN_PROGRESS"),
    )
