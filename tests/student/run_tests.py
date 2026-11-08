"""Deterministic independent checks for the Java implementation (Python 3.12+)."""
from __future__ import annotations

import argparse
import collections
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import shutil
import subprocess
import sys
import threading
import time
from functools import lru_cache

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from public_validate import check as public_check

SEED = 20261108
TIME_LIMIT = 20
OUTPUT_LIMIT = 8 * 1024 * 1024
JAVA_OPTIONS = ["-Xmx384m", "-XX:ActiveProcessorCount=1", "-XX:+UseSerialGC"]


def occurrences(text, pattern):
    return [i for i in range(len(text) - len(pattern) + 1)
            if text.startswith(pattern, i)]


def lcs_brute(a, b):
    short, other = sorted((a, b), key=len)
    best = ""
    for mask in range(1 << len(short)):
        if mask.bit_count() <= len(best):
            continue
        candidate = "".join(c for i, c in enumerate(short) if mask & (1 << i))
        iterator = iter(other)
        if all(any(c == value for value in iterator) for c in candidate):
            best = candidate
    return {"length": len(best), "sequence": best}


@lru_cache(maxsize=None)
def merge_brute(blocks):
    # Enumerate every possible next ADJACENT action, not interval-DP splits.
    if len(blocks) <= 1:
        return 0
    return min(blocks[i] + blocks[i + 1] +
               merge_brute(blocks[:i] + (blocks[i] + blocks[i + 1],) + blocks[i + 2:])
               for i in range(len(blocks) - 1))


def tree_brute(request):
    n, weights, edges = request["n"], request["weights"], request["edges"]
    best = 0
    for mask in range(1 << n):
        if any(mask & (1 << u) and mask & (1 << v) for u, v in edges):
            continue
        best = max(best, sum(w for i, w in enumerate(weights) if mask & (1 << i)))
    return {"weight": best}


def suffix_brute(text):
    # Materialising suffixes is intentionally restricted to the SMALL oracle.
    sa = sorted(range(len(text)), key=lambda i: text[i:])
    lcp = [0] * len(text)
    for j in range(1, len(sa)):
        a, b, common = sa[j - 1], sa[j], 0
        while a + common < len(text) and b + common < len(text) and text[a + common] == text[b + common]:
            common += 1
        lcp[j] = common
    best = max(range(len(lcp)), key=lcp.__getitem__) if lcp else 0
    return {"sa": sa, "lcp": lcp,
            "repeated": text[sa[best]:sa[best] + lcp[best]] if sa else ""}


def oracle(request):
    task = request["task"]
    if task == "lcs":
        return lcs_brute(request["a"], request["b"])
    if task == "merge":
        return {"cost": merge_brute(tuple(request["sizes"]))}
    if task == "tree":
        return tree_brute(request)
    if task in ("naive", "kmp", "rk"):
        return {"positions": occurrences(request["text"], request["pattern"])}
    if task == "suffix":
        return suffix_brute(request["text"])
    if task == "aho":
        return {"counts": [[len(occurrences(text, pattern)) for pattern in request["patterns"]]
                           for text in request["texts"]]}
    raise ValueError(task)


def random_cases():
    rng = random.Random(SEED)
    cases = []
    def word(maximum, alphabet="ab A!"):
        return "".join(rng.choice(alphabet) for _ in range(rng.randrange(maximum + 1)))
    def add(name, request):
        cases.append({"name": name, "reason": "Independent exhaustive/direct oracle; fixed seed.",
                      "input": request, "output": oracle(request)})
    for i in range(100):
        add(f"random-lcs-{i:03}", {"task": "lcs", "a": word(10), "b": word(10)})
    for i in range(80):
        add(f"random-merge-{i:03}", {"task": "merge", "sizes": [rng.randrange(12) for _ in range(rng.randrange(8))]})
    for i in range(100):
        n = rng.randrange(12)
        labels = list(range(n))
        rng.shuffle(labels)
        edges = [[labels[i], labels[rng.randrange(i)]] for i in range(1, n)]
        rng.shuffle(edges)
        add(f"random-tree-{i:03}", {"task": "tree", "n": n,
                                   "weights": [rng.randrange(-9, 12) for _ in range(n)], "edges": edges})
    for i in range(100):
        text, pattern = word(40), word(10)
        for task in ("naive", "kmp", "rk"):
            add(f"random-{task}-{i:03}", {"task": task, "text": text, "pattern": pattern})
    for i in range(100):
        add(f"random-suffix-{i:03}", {"task": "suffix", "text": word(40)})
    for i in range(100):
        patterns = [word(5) or "a" for _ in range(rng.randrange(10))]
        if patterns and i % 2 == 0:
            patterns.append(patterns[0])
        texts = [word(30) for _ in range(rng.randrange(6))]
        if texts:
            texts += [texts[0], ""]
        add(f"random-aho-{i:03}", {"task": "aho", "patterns": patterns, "texts": texts})
    rng.shuffle(cases)
    return cases


