import java.util.*;

/** Assignment 4 algorithms. All mutable state belongs to one request. */
public final class Algorithms {
    private Algorithms() { }

    /** Prefix DP followed by a walk back through optimal prefix states. */
    static Map<String, Object> lcs(Map<String, Object> input) {
        String a = (String) input.get("a");
        String b = (String) input.get("b");
        int n = a.length(), m = b.length();
        int[][] dp = new int[n + 1][m + 1];
        for (int i = 1; i <= n; i++) {
            for (int j = 1; j <= m; j++) {
                if (a.charAt(i - 1) == b.charAt(j - 1)) {
                    dp[i][j] = dp[i - 1][j - 1] + 1;
                } else {
                    dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
                }
            }
        }
        StringBuilder sequence = new StringBuilder(dp[n][m]);
        int i = n, j = m;
        while (i > 0 && j > 0) {
            if (a.charAt(i - 1) == b.charAt(j - 1)) {
                sequence.append(a.charAt(i - 1));
                i--;
                j--;
            } else if (dp[i - 1][j] >= dp[i][j - 1]) {
                i--;
            } else {
                j--;
            }
        }
        return Map.of("length", dp[n][m], "sequence", sequence.reverse().toString());
    }

    /** Interval DP: choose the last adjacent merge of each original interval. */
    static Map<String, Object> merge(Map<String, Object> input) {
        long[] sizes = longArray(input.get("sizes"));
        int n = sizes.length;
        List<int[]> plan = new ArrayList<>();
        if (n <= 1) {
            return Map.of("cost", 0L, "plan", plan);
        }
        long[] prefix = new long[n + 1];
        for (int i = 0; i < n; i++) {
            prefix[i + 1] = prefix[i] + sizes[i];
        }
        long[][] dp = new long[n][n];
        int[][] split = new int[n][n];
        for (int length = 2; length <= n; length++) {
            for (int left = 0; left + length <= n; left++) {
                int right = left + length - 1;
                long intervalSize = prefix[right + 1] - prefix[left];
                dp[left][right] = Long.MAX_VALUE;
                for (int middle = left; middle < right; middle++) {
                    long candidate = dp[left][middle] + dp[middle + 1][right] + intervalSize;
                    if (candidate < dp[left][right]) {
                        dp[left][right] = candidate;
                        split[left][right] = middle;
                    }
                }
            }
        }
        appendMergePlan(0, n - 1, split, plan);
        return Map.of("cost", dp[0][n - 1], "plan", plan);
    }

    // At most 200 blocks: this recursion is bounded, unlike the tree traversal.
    private static void appendMergePlan(int left, int right, int[][] split, List<int[]> plan) {
        if (left == right) {
            return;
        }
        int middle = split[left][right];
        appendMergePlan(left, middle, split, plan);
        appendMergePlan(middle + 1, right, split, plan);
        plan.add(new int[] {left, middle, right});
    }

    /** Iterative take/skip tree DP and parent-constrained reconstruction. */
    static Map<String, Object> tree(Map<String, Object> input) {
        int n = ((Number) input.get("n")).intValue();
        List<Integer> selected = new ArrayList<>();
        if (n == 0) {
            return Map.of("weight", 0L, "selected", selected);
        }
        long[] weights = longArray(input.get("weights"));
        List<?> edges = (List<?>) input.get("edges");
        int[] degree = new int[n];
        for (Object item : edges) {
            List<?> edge = (List<?>) item;
            degree[((Number) edge.get(0)).intValue()]++;
            degree[((Number) edge.get(1)).intValue()]++;
        }
        int[][] neighbours = new int[n][];
        for (int v = 0; v < n; v++) {
            neighbours[v] = new int[degree[v]];
        }
        Arrays.fill(degree, 0);
        for (Object item : edges) {
            List<?> edge = (List<?>) item;
            int u = ((Number) edge.get(0)).intValue();
            int v = ((Number) edge.get(1)).intValue();
            neighbours[u][degree[u]++] = v;
            neighbours[v][degree[v]++] = u;
        }
        // order is both a queue and a parent-before-child traversal.
        int[] parent = new int[n];
        int[] order = new int[n];
        parent[0] = -1;
        int size = 1;
        for (int index = 0; index < size; index++) {
            int v = order[index];
            for (int u : neighbours[v]) {
                if (u != parent[v]) {
                    parent[u] = v;
                    order[size++] = u;
                }
            }
        }
        long[] take = new long[n];
        long[] skip = new long[n];
        for (int index = n - 1; index >= 0; index--) {
            int v = order[index];
            take[v] = weights[v];
            for (int u : neighbours[v]) {
                if (parent[u] == v) {
                    take[v] += skip[u];
                    skip[v] += Math.max(take[u], skip[u]);
                }
            }
        }
        boolean[] chosen = new boolean[n];
        for (int v : order) {
            boolean parentChosen = parent[v] != -1 && chosen[parent[v]];
            if (!parentChosen && take[v] > skip[v]) {
                chosen[v] = true;
                selected.add(v);
            }
        }
        return Map.of("weight", Math.max(take[0], skip[0]), "selected", selected);
    }

