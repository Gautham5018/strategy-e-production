import argparse,csv,json,re
from pathlib import Path
def sym(f):
    m=re.match(r"^(.+?)_5minute$",Path(f).stem,re.I);return (m.group(1) if m else Path(f).stem).upper()
def main():
    p=argparse.ArgumentParser();p.add_argument('--universe',required=True);p.add_argument('--cache-dir',required=True);a=p.parse_args(); syms=[]
    for x in Path(a.universe).read_text(encoding='utf-8').splitlines():
        x=x.strip().upper()
        if x and not x.startswith('#') and x not in syms:syms.append(x)
    files={sym(f):f for f in Path(a.cache_dir).glob('*.csv')}
    missing=sorted(set(syms)-set(files)); present=sorted(set(syms)&set(files))
    out={'universe':len(syms),'cache_files':len(files),'covered':len(present),'missing':len(missing),'missing_symbols':missing,'extra_cache_symbols':sorted(set(files)-set(syms))}
    print(json.dumps(out,indent=2))
if __name__=='__main__':main()
