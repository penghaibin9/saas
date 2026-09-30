"""Compile approved meeting patterns against explicit school calendar occurrences.
No assumed Monday, 18-week semester, generic eight slots or omitted holiday lessons.
"""
from __future__ import annotations
from .contracts import InputError, Snapshot, obj, integer, numeric_id, text, strings

def compile_tasks(*,scope,tasks,rooms,calendar,occupied=(),travel_minutes=(),daily_limits=None):
    index={}; candidates_seen=set()
    for day in calendar:
        obj(day,{"campus","weekKey","teachingWeekday","date","slots"},
            {"campus","weekKey","teachingWeekday","date","slots"},"calendarDay")
        key=(text(day['campus'],'campus'),text(day['weekKey'],'weekKey'),integer(day['teachingWeekday'],1,7,'weekday'))
        if key in index:raise InputError('DUPLICATE_CALENDAR_OCCURRENCE',str(key))
        if not isinstance(day['slots'],list):raise InputError('ARRAY_REQUIRED','calendar.slots')
        slots=[]
        for slot in day['slots']:
            obj(slot,{'no','start','end','block'},{'no','start','end','block'},'calendar.slot')
            no=integer(slot['no'],1,48,'slot.no');start=integer(slot['start'],0,1439,'slot.start');end=integer(slot['end'],1,1440,'slot.end')
            if start>=end:raise InputError('INVALID_INTERVAL','calendar.slot')
            slots.append({'no':no,'start':start,'end':end,'block':text(slot['block'],'slot.block')})
        slots.sort(key=lambda x:x['start'])
        if len({x['no'] for x in slots})!=len(slots) or any(a['end']>b['start'] for a,b in zip(slots,slots[1:])):
            raise InputError('INVALID_TIMETABLE_SLOTS',str(key))
        index[key]={**day,'slots':slots}
    activities=[];relations=[];bindings={};diagnostics=[]; task_ids=set()
    for task in tasks:
        obj(task,{'taskId','teachers','learners','headcount','weeks','meetingPattern','plannedPeriods','roomKind','features','weekdays','minDayGap','lockedChoices','baselineChoices'},
            {'taskId','teachers','learners','headcount','weeks','meetingPattern','plannedPeriods'},'taskPlan')
        tid=numeric_id(task['taskId'],'taskId')
        if tid in task_ids:raise InputError('DUPLICATE_TASK_PLAN',tid)
        task_ids.add(tid)
        weeks=strings(task['weeks'],'weeks',True)
        pattern=task['meetingPattern']
        if not isinstance(pattern,list) or not pattern:raise InputError('MEETING_PATTERN_REQUIRED',tid)
        pattern=[integer(n,1,12,'pattern.periods') for n in pattern]
        if integer(task['plannedPeriods'],1,10000,'plannedPeriods')!=len(weeks)*sum(pattern):
            raise InputError('TOTAL_PERIODS_MISMATCH',tid)
        weekdays=task.get('weekdays',[1,2,3,4,5])
        if not isinstance(weekdays,list) or not weekdays or len(set(weekdays))!=len(weekdays):raise InputError('INVALID_WEEKDAYS',tid)
        weekdays=sorted(integer(w,1,7,'weekday') for w in weekdays)
        gap=integer(task.get('minDayGap',0),0,6,'minDayGap')
        segment_ids=[]
        for part,periods in enumerate(pattern,1):
            aid=f'{tid}:meeting:{part}';segment_ids.append(aid);options=[]
            for room in sorted(rooms,key=lambda r:r['id']):
                for wd in weekdays:
                    # Candidate start slot must exist on every requested week, on this campus.
                    days=[index.get((room['campus'],wk,wd)) for wk in weeks]
                    if any(d is None for d in days):continue
                    for first in days[0]['slots']:
                        occurrences=[];slotnos=None
                        for wk,day in zip(weeks,days):
                            ordered=day['slots'];positions=[i for i,s in enumerate(ordered) if s['no']==first['no']]
                            if not positions:break
                            block=ordered[positions[0]:positions[0]+periods]
                            if len(block)!=periods or len({s['block'] for s in block})!=1:break
                            if any(b['no'] != a['no'] + 1 for a,b in zip(block,block[1:])):break
                            if slotnos is not None and slotnos!=[s['no'] for s in block]:break
                            slotnos=[s['no'] for s in block]
                            occurrences.append({'key':wk,'date':day['date'],'start':block[0]['start'],'end':block[-1]['end'],'periods':periods})
                        if len(occurrences)!=len(weeks):continue
                        oid=f'd{wd}:s{first["no"]}:r{room["id"]}'
                        options.append({'id':oid,'roomId':room['id'],'occurrences':occurrences,'cost':0})
                        bindings[aid+'|'+oid]={'taskId':tid,'weekday':wd,'slotNos':slotnos,'roomId':room['id'],'weekKeys':list(weeks)}
            if not options:diagnostics.append({'code':'NO_CALENDAR_CANDIDATE','taskId':tid,'activityId':aid,
                'message':'No recurring block exists for all required occurrences; no lesson was silently omitted.'})
            activities.append({'id':aid,'taskId':tid,'teachers':task['teachers'],'learners':task['learners'],
                'headcount':task['headcount'],'roomKind':task.get('roomKind',''),'features':task.get('features',[]),
                'requiredOccurrences':list(weeks),'periods':periods,'options':options,
                'lockedOptionId':task.get('lockedChoices',{}).get(str(part)),
                'baselineOptionId':task.get('baselineChoices',{}).get(str(part))})
        if gap:
            for i,a in enumerate(segment_ids):
                for b in segment_ids[i+1:]:relations.append({'left':a,'right':b,'kind':'MIN_DAY_GAP','value':gap})
    raw={'contractVersion':1,'scope':scope,'rooms':rooms,'activities':activities,'occupied':list(occupied),
        'travelMinutes':list(travel_minutes),'dailyLimits':daily_limits or {},'relations':relations,'domainComplete':True}
    return Snapshot.parse(raw), {'bindings':bindings,'diagnostics':diagnostics,
        'domainStatement':'Complete only for the approved recurring same-weekday/same-room meeting patterns supplied to this compiler.'}
