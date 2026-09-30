import unittest
from copy import deepcopy
from optimizer.contracts import InputError, Snapshot
from optimizer.source_builder import compile_source, source_revision, cohorts
from optimizer.solver import solve
from optimizer.persistence import pack_snapshot, unpack_snapshot


def authority_fixture():
    facts={'scope':{'tenantId':'1000000000000000007','termId':'10','batchId':'20'},
        'batch':{'id':20,'term_id':10,'status':'DRAFT','college_id':None,'supersedes_batch_id':None},
        'term':{'id':10,'start_date':'2026-09-14','end_date':'2026-09-27','teaching_weeks':2,'status':'PUBLISHED'},
        'targetTaskIds':['101'],'tasks':[{'id':101,'batch_id':30,'course_id':40,'class_id':50,
            'teacher_key':'T1','expected_students':2,'weekly_hours':4,'total_hours':8,
            'start_week':1,'end_week':2,'required_room_type':'LECTURE','formation_mode':'ADMIN_FIXED',
            'status':'READY','no_auto_schedule':False}],
        'rooms':[{'id':1,'campus_code':'A','room_type':'LECTURE','capacity':40,'status':'AVAILABLE',
            'allow_schedule':True,'is_exclusive':False,'room_name':'R1','building_name':'Building','room_code':'101'}],
        'slots':[{'id':i,'campus_code':None,'slot_no':i,'start_time':f'{(480+(i-1)*55)//60:02}:{(480+(i-1)*55)%60:02}',
            'end_time':f'{(530+(i-1)*55)//60:02}:{(530+(i-1)*55)%60:02}', 'enabled':True,'status':'ENABLED'} for i in range(1,5)],
        'events':[],'existingItems':[],'availability':[],'bookings':[],
        'params':{'capacityCheck':True,'roomTypeMatch':True,'respectAvail':True,'weekdays':[1,2,3,4,5],
            'slots':[1,2,3,4],'forbidden':[],'teacherMaxPerDay':6,'classMaxPerDay':8},
        'teachers':{'101':['T1']},'rosters':{'101':{'ready':True,'teachingClassId':'99','rosterVersionId':'100','studentIds':['1','2']}},
        'ruleRows':[],'teachingClasses':[],'teacherRows':[]}
    plan={'version':1,'week1Monday':'2026-09-14','defaultCampus':'A',
          'slotBlocks':{'A':{str(i):'AM' for i in range(1,5)}},'taskPatterns':{'101':[2,2]},'minDayGap':{'101':1}}
    return facts,plan


