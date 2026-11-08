# Assignment 4 — Analysis

## Environment and commands

Language: Java, targeting Java 17. The actual local runtime/compiler was Temurin OpenJDK 21.0.12.1; all builds used `javac --release 17 -encoding UTF-8`. This is Java 17-compatible compilation, not a claim that a local Java 17 JVM was used. Python 3.12.14 runs the supplied launcher and student scripts.

Local environment: Windows 11, version 10.0.26200; 12th Gen Intel Core i5-12450H (8 cores, 12 logical processors); OS-reported physical RAM 16,906,129,408 bytes (approximately 15.75 GiB). The official checks used the supplied launcher defaults. Own stress tests used one CPU affinity and a 384 MiB Java heap; benchmark-specific settings are recorded below. These are local measurements for the current working tree, not CI or official-grader results.

Run the following from the repository root with Python 3.12+ and JDK 17+ on PATH:

~~~text
python tools/run.py --language Java --setup
python tools/run.py --language Java --input examples/lcs.jsonl
python tools/run.py --language Java --check
python tests/student/run_tests.py --report tests/student/results.json
python tests/student/run_tests.py --skip-build --only stress-batches --report tests/student/stress-batches-results.json
python tests/student/run_benchmark.py
~~~

The benchmark writes `tests/student/benchmark-results.json` by default; `--report path` selects another destination. Its Java harness is `tests/student/SearchBenchmark.java`.

On this Windows machine, `python` and `py` were not on the session PATH. Actual commands used the following executable in place of `python`:

~~~powershell
$pythonExe = 'C:\Users\Ablaykhan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $pythonExe tools/run.py --language Java --setup
& $pythonExe tools/run.py --language Java --check
& $pythonExe tests/student/run_tests.py --report tests/student/results.json
& $pythonExe tests/student/run_tests.py --skip-build --only stress-batches --report tests/student/stress-batches-results.json
& $pythonExe tests/student/run_benchmark.py
~~~

The ordinary build and launch performed by `tools/run.py` are equivalent to:

~~~text
javac --release 17 -encoding UTF-8 -d Java/build Java/source/Algorithms.java Java/source/Json.java Java/source/Main.java
java -Xmx384m -cp Java/build Main
~~~

The benchmark driver records its exact compilation and execution commands separately. Compilation is excluded from search timings. Build outputs stay in ignored `Java/build` directories.

## Shared implementation contract

Only `Java/source/Algorithms.java` contains production-code changes. All eight method signatures, `Main.java`, `Json.java`, the manifest, official tests, launcher, contracts and rubric remain unchanged. A request produces one JSON object on one line. Algorithms do not print diagnostics or keep mutable state across requests. Every required field is present, including empty witnesses.

Strings use printable ASCII 32–126, so Java character comparisons match the assignment's alphabet and order. Indices and lengths are `int`; costs, DP weight totals and Aho counts are `long`. JSON integers are read through `Number` rather than casting them to `Integer`. No library search replaces a required production algorithm. Standard collections and rank-pair sorting are used where permitted.

In the complexity statements below, auxiliary memory excludes the given input and returned output. Java array/object overhead changes constants, not the stated asymptotic bounds.

## Algorithm explanations and correctness

### 1. LCS

Let `dp[i][j]` be the optimal common-subsequence length of the first `i` characters of `a` and the first `j` characters of `b`. Row zero and column zero are zero because an empty prefix has no nonempty subsequence.

If the last characters agree, `dp[i][j] = dp[i-1][j-1] + 1`. Otherwise it is `max(dp[i-1][j], dp[i][j-1])`. Rows and columns increase, so every dependency is already computed.

Correctness follows by induction on prefix sizes. Equal final characters can extend an optimum of the shorter prefixes; an optimal subsequence can be chosen to end at these equal characters. When they differ, a common subsequence cannot use both final characters, so removing at least one endpoint exhausts the possibilities. The transition selects the best valid smaller optimum.

Reconstruction starts at `(n,m)`. Equal characters are appended while moving diagonally; otherwise the walk follows a neighbour with the same optimal value. On a tie, the implementation moves up. Each diagonal step records one valid character of an optimal subsequence. Reversing the builder restores the original order. Any optimal witness is allowed.

