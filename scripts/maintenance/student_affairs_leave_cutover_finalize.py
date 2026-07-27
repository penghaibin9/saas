from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_cutover():
    script = Path(__file__).with_name("student_affairs_leave_cutover_followup.py")
    spec = spec_from_file_location("student_affairs_leave_cutover_followup", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载施工脚本：{script}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cutover = _load_cutover()


if __name__ == "__main__":
    print("CUTOVER_FINALIZE first_cut", flush=True)
    cutover.first_cut_rerunnable()
    print("CUTOVER_FINALIZE second_cut", flush=True)
    cutover.base.second_cut()
    print("CUTOVER_FINALIZE route_ownership", flush=True)
    cutover.patch_route_ownership()
    print("CUTOVER_FINALIZE generic_entrypoints", flush=True)
    cutover.block_generic_leave_entrypoints()
    print("CUTOVER_FINALIZE runtime_contract", flush=True)
    cutover.absorb_leave_runtime_contract()
    print("CUTOVER_FINALIZE contract_test", flush=True)
    cutover.write_cutover_contract_test()
    print("CUTOVER_FINALIZE audit", flush=True)
    cutover.base.audit()
    cutover.audit_versions()
    print("leave cutover finalize audit passed", flush=True)
