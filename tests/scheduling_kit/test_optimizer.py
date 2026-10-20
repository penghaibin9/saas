"""Isolated real solver tests. No application import, database, network or fake MySQL."""
import copy
import itertools
import json
import random
import threading
import unittest
from optimizer.contracts import Snapshot, InputError
from optimizer.validation import validate_solution,quality
from optimizer.calendar import compile_tasks
from optimizer.solver import solve
from fixtures import activity,option,room,snapshot,calendar

class SchedulingTests(unittest.TestCase):
    def solved(self,raw,**kw):
        s=Snapshot.parse(raw);r=solve(s,time_limit=3,**kw)
        self.assertEqual(r['status'],'FEASIBLE',r)
        self.assertFalse(validate_solution(s,r['choices']))
        self.assertFalse(r['publishable'])
        return r
    def impossible(self,raw,**kw):
        r=solve(Snapshot.parse(raw),time_limit=3,**kw)
        self.assertEqual(r['status'],'INFEASIBLE',r);self.assertFalse(r['choices']);return r
    def test_single(self):self.solved(snapshot())
    def test_room_collision(self):self.impossible(snapshot([activity('1'),activity('2',teacher='t2',learner='g2')]))
    def test_teacher_collision(self):self.impossible(snapshot([activity('1'),activity('2',[option(room_id='2')],learner='g2')],[room(),room('2')]))
    def test_student_overlap_across_teaching_groups(self):
        a=activity('1');a['learners']=['g1','shared-student-7'];b=activity('2',[option(room_id='2')],teacher='t2',learner='shared-student-7')
        self.impossible(snapshot([a,b],[room(),room('2')]))
    def test_multiple_teachers(self):
        a=activity('1');a['teachers']=['t1','t2'];b=activity('2',[option(room_id='2')],teacher='t2',learner='g2')
        self.impossible(snapshot([a,b],[room(),room('2')]))
    def test_rotation_disjoint_groups(self):self.solved(snapshot([activity('1'),activity('2',[option(room_id='2')],teacher='t2',learner='g2')],[room(),room('2')]))
    def test_capacity(self):self.impossible(snapshot([activity(headcount=50)]))
    def test_room_type(self):
        a=activity();a['roomKind']='LAB';self.impossible(snapshot([a]))
    def test_room_feature(self):
        a=activity();a['features']=['CNC'];self.impossible(snapshot([a]))
    def test_matching_feature(self):
        a=activity();a['features']=['CNC'];self.solved(snapshot([a],[room(features=['CNC'])]))
    def test_room_unavailable(self):
        r=room();r['available']=False;self.impossible(snapshot(rooms=[r]))
    def test_external_room_reservation(self):
        s=snapshot();s['occupied']=[{'id':'booking1','actors':[],'roomId':'1','campus':'A','occurrences':option()['occurrences']}];self.impossible(s)
    def test_external_teacher_absence(self):
        s=snapshot();s['occupied']=[{'id':'absence1','actors':['teacher:t1'],'campus':'A','occurrences':option()['occurrences']}];self.impossible(s)
    def test_minimum_travel(self):
        a=activity('1');b=activity('2',[option(room_id='2',start=540,end=590)],learner='g2')
        s=snapshot([a,b],[room(),room('2','B')]);s['travelMinutes']=[{'from':'A','to':'B','minutes':30}];self.impossible(s)
    def test_travel_direction(self):
        a=activity('1');b=activity('2',[option(room_id='2',start=560,end=610)],learner='g2')
        s=snapshot([a,b],[room(),room('2','B')]);s['travelMinutes']=[{'from':'A','to':'B','minutes':30}];self.solved(s)
    def test_unknown_travel_fail_closed(self):
        self.impossible(snapshot([activity('1'),activity('2',[option(room_id='2',start=900,end=950)],learner='g2')],[room(),room('2','B')]))
    def test_different_dates_do_not_collide(self):self.solved(snapshot([activity('1'),activity('2',[option(day='2026-09-15')])]))
    def test_week_parity_is_actual_occurrence_set(self):
        a=activity('1');b=activity('2',[option(day='2026-09-21',key='W02')]);b['requiredOccurrences']=['W02'];self.solved(snapshot([a,b]))
    def test_locked_manual_choice(self):
        a=activity(options=[option('a',cost=100),option('b',day='2026-09-15')]);a['lockedOptionId']='a';r=self.solved(snapshot([a]));self.assertEqual(r['choices']['1'],'a')
    def test_hard_before_soft(self):
        a=activity('1');b=activity('2',[option('bad'),option('good',day='2026-09-15',cost=10000)],teacher='t2',learner='g2')
        self.assertEqual(self.solved(snapshot([a,b]))['choices']['2'],'good')
    def test_solver_repairs_greedy_dead_end(self):
        a=activity('1',[option('first'),option('second',start=540,end=590)]);b=activity('2',[option('only')],teacher='t2',learner='g2')
        self.assertEqual(self.solved(snapshot([a,b]))['choices']['1'],'second')
    def test_min_day_gap(self):
        a=activity('1');b=activity('2',[option('bad',start=540,end=590),option('good',day='2026-09-16')])
        s=snapshot([a,b]);s['relations']=[{'left':'1','right':'2','kind':'MIN_DAY_GAP','value':1}]
        self.assertEqual(self.solved(s)['choices']['2'],'good')
    def test_before_relation(self):
        s=snapshot([activity('1'),activity('2',[option(start=540,end=590)])]);s['relations']=[{'left':'1','right':'2','kind':'BEFORE','value':20}];self.impossible(s)
    def test_same_start_relation(self):
        s=snapshot([activity('1'),activity('2',[option(room_id='2')],teacher='t2',learner='g2')],[room(),room('2')]);s['relations']=[{'left':'1','right':'2','kind':'SAME_START','value':0}];self.solved(s)
    def test_daily_limits(self):
        s=snapshot([activity('1'),activity('2',[option(start=540,end=590)])]);s['dailyLimits']={'teacher:t1':1};self.impossible(s)
    def test_daily_load_counts_only_actual_date(self):
        a=activity('1');b=activity('2',[option(day='2026-09-21',key='W02')]);b['requiredOccurrences']=['W02'];s=snapshot([a,b]);s['dailyLimits']={'teacher:t1':1};self.solved(s)
    def test_daily_limit_includes_existing(self):
        s=snapshot();s['dailyLimits']={'teacher:t1':1};s['occupied']=[{'id':'fixed','actors':['teacher:t1'],'campus':'A','occurrences':option(start=600,end=650)['occurrences']}];self.impossible(s)
    def test_missing_occurrence_rejected(self):
        a=activity();a['requiredOccurrences'].append('W02')
        with self.assertRaisesRegex(InputError,'OCCURRENCE_COVERAGE'):Snapshot.parse(snapshot([a]))
    def test_missing_headcount_rejected(self):
        a=activity();a['headcount']=None
        with self.assertRaises(InputError):Snapshot.parse(snapshot([a]))
    def test_large_tenant_id_string(self):self.assertEqual(Snapshot.parse(snapshot()).tenant,'1000000000000000007')
    def test_numeric_tenant_id_rejected(self):
        s=snapshot();s['scope']['tenantId']=1000000000000000007
        with self.assertRaises(InputError):Snapshot.parse(s)
    def test_unknown_rule_rejected(self):
        s=snapshot();s['allowConflict']=True
        with self.assertRaisesRegex(InputError,'UNKNOWN_FIELDS'):Snapshot.parse(s)
    def test_boolean_capacity_rejected(self):
        s=snapshot();s['rooms'][0]['capacity']=True
        with self.assertRaises(InputError):Snapshot.parse(s)
    def test_empty_domain_not_fake_timeout(self):
        a=activity();a['options']=[];self.assertEqual(self.impossible(snapshot([a]))['diagnostics'][0]['code'],'EMPTY_DOMAIN')
    def test_restricted_domain_not_global_infeasible(self):
        a=activity();a['options']=[];s=snapshot([a]);s['domainComplete']=False
        self.assertEqual(solve(Snapshot.parse(s))['status'],'NO_SOLUTION_IN_RESTRICTED_DOMAIN')
    def test_cancellation(self):
        r=solve(Snapshot.parse(snapshot()),cancelled=lambda:True);self.assertEqual(r['status'],'CANCELLED');self.assertFalse(r['choices'])
    def test_timeout_not_infeasible(self):
        r=solve(Snapshot.parse(snapshot()),time_limit=0.000001);self.assertEqual(r['status'],'UNKNOWN')
    def test_invalid_budget_rejected(self):
        for value in [0,-1,float('nan'),float('inf'),True,601]:
            with self.subTest(value=value),self.assertRaises(InputError):solve(Snapshot.parse(snapshot()),time_limit=value)
    def test_repeatable_small_optimum(self):
        s=snapshot([activity(options=[option('bad',cost=100),option('good',day='2026-09-15')])]);a=self.solved(s);b=self.solved(s);self.assertEqual(a['proposalHash'],b['proposalHash'])
    def test_repair_scope_keeps_unrelated(self):
        a=activity('1',[option('a'),option('b',day='2026-09-15')]);a['baselineOptionId']='a'
        b=activity('2',[option('a'),option('b',day='2026-09-15')],teacher='t2',learner='g2');b['baselineOptionId']='a'
        r=self.solved(snapshot([a,b]),allowed_change_ids=['2'],max_changes=1)
        self.assertEqual(r['choices'],{'1':'a','2':'b'});self.assertEqual(r['quality']['changedActivities'],1)
    def test_max_changes_zero_blocks_repair(self):
        a=activity(options=[option('old',cost=100),option('new',day='2026-09-15')]);a['baselineOptionId']='old'
        self.assertEqual(self.solved(snapshot([a]),max_changes=0)['choices']['1'],'old')
    def test_lexicographic_change_before_quality(self):
        a=activity(options=[option('old',cost=100000),option('new',day='2026-09-15')]);a['baselineOptionId']='old'
        r=self.solved(snapshot([a]));self.assertEqual(r['choices']['1'],'old');self.assertEqual(r['phases'][0]['phase'],'MIN_CHANGES')
    def test_validator_rejects_omissions(self):self.assertTrue(validate_solution(Snapshot.parse(snapshot()),{}))
    def test_validator_rejects_unknown_choice(self):self.assertTrue(validate_solution(Snapshot.parse(snapshot()),{'1':'forged'}))
    def test_validator_rejects_conflict(self):
        s=Snapshot.parse(snapshot([activity('1'),activity('2')]))
        self.assertIn('ROOM_OVERLAP',{e.code for e in validate_solution(s,{'1':'a','2':'a'})})
    def test_relation_explanation_not_claim_minimal(self):
        r=self.impossible(snapshot([activity('1'),activity('2')]))
        self.assertFalse(r['diagnostics'][0]['minimalityProven'])
    def test_calendar_2_plus_2(self):
        task={'taskId':'1','teachers':['t'],'learners':['g'],'headcount':30,'weeks':['W01','W02'],'meetingPattern':[2,2],'plannedPeriods':8,'minDayGap':1}
        s,_=compile_tasks(scope=snapshot()['scope'],tasks=[task],rooms=[room()],calendar=calendar())
        r=solve(s,time_limit=3);self.assertEqual(r['status'],'FEASIBLE',r);self.assertEqual(r['quality']['scheduledPeriods'],8)
    def test_calendar_holiday_does_not_drop_hours(self):
        task={'taskId':'1','teachers':['t'],'learners':['g'],'headcount':30,'weeks':['W01','W02'],'meetingPattern':[2],'plannedPeriods':4,'weekdays':[1]}
        s,meta=compile_tasks(scope=snapshot()['scope'],tasks=[task],rooms=[room()],calendar=calendar(weeks=[1]))
        self.assertEqual(solve(s)['status'],'INFEASIBLE');self.assertTrue(meta['diagnostics'])
    def test_calendar_makeup_actual_date(self):
        cal=calendar(weeks=[1],days=[1]);cal[0]['date']='2026-09-19'
        task={'taskId':'1','teachers':['t'],'learners':['g'],'headcount':30,'weeks':['W01'],'meetingPattern':[2],'plannedPeriods':2,'weekdays':[1]}
        s,_=compile_tasks(scope=snapshot()['scope'],tasks=[task],rooms=[room()],calendar=cal)
        self.assertEqual(s.activities[0].options[0].occurrences[0].day,'2026-09-19')
    def test_calendar_block_break(self):
        cal=calendar(weeks=[1],days=[1]);cal[0]['slots'][2]['block']='PM';cal[0]['slots'][3]['block']='PM'
        task={'taskId':'1','teachers':['t'],'learners':['g'],'headcount':30,'weeks':['W01'],'meetingPattern':[4],'plannedPeriods':4,'weekdays':[1]}
        s,_=compile_tasks(scope=snapshot()['scope'],tasks=[task],rooms=[room()],calendar=cal);self.assertEqual(solve(s)['status'],'INFEASIBLE')
    def test_calendar_total_hours_mismatch(self):
        task={'taskId':'1','teachers':['t'],'learners':['g'],'headcount':30,'weeks':['W01'],'meetingPattern':[2],'plannedPeriods':4}
        with self.assertRaisesRegex(InputError,'TOTAL_PERIODS_MISMATCH'):compile_tasks(scope=snapshot()['scope'],tasks=[task],rooms=[room()],calendar=calendar())
    def test_exhaustive_tiny_feasibility(self):
        rng=random.Random(73)
        for case in range(16):
            acts=[]
            for i in range(1,5):
                choices=[option(str(k),start=480+k*60,end=530+k*60) for k in range(4) if rng.random()<.6]
                a=activity(str(i),choices or [option()],teacher='t'+str(i),learner='g'+str(i));acts.append(a)
            s=Snapshot.parse(snapshot(acts));brute=any(not validate_solution(s,dict(zip([a.id for a in s.activities],choice))) for choice in itertools.product(*[[o.id for o in a.options] for a in s.activities]))
            r=solve(s,time_limit=3)
            with self.subTest(case=case):self.assertEqual(r['status']=='FEASIBLE',brute,r)

if __name__=='__main__':unittest.main(verbosity=2)
