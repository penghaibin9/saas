"""Bounded, resource-indexed constructive incumbent. No infeasibility claims."""
from collections import defaultdict
import time
from .validation import pair_violations,validate_solution,daily_counts,room_map


def construct(snapshot,domains,weights,*,deadline,cancelled,max_changes=None):
    started=time.perf_counter();acts={a.id:a for a in snapshot.activities};rooms=room_map(snapshot)
    potential=defaultdict(set);selected_by=defaultdict(set);relations=defaultdict(set)
    selected={};remaining={aid:list(options) for aid,options in domains.items()}
    load=defaultdict(int,daily_counts(snapshot,{}));limit=dict(snapshot.daily_limits);busy=defaultdict(list)
    changed=0
    def keys(activity,option):
        for day in {o.day for o in option.occurrences}:
            yield 'room:'+option.room,day
            for actor in activity.actors:yield actor,day
    for aid,options in domains.items():
        if cancelled() or time.perf_counter()>=deadline:return None,{'complete':False,'reason':'BUDGET'}
        for option in options:
            for key in keys(acts[aid],option):potential[key].add(aid)
    for relation in snapshot.relations:
        relations[relation.left].add(relation.right);relations[relation.right].add(relation.left)
    for fixed in snapshot.occupied:
        if fixed.kind!='LESSON':continue
        for occ in fixed.occurrences:
            for actor in fixed.actors:busy[actor,occ.day].append((occ.start,occ.end))
    def compatible(activity,option):
        if max_changes is not None and changed+int(activity.baseline is not None and activity.baseline!=option.id)>max_changes:
            return False
        additions=defaultdict(int)
        for occ in option.occurrences:
            for actor in activity.actors:additions[actor,occ.day]+=occ.periods
        if any(actor in limit and load[actor,day]+n>limit[actor] for (actor,day),n in additions.items()):return False
        peers=set(relations[activity.id])&set(selected)
        for key in keys(activity,option):peers.update(selected_by[key])
        return not any(pair_violations(snapshot,activity,option,acts[aid],selected[aid]) for aid in peers)
    def gap(intervals):
        if not intervals:return 0
        return max(x[1] for x in intervals)-min(x[0] for x in intervals)-sum(b-a for a,b in intervals)
    def score(activity,option):
        extra=defaultdict(list)
        for occ in option.occurrences:
            for actor in activity.actors:extra[actor,occ.day].append((occ.start,occ.end))
        cost=option.cost*weights['preference']+(rooms[option.room].capacity-activity.headcount)*sum(o.periods for o in option.occurrences)*weights['roomWaste']
        for key,intervals in extra.items():
            cost+=(gap(busy[key]+intervals)-gap(busy[key]))*weights['teacherGap' if key[0].startswith('teacher:') else 'learnerGap']
        return (int(activity.baseline is not None and activity.baseline!=option.id),cost,
                min(o.absolute_start for o in option.occurrences),option.id)
    while remaining:
        if cancelled() or time.perf_counter()>=deadline:return None,{'complete':False,'reason':'BUDGET','placed':len(selected)}
        aid=min(remaining,key=lambda aid:(len(remaining[aid]),-len(acts[aid].actors),-acts[aid].headcount,aid))
        activity=acts[aid];options=[o for o in remaining.pop(aid) if compatible(activity,o)]
        if not options:return None,{'complete':False,'reason':'CONSTRUCTIVE_DEAD_END','placed':len(selected)}
        option=min(options,key=lambda o:score(activity,o));selected[aid]=option
        changed+=int(activity.baseline is not None and activity.baseline!=option.id)
        affected=set(relations[aid])
        for key in keys(activity,option):selected_by[key].add(aid);affected.update(potential[key])
        for occ in option.occurrences:
            for actor in activity.actors:
                load[actor,occ.day]+=occ.periods;busy[actor,occ.day].append((occ.start,occ.end))
        if max_changes is not None and changed==max_changes:affected.update(remaining)
        for other in affected&set(remaining):
            if time.perf_counter()>=deadline:return None,{'complete':False,'reason':'BUDGET','placed':len(selected)}
            remaining[other]=[o for o in remaining[other] if compatible(acts[other],o)]
    choices={aid:o.id for aid,o in selected.items()}
    errors=validate_solution(snapshot,choices)
    if errors:return None,{'complete':False,'reason':'VALIDATOR_REJECTED','errors':[e.as_dict() for e in errors]}
    return choices,{'complete':True,'strategy':'DYNAMIC_MRV_WITH_RESOURCE_FILTERING',
                    'elapsedSeconds':round(time.perf_counter()-started,6),'optimality':'NOT_PROVEN'}
