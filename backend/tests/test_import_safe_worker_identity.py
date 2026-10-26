"""Default lease identities must not read the host during module initialization."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest

SERVICES = Path(__file__).resolve().parents[1] / 'app/services'
MODULES = (
    'approval_export_service.py',
    'affairs_leave_export_service.py',
    'affairs_funding_export_service.py',
    'affairs_appeal_repair_service.py',
)


def initialize_identity(filename: str) -> str:
    tree = ast.parse((SERVICES / filename).read_text(encoding='utf-8'))
    assignments = [node for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == '_WORKER_ID'
                           for target in node.targets)]
    assert len(assignments) == 1

    def forbidden_hostname():
        raise RuntimeError('worker initialization attempted a hostname read')

    namespace = {'uuid': uuid, 'socket': SimpleNamespace(gethostname=forbidden_hostname)}
    expression = ast.Expression(body=assignments[0].value)
    return eval(compile(expression, str(SERVICES / filename), 'eval'), namespace)


@pytest.mark.parametrize('filename', MODULES)
def test_default_lease_identity_needs_no_hostname_and_is_unique_per_load(filename):
    first = initialize_identity(filename)
    second = initialize_identity(filename)
    assert isinstance(first, str) and 0 < len(first) <= 128
    assert first != second
