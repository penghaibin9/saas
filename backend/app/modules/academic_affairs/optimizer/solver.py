"""Bounded CP-SAT proposal generation. No ORM, network or official timetable writes."""
from __future__ import annotations
from collections import defaultdict, Counter
from dataclasses import replace
from itertools import combinations
import math
import threading
import time
from .contracts import Snapshot, InputError, fingerprint
from .validation import basic_violations, pair_violations, validate_solution, quality, room_map, fixed_violations

# Runtime initialization is outside each request's search budget. Worker reports readiness only after this import.
_runtime_started=time.perf_counter()
try:
    import ortools
    from ortools.sat.python import cp_model
except ImportError:
    ortools = cp_model = None
RUNTIME_STARTUP_SECONDS=time.perf_counter()-_runtime_started

ALGORITHM_VERSION = "yueke-cpsat-20260914.2"
PROFILES = {
    "BALANCED": {"preference":100,"teacherGap":1,"learnerGap":2,"worstGap":5,"roomWaste":1},
    "STUDENT_FRIENDLY": {"preference":100,"teacherGap":1,"learnerGap":5,"worstGap":8,"roomWaste":1},
    "TEACHER_COMPACT": {"preference":100,"teacherGap":5,"learnerGap":1,"worstGap":8,"roomWaste":1},
    "ROOM_EFFICIENT": {"preference":100,"teacherGap":1,"learnerGap":1,"worstGap":2,"roomWaste":5},
}