Time and auxiliary storage are `O((n+1)(m+1))`; reconstruction takes `O(n+m)` time. Input storage is `O(n+m+1)`, and the output string has `O(min(n,m)+1)` space. Both empty and one-empty cases yield length zero and an empty string.

Tests include `axbyc/abc` (subsequence versus substring), ties, repeated characters, both empty strings and four 1000-by-1000 inputs. The large random optimum is checked with a separate bit-parallel oracle, while small random optima are obtained by enumerating subsequences.

### 2. Ordered adjacent-block merging

`dp[left][right]` is the minimum cost to merge the closed original interval into one block. Single blocks have cost zero. Prefix sums provide `sum(left..right)` in constant time. For each possible final split `middle`:

`dp[left][right] = min(dp[left][middle] + dp[middle+1][right] + sum(left..right))`.

Intervals are processed by increasing length, ensuring the two smaller intervals are ready. Every legal final merge joins two adjacent contiguous intervals, so every possible optimum has one of the enumerated splits. Its subplans must be optimal; otherwise substituting a cheaper subplan improves the whole solution. This proves the recurrence by induction.

The chosen split is stored. Reconstruction emits the left child's merges, then the right child's merges, then `[left,middle,right]`. Thus both operands exist and are adjacent when each operation executes. Equal costs retain the first split. For `n>1` there are exactly `n-1` operations; empty and singleton inputs return zero cost and an empty plan. Reconstruction recursion is bounded by the permitted 200 blocks.

For nonempty inputs, time is `O(n^3)` and auxiliary memory `O(n^2)`; reconstruction/output are `O(n)`. Empty input takes constant work. All sizes, prefix sums and cost candidates use `long`: a conservative total-cost bound is `(n-1)*sum(sizes) <= 3.98e13`, safely within signed 64-bit range.

Tests replay the actual chronological plan. They cover zeros, ties, the adjacency counterexample `[1,100,1]`, and 200 blocks of size one billion. For the latter, the expected optimum is `1544e9`, derived from the external path length of a minimum-depth ordered full binary tree.

### 3. Tree maximum-weight independent set

The tree is rooted at vertex zero. An iterative queue creates a parent-before-child order using integer adjacency arrays. Reversing that order gives children before parents without recursion.

`take[v]` is the optimum in the rooted subtree when vertex `v` is included; `skip[v]` is the optimum when it is excluded:

- `take[v] = weight[v] + sum(skip[child])`.
- `skip[v] = sum(max(take[child], skip[child]))`.

The two cases exhaust the feasible choices. Including a parent forces every child to be excluded; excluding it leaves each child free. Different child subtrees have no connecting edges, so their optimum contributions add independently. Induction over the reversed order proves both states.

During reconstruction, vertices are visited parent first. A chosen parent forces its child to be skipped. Otherwise a vertex is chosen exactly when `take[v] > skip[v]`; ties choose skip. This realizes the root optimum while ensuring independence and emitting every selected vertex once. Negative weights do not force a selection: `skip` permits the empty set. An empty tree returns zero and an empty list.

Time and auxiliary storage are `O(n+1)`, including reconstruction. Input and output are each `O(n+1)`. Totals use `long`; their magnitudes are bounded by `1e14`. No recursion depends on tree height.

Small instances are checked by exhaustive subset enumeration with shuffled labels. Full-size positive chains, stars and negative chains have 100000 vertices; validators check optimal weight, unique IDs, absence of adjacent selected vertices and the exact sum.

### 4. Naive exact search

For every start from zero through `n-m`, characters are compared until a mismatch or a complete match. Every possible occurrence has exactly one such start, and a start is returned only after all pattern characters agree. Starts are considered in ascending order, so the output is sorted and includes overlaps.

When `m=0`, the comparison loop is empty and all `n+1` boundaries are reported. When `m>n`, there are no valid starts.

Time is `O(n*m+n+1)`, including emitted positions; auxiliary space is `O(1)`. Input takes `O(n+m+1)`, and `z` returned starts take `O(z+1)` space.

Tests cover overlapping `aaa` matches, empty patterns/texts, case, spaces and punctuation, and maximum-length dense/late-mismatch cases. An independent oracle checks each legal start with Python `startswith`.

