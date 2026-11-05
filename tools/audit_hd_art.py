#!/usr/bin/env python3
"""
Lists images whose sequences still use classic (non-HD) art, for docs/DESIGN-IDEAS.md IDEA-30.

  python3 tools/audit_hd_art.py      (run from the repo root)

Resolves every sequence file in mod.yaml order (HD files override classic ones) and keeps images that the rules,
weapons or maps mention. Some listed sequences are never drawn because the mod replaces them in code
(shroud, rallypoint, bib, icon).
"""
import glob
import re
ROOT='mods/rapx'
def parse(path):
    """Tiny MiniYaml parser -> nested list of (key, value, children)."""
    root=[]; stack=[(-1,root)]
    for raw in open(path, encoding='utf-8'):
        line=raw.rstrip('\n')
        if not line.strip() or line.lstrip().startswith('#'): continue
        depth=len(line)-len(line.lstrip('\t'))
        s=line.strip()
        k,_,v=s.partition(':')
        v=v.split('#')[0].strip()
        node=(k.strip(),v,[])
        while stack[-1][0]>=depth: stack.pop()
        stack[-1][1].append(node); stack.append((depth,node[2]))
    return root
mod=open(f'{ROOT}/mod.yaml').read()
seqfiles=re.findall(r'ra\|(sequences/\S+)', mod.split('\nSequences:')[1].split('\n\n')[0])
images={}   # image -> {seq: {'Filename':..., 'src':file}}, defaults
templates={}
for f in seqfiles:
    for k,v,ch in parse(f'{ROOT}/{f}'):
        img=images.setdefault(k,{'seqs':{},'defaults':{},'files':set()})
        img['files'].add(f)
        for sk,sv,sch in ch:
            if sk=='Defaults':
                for a,b,_ in sch: img['defaults'][a]=(b,f)
                continue
            if sk=='Inherits': continue
            if sk.startswith('-'):
                img['seqs'].pop(sk[1:],None); continue
            d=img['seqs'].setdefault(sk,{})
            for a,b,_ in sch: d[a]=(b,f)
# resolve; template images (^) inherited
def resolve(name):
    img=images[name]; out={}
    for s,d in img['seqs'].items():
        fn=d.get('Filename') or img['defaults'].get('Filename')
        out[s]=fn[0] if fn else None
    return out
# references from rules + weapons
reftext=''
for f in glob.glob(f'{ROOT}/rules/*.yaml')+glob.glob(f'{ROOT}/weapons/*.yaml')+glob.glob(f'{ROOT}/maps/*/*.yaml'):
    reftext+=open(f,encoding='utf-8',errors='ignore').read().lower()+'\n'
res={}
for name in images:
    if name.startswith('^'): continue
    r=resolve(name)
    hd=[s for s,fn in r.items() if fn and '/hd/' in fn]
    cl=[s for s,fn in r.items() if not (fn and '/hd/' in fn)]
    used=bool(re.search(r'(?<![\w.-])'+re.escape(name.lower())+r'(?![\w-])', reftext))
    res[name]={'hd':hd,'classic':cl,'used':used,'files':sorted(images[name]['files']),
               'cfiles':sorted({(r[s] or '?') for s in cl})[:4]}
for n,v in sorted(res.items()):
    if v['used'] and v['classic'] and n not in ('harvempty','harvhalf'):
        print(f"{'CLASSIC' if not v['hd'] else 'PARTLY ':8} {n:16} {','.join(v['classic'][:12])}")
full=[n for n,v in res.items() if not v['hd']]; part=[n for n,v in res.items() if v['hd'] and v['classic']]
print(f'images {len(res)}: no HD at all {len(full)}, partly HD {len(part)}')
