"""Run actual archived placement helpers and new solver on explicit common cases.
Synthetic data only. These measurements are not a school benchmark or competitor test.
"""
import json,sys,time,platform
from types import SimpleNamespace
from datetime import date,timedelta
from optimizer.contracts import Snapshot
from optimizer.solver import solve
from optimizer.validation import validate_solution
from fixtures import snapshot,activity,option,room
from archive_placement import _Grid,_place_task,_room_candidates


def compare_two_tasks():
    params={'weekdays':[1],'slots':[1,2],'respectAvail':True,'teacherMaxPerDay':6,
            'classMaxPerDay':8,'roomTypeMatch':True,'capacityCheck':True}
    rooms=[SimpleNamespace(id=1,room_type='NORMAL',capacity=40)]
    tasks=[SimpleNamespace(id=1,teacher_key='T1',class_id=1,required_room_type='NORMAL',expected_students=30),
           SimpleNamespace(id=2,teacher_key='T2',class_id=2,required_room_type='NORMAL',expected_students=20)]
    grid=_Grid();old=[];start=time.perf_counter()
    for task in tasks:
        placed,reason=_place_task(task,1,1,1,'ALL',params,set(),grid,rooms,rooms,{('T2',1,2)})
        old.append({'taskId':str(task.id),'slots':[(wd,sl,r.id) for wd,sl,r in placed],'reason':reason})
    old_seconds=time.perf_counter()-start
    a=activity('1',[option('s1',start=480,end=530),option('s2',start=535,end=585)],teacher='T1',learner='g1')
    b=activity('2',[option('s1',start=480,end=530)],teacher='T2',learner='g2',headcount=20)
    raw=snapshot([a,b]);snap=Snapshot.parse(raw);new=solve(snap,time_limit=2)
    return {'case':'two_tasks_shared_room_second_teacher_only_first_slot',
        'input':raw,'old':{'placements':old,'placedTasks':sum(bool(x['slots']) for x in old),'seconds':old_seconds},
        'new':new,'sharedConstraints':['one period each','one room','distinct teachers/classes','T2 unavailable at slot2'],
        'scope':'Exact archived placement function, not its database loader; deterministic synthetic counterexample'}


def scale_case(count):
    rooms=[room(str(i+1)) for i in range(8)];activities=[]
    for i in range(count):
        opts=[]
        for day in range(5):
            for slot in range(6):
                opts.append(option(f'd{day}s{slot}',room_id=str(i%8+1),
                    day=(date(2026,9,14)+timedelta(days=day)).isoformat(),start=480+slot*60,end=530+slot*60))
        activities.append(activity(str(i+1),opts,teacher='T'+str(i%32),learner='G'+str(i)))
    raw=snapshot(activities,rooms);start=time.perf_counter();snap=Snapshot.parse(raw)
    result=solve(snap,time_limit=4)
    return {'tasks':count,'candidateOptions':count*30,'elapsedIncludingParse':round(time.perf_counter()-start,6),
        'status':result['status'],'assigned':len(result['choices']),'validationErrors':len(validate_solution(snap,result['choices'])) if result['choices'] else None,
        'solverSeconds':result['elapsedSeconds'],'budgetSeconds':4,'optimality':result['optimality']}

if __name__=='__main__':
    result={'environment':{'python':platform.python_version(),'os':platform.system(),'processor':platform.processor()},
            'baselineComparison':compare_two_tasks(),'syntheticScale':[scale_case(n) for n in [32,64,128]],
            'notTested':['real school data','MySQL integration','old full auto_schedule endpoint','competitor software','1000+ tasks']}
    print(json.dumps(result,ensure_ascii=False,indent=2))
