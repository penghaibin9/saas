"""Offline code-resource runner. No database, school API, tokens or formal writes."""
import argparse,json,pathlib,sys,hashlib


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--facts',required=True,type=pathlib.Path)
    parser.add_argument('--plan',required=True,type=pathlib.Path)
    parser.add_argument('--output',required=True,type=pathlib.Path)
    parser.add_argument('--dependencies',type=pathlib.Path)
    parser.add_argument('--seconds',type=float,default=10)
    args=parser.parse_args()
    sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'app/modules/academic_affairs'))
    if args.dependencies:sys.path.insert(0,str(args.dependencies.resolve()))
    from optimizer.source_builder import compile_source,source_revision
    from optimizer.solver import solve
    from optimizer.options import normalize_options
    def unique_object(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('DUPLICATE_JSON_KEY')
            result[key]=value
        return result
    def read(path):
        if not path.is_file() or path.stat().st_size>32*1024*1024:raise ValueError('INPUT_SIZE_INVALID')
        return json.loads(path.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_object)
    facts=read(args.facts);plan=read(args.plan)
    snapshot,binding=compile_source(facts,plan,expected_revision=source_revision(facts))
    options=normalize_options({'time_limit':args.seconds},snapshot)
    result=solve(snapshot,**options)
    output=args.output.resolve()
    if output.exists():raise ValueError('OUTPUT_EXISTS_NO_OVERWRITE')
    output.mkdir(parents=True,exist_ok=False)
    objects={'snapshot.json':snapshot.raw,'binding.json':binding,'result.json':result}
    checksums={}
    for name,value in objects.items():
        data=(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8')
        (output/name).write_bytes(data);checksums[name]=hashlib.sha256(data).hexdigest()
    manifest={'status':result['status'],'trustMode':'OFFLINE_INPUT_NOT_AUTHENTICATED_SCHOOL_DATA',
        'formalApplyAllowed':False,'files':checksums,'sourceRevision':source_revision(facts),
        'inputHash':snapshot.input_hash,'algorithmVersion':result['algorithmVersion']}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(output),'status':result['status'],'activities':len(result.get('choices',{})),
                      'formalApplyAllowed':False,'validation':result.get('validation',[])},ensure_ascii=False))
    return 0 if result['status']=='FEASIBLE' else 3

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'status':'FAILED','type':type(error).__name__,'reasonCode':getattr(error,'code',None)},ensure_ascii=False))
        raise SystemExit(2)
