"""Validate queued work before persistence; no solver import or app initialization."""
import math
from .contracts import InputError, integer, strings

PROFILES = {'BALANCED', 'STUDENT_FRIENDLY', 'TEACHER_COMPACT', 'ROOM_EFFICIENT'}

def normalize_options(raw, snapshot=None):
    if not isinstance(raw, dict):
        raise InputError('OPTIONS_REQUIRED', 'object')
    allowed = {'profile', 'time_limit', 'seed', 'allowed_change_ids', 'max_changes'}
    if set(raw) - allowed:
        raise InputError('UNKNOWN_SOLVER_OPTION', ','.join(sorted(set(raw) - allowed)))
    profile = raw.get('profile', 'BALANCED')
    if profile not in PROFILES:
        raise InputError('UNKNOWN_PROFILE', str(profile))
    budget = raw.get('time_limit', 10.0)
    if isinstance(budget, bool) or not isinstance(budget, (int, float)) or not math.isfinite(budget) or not 0 < budget <= 600:
        raise InputError('INVALID_TIME_LIMIT', '0 < seconds <= 600')
    result = {'profile': profile, 'time_limit': float(budget),
              'seed': integer(raw.get('seed', 0), 0, 2147483647, 'seed')}
    if raw.get('max_changes') is not None:
        result['max_changes'] = integer(raw['max_changes'], 0, 5000, 'max_changes')
    if raw.get('allowed_change_ids') is not None:
        identifiers = list(strings(raw['allowed_change_ids'], 'allowed_change_ids'))
        if snapshot is not None and set(identifiers) - {a.id for a in snapshot.activities}:
            raise InputError('UNKNOWN_REPAIR_ACTIVITY', 'activity outside snapshot')
        result['allowed_change_ids'] = identifiers
    return result
