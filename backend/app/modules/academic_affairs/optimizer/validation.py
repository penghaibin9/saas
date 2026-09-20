"""One explicit constraint vocabulary, with an independent result traversal."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from .contracts import Activity, Option, Snapshot

@dataclass(frozen=True)
class Violation:
    code: str
    activities: tuple[str,...]
    detail: str
    def as_dict(self):
        return {"code":self.code,"activities":list(self.activities),"detail":self.detail}

def room_map(snapshot): return {r.id:r for r in snapshot.rooms}
def travel_map(snapshot): return {(a,b):m for a,b,m in snapshot.travel}

def interval_conflict(x,y,campus_x,campus_y,shared_actor,shared_room,travel):
    if x.day!=y.day: return None
    if x.start<y.end and y.start<x.end:
        return "ROOM_OVERLAP" if shared_room else "PERSON_OVERLAP" if shared_actor else None
    if shared_actor and campus_x!=campus_y:
        left,right=(x,y) if x.end<=y.start else (y,x)
        a,b=(campus_x,campus_y) if left is x else (campus_y,campus_x)
        needed=travel.get((a,b))
        if needed is None: return "TRAVEL_TIME_UNKNOWN"
        if right.start-left.end < needed: return "TRAVEL_TIME_SHORT"
    return None

def basic_violations(snapshot:Snapshot,activity:Activity,option:Option):
    room=room_map(snapshot)[option.room]; out=[]
    for bad,code in [(not room.available,"ROOM_UNAVAILABLE"),(room.capacity<activity.headcount,"CAPACITY"),
                     (bool(activity.room_kind) and room.kind!=activity.room_kind,"ROOM_TYPE"),
                     (not set(activity.features).issubset(room.features),"ROOM_FEATURE"),
                     (activity.locked is not None and activity.locked!=option.id,"LOCKED")]:
        if bad:out.append(Violation(code,(activity.id,),option.id))
    travel=travel_map(snapshot)
    for fixed in snapshot.occupied:
        shared_actor=bool(set(activity.actors)&set(fixed.actors));shared_room=option.room==fixed.room
        if not shared_actor and not shared_room:continue
        for x in option.occurrences:
            for y in fixed.occurrences:
                destination = fixed.campus if fixed.kind == "LESSON" else room.campus
                code=interval_conflict(x,y,room.campus,destination,shared_actor,shared_room,travel)
                if code:out.append(Violation(code,(activity.id,),fixed.id+":"+x.day))
    return out

def pair_violations(snapshot,left,lo,right,ro):
    out=[];rooms=room_map(snapshot);travel=travel_map(snapshot)
    shared_actor=bool(set(left.actors)&set(right.actors));shared_room=lo.room==ro.room
    if shared_actor or shared_room:
        for x in lo.occurrences:
            for y in ro.occurrences:
                code=interval_conflict(x,y,rooms[lo.room].campus,rooms[ro.room].campus,shared_actor,shared_room,travel)
                if code:out.append(Violation(code,(left.id,right.id),x.day))
    for relation in snapshot.relations:
        if {relation.left,relation.right}!={left.id,right.id}:continue
        a,b=(lo,ro) if relation.left==left.id else (ro,lo)
        aa={x.key:x for x in a.occurrences};bb={x.key:x for x in b.occurrences}
        if set(aa)!=set(bb):
            out.append(Violation("RELATION_OCCURRENCE_KEYS",(left.id,right.id),relation.kind));continue
        for key,x in aa.items():
            y=bb[key]
            if relation.kind=="MIN_DAY_GAP":
                bad=abs(x.absolute_start//1440-y.absolute_start//1440)<relation.value
            elif relation.kind=="BEFORE":bad=x.absolute_end+relation.value>y.absolute_start
            else:bad=x.absolute_start!=y.absolute_start
            if bad:out.append(Violation(relation.kind,(left.id,right.id),key))
    return out

def daily_counts(snapshot,selected):
    counts=defaultdict(int)
    for fixed in snapshot.occupied:
        if fixed.kind != "LESSON": continue
        for o in fixed.occurrences:
            for actor in fixed.actors:counts[(actor,o.day)]+=o.periods
    acts={a.id:a for a in snapshot.activities}
    for aid,option in selected.items():
        for o in option.occurrences:
            for actor in acts[aid].actors:counts[(actor,o.day)]+=o.periods
    return counts

def validate_solution(snapshot:Snapshot,choices:dict[str,str],*,require_complete=True):
    if not isinstance(choices,dict):return [Violation("CHOICES_REQUIRED",(),"object expected")]
    acts={a.id:a for a in snapshot.activities};out=list(fixed_violations(snapshot));selected={}
    for aid,oid in choices.items():
        if aid not in acts:
            out.append(Violation("UNKNOWN_ACTIVITY",(str(aid),),str(oid)));continue
        option=next((o for o in acts[aid].options if o.id==oid),None)
        if option is None:
            out.append(Violation("UNKNOWN_OPTION",(aid,),str(oid)));continue
        selected[aid]=option;out.extend(basic_violations(snapshot,acts[aid],option))
    if require_complete:
        for aid in sorted(set(acts)-set(selected)):out.append(Violation("MISSING_ACTIVITY",(aid,),"required"))
    # Deliberately does NOT reuse the solver's precompiled incompatibility graph.
    for aid,bid in related_pairs(snapshot,selected):
        out.extend(pair_violations(snapshot,acts[aid],selected[aid],acts[bid],selected[bid]))
    for (actor,day),count in daily_counts(snapshot,selected).items():
        limit=dict(snapshot.daily_limits).get(actor)
        if limit is not None and count>limit:
            out.append(Violation("DAILY_LIMIT",(),f"{actor}:{day}:{count}>{limit}"))
    return out

def quality(snapshot:Snapshot,choices):
    acts={a.id:a for a in snapshot.activities};rooms=room_map(snapshot)
    chosen={aid:next(o for o in acts[aid].options if o.id==oid) for aid,oid in choices.items()}
    lines=defaultdict(list);changes=0;cost=0;waste=0;periods=0
    for fixed in snapshot.occupied:
        if fixed.kind != "LESSON": continue
        for occ in fixed.occurrences:
            for actor in fixed.actors: lines[actor,occ.day].append((occ.start,occ.end,fixed.campus))
    for aid,o in chosen.items():
        a=acts[aid];changes+=int(a.baseline is not None and o.id!=a.baseline);cost+=o.cost
        for occ in o.occurrences:
            periods+=occ.periods;waste+=(rooms[o.room].capacity-a.headcount)*occ.periods
            for actor in a.actors:lines[(actor,occ.day)].append((occ.start,occ.end,rooms[o.room].campus))
    gaps={"teacher":0,"learner":0};moves=0;worst_gap=0
    for (actor,_),intervals in lines.items():
        intervals.sort();total=0
        for a,b in zip(intervals,intervals[1:]):
            total+=max(0,b[0]-a[1]);moves+=int(a[2]!=b[2])
        gaps[actor.split(':',1)[0]]+=total;worst_gap=max(worst_gap,total)
    return {"assignedActivities":len(chosen),"requiredActivities":len(acts),"scheduledPeriods":periods,
        "usedRoomCount":len({o.room for o in chosen.values()}),
        "assignedCourses":len({acts[aid].task_id for aid in chosen}),
        "requiredCourses":len({a.task_id for a in acts.values()}),
        "changedActivities":changes,"preferenceCost":cost,"unusedSeatPeriods":waste,
        "teacherGapMinutes":gaps['teacher'],"learnerGroupGapMinutes":gaps['learner'],
        "maxActorDayGapMinutes":worst_gap,"actorCampusTransitions":moves,
        "metricsNote":"Gap diagnostics include breaks, selected activities and fixed LESSON occupancies; BLOCKED periods are not lessons; learner actors are not weighted student counts."}

def fixed_violations(snapshot):
    """Validate existing lessons too; overlapping unavailability declarations are legal."""
    buckets = defaultdict(list)
    out = []
    for fixed in snapshot.occupied:
        for occurrence in fixed.occurrences:
            resources = list(fixed.actors) + (['room:' + fixed.room] if fixed.room else [])
            for resource in resources:
                buckets[resource, occurrence.day].append((fixed, occurrence))
    seen = set()
    travel = travel_map(snapshot)
    for entries in buckets.values():
        for (left, x), (right, y) in combinations(entries, 2):
            signature = tuple(sorted(((left.id, x.key), (right.id, y.key))))
            if signature in seen:
                continue
            seen.add(signature)
            if left.kind == right.kind == 'BLOCKED':
                continue
            shared_actor = bool(set(left.actors) & set(right.actors))
            shared_room = bool(left.room and left.room == right.room)
            cx, cy = left.campus, right.campus
            if 'BLOCKED' in (left.kind, right.kind):
                cy = cx  # Unavailability is not a real physical journey.
            code = interval_conflict(x, y, cx, cy, shared_actor, shared_room, travel)
            if code:
                out.append(Violation('FIXED_' + code, (), left.id + '/' + right.id + ':' + x.day))
    for (actor, day), count in daily_counts(snapshot, {}).items():
        limit = dict(snapshot.daily_limits).get(actor)
        if limit is not None and count > limit:
            out.append(Violation('FIXED_DAILY_LIMIT', (), f'{actor}:{day}'))
    return out


def related_pairs(snapshot, selected):
    """Independent resource/date index; not the solver's incompatibility graph."""
    activities = {a.id: a for a in snapshot.activities}
    buckets = defaultdict(set)
    for aid, option in selected.items():
        resources = list(activities[aid].actors) + ['room:' + option.room]
        for day in {o.day for o in option.occurrences}:
            for resource in resources:
                buckets[resource, day].add(aid)
    pairs = set()
    for identifiers in buckets.values():
        pairs.update(combinations(sorted(identifiers), 2))
    pairs.update(tuple(sorted((r.left, r.right))) for r in snapshot.relations
                 if r.left in selected and r.right in selected)
    return sorted(pairs)
