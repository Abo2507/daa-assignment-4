# Student tests

These independent tests supplement the official 44 public cases without changing
their inputs, validators or contracts.

## Run

From the repository root, with Python 3.12+ and JDK 17+ on PATH:

~~~text
python tests/student/run_tests.py --report tests/student/results.json
~~~

The runner compiles Java with --release 17, then calls Main through its unchanged
UTF-8 JSON Lines interface. Use --skip-build after a successful compilation;
--only small and --only stress select individual suites.

The official launcher does not automatically discover this directory:
tools/run.py --check reads tests/public.json only. Its --input mode executes
requests but does not compare answers with expected results.

## Independent expectations and regression fixtures

cases.json contains 57 named fixtures with inputs, expected optimum values or
answers, and a description of the defect each case detects. For LCS, merge and
tree, reconstructed witnesses are checked semantically: an alternative optimal
sequence, merge plan or independent set is accepted.

The runner additionally generates 780 cases with seed 20261108: 100 LCS, 80 merge,
100 tree, 100 shared search inputs checked by all three algorithms, 100 suffix
and 100 Aho requests. Their independent oracles are:

- LCS: enumerate subsequences of the shorter string.
- Merge: enumerate all choices of the next adjacent merge, with memoization.
- Tree: enumerate vertex subsets and reject adjacent selected endpoints.
- Search: use Python startswith at every valid position.
- Suffix: directly sort materialized suffixes on SMALL inputs, then directly
  compare adjacent characters to compute LCP.
- Aho: directly count each pattern at every legal start in each text.

Built-in searches and suffix materialization are used only in these independent
test oracles, not as replacements for the required Java algorithms.

public_validate.check checks schemas and witnesses against these independent
expected optimum values. Merge plans are replayed chronologically; tree sets
are checked for uniqueness, independence and exact weight; returned LCS strings
must be subsequences of both inputs with the independently computed length.

The 837 small cases run once in a mixed batch, then forward and backward inside
ONE process (1674 requests). This verifies repeated requests and state reset
across different task types.

## Thirty full-domain stress cases

- LCS: 1000 by 1000 identical, disjoint, alternating and random strings. The
  random optimum uses an independent bit-parallel oracle.
- Merge: 200 blocks of 1000000000 and 200 zero blocks, with full chronological
  witness validation. Equal weights have optimal external path length
  200*8 - (256-200) = 1544, hence cost 1544000000000.
- Tree: 100000-vertex positive chain, positive star and negative chain. Verify
  optimum weight and every reconstructed vertex, including 64-bit totals.
- Naive: maximum text/pattern dimensions of 3000, dense overlaps, late
  mismatches and the empty pattern.
- KMP: text length 200000 and pattern length 100000, dense overlaps, late
  mismatches, a longer pattern, and all 200001 empty-pattern starts.
- RK: text length 10000 with pattern length 2000 (product 20000000), dense
  overlaps, late mismatches, the empty pattern, and a maximum-length pattern
  longer than its text.
- Suffix: 50000 identical, alternating and random characters. Closed-form SA/LCP
  values avoid quadratic checks on repetitive strings. Random data is checked
  through the entire permutation, every adjacent suffix order and direct LCP
  comparison, plus the longest-repeat witness. Large suffixes are never all
  materialized by the oracle.
- Aho: a 100000-character pattern and 100001 trie states, 100 independent texts,
  10000 duplicates totalling 100000 pattern characters, dense suffix matches,
  a broad printable-ASCII trie and a 100 by 10000 output matrix. Text lengths
  total up to 200000; every count is checked exactly.

The suite contains 867 named scenarios and 2541 case executions including
repetitions.

## Consecutive maximum-size requests

To run the same 30 stress scenarios grouped by algorithm in eight JVM processes:

~~~text
python tests/student/run_tests.py --skip-build --only stress-batches --report tests/student/stress-batches-results.json
~~~

Each task's complete group shares one 20-second timeout and one 8 MiB output
limit. This supplements isolated stress checks with maximum-size consecutive
requests, heap reuse and state reset, like the official requirement-group
batches. It adds 30 executions of the existing scenarios, not 30 new scenarios.
The report is separate so it does not overwrite the base suite's 2541 results.

## Limits, measurements and actual results

Each Java batch has a 20-second timeout, a 384 MiB heap, Serial GC and
ActiveProcessorCount=1. On Windows each process is also pinned to one available
CPU when permitted; success is recorded. Output over 8 MiB fails the batch.

Windows memory is sampled every 10 ms: the report contains the largest observed
OS-reported peak working set and sampled private bytes. These are process
measurements, not the official grading container's total memory. Windows memory
metrics are omitted on other platforms.

Wall time includes JVM startup, JSON parsing and serialization. It measures a
stress-test execution, not algorithm-only benchmark performance.

Actual recorded run: 2541 PASS, 0 FAIL. All 30 stress tests passed, and all Java
batches were pinned to one CPU. Maximum batch wall time was 1.188405 seconds;
maximum output was 5000214 bytes; maximum observed peak working set was
124944384 bytes (about 119.2 MiB). See results.json for the exact command,
environment, batch metrics, and each test execution.

The additional grouped run recorded 30 PASS, 0 FAIL across eight task batches.
All eight batches were pinned to one CPU. Its maximum batch time was 1.437858
seconds; maximum output was 5093828 bytes; maximum observed peak working set was
150589440 bytes (about 143.6 MiB). See stress-batches-results.json. Across the two
reports there are 2571 successful case executions, zero failures and 867 named
input scenarios.

results.json stores PASS/FAIL, test purpose, expected/actual output and small
input. Large values are summarized by lengths, selected endpoints and SHA-256
hashes. Inputs remain reproducible from the fixture file, script and seed.

A crash, timeout, malformed JSON, incorrect result-line count or excess output
fails all cases in that batch. Stress failures therefore cannot be hidden by a
partial list of successful answers.

## Attribution

The fixtures and runner were created with ChatGPT/Codex assistance. Their
oracles are separate from the Java implementation. The recorded pass counts
above come from an actual execution, not inferred success.

## Search benchmark

Run `python tests/student/run_benchmark.py` from the repository root. It compiles
`SearchBenchmark.java` together with the production Java sources into the ignored
`Java/build/student-benchmark` directory. `--report path` can select another JSON
report path. The default is `tests/student/benchmark-results.json`.

The actual recorded run contains 54 measured trials (3 methods, 3 sizes, 2 input
families, 3 trials), with each method/input combination checked against an independent oracle.
Compilation, JVM startup and JSON transport are outside the timed method calls.
Raw batch durations, normalized times, medians, seeds, repetitions, warm-up/JIT
policy and environment are recorded. See `ANALYSIS.md` for the full comparison.