    /** Compare the pattern at every valid start, including overlapping starts. */
    static Map<String, Object> naive(Map<String, Object> input) {
        String text = (String) input.get("text");
        String pattern = (String) input.get("pattern");
        int n = text.length(), m = pattern.length();
        List<Integer> positions = new ArrayList<>();
        for (int start = 0; start <= n - m; start++) {
            int matched = 0;
            while (matched < m && text.charAt(start + matched) == pattern.charAt(matched)) {
                matched++;
            }
            if (matched == m) {
                positions.add(start);
            }
        }
        return Map.of("positions", positions);
    }

    /** Prefix-function KMP; fallback after a full match preserves overlaps. */
    static Map<String, Object> kmp(Map<String, Object> input) {
        String text = (String) input.get("text");
        String pattern = (String) input.get("pattern");
        int n = text.length(), m = pattern.length();
        if (m == 0) {
            return Map.of("positions", boundaries(n));
        }
        List<Integer> positions = new ArrayList<>();
        if (m > n) {
            return Map.of("positions", positions);
        }
        int[] pi = new int[m];
        for (int i = 1; i < m; i++) {
            int matched = pi[i - 1];
            while (matched > 0 && pattern.charAt(i) != pattern.charAt(matched)) {
                matched = pi[matched - 1];
            }
            if (pattern.charAt(i) == pattern.charAt(matched)) {
                matched++;
            }
            pi[i] = matched;
        }
        int matched = 0;
        for (int i = 0; i < n; i++) {
            while (matched > 0 && text.charAt(i) != pattern.charAt(matched)) {
                matched = pi[matched - 1];
            }
            if (text.charAt(i) == pattern.charAt(matched)) {
                matched++;
            }
            if (matched == m) {
                positions.add(i - m + 1);
                matched = pi[matched - 1];
            }
        }
        return Map.of("positions", positions);
    }

    /** Exact Rabin-Karp with the required small hash and character verification. */
    static Map<String, Object> rk(Map<String, Object> input) {
        String text = (String) input.get("text");
        String pattern = (String) input.get("pattern");
        int n = text.length(), m = pattern.length();
        if (m == 0) {
            return Map.of("positions", boundaries(n));
        }
        List<Integer> positions = new ArrayList<>();
        if (m > n) {
            return Map.of("positions", positions);
        }
        final long base = 31, modulus = 101;
        long highestPower = 1;
        long patternHash = 0, windowHash = 0;
        for (int i = 0; i < m; i++) {
            patternHash = (patternHash * base + pattern.charAt(i)) % modulus;
            windowHash = (windowHash * base + text.charAt(i)) % modulus;
            if (i < m - 1) {
                highestPower = highestPower * base % modulus;
            }
        }
        for (int start = 0; start <= n - m; start++) {
            if (windowHash == patternHash) {
                int matched = 0;
                while (matched < m && text.charAt(start + matched) == pattern.charAt(matched)) {
                    matched++;
                }
                if (matched == m) {
                    positions.add(start);
                }
            }
            if (start < n - m) {
                long remainder = (windowHash - text.charAt(start) * highestPower) % modulus;
                if (remainder < 0) {
                    remainder += modulus;
                }
                windowHash = (remainder * base + text.charAt(start + m)) % modulus;
            }
        }
        return Map.of("positions", positions);
    }

