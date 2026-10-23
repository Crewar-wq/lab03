#!/usr/bin/env python3
"""Run all model/database checks and preserve the actual execution evidence."""
from pathlib import Path
import argparse
import json
import platform
import sqlite3
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,default=ROOT/'artifacts')
args=parser.parse_args()
args.output.mkdir(parents=True,exist_ok=True)
tests=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,capture_output=True,text=True)
log=tests.stdout+tests.stderr
(args.output/'checks.txt').write_text(log,encoding='utf-8',newline='\n')
print(log,end='')
if tests.returncode:sys.exit(tests.returncode)
subprocess.run([sys.executable,str(ROOT/'scripts/demo_scenarios.py'),'--output',str(args.output/'scenarios.json')],check=True)
versions={'python':platform.python_version(),'sqlite':sqlite3.sqlite_version,'status':'passed'}
(args.output/'environment.json').write_text(json.dumps(versions,indent=2)+'\n',encoding='utf-8',newline='\n')
print('All model and database verification stages passed')
