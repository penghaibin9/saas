"""OS-process deadline and cancellation boundary, independent of CP-SAT cooperative timing."""
import importlib.util,json,pathlib,subprocess,sys,time
from .contracts import canonical,InputError
from .options import normalize_options
from .validation import validate_solution


def solve_supervised(snapshot,*,cancelled=lambda:False,hard_timeout=None,**options):
    options=normalize_options(options,snapshot)
    def response(status,code,**extra):
        return {'status':status,'inputHash':snapshot.input_hash,'choices':{},'publishable':False,
                'diagnostics':[{'code':code}],**extra}
    if cancelled():return response('CANCELLED','CANCELLED_BEFORE_START')
    spec=importlib.util.find_spec('ortools')
    if not spec or not spec.origin:return response('DEPENDENCY_MISSING','SOLVER_DEPENDENCY_MISSING')
    timeout=hard_timeout if hard_timeout is not None else options['time_limit']+10
    if isinstance(timeout,bool) or not isinstance(timeout,(float,int)) or not 0<timeout<=620:
        raise InputError('PROCESS_TIMEOUT_INVALID','0..620 seconds')
    request=canonical({'snapshot':snapshot.raw,'options':options}).encode('utf-8')
    if len(request)>48*1024*1024:raise InputError('PROCESS_INPUT_LIMIT','48 MiB')
    dependency_root=str(pathlib.Path(spec.origin).resolve().parent.parent)
    command=[sys.executable,'-I','-B',str(pathlib.Path(__file__).with_name('isolated_solver_process.py')),dependency_root]
    started=time.perf_counter();deadline=started+timeout
    process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    first=True
    try:
        while True:
            stop=cancelled();remaining=deadline-time.perf_counter()
            if stop or remaining<=0:
                process.terminate()
                try:process.communicate(timeout=2)
                except subprocess.TimeoutExpired:process.kill();process.communicate(timeout=2)
                return response('CANCELLED' if stop else 'UNKNOWN','PROCESS_CANCELLED' if stop else 'PROCESS_DEADLINE',
                    workerTerminated=True,workerExitCode=process.returncode,elapsedSeconds=round(time.perf_counter()-started,6))
            try:
                stdout,stderr=process.communicate(input=request if first else None,timeout=min(.2,remaining))
                break
            except subprocess.TimeoutExpired:first=False
        if len(stdout)>16*1024*1024:return response('FAILED','PROCESS_OUTPUT_LIMIT')
        result=json.loads(stdout)
        if process.returncode!=0 or result.get('inputHash')!=snapshot.input_hash:
            return response('FAILED','PROCESS_RESULT_INVALID',workerExitCode=process.returncode)
        if result.get('status')=='FEASIBLE':
            errors=validate_solution(snapshot,result.get('choices',{}))
            if errors:return response('FAILED','PROCESS_RESULT_VALIDATION_FAILED')
        result['processElapsedSeconds']=round(time.perf_counter()-started,6)
        result['processExitCode']=process.returncode
        return result
    finally:
        if process.poll() is None:
            process.kill();process.communicate(timeout=2)
