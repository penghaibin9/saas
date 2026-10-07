"""Pure archive-to-optimizer bridge. Only the authenticated server reader supplies facts.
An explicit planning proposal can choose meeting patterns, not users, counts or clock times.
"""
from collections import defaultdict
from datetime import date, timedelta
from copy import deepcopy
import re
from .contracts import InputError, fingerprint, obj, integer, numeric_id
from .calendar import compile_tasks

ADAPTER_VERSION = 'archive-815d7160-source-v2'
MAX_SOURCE_TASKS = 5000


def iso(value):
    if not isinstance(value, str):
        raise InputError('SOURCE_DATE_REQUIRED', 'ISO date')
    try:
        return date.fromisoformat(value[:10])
    except (ValueError, TypeError) as exc:
        raise InputError('SOURCE_DATE_INVALID', str(value)[:20]) from exc


def clock(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-2][0-9]:[0-5][0-9]', value):
        raise InputError('SOURCE_CLOCK_INVALID', str(value)[:20])
    hour, minute = map(int, value.split(':'))
    if hour > 23:
        raise InputError('SOURCE_CLOCK_INVALID', value)
    return hour * 60 + minute


def source_revision(facts):
    # The reader emits only bounded, non-secret source fields in a stable order.
    return fingerprint(facts)


def cohorts(rosters):
    """Compress identical student membership signatures; never use admin-class guesses."""
    memberships = defaultdict(set)
    for task_id, roster in rosters.items():
        members = roster.get('studentIds')
        if roster.get('ready') is not True or not roster.get('rosterVersionId') or not members:
            raise InputError('FORMAL_ROSTER_REQUIRED', task_id)
        if len(set(members)) != len(members):
            raise InputError('DUPLICATE_ROSTER_MEMBER', task_id)
        for student in members:
            memberships[numeric_id(str(student), 'studentId')].add(str(task_id))
    groups = defaultdict(list)
    for student, task_ids in memberships.items():
        groups[tuple(sorted(task_ids))].append(student)
    result = defaultdict(list)
    for task_ids, students in sorted(groups.items()):
        cohort = 'cohort:' + fingerprint(sorted(students))[:24]
        for task_id in task_ids:
            result[task_id].append(cohort)
    return dict(result)


