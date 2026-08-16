from pathlib import Path

p = Path("backend/app/modules/academic_affairs/services/academic_affairs_task_generation_service.py")
text = p.read_text()
old = '''                for program_course in courses:\n                    formation_mode = formation_policy.normalize_direct_mode(program_course.formation_mode)\n                    try:\n                        open_term_no = int(program_course.open_term_no)\n                    except (TypeError, ValueError):\n                        unresolved_program_courses += 1\n                        continue\n                    if open_term_no != current_semester:\n                        out_of_term_courses += 1\n                        continue\n                    if not program_course.course_id:\n'''
new = '''                for program_course in courses:\n                    try:\n                        open_term_no = int(program_course.open_term_no)\n                    except (TypeError, ValueError):\n                        unresolved_program_courses += 1\n                        continue\n                    if open_term_no != current_semester:\n                        out_of_term_courses += 1\n                        continue\n                    formation_mode = formation_policy.normalize_direct_mode(program_course.formation_mode)\n                    if not program_course.course_id:\n'''
if text.count(old) != 1:
    raise SystemExit(f"generation scope refinement guard failed: count={text.count(old)}")
p.write_text(text.replace(old, new))