def lcs_bitset_length(a, b):
    # A distinct bit-parallel oracle for the full-size random case.
    masks = {}
    for i, character in enumerate(b):
        masks[character] = masks.get(character, 0) | (1 << i)
    row = 0
    for character in a:
        matches = masks.get(character, 0) | row
        row = matches & ~(matches - ((row << 1) | 1))
    return row.bit_count()


def stress_cases():
    rng = random.Random(SEED + 1)
    def case(name, request, expected, reason, validator="public"):
        return {"name": name, "input": request, "output": expected,
                "reason": reason, "validator": validator}
    a = "".join(rng.choice("abcd") for _ in range(1000))
    b = "".join(rng.choice("abcd") for _ in range(1000))
    for name, first, second, length in (
        ("lcs-limit-identical", "a" * 1000, "a" * 1000, 1000),
        ("lcs-limit-disjoint", "a" * 1000, "b" * 1000, 0),
        ("lcs-limit-tie", "ab" * 500, "ba" * 500, 999),
        ("lcs-limit-random", a, b, lcs_bitset_length(a, b)),
    ):
        yield case(name, {"task": "lcs", "a": first, "b": second}, {"length": length},
                   "1000 x 1000; verify optimum and reconstructed subsequence.")
    yield case("merge-limit-64bit", {"task": "merge", "sizes": [10**9] * 200},
               {"cost": 1544 * 10**9},
               "200 equal leaves: optimal external path length 200*8-(256-200)=1544; chronological witness.")
    yield case("merge-limit-zeros", {"task": "merge", "sizes": [0] * 200}, {"cost": 0},
               "200 blocks, many optima; all 199 chronological operations required.")
    n = 100000
    for name, weights, edges, best in (
        ("tree-limit-deep-chain", [10**9] * n, [[i - 1, i] for i in range(1, n)], n // 2 * 10**9),
        ("tree-limit-star", [10**9] * n, [[0, i] for i in range(1, n)], (n - 1) * 10**9),
        ("tree-limit-negative", [-10**9] * n, [[i - 1, i] for i in range(1, n)], 0),
    ):
        yield case(name, {"task": "tree", "n": n, "weights": weights, "edges": edges},
                   {"weight": best}, "100000 vertices; exact weight, unique valid reconstructed set, no recursion overflow.")
    for task, size, pattern_size in (("naive", 3000, 1500), ("kmp", 200000, 100000), ("rk", 10000, 2000)):
        for label, pattern, expected in (
            ("dense", "a" * pattern_size, list(range(size - pattern_size + 1))),
            ("late-mismatch", "a" * (pattern_size - 1) + "b", []),
            ("empty-pattern", "", list(range(size + 1))),
        ):
            yield case(f"{task}-limit-{label}", {"task": task, "text": "a" * size, "pattern": pattern},
                       {"positions": expected}, "Maximum text length; all starts checked exactly; RK n*m <= 20000000.")
    yield case("naive-maximum-pattern", {"task": "naive", "text": "a" * 3000, "pattern": "a" * 3000},
               {"positions": [0]}, "Both naive string length bounds.")
    yield case("rk-maximum-pattern-longer", {"task": "rk", "text": "a" * 2000, "pattern": "a" * 10000},
               {"positions": []}, "Maximum RK pattern, valid n*m=20000000, no invalid initial window.")
    yield case("kmp-maximum-pattern-longer", {"task": "kmp", "text": "a", "pattern": "a" * 100000},
               {"positions": []}, "Pattern longer than text at maximum pattern length.")
    n = 50000
    yield case("suffix-limit-equal", {"task": "suffix", "text": "a" * n},
               {"sa": list(range(n - 1, -1, -1)), "lcp": list(range(n)), "repeated": "a" * (n - 1)},
               "50000 equal characters; closed-form SA/LCP avoids quadratic oracle.", "exact")
    periodic = "ab" * (n // 2)
    periodic_sa = list(range(n - 2, -1, -2)) + list(range(n - 1, 0, -2))
    periodic_lcp = list(range(0, n, 2)) + [0] + list(range(1, n - 1, 2))
    yield case("suffix-limit-periodic", {"task": "suffix", "text": periodic},
               {"sa": periodic_sa, "lcp": periodic_lcp, "repeated": periodic[:-2]},
               "50000 periodic characters; closed-form ranks/LCP, overlapping longest repeat.", "exact")
    random_text = "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(n))
    yield case("suffix-limit-random", {"task": "suffix", "text": random_text}, None,
               "50000 random characters; verify permutation, every adjacent suffix order and exact LCP directly.",
               "suffix-adjacent")
    yield case("aho-limit-long-pattern", {"task": "aho", "patterns": ["a" * 100000],
                                        "texts": ["a" * 200000]},
               {"counts": [[100001]]}, "100000 pattern characters, 100001 trie states, 200000 text characters.")
    yield case("aho-limit-states-100-texts", {"task": "aho", "patterns": ["a" * 100000],
                                           "texts": ["a" * 2000] * 100},
               {"counts": [[0]] * 100}, "Maximum trie depth/states and text count; no state/count leakage.")
    yield case("aho-limit-duplicates-dense", {"task": "aho", "patterns": ["a" * 10] * 10000,
                                            "texts": ["a" * 200000]},
               {"counts": [[199991] * 10000]}, "10000 duplicate positions, total pattern length 100000; aggregate dense matches.")
    yield case("aho-limit-output-matrix", {"task": "aho", "patterns": ["a" * 10] * 10000,
                                         "texts": ["a" * 2000] * 100},
               {"counts": [[1991] * 10000] * 100},
               "Maximum p=10000, q=100, total pattern length 100000 and text length 200000; one million exact counts.")
    lengths = list(range(1, 447)) + [319]
    yield case("aho-limit-suffix-density", {"task": "aho", "patterns": ["a" * k for k in lengths],
                                          "texts": ["a" * 200000]},
               {"counts": [[200001 - k for k in lengths]]},
               "Total pattern length exactly 100000; dense suffix-pattern matches and a duplicate.")
    alphabet = "".join(chr(i) for i in range(32, 127) if chr(i) != "a")
    patterns = ["".join(rng.choice(alphabet) for _ in range(10)) for _ in range(10000)]
    yield case("aho-limit-branching", {"task": "aho", "patterns": patterns, "texts": ["a" * 200000]},
               {"counts": [[0] * 10000]}, "100000 dictionary characters across a broad printable-ASCII trie.")


def windows_probe(process):
    """Return (poll_memory, pin_one_cpu); None metrics on non-Windows hosts."""
    if os.name != "nt":
        return lambda: {}, False
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in (
                "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
                "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage",
                "PeakPagefileUsage", "PrivateUsage")]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.GetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
    kernel.GetProcessAffinityMask.restype = wintypes.BOOL
    kernel.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
    kernel.SetProcessAffinityMask.restype = wintypes.BOOL
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    handle = wintypes.HANDLE(int(process._handle))
    process_mask, system_mask = ctypes.c_size_t(), ctypes.c_size_t()
    pinned = False
    if kernel.GetProcessAffinityMask(handle, ctypes.byref(process_mask), ctypes.byref(system_mask)):
        bit = process_mask.value & -process_mask.value
        pinned = bool(bit and kernel.SetProcessAffinityMask(handle, bit))
    def poll():
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return {"peak_working_set_bytes": counters.PeakWorkingSetSize,
                    "sampled_private_bytes": counters.PrivateUsage}
        return {}
    return poll, pinned


def execute(command, cases):
    data = "".join(json.dumps(case["input"], separators=(",", ":")) + "\n" for case in cases).encode("utf-8")
    began = time.perf_counter()
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    poll_memory, pinned = windows_probe(process)
    peak = poll_memory()
    stop = threading.Event()
    def monitor():
        while not stop.wait(0.01):
            for key, value in poll_memory().items():
                peak[key] = max(peak.get(key, 0), value)
    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()
    error = None
    try:
        stdout, stderr = process.communicate(data, timeout=TIME_LIMIT)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        error = f"Java batch exceeded {TIME_LIMIT} seconds"
    finally:
        for key, value in poll_memory().items():
            peak[key] = max(peak.get(key, 0), value)
        stop.set()
        monitor_thread.join()
    metrics = {"wall_seconds": round(time.perf_counter() - began, 6), "input_bytes": len(data),
               "output_bytes": len(stdout), "exit_code": process.returncode, "single_cpu_affinity": pinned, **peak}
    if not error and process.returncode:
        error = f"Java exit {process.returncode}: {stderr.decode('utf-8', errors='replace')[:2000]}"
    if not error and len(stdout) > OUTPUT_LIMIT:
        error = f"Output exceeds {OUTPUT_LIMIT} bytes"
    if not error and peak.get("peak_working_set_bytes", 0) > 768 * 1024 * 1024:
        error = "Observed Java working set exceeds 768 MiB"
    answers = []
    if not error:
        try:
            lines = stdout.decode("utf-8").splitlines()
            if len(lines) != len(cases):
                raise ValueError(f"Expected {len(cases)} JSON lines, received {len(lines)}")
            def reject_constant(value):
                raise ValueError(f"Invalid JSON constant {value}")
            answers = [json.loads(line, parse_constant=reject_constant) for line in lines]
            if any(type(answer) is not dict for answer in answers):
                raise ValueError("Every result must be a JSON object")
        except (ValueError, UnicodeError) as exception:
            error = str(exception)
    return answers, metrics, error


def suffix_adjacent_check(request, answer):
    text = request["text"]
    n = len(text)
    sa, lcp, repeated = answer.get("sa"), answer.get("lcp"), answer.get("repeated")
    if not isinstance(sa, list) or not isinstance(lcp, list) or not isinstance(repeated, str):
        return False
    if len(sa) != n or len(lcp) != n or any(type(v) is not int for v in sa + lcp):
        return False
    if sorted(sa) != list(range(n)) or (n and lcp[0] != 0):
        return False
    longest = 0
    for i in range(1, n):
        left, right, common = sa[i - 1], sa[i], 0
        while left + common < n and right + common < n and text[left + common] == text[right + common]:
            common += 1
        if lcp[i] != common or right + common == n:
            return False
        if left + common < n and text[left + common] >= text[right + common]:
            return False
        longest = max(longest, common)
    if len(repeated) != longest:
        return False
    if not repeated:
        return True
    first = text.find(repeated)
    return first >= 0 and text.find(repeated, first + 1) >= 0


def validate(case, answer):
    mode = case.get("validator", "public")
    if mode == "exact":
        expected = case["output"]
        if any(type(value) is not int for key in ("sa", "lcp") for value in answer.get(key, [])):
            return False
        return all(answer.get(key) == value for key, value in expected.items())
    if mode == "suffix-adjacent":
        return suffix_adjacent_check(case["input"], answer)
    return public_check(case["input"], answer, case["output"])


def compact(value):
    raw = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode()
    if len(raw) <= 3000:
        return value
    result = {"serialized_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    if isinstance(value, dict):
        result["fields"] = {}
        for key, item in value.items():
            if isinstance(item, (list, str)):
                result["fields"][key] = {"length": len(item)}
                if isinstance(item, list) and item and isinstance(item[0], list):
                    result["fields"][key]["row_lengths"] = sorted(set(map(len, item)))
                elif isinstance(item, list):
                    result["fields"][key]["first"] = item[:5]
                    result["fields"][key]["last"] = item[-5:]
            else:
                result["fields"][key] = item
    return result


def run_batch(command, label, cases, records, batches):
    answers, metrics, error = execute(command, cases)
    failed = 0
    for i, case in enumerate(cases):
        answer = answers[i] if i < len(answers) else None
        try:
            okay = not error and validate(case, answer)
        except (ValueError, TypeError, KeyError, IndexError) as exception:
            okay = False
            detail = str(exception)
        else:
            detail = error or ("Output does not satisfy independent expectation/witness checks" if not okay else "")
        failed += not okay
        records.append({"name": case["name"], "batch": label, "task": case["input"]["task"],
                        "status": "PASS" if okay else "FAIL", "reason": case["reason"],
                        "input": compact(case["input"]), "expected": compact(case["output"]),
                        "actual": compact(answer), **({"error": detail} if not okay else {})})
    batches.append({"name": label, "cases": len(cases), "passed": len(cases) - failed,
                    "failed": failed, **metrics, **({"error": error} if error else {})})
    peak_mib = metrics.get("peak_working_set_bytes", 0) / 1024**2
    print(f"{'PASS' if not failed else 'FAIL'} {label}: {len(cases) - failed}/{len(cases)}, "
          f"{metrics['wall_seconds']:.3f}s, {metrics['output_bytes']} output bytes, "
          f"{peak_mib:.1f} MiB observed peak working set", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--skip-build", action="store_true", help="Use the already compiled Java/build classes")
    parser.add_argument("--only", choices=("all", "small", "stress", "stress-batches"), default="all")
    args = parser.parse_args()
    if args.report is None:
        report_name = "stress-batches-results.json" if args.only == "stress-batches" else "results.json"
        args.report = ROOT / "tests/student" / report_name
    java, javac = shutil.which("java"), shutil.which("javac")
    if not java or (not javac and not args.skip_build):
        parser.error("JDK 17+ java and javac must be on PATH")
    build = ROOT / "Java/build"
    compilation = {"skipped": args.skip_build}
    if not args.skip_build:
        build.mkdir(exist_ok=True)
        command = [javac, "--release", "17", "-encoding", "UTF-8", "-d", str(build),
                   *map(str, sorted((ROOT / "Java/source").glob("*.java")))]
        start = time.perf_counter()
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        compilation = {"skipped": False, "exit_code": result.returncode,
                       "wall_seconds": round(time.perf_counter() - start, 6),
                       "stderr": result.stderr, "command": command}
        if result.returncode:
            print(result.stderr, file=sys.stderr)
            return result.returncode
    command = [java, *JAVA_OPTIONS, "-cp", str(build), "Main"]
    records, batches = [], []
    if args.only in ("all", "small"):
        fixed = json.loads((ROOT / "tests/student/cases.json").read_text(encoding="utf-8-sig"))
        small = fixed + random_cases()
        run_batch(command, "fixed-and-random-mixed", small, records, batches)
        replay = [{**case, "name": "replay-" + case["name"]} for case in reversed(small)]
        run_batch(command, "two-mixed-batches-one-process", small + replay, records, batches)
    if args.only in ("all", "stress"):
        for case in stress_cases():
            run_batch(command, case["name"], [case], records, batches)
    if args.only == "stress-batches":
        grouped = collections.defaultdict(list)
        for case in stress_cases():
            grouped[case["input"]["task"]].append(case)
        for task, cases in grouped.items():
            run_batch(command, "grouped-stress-" + task, cases, records, batches)
    counts = collections.Counter(record["task"] for record in records)
    passed = sum(record["status"] == "PASS" for record in records)
    report = {
        "seed": SEED, "python": sys.version, "platform": platform.platform(),
        "java_version": subprocess.run([java, "-version"], capture_output=True, text=True).stderr.strip(),
        "command": command, "compilation": compilation,
        "limits": {"batch_seconds": TIME_LIMIT, "output_bytes": OUTPUT_LIMIT,
                   "java_heap_mib": 384, "java_active_processors": 1,
                   "memory_note": "Windows OS-reported peak working set observed during execution; private bytes sampled every 10ms. These process metrics are not an official container-memory measurement."},
        "summary": {"total_executed_cases": len(records), "passed": passed, "failed": len(records) - passed,
                    "by_task": dict(sorted(counts.items())),
                    "max_batch_wall_seconds": max((batch["wall_seconds"] for batch in batches), default=0),
                    "max_output_bytes": max((batch["output_bytes"] for batch in batches), default=0),
                    "max_observed_peak_working_set_bytes": max((batch.get("peak_working_set_bytes", 0) for batch in batches), default=0),
                    "all_windows_batches_pinned_one_cpu": all(batch["single_cpu_affinity"] for batch in batches) if os.name == "nt" else None},
        "batches": batches, "cases": records,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"TOTAL {passed}/{len(records)} passed; report: {args.report}", flush=True)
    return int(passed != len(records))


if __name__ == "__main__":
    raise SystemExit(main())