### 5. KMP

`pi[i]` is the length of the longest proper prefix of `pattern[0..i]` that is also its suffix. Prefix-function construction proceeds left to right. On a mismatch, `matched = pi[matched-1]` tries the next smaller border.

During text scanning, `matched` is the length of a pattern prefix equal to a suffix of the text processed so far. Fallback preserves this invariant while discarding impossible candidates; extending on equality maintains it. A value of `m` proves a complete occurrence. After reporting it, the same border fallback retains possible overlapping matches.

Each increase in `matched` is bounded by characters processed, and fallbacks strictly decrease it. This amortized argument gives `O(n+m+z+1)` time. The prefix array uses `O(m+1)` auxiliary memory; output uses `O(z+1)` and input `O(n+m+1)`. Empty patterns are handled before any pattern indexing, and a longer pattern returns immediately.

Tests include nested borders, overlaps, common-domain agreement with the independent oracle, maximum text length 200000, pattern length 100000, and the 200001 boundaries for an empty pattern.

### 6. Exact Rabin–Karp

The hash uses ASCII codes, base 31 and modulus 101, with the highest power on the left. `highestPower = 31^(m-1) mod 101`. Initial pattern/window hashes are constructed left to right.

To slide one position, subtract the outgoing character times `highestPower`, reduce and normalize the remainder into `0..100`, multiply by 31 and add the incoming character modulo 101. By polynomial algebra, this is precisely the next window's hash.

Unequal hashes rule out equality. Equal hashes trigger explicit character comparisons, so collisions never create false occurrences. Sliding considers every legal start, ensuring completeness and overlaps. Empty and longer patterns are handled before an initial window is formed.

For `1<=m<=n`, time is `O(n+m+c*m)`, where `c` counts equal-hash windows. Across all inputs a valid bound is `O(n*m+n+m+1)`; deterministic linear worst-case time is not claimed. This implementation uses `O(1)` auxiliary storage, with `O(z+1)` output and `O(n+m+1)` input. Hash arithmetic uses `long`.

The known collision `ab/dj` is tested, along with rolling subtraction requiring normalization, overlaps and maximum permitted `n*m=20000000`. Empty-pattern and exact-output tests are shared with the other searches.

### 7. Suffix array and Kasai LCP

Suffix-array construction begins with ASCII character ranks. At doubling width `w`, suffix starts are sorted by `(rank[i], rank[i+w])`, using -1 when the second half is absent. The comparator captures an unchanged rank array and width. A separate array assigns equal ranks to equal pairs and increasing ranks to different pairs.

Inductively, ranks represent lexicographic order of prefixes of width `w`; sorting the two halves correctly orders prefixes of width `2w`. Doubling continues until all suffixes have different ranks or the represented width covers the text. Distinct prefix ranks already decide the complete suffix order, which justifies early stopping. Only the original nonempty suffix starts are returned. No suffix strings are materialized for sorting.

Kasai builds the inverse suffix position and scans text starts in increasing order. Each suffix is compared to its lexicographic predecessor. After moving one text position, a previous common prefix can decrease by at most one before further comparisons are needed; the first-ranked suffix resets the reused length to zero. Thus total character increments are linear. `lcp[0]=0`; every later entry compares adjacent suffixes.

Any repeated substring begins at two suffix starts. All suffixes sharing its prefix occupy a contiguous lexicographic interval, so some adjacent pair has at least that common prefix. Conversely, every positive adjacent LCP represents a repeat. Hence the maximum LCP yields a longest repeated substring, including overlapping occurrences. The implementation retains the first strict maximum encountered in text-start order; ties need no special lexicographic rule.

Comparison sorting of boxed indices costs `O(n log^2(n+1))` overall; Kasai costs `O(n)`. Arrays, boxed indices and sorting workspace use `O(n+1)` auxiliary space; input and output are `O(n+1)`. Only the final repeated substring is copied. Empty input is constant time, and one character returns SA [0], LCP [0], and no repeat.