def compile_source(facts, plan, *, expected_revision):
    if source_revision(facts) != expected_revision:
        raise InputError('SOURCE_VERSION_CONFLICT', 'Reload current input before confirming')
    obj(plan, {'version','week1Monday','slotBlocks','taskPatterns','minDayGap','travelMinutes','defaultCampus','replaceAuto','taskParities'},
        {'version','week1Monday','slotBlocks','taskPatterns','defaultCampus'}, 'plan')
    if type(plan['version']) is not int or plan['version'] != 1:
        raise InputError('PLAN_VERSION_UNSUPPORTED', 'version')
    if 'replaceAuto' in plan and type(plan['replaceAuto']) is not bool:
        raise InputError('REPLACE_MODE_INVALID','replaceAuto')
    parities=plan.get('taskParities',{})
    if not isinstance(parities,dict) or any(v not in {'ALL','ODD','EVEN'} for v in parities.values()):
        raise InputError('WEEK_PARITY_INVALID','taskParities')
    if not isinstance(plan['taskPatterns'], dict) or not isinstance(plan['slotBlocks'], dict):
        raise InputError('PLAN_OBJECT_REQUIRED', 'taskPatterns/slotBlocks')
    if not isinstance(plan['defaultCampus'],str) or not plan['defaultCampus'].strip() or len(plan['defaultCampus'])>100:
        raise InputError('CAMPUS_REQUIRED','Explicit default campus')
    if not isinstance(plan.get('minDayGap',{}),dict):raise InputError('PLAN_OBJECT_REQUIRED','minDayGap')
    for task_id,value in plan.get('minDayGap',{}).items():
        integer(value,0,6,'minDayGap')
    anchor = iso(plan['week1Monday'])
    term = facts['term']; first = iso(term['start_date']); last = iso(term['end_date'])
    if anchor.weekday() != 0 or not anchor <= first < anchor + timedelta(days=7):
        raise InputError('CALENDAR_ANCHOR_INVALID', 'Explicit week-one Monday must contain term start')
    weeks = integer(term['teaching_weeks'], 1, 30, 'teachingWeeks')
    tasks = facts['tasks']
    if not tasks or len(tasks) > MAX_SOURCE_TASKS:
        raise InputError('SOURCE_TASK_LIMIT', str(len(tasks)))
    by_id = {str(t['id']): t for t in tasks}
    if len(by_id) != len(tasks):
        raise InputError('DUPLICATE_SOURCE_TASK', 'tasks')
    roster_groups = cohorts(facts['rosters'])
    targets=[by_id[str(tid)] for tid in facts['targetTaskIds']]
    target_teachers={teacher for task in targets for teacher in facts['teachers'][str(task['id'])]}
    target_learners={group for task in targets for group in roster_groups[str(task['id'])]}
    params = facts['params']
    if any(params.get(k) is not True for k in ['capacityCheck','roomTypeMatch','respectAvail']):
        raise InputError('HARD_RULE_DISABLED', 'Enable existing capacity/type/availability safeguards')
    room_map = {}; rooms = []
    for row in facts['rooms']:
        if row.get('status') != 'AVAILABLE' or row.get('allow_schedule') is not True:
            continue
        if row.get('is_exclusive'):
            continue  # Dedicated rooms require an existing separately approved allocation.
        rid = str(row['id']); campus = row.get('campus_code') or plan['defaultCampus']
        if not isinstance(campus, str) or not campus.strip():
            raise InputError('CAMPUS_REQUIRED', rid)
        room_map[rid] = row
        rooms.append({'id':rid,'campus':campus,'kind':row['room_type'],
                      'capacity':row['capacity'],'features':[],'available':True})
    if not rooms:
        raise InputError('NO_SCHEDULABLE_ROOMS', 'room dictionary')
    reachable_rooms={room['id'] for room in rooms if any(not task.get('required_room_type')
        or task['required_room_type']==room['kind'] for task in targets)}
    campuses = sorted({r['campus'] for r in rooms})
    swaps = {}; holidays = set(); projection_warnings = []
    for event in facts['events']:
        kind = event['event_type']; start = iso(event['start_date']); end = iso(event['end_date'])
        if end < start or (end-start).days > 366:
            raise InputError('CALENDAR_EVENT_RANGE', str(event['id']))
        if kind == 'SWAP':
            if start != end or not event.get('swap_to_date') or start in swaps:
                raise InputError('SWAP_MAPPING_AMBIGUOUS', str(event['id']))
            swaps[start] = iso(event['swap_to_date'])
            projection_warnings.append('DATE_PROJECTION_REQUIRES_FOUR_END_VERIFICATION')
        elif kind == 'HOLIDAY':
            holidays.update(start + timedelta(days=i) for i in range((end-start).days+1))
            projection_warnings.append('DATE_PROJECTION_REQUIRES_FOUR_END_VERIFICATION')
        # Canonical occurrence owner only moves/stops HOLIDAY and SWAP. EXAM and
        # INTERNSHIP are calendar labels, not school-wide stop commands.
        elif kind not in {'TEACHING','EXAM','INTERNSHIP'}:
            raise InputError('SPECIAL_CALENDAR_ADAPTER_REQUIRED', str(event['id'])+':'+kind)
    if len(set(swaps.values()))!=len(swaps) or set(swaps.values()) & (set(swaps)|holidays):
        raise InputError('SWAP_MAPPING_AMBIGUOUS','调休补课日期与其他校历事实冲突')
    calendar = []; full = {}; used_dates = set()
    for campus in campuses:
        exact = [s for s in facts['slots'] if s.get('campus_code') == campus]
        slots = exact or [s for s in facts['slots'] if not s.get('campus_code')]
        slots = [s for s in slots if s.get('enabled') is True and s.get('status') == 'ENABLED']
        if not slots or len({s['slot_no'] for s in slots}) != len(slots):
            raise InputError('SLOT_SCOPE_AMBIGUOUS', campus)
        approved_blocks = plan['slotBlocks'].get(campus)
        if not isinstance(approved_blocks, dict):
            raise InputError('SLOT_BLOCK_CONFIRMATION_REQUIRED', campus)
        prepared = []
        for slot in slots:
            no = slot['slot_no']; block = approved_blocks.get(str(no))
            if not isinstance(block, str) or not block:
                raise InputError('SLOT_BLOCK_REQUIRED', campus+':'+str(no))
            prepared.append({'no':no,'start':clock(slot['start_time']),
                             'end':clock(slot['end_time']),'block':block})
        for week in range(1,weeks+1):
            for wd in range(1,8):
                # Same week numbering as the canonical occurrence consumer: term start + 7-day windows.
                teaching_day = first + timedelta(weeks=week-1,days=(wd-first.isoweekday())%7)
                if not first <= teaching_day <= last:
                    continue
                if teaching_day in swaps.values():
                    continue  # The target date consumes the source day's curriculum only.
                actual = swaps.get(teaching_day, teaching_day)
                if teaching_day in holidays and teaching_day not in swaps:
                    continue
                if not first <= actual <= last:
                    raise InputError('SWAP_OUTSIDE_TERM', actual.isoformat())
                # Non-teaching weekends only become real occurrences through SWAP.
                signature = campus,actual
                if signature in used_dates:
                    raise InputError('DUPLICATE_ACTUAL_TEACHING_DAY', campus+':'+actual.isoformat())
                used_dates.add(signature)
                day_slots=[]
                for slot, base_slot in zip(slots,prepared):
                    bands=[b for b in facts.get('timeBands',[]) if str(b['slot_id'])==str(slot['id'])
                           and (not b.get('campus_code') or b['campus_code']==campus)
                           and (not b.get('effective_start') or iso(b['effective_start'])<=actual)
                           and (not b.get('effective_end') or actual<=iso(b['effective_end']))]
                    exact_bands=[b for b in bands if b.get('campus_code')==campus]
                    bands=exact_bands or bands
                    if len(bands)>1:raise InputError('SLOT_SCOPE_AMBIGUOUS',campus+':'+str(slot['slot_no']))
                    day_slots.append({**base_slot,'start':clock(bands[0]['start_time']),
                                      'end':clock(bands[0]['end_time'])} if bands else base_slot)
                full[campus,week,wd] = {'date':actual.isoformat(),'slots':day_slots}
                if wd not in params['weekdays']:
                    continue
                forbidden = {f.get('slotNo') for f in params['forbidden'] if f['weekday']==wd}
                filtered = [s for s in day_slots if s['no'] in params['slots'] and None not in forbidden and s['no'] not in forbidden]
                calendar.append({'campus':campus,'weekKey':f'W{week:02}',
                                 'teachingWeekday':wd,'date':actual.isoformat(),'slots':filtered})
    own_count = defaultdict(int); occupied = []
    room_info = {r['id']:r for r in rooms}
    for item in facts['existingItems']:
        if plan.get('replaceAuto') is True and str(item['batch_id'])==str(facts['scope']['batchId']) and item.get('source')=='AUTO':
            continue
        tid = str(item.get('task_id') or '')
        if tid not in by_id or tid not in roster_groups:
            raise InputError('EXISTING_TASK_ROSTER_UNRESOLVED', str(item['id']))
        rid = str(item.get('classroom_id') or '')
        if rid not in room_info:
            raise InputError('EXISTING_ROOM_UNRESOLVED', str(item['id']))
        if str(item['batch_id']) == str(facts['scope']['batchId']):
            task = by_id[tid]
            if item['week_parity'] != parities.get(tid,'ALL') or item['start_week'] != task['start_week'] or item['end_week'] != task['end_week']:
                raise InputError('PARTIAL_WEEK_REPAIR_ADAPTER_REQUIRED', str(item['id']))
            own_count[tid] += 1
        # Keep every resource the candidate could share. Existing conflicts between
        # unrelated courses/rooms belong to the existing conflict ledger, not this job.
        if rid not in reachable_rooms and not target_teachers.intersection(facts['teachers'][tid]) and not target_learners.intersection(roster_groups[tid]):
            continue
        occurrences = []
        for week in range(item['start_week'],item['end_week']+1):
            if item['week_parity']=='ODD' and week%2==0 or item['week_parity']=='EVEN' and week%2==1:
                continue
            d = full.get((room_info[rid]['campus'],week,item['weekday']))
            if d is None:
                continue  # Canonical holidays have no occurrence; never invent a lesson on that date.
            slot = next((s for s in d['slots'] if s['no']==item['slot_no']),None) if d else None
            if not slot:
                raise InputError('EXISTING_CALENDAR_UNRESOLVED', str(item['id']))
            occurrences.append({'key':f'W{week:02}','date':d['date'],'start':slot['start'],'end':slot['end'],'periods':1})
        teachers = facts['teachers'][tid]
        occupied.append({'id':'item:'+str(item['id']),'kind':'LESSON','roomId':rid,
                         'actors':['teacher:'+t for t in teachers]+['learner:'+x for x in roster_groups[tid]],
                         'campus':room_info[rid]['campus'],'occurrences':occurrences})
    target_ids = set(str(v) for v in facts['targetTaskIds'])
    pending = {tid for tid in target_ids if by_id[tid]['weekly_hours'] > own_count[tid]}
    if set(plan['taskPatterns']) != pending:
        raise InputError('TASK_PLAN_SET_CHANGED', 'The confirmed plan must cover exactly the remaining tasks')
    if set(plan.get('minDayGap',{}))-pending:
        raise InputError('UNKNOWN_TASK_GAP','Gap refers to a task outside the confirmed plan')
    if set(parities)-pending:
        raise InputError('UNKNOWN_TASK_PARITY','Parity refers to a task outside the confirmed plan')
    plans = []; limits = {}
    for tid in sorted(pending):
        task=by_id[tid]; pattern=plan['taskPatterns'][tid]
        start=integer(task['start_week'],1,weeks,'startWeek');end=integer(task['end_week'],start,weeks,'endWeek')
        count=integer(task['expected_students'],1,100000,'headcount')
        members=facts['rosters'][tid]['studentIds']
        if count < len(members):raise InputError('HEADCOUNT_BELOW_ROSTER',tid)
        selected_weeks=[w for w in range(start,end+1) if parities.get(tid,'ALL')=='ALL'
                        or (w%2==1 if parities[tid]=='ODD' else w%2==0)]
        if not selected_weeks or task['total_hours'] != task['weekly_hours']*len(selected_weeks):
            raise InputError('SEGMENTED_ACTIVITY_PLAN_REQUIRED',tid)
        if not isinstance(pattern,list) or not pattern or any(type(p) is not int or not 1<=p<=12 for p in pattern):
            raise InputError('MEETING_PATTERN_INVALID',tid)
        if sum(pattern) != task['weekly_hours']-own_count[tid]:
            raise InputError('PATTERN_PERIODS_MISMATCH',tid)
        teachers=facts['teachers'][tid]
        if len(teachers)>1 or task.get('formation_mode') not in {'ADMIN_FIXED','MERGED'}:
            projection_warnings.append('COMPLEX_FORMATION_FOUR_END_PROJECTION_NOT_VERIFIED')
        plans.append({'taskId':tid,'teachers':teachers,'learners':roster_groups[tid],
            'headcount':count,'weeks':[f'W{w:02}' for w in selected_weeks],
            'meetingPattern':pattern,'plannedPeriods':sum(pattern)*len(selected_weeks),
            'roomKind':task.get('required_room_type') or '', 'weekdays':params['weekdays'],
            'minDayGap':plan.get('minDayGap',{}).get(tid,0)})
        for teacher in teachers:limits['teacher:'+teacher]=params['teacherMaxPerDay']
        for group in roster_groups[tid]:limits['learner:'+group]=params['classMaxPerDay']
    for row in facts['bookings']:
        booking_day=iso(row['booking_date'])
        if not first<=booking_day<=last:continue
        # Match the canonical booking guard: an approved lab booking with no frozen
        # classroom blocks this slot in every room, rather than guessing a room.
        room_ids=[str(row['classroom_id'])] if row['classroom_id'] is not None else sorted(room_info)
        for rid in room_ids:
            if rid not in reachable_rooms:continue
            day=booking_day.isoformat();campus=room_info[rid]['campus']
            candidates=[s for (c,_,_),d in full.items() for s in d['slots'] if c==campus and d['date']==day and s['no']==row['slot_no']]
            distinct={(s['start'],s['end']) for s in candidates}
            if not distinct and (booking_day in holidays or booking_day in swaps):continue
            if len(distinct)!=1:raise InputError('BOOKING_CLOCK_UNRESOLVED',str(row['id']))
            start,end=next(iter(distinct))
            occupied.append({'id':'booking:'+str(row['id'])+':'+rid,'kind':'BLOCKED','actors':[], 'roomId':rid,'campus':campus,
                             'occurrences':[{'key':'booking','date':day,'start':start,'end':end,'periods':1}]})
    for row in facts['availability']:
        for campus in campuses:
            occurrences=[]
            for week in range(1,weeks+1):
                d=full.get((campus,week,row['weekday']))
                slot=next((s for s in d['slots'] if s['no']==row['slot_no']),None) if d else None
                if slot:occurrences.append({'key':f'W{week:02}','date':d['date'],'start':slot['start'],'end':slot['end'],'periods':1})
            if occurrences:occupied.append({'id':'unavailable:'+str(row['id'])+':'+campus,'kind':'BLOCKED',
                'actors':['teacher:'+row['teacher_key']],'campus':campus,'occurrences':occurrences})
    scope={**facts['scope'],'revision':expected_revision}
    snapshot,binding=compile_tasks(scope=scope,tasks=plans,rooms=rooms,calendar=calendar,
        occupied=occupied,travel_minutes=plan.get('travelMinutes',[]),daily_limits=limits)
    for placement in binding['bindings'].values():
        task=by_id[placement['taskId']]; room=room_map[placement['roomId']]
        placement.update({'courseName':task.get('course_name') or '',
            'teachingClassId':facts['rosters'][str(task['id'])]['teachingClassId'],
            'teacherLabels':{row['teacher_key']:row.get('teacher_name') or row['teacher_key'] for row in facts.get('teacherRows',[]) if row['teacher_key'] in facts['teachers'][str(task['id'])]},
            'teacherName':task.get('teacher_name') or '', 'className':task.get('teaching_class_name') or '',
            'classroomText':room.get('room_name') or str(room.get('building_name',''))+str(room.get('room_code','')),
            'campus':room.get('campus_code') or plan['defaultCampus']})
    binding.update({'adapterVersion':ADAPTER_VERSION,'sourceRevision':expected_revision,
        'plan':deepcopy(plan),'projectionWarnings':sorted(set(projection_warnings)),
        'formalApplySupported':False,'previewOnly':True})
    from .contracts import Snapshot
    provenance={key:binding[key] for key in ('adapterVersion','sourceRevision','plan','bindings','projectionWarnings','formalApplySupported','previewOnly')}
    return Snapshot.parse({**snapshot.raw,'provenance':provenance}),binding
