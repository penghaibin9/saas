"""Strict, immutable optimizer input. IDs remain strings; no ORM objects cross workers."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json
import re
from typing import Any

CONTRACT_VERSION = 1
MAX_ACTIVITIES = 5000
MAX_OPTIONS = 100000
MAX_OCCURRENCES = 1000000

class InputError(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail

def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)

def fingerprint(value: Any) -> str:
    return sha256(canonical(value).encode("utf-8")).hexdigest()

def obj(value, allowed, required, label):
    if not isinstance(value, dict):
        raise InputError("OBJECT_REQUIRED", label)
    if set(value) - set(allowed):
        raise InputError("UNKNOWN_FIELDS", label + ":" + ",".join(sorted(set(value)-set(allowed))))
    if set(required) - set(value):
        raise InputError("MISSING_FIELDS", label + ":" + ",".join(sorted(set(required)-set(value))))
    return value

def integer(value, lo, hi, label):
    if type(value) is not int or not lo <= value <= hi:
        raise InputError("INVALID_INTEGER", label)
    return value

def text(value, label, maximum=128):
    if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > maximum:
        raise InputError("INVALID_STRING", label)
    return value

def numeric_id(value, label):
    value = text(value, label, 20)
    if not re.fullmatch(r"[1-9][0-9]*", value) or int(value) > 9223372036854775807:
        raise InputError("INVALID_ID", label)
    return value

def strings(value, label, required=False):
    if not isinstance(value, list) or (required and not value):
        raise InputError("ARRAY_REQUIRED", label)
    result = tuple(text(x, label) for x in value)
    if len(set(result)) != len(result):
        raise InputError("DUPLICATE_VALUE", label)
    return tuple(sorted(result))

@dataclass(frozen=True)
class Occurrence:
    key: str
    day: str
    start: int
    end: int
    periods: int
    @property
    def absolute_start(self):
        return date.fromisoformat(self.day).toordinal() * 1440 + self.start
    @property
    def absolute_end(self):
        return date.fromisoformat(self.day).toordinal() * 1440 + self.end
    @classmethod
    def parse(cls, raw):
        obj(raw, {"key","date","start","end","periods"}, {"key","date","start","end","periods"}, "occurrence")
        day = text(raw["date"], "date", 10)
        try:
            if date.fromisoformat(day).isoformat() != day: raise ValueError(day)
        except ValueError as exc:
            raise InputError("INVALID_DATE", day) from exc
        start = integer(raw["start"], 0, 1439, "start")
        end = integer(raw["end"], 1, 1440, "end")
        if start >= end: raise InputError("INVALID_INTERVAL", day)
        return cls(text(raw["key"], "occurrence.key"), day, start, end, integer(raw["periods"],1,24,"periods"))

@dataclass(frozen=True)
class Room:
    id: str
    campus: str
    kind: str
    capacity: int
    features: tuple[str,...]
    available: bool

@dataclass(frozen=True)
class Option:
    id: str
    room: str
    occurrences: tuple[Occurrence,...]
    cost: int

@dataclass(frozen=True)
class Activity:
    id: str
    task_id: str
    teachers: tuple[str,...]
    learners: tuple[str,...]
    headcount: int
    room_kind: str
    features: tuple[str,...]
    required: tuple[str,...]
    periods: int
    options: tuple[Option,...]
    locked: str | None
    baseline: str | None
    @property
    def actors(self):
        return tuple("teacher:"+x for x in self.teachers) + tuple("learner:"+x for x in self.learners)

@dataclass(frozen=True)
class Occupancy:
    id: str
    actors: tuple[str,...]
    room: str | None
    campus: str
    occurrences: tuple[Occurrence,...]
    kind: str = "LESSON"

@dataclass(frozen=True)
class Relation:
    left: str
    right: str
    kind: str
    value: int

@dataclass(frozen=True)
class Snapshot:
    tenant: str
    term: str
    batch: str
    revision: str
    rooms: tuple[Room,...]
    activities: tuple[Activity,...]
    occupied: tuple[Occupancy,...]
    travel: tuple[tuple[str,str,int],...]
    relations: tuple[Relation,...]
    daily_limits: tuple[tuple[str,int],...]
    domain_complete: bool
    input_hash: str
    raw: dict

    @classmethod
    def parse(cls, raw: dict) -> "Snapshot":
        obj(raw,{"contractVersion","scope","rooms","activities","occupied","travelMinutes","relations","dailyLimits","domainComplete","provenance"},
            {"contractVersion","scope","rooms","activities","domainComplete"},"snapshot")
        if type(raw["contractVersion"]) is not int or raw["contractVersion"] != CONTRACT_VERSION:
            raise InputError("UNSUPPORTED_CONTRACT", str(raw["contractVersion"]))
        sc=obj(raw["scope"],{"tenantId","termId","batchId","revision"},{"tenantId","termId","batchId","revision"},"scope")
        tenant,term,batch=(numeric_id(sc[x],x) for x in ("tenantId","termId","batchId"))
        revision=text(sc["revision"],"revision")
        if type(raw["domainComplete"]) is not bool: raise InputError("INVALID_BOOLEAN","domainComplete")
        if not isinstance(raw["rooms"],list) or not raw["rooms"]: raise InputError("ROOMS_REQUIRED","rooms")
        rooms=[]
        for r in raw["rooms"]:
            obj(r,{"id","campus","kind","capacity","features","available"},{"id","campus","kind","capacity","available"},"room")
            if type(r["available"]) is not bool: raise InputError("INVALID_BOOLEAN","available")
            rooms.append(Room(numeric_id(r["id"],"room.id"),text(r["campus"],"campus"),text(r["kind"],"kind"),
                integer(r["capacity"],1,100000,"capacity"),strings(r.get("features",[]),"features"),r["available"]))
        if len({r.id for r in rooms}) != len(rooms): raise InputError("DUPLICATE_ROOM","rooms")
        roomids={r.id for r in rooms}; campuses={r.campus for r in rooms}
        if not isinstance(raw["activities"],list) or not 1<=len(raw["activities"])<=MAX_ACTIVITIES:
            raise InputError("ACTIVITY_LIMIT",str(MAX_ACTIVITIES))
        acts=[]; option_count=0; occurrence_count=0
        for a in raw["activities"]:
            obj(a,{"id","taskId","teachers","learners","headcount","roomKind","features","requiredOccurrences","periods","options","lockedOptionId","baselineOptionId"},
                {"id","taskId","teachers","learners","headcount","requiredOccurrences","periods","options"},"activity")
            aid=text(a["id"],"activity.id"); required=strings(a["requiredOccurrences"],"requiredOccurrences",True)
            if not isinstance(a["options"],list): raise InputError("ARRAY_REQUIRED","options")
            options=[]
            for o in a["options"]:
                obj(o,{"id","roomId","occurrences","cost"},{"id","roomId","occurrences"},"option")
                room=numeric_id(o["roomId"],"option.roomId")
                if room not in roomids: raise InputError("UNKNOWN_ROOM",room)
                if not isinstance(o["occurrences"],list): raise InputError("ARRAY_REQUIRED","occurrences")
                occ=tuple(Occurrence.parse(x) for x in o["occurrences"])
                if set(x.key for x in occ)!=set(required) or len(occ)!=len(required):
                    raise InputError("OCCURRENCE_COVERAGE",aid+":"+str(o["id"]))
                per=integer(a["periods"],1,24,"activity.periods")
                if any(x.periods!=per for x in occ): raise InputError("PERIOD_MISMATCH",aid)
                ordered=sorted(occ,key=lambda x:x.absolute_start)
                if any(x.absolute_end>y.absolute_start for x,y in zip(ordered,ordered[1:])):
                    raise InputError("SELF_OVERLAP",aid)
                options.append(Option(text(o["id"],"option.id"),room,tuple(sorted(occ,key=lambda x:x.key)),integer(o.get("cost",0),0,1000000,"cost")))
                occurrence_count+=len(occ)
                if occurrence_count>MAX_OCCURRENCES: raise InputError("MODEL_SIZE_LIMIT","occurrences")
            ids={o.id for o in options}
            if len(ids)!=len(options): raise InputError("DUPLICATE_OPTION",aid)
            locked=a.get("lockedOptionId");baseline=a.get("baselineOptionId")
            if locked is not None and locked not in ids: raise InputError("LOCK_NOT_IN_DOMAIN",aid)
            if baseline is not None: text(baseline,"baselineOptionId")
            acts.append(Activity(aid,numeric_id(a["taskId"],"taskId"),strings(a["teachers"],"teachers",True),strings(a["learners"],"learners",True),
                integer(a["headcount"],1,100000,"headcount"),str(a.get("roomKind", "")),strings(a.get("features",[]),"features"),
                required,integer(a["periods"],1,24,"periods"),tuple(sorted(options,key=lambda x:x.id)),locked,baseline))
            option_count+=len(options)
        if option_count>MAX_OPTIONS or occurrence_count>MAX_OCCURRENCES: raise InputError("MODEL_SIZE_LIMIT","options/occurrences")
        actids={a.id for a in acts}
        if len(actids)!=len(acts): raise InputError("DUPLICATE_ACTIVITY","activities")
        occupied=[]
        for field in ("occupied", "travelMinutes", "relations"):
            if not isinstance(raw.get(field, []), list): raise InputError("ARRAY_REQUIRED", field)
        if not isinstance(raw.get("dailyLimits", {}), dict): raise InputError("OBJECT_REQUIRED", "dailyLimits")
        for o in raw.get("occupied",[]):
            obj(o,{"id","actors","roomId","campus","occurrences","kind"},{"id","actors","campus","occurrences"},"occupied")
            actor=strings(o["actors"],"occupied.actors")
            if any(not x.startswith(("teacher:","learner:")) for x in actor): raise InputError("INVALID_ACTOR",str(actor))
            rid=o.get("roomId")
            if rid is not None and rid not in roomids: raise InputError("UNKNOWN_ROOM",str(rid))
            campus=text(o["campus"],"occupied.campus");campuses.add(campus)
            kind=o.get("kind","LESSON")
            if kind not in {"LESSON","BLOCKED"}: raise InputError("UNKNOWN_OCCUPANCY_KIND",str(kind))
            if not isinstance(o["occurrences"],list) or not o["occurrences"]: raise InputError("ARRAY_REQUIRED","occupied.occurrences")
            occurrences=tuple(Occurrence.parse(x) for x in o["occurrences"])
            if len({x.key for x in occurrences})!=len(occurrences): raise InputError("DUPLICATE_OCCUPANCY_KEY",str(o["id"]))
            occurrence_count+=len(occurrences)
            if occurrence_count>MAX_OCCURRENCES: raise InputError("MODEL_SIZE_LIMIT","occupied occurrences")
            occupied.append(Occupancy(text(o["id"],"occupied.id"),actor,rid,campus,occurrences,kind))
        if len({o.id for o in occupied})!=len(occupied): raise InputError("DUPLICATE_OCCUPANCY","occupied")
        travel=[]
        for t in raw.get("travelMinutes",[]):
            obj(t,{"from","to","minutes"},{"from","to","minutes"},"travel")
            if t["from"] not in campuses or t["to"] not in campuses: raise InputError("UNKNOWN_CAMPUS","travel")
            travel.append((t["from"],t["to"],integer(t["minutes"],0,1440,"travel.minutes")))
        if len({(a,b) for a,b,_ in travel})!=len(travel): raise InputError("DUPLICATE_TRAVEL","travel")
        relations=[]
        for r in raw.get("relations",[]):
            obj(r,{"left","right","kind","value"},{"left","right","kind","value"},"relation")
            if r["left"] not in actids or r["right"] not in actids or r["left"]==r["right"]: raise InputError("UNKNOWN_RELATION_ACTIVITY","relation")
            if r["kind"] not in {"MIN_DAY_GAP","BEFORE","SAME_START"}: raise InputError("UNKNOWN_RELATION",str(r["kind"]))
            relations.append(Relation(r["left"],r["right"],r["kind"],integer(r["value"],0,10080,"relation.value")))
        limits=[]
        for actor,limit in raw.get("dailyLimits",{}).items():
            if not actor.startswith(("teacher:","learner:")): raise InputError("INVALID_ACTOR",actor)
            limits.append((actor,integer(limit,1,24,"dailyLimit")))
        if 'provenance' in raw:
            obj(raw['provenance'], {'adapterVersion','sourceRevision','plan','bindings','projectionWarnings','formalApplySupported','previewOnly'},
                {'adapterVersion','sourceRevision','plan','bindings','formalApplySupported','previewOnly'}, 'provenance')
            if raw['provenance']['formalApplySupported'] is not False or raw['provenance']['previewOnly'] is not True:
                raise InputError('FORMAL_APPLY_DISABLED', 'This adapter is preview-only pending integration gates')
        normalized=json.loads(canonical(raw))
        return cls(tenant,term,batch,revision,tuple(sorted(rooms,key=lambda x:x.id)),tuple(sorted(acts,key=lambda x:x.id)),
            tuple(sorted(occupied,key=lambda x:x.id)),tuple(sorted(travel)),tuple(relations),tuple(sorted(limits)),raw["domainComplete"],fingerprint(normalized),normalized)