Small cases use direct suffix sorting and direct LCP comparisons as a separate oracle. At length 50000, equal and alternating strings have closed-form expected arrays. A random case checks the complete permutation, every adjacent suffix order, every LCP, and the longest-repeat witness.

### 8. Aho–Corasick

A trie uses one 95-entry integer transition row per actual state. Each dictionary position records its terminal state, so duplicate patterns share trie nodes but retain separate output columns.

Breadth-first construction sets failure links to the longest proper suffix that is also a trie prefix, then fills missing transitions from the failure state's row. The failure destination is at smaller depth and is already processed, making each completed transition correct.

For each independent text, state and a `long[] visits` array are reset. Each consumed character follows a completed transition and increments the reached state's visits. Reverse BFS order propagates each state's count to its failure parent. A terminal pattern matches exactly when its state is the current state or lies on its failure chain. Propagation therefore counts all suffix-pattern occurrences and overlaps without enumerating individual matches. Reading the terminal count for each original dictionary position gives equal counts for duplicates in the required column order.

Empty dictionaries produce one empty row per text; no texts produce an empty outer list; an empty text produces a row of zeros. There are no copied inherited output lists.

Let `L` be total dictionary length including duplicates, `S` actual trie states, `p` dictionary size and `q` text count. Construction costs `O(L+95*S+p)`; each text costs `O(|text|+S+p)`. Auxiliary storage is `O(95*S+p)`; output is `O(q*(p+1)+1)`. Input storage includes `O(L+totalTextLength+p+q+1)`. Only actual trie states allocate transition rows.

Tests cover suffix patterns, duplicate dictionary positions, overlaps, empty arrays/texts, repeated independent texts, 100001 states, 10000 patterns and dense matches. The largest output fixture checks all one million cells of a 100-by-10000 matrix.

## Own tests and actual validation

Fixtures, independent test code and reproduction details are under `tests/student`. The 57 fixed cases include their inputs, expected results/optima and the defect being detected. Seed 20261108 generates 780 additional small cases: 100 LCS, 80 merge, 100 tree, 100 shared text/pattern pairs for all three searches, 100 suffix and 100 Aho. Expected values come from exhaustive/direct oracles, not from agreement between the production algorithms.

For LCS, merge and tree, `tools/public_validate.py` checks reconstructed witnesses semantically against independent optimum values. Merge plans are replayed, tree sets are checked for independence/uniqueness/exact weight, and LCS strings must have optimal length and be subsequences of both inputs. Alternative optima are accepted. Built-in searching and materialized suffixes occur only in small test oracles, not in the Java implementations.

The 837 small scenarios run once, then twice in a single process (forward and reversed) to detect stale state. Thirty additional full-domain stress scenarios bring the number of distinct own scenarios to 867.

Actual results:

| Suite | Passed | Failed | Evidence |
|---|---:|---:|---|
| Official setup ping | 1 | 0 | `tests/student/setup.log` |
| Official public cases, including ping | 44 | 0 | `tests/student/public-checks.log` |
| Official repeated mixed batch | 88 requests | 0 | Same public log, state-reset check |
| Own fixed + seeded small cases | 837 | 0 | `tests/student/results.json` |
| Own two mixed batches in one process | 1674 requests | 0 | Same results JSON |
| Own full-domain cases, separate processes | 30 | 0 | Same results JSON |
| Same full-domain cases grouped by task, 8 processes | 30 | 0 | `tests/student/stress-batches-results.json` |
| **Own executions including repeats** | **2571** | **0** | **867 distinct named own scenarios** |

All reported numbers come from actual executions. Public cases do not determine the official 19-group score. The only compilation note concerned existing unchecked operations in the supplied `Main.java`; it did not prevent compilation or execution.

The recorded logs are `setup.log`, `public-checks.log`, `official-results.json`, `results.json` and `stress-batches-results.json` under `tests/student`. Per-case records retain PASS/FAIL, expected and actual results, and test purpose. Large arrays/strings are compacted to lengths, endpoints and SHA-256 digests; their complete inputs are reproducible from the generator and seed.

Representative fixed cases and the actual full-size outcomes:

