from copy import deepcopy

def room(rid="1",campus="A",kind="NORMAL",capacity=40,features=()):
    return {"id":rid,"campus":campus,"kind":kind,"capacity":capacity,"features":list(features),"available":True}

def option(oid="a",room_id="1",day="2026-09-14",start=480,end=530,periods=1,key="W01",cost=0):
    return {"id":oid,"roomId":room_id,"occurrences":[{"key":key,"date":day,"start":start,"end":end,"periods":periods}],"cost":cost}

def activity(aid="1",options=None,teacher="t1",learner="g1",headcount=30,periods=1):
    return {"id":aid,"taskId":str(int(aid.split(':')[0])),"teachers":[teacher],"learners":[learner],"headcount":headcount,
        "requiredOccurrences":["W01"],"periods":periods,"options":options or [option()]}

def snapshot(activities=None,rooms=None):
    return {"contractVersion":1,"scope":{"tenantId":"1000000000000000007","termId":"10","batchId":"20","revision":"fixture-1"},
        "rooms":rooms or [room()],"activities":activities or [activity()],"domainComplete":True}

def calendar(weeks=(1,2),days=(1,2,3,4,5),campus="A"):
    from datetime import date,timedelta
    out=[]
    for week in weeks:
        for wd in days:
            day=(date(2026,9,14)+timedelta(weeks=week-1,days=wd-1)).isoformat()
            out.append({"campus":campus,"weekKey":f"W{week:02}","teachingWeekday":wd,"date":day,
                "slots":[{"no":i+1,"start":480+i*55,"end":530+i*55,"block":"AM"} for i in range(4)]})
    return out
