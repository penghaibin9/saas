"""Read-only M0 key comparison. Pairing and cascade semantics must not be flattened.

A match here is not tenant isolation, consumer closure or deletion approval.
Names are retained as evidence but are not key-equivalence criteria.
"""
from __future__ import annotations

import json


def action(value):
    value = (value or 'RESTRICT').upper()
    return 'RESTRICT' if value == 'NO ACTION' else value


def sort_records(values):
    return sorted(values, key=lambda value: json.dumps(value, sort_keys=True))


def metadata_contract(table):
    from sqlalchemy import Column, UniqueConstraint
    from sqlalchemy.dialects.mysql import dialect
    result = {'version': 1, 'primaryKey': [column.name for column in table.primary_key.columns],
              'foreignKeys': [], 'uniqueKeys': [], 'unsupported': []}
    for fk in table.foreign_key_constraints:
        targets = []
        for element in fk.elements:
            parts = element.target_fullname.split('.')
            if len(parts) not in (2, 3):
                result['unsupported'].append('UNRESOLVED_FK_TARGET')
            targets.append({'schema': parts[0] if len(parts) == 3 else None,
                            'table': parts[-2] if len(parts) >= 2 else '', 'column': parts[-1]})
        result['foreignKeys'].append({'name': fk.name, 'columns': [e.parent.name for e in fk.elements],
            'targets': targets, 'onDelete': action(fk.ondelete), 'onUpdate': action(fk.onupdate)})
    for constraint in table.constraints:
        if isinstance(constraint, UniqueConstraint):
            result['uniqueKeys'].append({'name': constraint.name, 'parts': [
                {'column': c.name, 'prefixLength': None, 'expression': None, 'direction': 'ASC'}
                for c in constraint.columns]})
    for index in table.indexes:
        if not index.unique:
            continue
        parts = []
        length = index.dialect_options['mysql'].get('length')
        for expression in index.expressions:
            name = expression.name if isinstance(expression, Column) else None
            prefix = length.get(name) if isinstance(length, dict) else length
            parts.append({'column': name, 'prefixLength': prefix,
                'expression': None if name else str(expression.compile(dialect=dialect())), 'direction': 'ASC'})
            if name is None:
                result['unsupported'].append('EXPRESSION_INDEX_REQUIRES_REVIEW')
        result['uniqueKeys'].append({'name': index.name, 'parts': parts})
    result['foreignKeys'] = sort_records(result['foreignKeys'])
    result['uniqueKeys'] = sort_records(result['uniqueKeys'])
    result['unsupported'] = sorted(set(result['unsupported']))
    return result


def mysql_contracts(table_names, foreign_rows, index_rows, database):
    """Rows from information_schema only; never selects customer business rows.

    foreign row: table,name,ordinal,column,target-schema,target-table,target-column,delete,update.
    index row: table,name,non-unique,sequence,column,prefix,expression,collation.
    """
    result = {name: {'version': 1, 'primaryKey': [], 'foreignKeys': [], 'uniqueKeys': [], 'unsupported': []}
              for name in table_names}
    foreign, indexes = {}, {}
    for table, name, ordinal, column, schema, target, target_column, on_delete, on_update in foreign_rows:
        if table not in result:
            continue
        key = (table, name)
        item = foreign.setdefault(key, {'name': name, 'members': {}, 'onDelete': action(on_delete), 'onUpdate': action(on_update)})
        if item['onDelete'] != action(on_delete) or item['onUpdate'] != action(on_update) or ordinal in item['members']:
            raise ValueError('INCONSISTENT_FOREIGN_KEY_EVIDENCE')
        item['members'][ordinal] = (column, {'schema': None if schema == database else schema, 'table': target, 'column': target_column})
    for (table, _), item in sorted(foreign.items()):
        if sorted(item['members']) != list(range(1, len(item['members']) + 1)):
            raise ValueError('INCOMPLETE_FOREIGN_KEY_EVIDENCE')
        members = [item['members'][key] for key in sorted(item['members'])]
        result[table]['foreignKeys'].append({'name': item['name'], 'columns': [m[0] for m in members],
            'targets': [m[1] for m in members], 'onDelete': item['onDelete'], 'onUpdate': item['onUpdate']})
    for table, name, non_unique, sequence, column, prefix, expression, collation in index_rows:
        if table not in result or non_unique:
            continue
        item = indexes.setdefault((table, name), {})
        if sequence in item:
            raise ValueError('DUPLICATE_INDEX_POSITION')
        item[sequence] = {'column': column, 'prefixLength': prefix, 'expression': expression,
                          'direction': 'DESC' if collation == 'D' else 'ASC'}
    for (table, name), parts in sorted(indexes.items()):
        if sorted(parts) != list(range(1, len(parts) + 1)):
            raise ValueError('INCOMPLETE_INDEX_EVIDENCE')
        ordered = [parts[key] for key in sorted(parts)]
        if name == 'PRIMARY':
            if any(p['column'] is None or p['prefixLength'] is not None or p['expression'] for p in ordered):
                raise ValueError('UNSUPPORTED_PRIMARY_KEY')
            result[table]['primaryKey'] = [p['column'] for p in ordered]
        else:
            result[table]['uniqueKeys'].append({'name': name, 'parts': ordered})
            if any(p['expression'] or p['column'] is None for p in ordered):
                result[table]['unsupported'].append('EXPRESSION_INDEX_REQUIRES_REVIEW')
    return result