| Command | Fixture in `tests/student/cases.json` | Expected | Actual result / evidence | Defect detected |
|---|---|---|---|---|
| LCS | `lcs-gapped-subsequence`: axbycz / abc | Length 3, abc | Length 3, abc; PASS | Mistaking subsequence for substring |
| Merge | `merge-adjacency`: [1,100,1] | Cost 203 | Cost 203, plan [[1,1,2],[0,0,2]]; PASS | Merging nonadjacent smallest blocks |
| Tree | `tree-parent-decision`: star, weights [9,6,6,6] | Weight 18 | Weight 18, selected [1,2,3]; PASS | Greedy root selection |
| Naive | `naive-empty-pattern` | Every boundary including final | Exact expected positions; PASS | Missing final empty-pattern boundary |
| KMP | `kmp-overlap`: abababa / aba | [0,2,4] | [0,2,4]; PASS | Losing overlaps after a full match |
| RK | `rk-collision`: abdjab / ab | [0,4] | [0,4]; PASS | Treating equal hash dj as a match |
| Suffix | `suffix-banana` | SA [5,3,1,0,4,2], LCP [0,1,3,0,0,2], ana | All arrays exact and ana; PASS | Wrong LCP convention or order |
| Aho | `aho-duplicates`: a, aa, a; texts aaaa, empty, aaaa | [[4,3,4],[0,0,0],[4,3,4]] | Exact matrix; PASS | Lost duplicates, overlaps or text reset |

Each full-size test name and its expected/actual result summary appears in the results JSON. In particular, large tree witnesses, merge operations, LCS subsequences and every Aho matrix count were validated, not merely timed.

The own-test JVMs use a 384 MiB heap, Serial GC, `ActiveProcessorCount=1`, a 20-second batch timeout and an 8 MiB output check. On this Windows run all Java test processes were also pinned to one allowed CPU. Reported stress wall times include JVM startup, JSON parsing and serialization; independent Python validation occurs outside that interval.

The 30 individually launched stress scenarios all passed. Across the initial own suite, maximum batch time was 1.188405 s, maximum output was 5,000,214 bytes and maximum observed peak working set was 124,944,384 bytes (119.2 MiB).

The additional large-input batches, grouped as official checks group requests, also all passed:

| Task | Requests in one JVM | Wall seconds | UTF-8 output bytes | Observed peak working set, MiB |
|---|---:|---:|---:|---:|
| lcs | 4 | 0.324375 | 2760 | 57.1 |
| merge | 2 | 0.169993 | 5076 | 41.6 |
| tree | 3 | 0.955546 | 883441 | 131.9 |
| naive | 4 | 0.182768 | 20361 | 40.5 |
| kmp | 4 | 0.553595 | 1877864 | 78.4 |
| rk | 4 | 0.241521 | 87861 | 44.1 |
| suffix | 3 | 1.437858 | 1644545 | 83.3 |
| aho | 6 | 0.843694 | 5093828 | 143.6 |

Every observed batch remained below 20 seconds and 8 MiB output. The largest observed peak working set was 150,589,440 bytes (143.6 MiB). Memory was sampled every 10 ms using Windows process counters; the report also retains sampled private bytes.

Working-set and private-memory measurements refer to the Java process on Windows, not to an official Linux container. The official 768 MiB container and 512 MiB Java-heap configuration were not recreated here. Published-limit cases passed under the smaller local heap, but hidden official tests and the submitted-commit CI run remain unverified.

## Reproducible search comparison

The recorded comparison consists of **18 method/input combinations and 54 measured trials**, all with verified correct results. The benchmark JVM completed in 4.193567 seconds; this overall duration is not used as an algorithm time.

Inputs are identical for all three algorithms at each case/size. Sizes are (n,m) = (500,50), (1500,150), (3000,300), all within the common domain. Random texts use `java.util.Random` with seed `20261108+n` and uniformly selected lowercase ASCII letters. After text generation, a uniformly selected valid start determines a substring pattern, ensuring at least one match. The actual seeds/starts are 20261608/444, 20262608/788 and 20264108/302; each random pair has exactly one occurrence. Repetitive inputs are `a^n` and `a^m`, producing 451, 1351 and 2701 overlapping occurrences respectively.

