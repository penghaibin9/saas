"""Private bounded solver subprocess entry. No application, HTTP or database imports."""
import sys,json,pathlib
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
if len(sys.argv)==2:sys.path.insert(0,sys.argv[1])

def main():
    from optimizer.contracts import Snapshot,InputError
    from optimizer.options import normalize_options
    from optimizer.solver import solve
    raw=sys.stdin.buffer.read(48*1024*1024+1)
    if len(raw)>48*1024*1024:raise InputError('PROCESS_INPUT_LIMIT','48 MiB')
    request=json.loads(raw)
    snapshot=Snapshot.parse(request['snapshot'])
    result=solve(snapshot,**normalize_options(request['options'],snapshot))
    sys.stdout.write(json.dumps(result,ensure_ascii=True,separators=(',',':'),allow_nan=False))

if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'status':'FAILED','publishable':False,'choices':{},
                          'diagnostics':[{'code':getattr(error,'code','CHILD_ERROR'),'type':type(error).__name__}]}))
        raise SystemExit(2)