def signatures(contract):
    if not isinstance(contract, dict) or type(contract.get('version')) is not int or contract['version'] != 1:
        return None
    for field in ('primaryKey', 'foreignKeys', 'uniqueKeys', 'unsupported'):
        if not isinstance(contract.get(field), list):
            raise ValueError('INCOMPLETE_KEY_CONTRACT')
    names = contract['primaryKey']
    if any(not isinstance(name, str) or not name for name in names) or len(set(names)) != len(names):
        raise ValueError('INVALID_PRIMARY_KEY_EVIDENCE')
    if any(not isinstance(value, str) or not value for value in contract['unsupported']):
        raise ValueError('INVALID_UNSUPPORTED_KEY_EVIDENCE')
    fks = []
    for row in contract['foreignKeys']:
        if not isinstance(row, dict) or not isinstance(row.get('columns'), list) or not isinstance(row.get('targets'), list) or not row['columns'] or len(row['columns']) != len(row['targets']):
            raise ValueError('INVALID_PAIRED_FOREIGN_KEY')
        if any(not isinstance(column, str) or not column for column in row['columns']):
            raise ValueError('INVALID_FOREIGN_KEY_COLUMN')
        for target in row['targets']:
            if not isinstance(target, dict) or set(target) != {'schema', 'table', 'column'} or any(not isinstance(target.get(key), str) or not target[key] for key in ('table', 'column')) or (target['schema'] is not None and (not isinstance(target['schema'], str) or not target['schema'])):
                raise ValueError('INVALID_FOREIGN_KEY_TARGET')
        if any(row.get(key) not in ('RESTRICT', 'NO ACTION', 'CASCADE', 'SET NULL', 'SET DEFAULT') for key in ('onDelete', 'onUpdate')):
            raise ValueError('MISSING_OR_INVALID_FOREIGN_KEY_ACTION')
        fks.append({'columns': row['columns'], 'targets': row['targets'],
                    'onDelete': action(row.get('onDelete')), 'onUpdate': action(row.get('onUpdate'))})
    uniques = []
    for row in contract['uniqueKeys']:
        if not isinstance(row.get('parts'), list) or not row['parts']:
            raise ValueError('EMPTY_UNIQUE_KEY')
        for part in row['parts']:
            if not isinstance(part, dict) or not {'column', 'prefixLength', 'expression', 'direction'} <= part.keys():
                raise ValueError('INCOMPLETE_UNIQUE_KEY_PART')
            column, expression, prefix = part['column'], part['expression'], part['prefixLength']
            if ((column is None) == (expression is None) or (column is not None and (not isinstance(column, str) or not column))
                    or (expression is not None and (not isinstance(expression, str) or not expression))
                    or (prefix is not None and (type(prefix) is not int or prefix < 1))
                    or part['direction'] not in ('ASC', 'DESC')):
                raise ValueError('INVALID_UNIQUE_KEY_PART')
        uniques.append(row['parts'])
    # A UNIQUE constraint can also appear as a unique Index in a dialect. Do not double count it.
    unique = {json.dumps(value, sort_keys=True, separators=(',', ':')) for value in uniques}
    foreign = {json.dumps(value, sort_keys=True, separators=(',', ':')) for value in fks}
    return {'primaryKey': contract['primaryKey'], 'foreignKeys': sorted(foreign),
            'uniqueKeys': sorted(unique), 'unsupported': sorted(set(contract['unsupported']))}


def compare(runtime, physical):
    expected, actual = signatures(runtime), signatures(physical)
    if expected is None or actual is None:
        return {'status': 'NOT_COLLECTED', 'runtimeAvailable': expected is not None, 'mysqlAvailable': actual is not None}
    differences = {}
    for name in ('primaryKey', 'foreignKeys', 'uniqueKeys'):
        if expected[name] != actual[name]:
            differences[name] = {'runtime': expected[name], 'mysql': actual[name]}
    if expected['unsupported'] or actual['unsupported']:
        differences['unsupported'] = {'runtime': expected['unsupported'], 'mysql': actual['unsupported']}
    return {'status': 'REVIEW_REQUIRED' if differences else 'MATCH', 'differences': differences}
