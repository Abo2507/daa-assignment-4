import java.util.*;

/** Reproducible algorithm-only comparison; this is test code, not production search. */
public final class SearchBenchmark {
    private static volatile Object sink;
    private static final String[] METHODS = {"naive", "kmp", "rk"};
    private static final long BASE_SEED = 20261108L;
    private static final long WARMUP_NS = 100_000_000L;
    private static final long TARGET_NS = 20_000_000L;

    private static Map<String, Object> call(int method, Map<String, Object> input) {
        return switch (method) {
            case 0 -> Algorithms.naive(input);
            case 1 -> Algorithms.kmp(input);
            case 2 -> Algorithms.rk(input);
            default -> throw new IllegalArgumentException();
        };
    }

    private static List<Integer> oracle(String text, String pattern) {
        List<Integer> expected = new ArrayList<>();
        for (int i = 0; i <= text.length() - pattern.length(); i++) {
            if (text.startsWith(pattern, i)) {
                expected.add(i);
            }
        }
        return expected;
    }

    private static void verify(Object answer, List<Integer> expected) {
        if (!(answer instanceof Map<?, ?> map) || !expected.equals(map.get("positions"))) {
            throw new AssertionError("Search result differs from independent oracle");
        }
    }

    private static long measure(int method, Map<String, Object> input, int repetitions) {
        long start = System.nanoTime();
        for (int i = 0; i < repetitions; i++) {
            sink = call(method, input);
        }
        return System.nanoTime() - start;
    }

    public static void main(String[] args) {
        List<Map<String, Object>> results = new ArrayList<>();
        Map<String, Object> collision = Map.of("text", "abdjab", "pattern", "ab");
        for (int method = 0; method < METHODS.length; method++) {
            verify(call(method, collision), List.of(0, 4));
        }
        for (String kind : List.of("random", "repetitive")) {
            for (int n : new int[] {500, 1500, 3000}) {
                int m = n / 10;
                long seed = BASE_SEED + n;
                Random random = new Random(seed);
                String text, pattern;
                int patternStart;
                if (kind.equals("random")) {
                    StringBuilder builder = new StringBuilder(n);
                    for (int i = 0; i < n; i++) {
                        builder.append((char) ('a' + random.nextInt(26)));
                    }
                    text = builder.toString();
                    patternStart = random.nextInt(n - m + 1);
                    pattern = text.substring(patternStart, patternStart + m);
                } else {
                    text = "a".repeat(n);
                    pattern = "a".repeat(m);
                    patternStart = 0;
                }
                Map<String, Object> input = Map.of("text", text, "pattern", pattern);
                List<Integer> expected = oracle(text, pattern);
                int[] repetitions = new int[METHODS.length];
                long[][] elapsed = new long[METHODS.length][3];
                double[][] perCall = new double[METHODS.length][3];
                // Check every method before warm-up, calibration or measured trials.
                for (int method = 0; method < METHODS.length; method++) {
                    verify(call(method, input), expected);
                }
                for (int method = 0; method < METHODS.length; method++) {
                    long end = System.nanoTime() + WARMUP_NS;
                    do {
                        sink = call(method, input);
                    } while (System.nanoTime() < end);
                    verify(sink, expected);
                    long calibration = measure(method, input, 32);
                    verify(sink, expected);
                    repetitions[method] = (int) Math.max(1L,
                            Math.min(32768L, TARGET_NS * 32 / Math.max(1L, calibration)));
                }
                // Each method occupies each position in the order exactly once.
                for (int trial = 0; trial < 3; trial++) {
                    for (int offset = 0; offset < METHODS.length; offset++) {
                        int method = (trial + offset) % METHODS.length;
                        elapsed[method][trial] = measure(method, input, repetitions[method]);
                        perCall[method][trial] = (double) elapsed[method][trial] / repetitions[method];
                        verify(sink, expected);
                    }
                }
                for (int method = 0; method < METHODS.length; method++) {
                    double[] sorted = perCall[method].clone();
                    Arrays.sort(sorted);
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("case", kind);
                    row.put("n", n);
                    row.put("m", m);
                    row.put("seed", kind.equals("random") ? seed : 0L);
                    row.put("pattern_start", patternStart);
                    row.put("algorithm", METHODS[method]);
                    row.put("occurrences", expected.size());
                    row.put("repetitions_per_trial", repetitions[method]);
                    row.put("elapsed_ns", elapsed[method]);
                    row.put("ns_per_call", perCall[method]);
                    row.put("median_ns_per_call", sorted[1]);
                    row.put("correct_outputs_checked", true);
                    results.add(row);
                }
            }
        }
        Map<String, Object> report = new LinkedHashMap<>();
        report.put("java_version", System.getProperty("java.runtime.version"));
        report.put("generator", "java.util.Random(seed=20261108+n); uniform lowercase text; random substring pattern; repetitive=a^n/a^m");
        report.put("warmup_ns_per_method_case", WARMUP_NS);
        report.put("calibration_calls", 32);
        report.put("target_trial_ns", TARGET_NS);
        report.put("maximum_repetitions", 32768);
        report.put("measured_trials_per_method_case", 3);
        report.put("collision_test_passed", true);
        report.put("scope", "Direct Algorithms method, including preprocessing and output allocation; shared switch dispatch, loop and volatile sink assignment included. Excludes compilation, JVM startup, input generation, JSON and oracle validation.");
        report.put("jit_policy", "Default tiered JVM compilation; 100ms warmup per method/case plus calibration; no forced GC, GC pauses remain included.");
        report.put("rows", results);
        System.out.println(Json.write(report));
    }
}