An independent `String.startsWith`-at-every-start oracle checks each algorithm's full positions list before warm-up or measurements. The final output of every warm-up, calibration and measured batch is checked again outside its timer. A separate collision check `abdjab/ab -> [0,4]` passes before measurements. Production code does not use this library oracle.

Timing uses `System.nanoTime()` around repeated direct calls to the same production methods. It includes pattern preprocessing, output list/map allocation and shared harness dispatch/loop/volatile-sink overhead. It excludes compilation, JVM startup, input generation, JSON parsing/serialization and oracle checks. A volatile sink makes returned results observable. This scope is identical for all methods.

Each method/input combination receives at least 100 ms of warm-up with default tiered JIT compilation. A 32-call calibration chooses a fixed repetition count for that combination, targeting approximately 20 ms per measured batch and capped at 32768 calls. The target is not a guaranteed elapsed time; the raw durations show variation. There are exactly three measured batches per combination. Their order rotates naive/KMP/RK, then KMP/RK/naive, then RK/naive/KMP. No explicit GC is forced; allocation-related GC pauses remain part of measured execution.

The JVM used `-Xmx384m -XX:ActiveProcessorCount=1 -XX:+UseSerialGC` and was successfully pinned to one CPU. Tests were complete before this run, so the student test runner was not competing with the measurements. The benchmark makes no claim that all background activity on the machine was eliminated.

The table reports each measured batch divided by its call count, in **microseconds per call**. These are observed values, not theoretical estimates. The raw integer nanosecond batch durations, precise normalized values, repetition counts, environment and commands are retained in `tests/student/benchmark-results.json`.

| Case | n | m | Seed | Algorithm | Calls/trial | Run 1, us/call | Run 2, us/call | Run 3, us/call | Median, us/call | Correct |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|
| random | 500 | 50 | 20261608 | naive | 24521 | 0.887 | 1.258 | 1.231 | 1.231 | yes |
| random | 500 | 50 | 20261608 | kmp | 19937 | 2.954 | 1.417 | 1.203 | 1.417 | yes |
| random | 500 | 50 | 20261608 | rk | 5190 | 4.776 | 4.441 | 4.403 | 4.441 | yes |
| random | 1500 | 150 | 20262608 | naive | 8432 | 7.829 | 5.078 | 4.523 | 5.078 | yes |
| random | 1500 | 150 | 20262608 | kmp | 5446 | 4.204 | 4.025 | 3.811 | 4.025 | yes |
| random | 1500 | 150 | 20262608 | rk | 1509 | 22.994 | 14.852 | 15.239 | 15.239 | yes |
| random | 3000 | 300 | 20264108 | naive | 3011 | 7.044 | 8.221 | 8.107 | 8.107 | yes |
| random | 3000 | 300 | 20264108 | kmp | 627 | 5.774 | 6.515 | 6.254 | 6.254 | yes |
| random | 3000 | 300 | 20264108 | rk | 303 | 24.699 | 22.236 | 22.758 | 22.758 | yes |
| repetitive | 500 | 50 | a^n / a^m | naive | 481 | 58.053 | 48.252 | 45.273 | 48.252 | yes |
| repetitive | 500 | 50 | a^n / a^m | kmp | 4309 | 37.629 | 4.268 | 3.887 | 4.268 | yes |
| repetitive | 500 | 50 | a^n / a^m | rk | 146 | 55.765 | 145.419 | 44.497 | 55.765 | yes |
| repetitive | 1500 | 150 | a^n / a^m | naive | 31 | 452.329 | 464.687 | 390.526 | 452.329 | yes |
| repetitive | 1500 | 150 | a^n / a^m | kmp | 1931 | 16.107 | 22.227 | 11.501 | 16.107 | yes |
| repetitive | 1500 | 150 | a^n / a^m | rk | 48 | 367.523 | 665.585 | 385.962 | 385.962 | yes |
| repetitive | 3000 | 300 | a^n / a^m | naive | 12 | 1952.225 | 1906.550 | 2114.183 | 1952.225 | yes |
| repetitive | 3000 | 300 | a^n / a^m | kmp | 984 | 23.587 | 26.050 | 28.674 | 26.050 | yes |
| repetitive | 3000 | 300 | a^n / a^m | rk | 11 | 2978.100 | 1664.145 | 1761.600 | 1761.600 | yes |