def solve(snapshot:Snapshot, *, profile="BALANCED", time_limit=10.0, seed=0,
          allowed_change_ids=None, max_changes=None, cancelled=lambda:False):
    if profile not in PROFILES: raise InputError("UNKNOWN_PROFILE",str(profile))
    if isinstance(time_limit,bool) or not isinstance(time_limit,(int,float)) or not math.isfinite(time_limit) or not 0<time_limit<=600:
        raise InputError("INVALID_TIME_LIMIT","0 < seconds <= 600")
    if type(seed) is not int or not 0<=seed<=2147483647: raise InputError("INVALID_SEED",str(seed))
    if max_changes is not None and (type(max_changes) is not int or max_changes<0): raise InputError("INVALID_CHANGE_LIMIT",str(max_changes))
    started=time.perf_counter();deadline=started+time_limit
    result={"algorithmVersion":ALGORITHM_VERSION,"inputHash":snapshot.input_hash,"profile":profile,
            "seed":seed,"workers":1,"status":"UNKNOWN","choices":{},"phases":[],"diagnostics":[],
            "domainComplete":snapshot.domain_complete,"publishable":False,"optimality":"NOT_PROVEN"}
    def finish(status):
        result['status']=status;result['elapsedSeconds']=round(time.perf_counter()-started,6)
        if result['choices']:
            errors=validate_solution(snapshot,result['choices'])
            result['validation']=[e.as_dict() for e in errors]
            if errors:
                result['status']='VALIDATOR_REJECTED';result['choices']={};result['publishable']=False
            else:
                result['quality']=quality(snapshot,result['choices'])
                result['proposalHash']=fingerprint({'inputHash':snapshot.input_hash,'choices':result['choices']})
                result['candidateComplete']=True
        # Formal publication is always a separate canonical command.
        result['publishable']=False
        return result
    if cancelled():return finish('CANCELLED')
    input_errors=fixed_violations(snapshot)
    if input_errors:
        result['diagnostics']=[e.as_dict() for e in input_errors]
        return finish('INPUT_CONFLICT')
    allowed=None if allowed_change_ids is None else set(allowed_change_ids)
    if allowed is not None and allowed-set(a.id for a in snapshot.activities):raise InputError("UNKNOWN_REPAIR_ACTIVITY",str(allowed))
    domains={}; reasons={}; acts={a.id:a for a in snapshot.activities}
    for a in snapshot.activities:
        if cancelled():return finish('CANCELLED')
        good=[];bad=Counter()
        for o in a.options:
            if cancelled():return finish('CANCELLED')
            if time.perf_counter()>=deadline:return finish('FEASIBLE' if result['choices'] else 'UNKNOWN')
            errors=basic_violations(snapshot,a,o)
            if allowed is not None and a.id not in allowed and a.baseline!=o.id:
                bad['OUTSIDE_REPAIR_SCOPE']+=1;continue
            if errors:bad.update(set(e.code for e in errors))
            else:good.append(o)
        domains[a.id]=good;reasons[a.id]=dict(bad)
    empty=[aid for aid,opts in domains.items() if not opts]
    if empty:
        result['diagnostics']=[{'code':'EMPTY_DOMAIN','activityId':aid,'rejectedBy':reasons[aid],
                                'candidateCount':len(acts[aid].options)} for aid in empty]
        return finish('INFEASIBLE' if snapshot.domain_complete else 'NO_SOLUTION_IN_RESTRICTED_DOMAIN')
    if time.perf_counter()>=deadline:return finish('FEASIBLE' if result['choices'] else 'UNKNOWN')
    if cp_model is None:
        result['diagnostics']=[{'code':'SOLVER_DEPENDENCY_MISSING','requirement':'ortools==9.15.6755'}]
        return finish('DEPENDENCY_MISSING')
    result['solverVersion']=ortools.__version__;result['runtimeStartupSeconds']=RUNTIME_STARTUP_SECONDS
    from .warm_start import construct
    incumbent,details=construct(snapshot,domains,PROFILES[profile],
        deadline=min(deadline,time.perf_counter()+min(1.5,time_limit*0.25)),cancelled=cancelled,max_changes=max_changes)
    result['constructive']=details
    if cancelled():return finish('CANCELLED')
    if incumbent:
        result['choices']=incumbent;result['incumbentSource']='VALIDATED_CONSTRUCTIVE'
    if time.perf_counter()>=deadline:return finish('FEASIBLE' if incumbent else 'UNKNOWN')
    model=cp_model.CpModel();rooms=room_map(snapshot);x={};by_resource=defaultdict(list);by_day=defaultdict(list)
    assumptions={};changes=[];soft=[];weights=PROFILES[profile]
    for aid,opts in domains.items():
        a=acts[aid];present=model.new_bool_var('required:'+aid);assumptions[present.index]=aid
        for o in opts:
            if cancelled():return finish('CANCELLED')
            if time.perf_counter()>=deadline:return finish('FEASIBLE' if result['choices'] else 'UNKNOWN')
            v=model.new_bool_var(aid+':'+o.id);x[aid,o.id]=v;model.add(v<=present)
            if a.baseline is not None and a.baseline!=o.id:changes.append(v)
            waste=(rooms[o.room].capacity-a.headcount)*sum(t.periods for t in o.occurrences)
            soft.append((o.cost*weights['preference']+waste*weights['roomWaste'])*v)
            for occ in o.occurrences:
                interval=model.new_optional_fixed_size_interval_var(occ.absolute_start,occ.end-occ.start,v,aid+':'+o.id+':'+occ.key)
                by_resource['room:'+o.room].append(interval)
                for actor in a.actors:
                    by_resource[actor].append(interval)
                    by_day[actor,occ.day].append((v,occ,aid,o))
        model.add(sum(x[aid,o.id] for o in opts)==1).only_enforce_if(present)
        model.add_assumption(present)
    for intervals in by_resource.values():model.add_no_overlap(intervals)
    # Cross-campus travel is sequence dependent. Pair only choices sharing an actor/day.
    edges=set();checks=0
    for (_actor,_day),entries in by_day.items():
        candidates={(aid,o.id):(acts[aid],o) for _,_,aid,o in entries}
        for (aid,oid),(bid,pid) in combinations(sorted(candidates),2):
            if aid==bid or rooms[candidates[aid,oid][1].room].campus==rooms[candidates[bid,pid][1].room].campus:continue
            checks+=1
            if checks>2000000:raise InputError('MODEL_PAIR_BUDGET','travel/relations')
            if time.perf_counter()>=deadline:return finish('FEASIBLE' if result['choices'] else 'UNKNOWN')
            if pair_violations(snapshot,*candidates[aid,oid],*candidates[bid,pid]):edges.add(((aid,oid),(bid,pid)))
    for rel in snapshot.relations:
        for lo in domains[rel.left]:
            for ro in domains[rel.right]:
                checks+=1
                if checks>2000000:raise InputError('MODEL_PAIR_BUDGET','travel/relations')
                if time.perf_counter()>=deadline:return finish('FEASIBLE' if result['choices'] else 'UNKNOWN')
                if pair_violations(snapshot,acts[rel.left],lo,acts[rel.right],ro):
                    edges.add(tuple(sorted(((rel.left,lo.id),(rel.right,ro.id)))))
    for a,b in sorted(edges):model.add(x[a]+x[b]<=1)
    # Daily loads count actual occurrences, never all semester rows in a weekday bucket.
    fixed_load=defaultdict(int)
    for fixed in snapshot.occupied:
        if fixed.kind != 'LESSON': continue
        for occ in fixed.occurrences:
            for actor in fixed.actors:fixed_load[actor,occ.day]+=occ.periods
    for (actor,day),entries in by_day.items():
        if actor in dict(snapshot.daily_limits):
            model.add(sum(v*occ.periods for v,occ,_,_ in entries)+fixed_load[actor,day]<=dict(snapshot.daily_limits)[actor])
    # Gap objectives for selected activities, with a worst-actor-day penalty for fairness.
    fixed_by_day=defaultdict(list)
    for fixed in snapshot.occupied:
        if fixed.kind != 'LESSON': continue
        for occ in fixed.occurrences:
            for actor in fixed.actors: fixed_by_day[actor,occ.day].append(occ)
    gap_vars=[]
    for actor,day in sorted(set(by_day)|set(fixed_by_day)):
        if cancelled():return finish('CANCELLED')
        if time.perf_counter()>=deadline:return finish('FEASIBLE' if result['choices'] else 'UNKNOWN')
        entries=by_day.get((actor,day),[]); fixed=fixed_by_day.get((actor,day),[])
        used=model.new_bool_var('used:'+actor+day)
        if fixed: model.add(used==1)
        else: model.add_max_equality(used,[v for v,_,_,_ in entries])
        first=model.new_int_var(0,1440,'first:'+actor+day)
        last=model.new_int_var(0,1440,'last:'+actor+day)
        starts=[o.start for o in fixed]+[occ.start*v+1440*(1-v) for v,occ,_,_ in entries]
        ends=[o.end for o in fixed]+[occ.end*v for v,occ,_,_ in entries]
        model.add_min_equality(first,starts);model.add_max_equality(last,ends)
        duration=sum(o.end-o.start for o in fixed)+sum((occ.end-occ.start)*v for v,occ,_,_ in entries)
        gap=model.new_int_var(0,1440,'gap:'+actor+day)
        model.add(gap==last-first-duration).only_enforce_if(used)
        model.add(gap==0).only_enforce_if(used.negated())
        gap_vars.append(gap)
        soft.append(weights['teacherGap' if actor.startswith('teacher:') else 'learnerGap']*gap)
    if gap_vars:
        worst=model.new_int_var(0,1440,'worst_gap');model.add_max_equality(worst,gap_vars);soft.append(weights['worstGap']*worst)
    changed=sum(changes)
    if max_changes is not None:model.add(changed<=max_changes)
    # Safe hints are not accepted as solutions until solved and validated.
    for aid,opts in domains.items():
        baseline=(incumbent or {}).get(aid) or acts[aid].baseline
        if baseline in {o.id for o in opts}:
            for o in opts:model.add_hint(x[aid,o.id],int(o.id==baseline))
    validation_error=model.validate()
    if validation_error:
        result['diagnostics']=[{'code':'MODEL_INVALID','detail':validation_error}];return finish('MODEL_INVALID')
    phase_objectives=[('MIN_CHANGES',changed),('QUALITY',sum(soft))] if changes else [('QUALITY',sum(soft))]
    for label,objective in phase_objectives:
        remaining=deadline-time.perf_counter()
        if remaining<=0:break
        if cancelled():result['choices']={};return finish('CANCELLED')
        model.minimize(objective);solver=cp_model.CpSolver()
        solver.parameters.max_time_in_seconds=remaining;solver.parameters.num_search_workers=1;solver.parameters.random_seed=seed
        done=threading.Event();seen_cancel=threading.Event()
        def monitor():
            while not done.wait(.05):
                if cancelled():seen_cancel.set();solver.stop_search();return
        thread=threading.Thread(target=monitor,daemon=True);thread.start()
        try:status=solver.solve(model)
        finally:done.set();thread.join(timeout=1)
        if seen_cancel.is_set() or cancelled():result['choices']={};return finish('CANCELLED')
        state=solver.status_name(status)
        result['phases'].append({'phase':label,'status':state,'wallSeconds':solver.wall_time,
            'objective':solver.objective_value if status in (cp_model.OPTIMAL,cp_model.FEASIBLE) else None,
            'bound':solver.best_objective_bound})
        if status==cp_model.INFEASIBLE:
            if result['choices']:
                result['diagnostics']=[{'code':'SOLVER_VALIDATOR_DISAGREEMENT'}]
                result['choices']={}
                return finish('MODEL_INVALID')
            result['diagnostics']=[{'code':'SUFFICIENT_CONFLICT_SET','activityIds':[assumptions[i] for i in solver.sufficient_assumptions_for_infeasibility() if i in assumptions],
                                    'minimalityProven':False}]
            return finish('INFEASIBLE' if snapshot.domain_complete else 'NO_SOLUTION_IN_RESTRICTED_DOMAIN')
        if status not in (cp_model.OPTIMAL,cp_model.FEASIBLE):
            break
        result['choices']={aid:o.id for aid,opts in domains.items() for o in opts if solver.boolean_value(x[aid,o.id])}
        result['incumbentSource']='CP_SAT'
        if status!=cp_model.OPTIMAL:break
        if label=='MIN_CHANGES':model.add(changed==int(round(solver.objective_value)))
        else:result['optimality']='OPTIMAL_IN_DECLARED_MODEL' if snapshot.domain_complete else 'OPTIMAL_IN_RESTRICTED_DOMAIN'
    if result['choices']:return finish('FEASIBLE')
    return finish('UNKNOWN')
