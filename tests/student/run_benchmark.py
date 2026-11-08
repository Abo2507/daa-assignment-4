"""Compile and run the Java search benchmark; only measured results are recorded."""
from __future__ import annotations
import argparse
import ctypes
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True
from run_tests import windows_probe

ROOT = Path(__file__).resolve().parents[2]

def environment():
    result = {'platform': platform.platform(), 'python': sys.version,
              'logical_cpus': os.cpu_count(), 'processor': platform.processor()}
    if os.name == 'nt':
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
            result['processor'] = winreg.QueryValueEx(key, 'ProcessorNameString')[0].strip()
        class Memory(ctypes.Structure):
            _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong) for name in ('total_physical', 'available_physical',
                'total_pagefile', 'available_pagefile', 'total_virtual', 'available_virtual', 'extended_virtual')]
        memory = Memory()
        memory.length = ctypes.sizeof(memory)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
            result['physical_ram_bytes'] = memory.total_physical
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=ROOT / 'tests/student/benchmark-results.json')
    args = parser.parse_args()
    java, javac = shutil.which('java'), shutil.which('javac')
    if not java or not javac:
        parser.error('JDK 17+ must be on PATH')
    build = ROOT / 'Java/build/student-benchmark'
    build.mkdir(parents=True, exist_ok=True)
    compile_command = [javac, '--release', '17', '-encoding', 'UTF-8', '-d', str(build),
                       *map(str, sorted((ROOT / 'Java/source').glob('*.java'))),
                       str(ROOT / 'tests/student/SearchBenchmark.java')]
    compilation = subprocess.run(compile_command, capture_output=True, text=True, timeout=60)
    if compilation.returncode:
        print(compilation.stderr, file=sys.stderr)
        return compilation.returncode
    command = [java, '-Xmx384m', '-XX:ActiveProcessorCount=1', '-XX:+UseSerialGC',
               '-cp', str(build), 'SearchBenchmark']
    started = time.perf_counter()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _, pinned = windows_probe(process)
    try:
        output, errors = process.communicate(timeout=20)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        print('Benchmark exceeded 20 seconds; no successful result recorded', file=sys.stderr)
        return 1
    wall = time.perf_counter() - started
    if process.returncode:
        print(errors.decode('utf-8', errors='replace'), file=sys.stderr)
        return process.returncode
    benchmark = json.loads(output.decode('utf-8'))
    assert len(benchmark['rows']) == 18
    assert all(row['correct_outputs_checked'] and len(row['elapsed_ns']) == 3 for row in benchmark['rows'])
    report = {'environment': environment(), 'compile_command': compile_command,
              'compile_exit_code': compilation.returncode, 'compile_stderr': compilation.stderr,
              'command': command, 'exit_code': process.returncode,
              'single_cpu_affinity': pinned, 'wall_seconds': wall, 'benchmark': benchmark}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    for row in benchmark['rows']:
        print(f"{row['case']} n={row['n']} m={row['m']} {row['algorithm']}: "
              f"{row['median_ns_per_call'] / 1000:.3f} us/call median; "
              f"{row['repetitions_per_trial']} calls/trial; correct")
    print(f'54 measured trials completed in {wall:.3f}s; one CPU affinity={pinned}; report: {args.report}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