class SourceBridgeTests(unittest.TestCase):
    def test_relevant_resources_include_shared_teacher_but_not_unrelated_room_conflicts(self):
        facts,plan=authority_fixture()
        facts['rooms'].append({**facts['rooms'][0],'id':2,'room_type':'LAB','room_name':'LAB2'})
        facts['tasks'].append({**facts['tasks'][0],'id':102,'required_room_type':'LAB','teacher_key':'T2'})
        facts['teachers']['102']=['T2']
        facts['rosters']['102']={'ready':True,'teachingClassId':'199','rosterVersionId':'200','studentIds':['3','4']}
        facts['existingItems']=[{'id':day*10+slot,'batch_id':21,'task_id':102,'classroom_id':2,
            'weekday':day,'slot_no':slot,'start_week':1,'end_week':2,'week_parity':'ALL','source':'MANUAL'} for day in range(1,6) for slot in range(1,5)]
        facts['bookings']=[{'id':1,'classroom_id':2,'booking_date':'2026-09-14','slot_no':1}]
        snapshot,_=self.compile(facts,plan)
        self.assertEqual(solve(snapshot,time_limit=2)['status'],'FEASIBLE')
        facts['teachers']['102']=['T1']
        snapshot,_=self.compile(facts,plan)
        self.assertEqual(solve(snapshot,time_limit=2)['status'],'INFEASIBLE')
    def test_calendar_labels_do_not_invent_stop_commands(self):
        facts,plan=authority_fixture()
        baseline,_=self.compile(facts,plan)
        for kind in ['EXAM','INTERNSHIP']:
            facts['events']=[{'id':1,'event_type':kind,'start_date':'2026-09-14','end_date':'2026-09-27'}]
            snapshot,_=self.compile(facts,plan)
            self.assertEqual([len(a.options) for a in baseline.activities],[len(a.options) for a in snapshot.activities])
    def test_single_double_weeks_keep_formal_pattern(self):
        for parity,week in [('ODD','W01'),('EVEN','W02')]:
            facts,plan=authority_fixture();facts['tasks'][0]['total_hours']=4
            plan['taskParities']={'101':parity}
            snapshot,_=self.compile(facts,plan)
            result=solve(snapshot,time_limit=2)
            self.assertEqual(result['status'],'FEASIBLE')
            self.assertEqual(result['quality']['scheduledPeriods'],4)
            for activity in snapshot.activities:
                for option in activity.options:self.assertEqual({o.key for o in option.occurrences},{week})

    def test_weekend_swap_consumes_source_date_only(self):
        facts,plan=authority_fixture()
        facts['events']=[{'id':1,'event_type':'SWAP','start_date':'2026-09-14',
                          'end_date':'2026-09-14','swap_to_date':'2026-09-19'}]
        snapshot,_=self.compile(facts,plan)
        dates={o.day for a in snapshot.activities for p in a.options for o in p.occurrences}
        self.assertIn('2026-09-19',dates);self.assertNotIn('2026-09-14',dates)

    def test_non_monday_term_start_uses_formal_week_windows(self):
        facts,plan=authority_fixture();facts['term'].update(start_date='2026-09-16',end_date='2026-09-29')
        snapshot,_=self.compile(facts,plan)
        for a in snapshot.activities:
            for p in a.options:
                for o in p.occurrences:
                    from datetime import date
                    self.assertEqual(int(o.key[1:]),(date.fromisoformat(o.day)-date(2026,9,16)).days//7+1)

    def test_seasonal_clock_and_nonconsecutive_slot(self):
        facts,plan=authority_fixture()
        facts['timeBands']=[{'id':1,'slot_id':1,'campus_code':'A','effective_start':'2026-09-21',
                            'effective_end':'2026-09-27','start_time':'07:30','end_time':'08:20'}]
        snapshot,_=self.compile(facts,plan)
        self.assertTrue(any(o.start==450 for a in snapshot.activities for p in a.options for o in p.occurrences))
        facts,plan=authority_fixture();facts['params']['slots']=[1,3]
        snapshot,_=self.compile(facts,plan)
        self.assertEqual(solve(snapshot,time_limit=2)['status'],'INFEASIBLE')

    def compile(self,facts,plan):
        return compile_source(facts,plan,expected_revision=source_revision(facts))
    def test_real_field_shape_and_two_plus_two(self):
        facts,plan=authority_fixture(); snap,binding=self.compile(facts,plan)
        result=solve(snap,time_limit=2)
        self.assertEqual(result['status'],'FEASIBLE')
        self.assertEqual(result['quality']['scheduledPeriods'],8)
        self.assertEqual(len(result['choices']),2)
        self.assertFalse(binding['formalApplySupported'])
    def test_source_version_changed(self):
        facts,plan=authority_fixture(); old=source_revision(facts);facts['tasks'][0]['expected_students']=3
        with self.assertRaisesRegex(InputError,'SOURCE_VERSION_CONFLICT'):
            compile_source(facts,plan,expected_revision=old)
    def test_no_learner_fallback(self):
        facts,plan=authority_fixture();facts['rosters']['101']['rosterVersionId']=None
        with self.assertRaisesRegex(InputError,'FORMAL_ROSTER_REQUIRED'):self.compile(facts,plan)
    def test_plan_cannot_supply_student_ids(self):
        facts,plan=authority_fixture();plan['studentIds']=['999']
        with self.assertRaisesRegex(InputError,'UNKNOWN_FIELDS'):self.compile(facts,plan)
    def test_headcount_below_current_roster(self):
        facts,plan=authority_fixture();facts['tasks'][0]['expected_students']=1
        with self.assertRaisesRegex(InputError,'HEADCOUNT_BELOW_ROSTER'):self.compile(facts,plan)
    def test_pattern_must_cover_remaining_periods(self):
        facts,plan=authority_fixture();plan['taskPatterns']['101']=[2]
        with self.assertRaisesRegex(InputError,'PATTERN_PERIODS_MISMATCH'):self.compile(facts,plan)
    def test_no_silent_concentrated_teaching_conversion(self):
        facts,plan=authority_fixture();facts['tasks'][0]['total_hours']=10
        with self.assertRaisesRegex(InputError,'SEGMENTED_ACTIVITY_PLAN_REQUIRED'):self.compile(facts,plan)
    def test_unknown_calendar_event_blocks(self):
        facts,plan=authority_fixture();facts['events']=[{'id':1,'event_type':'UNKNOWN','start_date':'2026-09-15','end_date':'2026-09-15'}]
        with self.assertRaisesRegex(InputError,'SPECIAL_CALENDAR_ADAPTER_REQUIRED'):self.compile(facts,plan)
    def test_missing_slot_clock_blocks(self):
        facts,plan=authority_fixture();facts['slots'][0]['start_time']=None
        with self.assertRaisesRegex(InputError,'SOURCE_CLOCK_INVALID'):self.compile(facts,plan)
    def test_no_assumed_lunch_continuity(self):
        facts,plan=authority_fixture();del plan['slotBlocks']['A']['2']
        with self.assertRaisesRegex(InputError,'SLOT_BLOCK_REQUIRED'):self.compile(facts,plan)
    def test_no_implicit_monday(self):
        facts,plan=authority_fixture();plan['week1Monday']='2026-09-15'
        with self.assertRaisesRegex(InputError,'CALENDAR_ANCHOR_INVALID'):self.compile(facts,plan)
    def test_respect_existing_teacher_unavailability(self):
        facts,plan=authority_fixture();facts['availability']=[{'id':i,'teacher_key':'T1','weekday':1,'slot_no':i} for i in range(1,5)]
        snap,binding=self.compile(facts,plan);result=solve(snap,time_limit=2)
        self.assertEqual(result['status'],'FEASIBLE')
        for aid,oid in result['choices'].items():self.assertNotEqual(binding['bindings'][aid+'|'+oid]['weekday'],1)
    def test_cohorts_keep_overlapping_membership(self):
        rosters={'1':{'ready':True,'rosterVersionId':'1','studentIds':['1','2']},
                 '2':{'ready':True,'rosterVersionId':'2','studentIds':['2','3']}}
        result=cohorts(rosters)
        self.assertEqual(len(set(result['1'])&set(result['2'])),1)
    def test_snapshot_provenance_is_hashed_and_compressed(self):
        facts,plan=authority_fixture();snap,binding=self.compile(facts,plan);payload,packed=pack_snapshot(snap)
        row={'tenant_id':int(snap.tenant),'term_id':int(snap.term),'batch_id':int(snap.batch),
             'payload_bytes':len(payload),'payload_zlib':packed,'input_hash':snap.input_hash}
        restored=unpack_snapshot(row)
        self.assertEqual(restored.raw['provenance']['plan'],plan)
        self.assertEqual(restored.input_hash,snap.input_hash)
    def test_empty_or_foreign_task_plan_not_ignored(self):
        facts,plan=authority_fixture();plan['taskPatterns']={}
        with self.assertRaisesRegex(InputError,'TASK_PLAN_SET_CHANGED'):self.compile(facts,plan)
    def test_exclusive_room_not_taken(self):
        facts,plan=authority_fixture();facts['rooms'][0]['is_exclusive']=True
        with self.assertRaisesRegex(InputError,'NO_SCHEDULABLE_ROOMS'):self.compile(facts,plan)

    def test_historical_booking_does_not_block_current_term(self):
        facts,plan=authority_fixture()
        facts['bookings']=[{'id':999,'classroom_id':1,'booking_date':'2025-01-01','slot_no':1}]
        snapshot,binding=self.compile(facts,plan)
        self.assertEqual(solve(snapshot,time_limit=2)['status'],'FEASIBLE')
    def test_gap_boolean_and_unknown_task_rejected(self):
        for gaps in [{'101':True},{'999':1}]:
            facts,plan=authority_fixture();plan['minDayGap']=gaps
            with self.assertRaises(InputError):self.compile(facts,plan)