On the largest repetitive pair, medians were 1952.225 us for naive, 26.050 us for KMP and 1761.600 us for exact RK. Every valid window matches here, so naive and RK compare all pattern characters at every start; hashing cannot avoid RK's mandatory character verification. KMP uses prefix information and still pays the unavoidable cost of emitting 2701 positions.

On random inputs, most naive comparisons terminate quickly. Naive was slightly faster than KMP at the smallest pair in this run, while KMP was faster at the two larger pairs. RK was slower than both on these random samples. Hash arithmetic, candidate verification and implementation constants all contribute; this experiment does not separately measure those costs.

The deliberately small modulus 101 permits collisions and requires verification. The results concern this assignment's exact RK implementation and should not be generalized to every production hashing scheme. KMP's deterministic linear bound and RK's candidate-sensitive worst case follow from the analyses above, not from a timing ranking.

There is substantial run-to-run variation: for example, repetitive n=500 KMP measured 37.629, 4.268 and 3.887 us/call. All three observations are retained. Short warm-up, JIT compilation, GC, scheduling and CPU frequency changes may affect measurements; this run does not isolate a specific cause. The median reduces the effect of one outlier but does not prove JIT convergence or statistical significance. This is a reproducible local microbenchmark, not a substitute for asymptotic reasoning or a broad performance study.

## Sources and AI assistance

Sources actually used:

- Official template README: https://github.com/RZhaniya/daa-assignment-4-archive
- Local `docs/Assignment_4_EN.md`, `docs/guide/CONTRACTS.md`, `RUBRIC.md`, `TESTING.md` and `SUBMISSION.md`: required algorithms, domains, schemas, grading, testing and submission rules.
- Supplied `Main.java`, `Json.java`, `tools/run.py`, `tools/public_validate.py`, `tests/public.json` and original `ANALYSIS.md`: integration, public validation and required reporting structure.
- The Java implementations, own test/benchmark source and recorded logs in this repository provide the direct evidence for the implementation and measurements described above.

## Sources and AI Assistance

### Sources Used

- Official Assignment 4 GitHub template and README.
- Assignment specifications, algorithm contracts, grading rubric, testing guidelines, and submission instructions.
- Provided Java starter files, testing tools, and public test cases.
- Official course materials and assignment examples.

### AI Usage and Student Contribution

I wrote the code for this assignment myself, in Java. ChatGPT and Codex were used as assistants: they helped me work through the algorithms, debug my implementations, generate additional test cases, set up the performance benchmark, and draft parts of the documentation.

I reviewed the assignment requirements, chose Java as the implementation language, and directed the AI assistants at each stage. I studied the algorithms and followed the logic of every implementation, ran the official public tests, the additional student tests and the benchmark, and reviewed the recorded results. I checked all AI-assisted code and text before submission, and I am prepared to explain and defend the solution.

## Submission status and commands

Implementation, local tests, own stress checks, benchmark evidence and this analysis are complete. The exact logs identify the tested working-tree implementation; no final submission commit has been created by this work. Review the diff and AI attribution first. Then, when ready, the student may run:

~~~text
git diff --check
git diff -- Java/source/Algorithms.java ANALYSIS.md tests/student/README.md
git status --short
git add Java/source/Algorithms.java ANALYSIS.md tests/student
git commit -m "Implement Assignment 4 algorithms with tests and analysis"
git push origin main
~~~

Check Actions -> Public checks for that exact commit. The workflow also checks starter setup in the other three languages, whose templates remain untouched. Those other-language setup jobs were not run locally in this Java-focused work.

To obtain the full commit URL in PowerShell after committing:

~~~powershell
$sha = (git rev-parse HEAD).Trim()
"https://github.com/Abo2507/daa-assignment-4/commit/$sha"
~~~

The SHA must contain all 40 characters. Submit that URL and the selected language Java in Moodle; optionally include the Actions run URL for the same SHA. Ensure the instructor can access a private repository, then verify the final Moodle submission status. A later revision requires updating the submitted commit URL. The repository gives 8 November 2026, 23:59 as the deadline; approved extensions and final availability are recorded in Moodle.