    /** Prefix doubling with rank-pair comparison sorting, then Kasai LCP. */
    static Map<String, Object> suffix(Map<String, Object> input) {
        String text = (String) input.get("text");
        int n = text.length();
        if (n == 0) {
            return Map.of("sa", new int[0], "lcp", new int[0], "repeated", "");
        }
        Integer[] order = new Integer[n];
        int[] rank = new int[n];
        for (int i = 0; i < n; i++) {
            order[i] = i;
            rank[i] = text.charAt(i);
        }
        for (int width = 1; width < n; width *= 2) {
            final int step = width;
            final int[] previousRank = rank;
            Arrays.sort(order, (left, right) -> compareRankPairs(left, right, previousRank, step));
            int[] nextRank = new int[n];
            int classes = 1;
            for (int i = 1; i < n; i++) {
                if (compareRankPairs(order[i - 1], order[i], previousRank, step) != 0) {
                    classes++;
                }
                nextRank[order[i]] = classes - 1;
            }
            rank = nextRank;
            if (classes == n) {
                break;
            }
        }
        int[] sa = new int[n];
        int[] position = new int[n];
        for (int i = 0; i < n; i++) {
            sa[i] = order[i];
            position[sa[i]] = i;
        }
        int[] lcp = new int[n];
        int common = 0, longest = 0, repeatedStart = 0;
        for (int start = 0; start < n; start++) {
            int index = position[start];
            if (index == 0) {
                common = 0;
                continue;
            }
            int previous = sa[index - 1];
            while (start + common < n && previous + common < n
                    && text.charAt(start + common) == text.charAt(previous + common)) {
                common++;
            }
            lcp[index] = common;
            if (common > longest) {
                longest = common;
                repeatedStart = start;
            }
            if (common > 0) {
                common--;
            }
        }
        return Map.of("sa", sa, "lcp", lcp,
                "repeated", text.substring(repeatedStart, repeatedStart + longest));
    }

    private static int compareRankPairs(int left, int right, int[] rank, int width) {
        int first = Integer.compare(rank[left], rank[right]);
        if (first != 0) {
            return first;
        }
        int leftSecond = left + width < rank.length ? rank[left + width] : -1;
        int rightSecond = right + width < rank.length ? rank[right + width] : -1;
        return Integer.compare(leftSecond, rightSecond);
    }

    /** Aho-Corasick with reverse failure propagation instead of per-match output. */
    static Map<String, Object> aho(Map<String, Object> input) {
        List<?> patterns = (List<?>) input.get("patterns");
        List<?> texts = (List<?>) input.get("texts");
        final int alphabet = 95;
        List<int[]> rows = new ArrayList<>();
        rows.add(new int[alphabet]);
        int[] terminal = new int[patterns.size()];
        for (int i = 0; i < patterns.size(); i++) {
            String pattern = (String) patterns.get(i);
            int state = 0;
            for (int j = 0; j < pattern.length(); j++) {
                int symbol = pattern.charAt(j) - 32;
                int[] transitions = rows.get(state);
                if (transitions[symbol] == 0) {
                    transitions[symbol] = rows.size();
                    rows.add(new int[alphabet]);
                }
                state = transitions[symbol];
            }
            terminal[i] = state;
        }
        int[][] next = rows.toArray(new int[0][]);
        int states = next.length;
        int[] failure = new int[states];
        int[] bfs = new int[states];
        int size = 0;
        for (int symbol = 0; symbol < alphabet; symbol++) {
            if (next[0][symbol] != 0) {
                bfs[size++] = next[0][symbol];
            }
        }
        for (int head = 0; head < size; head++) {
            int state = bfs[head];
            for (int symbol = 0; symbol < alphabet; symbol++) {
                int child = next[state][symbol];
                if (child != 0) {
                    failure[child] = next[failure[state]][symbol];
                    bfs[size++] = child;
                } else {
                    next[state][symbol] = next[failure[state]][symbol];
                }
            }
        }
        List<long[]> counts = new ArrayList<>(texts.size());
        long[] visits = new long[states];
        for (Object item : texts) {
            Arrays.fill(visits, 0L);
            String text = (String) item;
            int state = 0;
            for (int i = 0; i < text.length(); i++) {
                state = next[state][text.charAt(i) - 32];
                visits[state]++;
            }
            for (int i = size - 1; i >= 0; i--) {
                int v = bfs[i];
                visits[failure[v]] += visits[v];
            }
            long[] row = new long[patterns.size()];
            for (int i = 0; i < terminal.length; i++) {
                row[i] = visits[terminal[i]];
            }
            counts.add(row);
        }
        return Map.of("counts", counts);
    }

    private static List<Integer> boundaries(int textLength) {
        List<Integer> positions = new ArrayList<>(textLength + 1);
        for (int i = 0; i <= textLength; i++) {
            positions.add(i);
        }
        return positions;
    }

    private static long[] longArray(Object value) {
        List<?> values = (List<?>) value;
        long[] result = new long[values.size()];
        for (int i = 0; i < result.length; i++) {
            result[i] = ((Number) values.get(i)).longValue();
        }
        return result;
    }
}
