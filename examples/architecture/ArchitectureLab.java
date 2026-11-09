import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

// Deterministic scheduling exercise. All durations and A/B facts are teaching fixtures.
class ArchitectureLab {
    enum Task { COMPARE, FIRST_AVAILABLE }
    enum Status { AVAILABLE, UNAVAILABLE, TIMEOUT }
    static final int DECISION_MS = 500;
    final boolean failA;
    final Map<String, Status> observations = new LinkedHashMap<>();
    final List<String> events = new ArrayList<>();
    int decisionTurns, reads, virtualMs;

    ArchitectureLab(boolean failA) { this.failA = failA; }

    void decide(String label) {
        decisionTurns++;
        virtualMs += DECISION_MS;
        events.add(label);
    }

    void readBatch(String... targets) {
        int longest = 0;
        for (String target : targets) {
            if (observations.containsKey(target)) throw new IllegalStateException("duplicate read");
            boolean first = target.equals("A");
            Status value = first ? (failA ? Status.TIMEOUT : Status.AVAILABLE) : Status.UNAVAILABLE;
            observations.put(target, value);
            longest = Math.max(longest, first ? (failA ? 250 : 80) : 120);
            reads++;
        }
        virtualMs += longest;
        events.add("read" + Arrays.toString(targets));
    }

    String result(Task task) {
        if (task == Task.FIRST_AVAILABLE && observations.get("A") == Status.AVAILABLE) return "A";
        if (observations.containsValue(Status.TIMEOUT)) return "PARTIAL";
        if (observations.size() != 2) throw new IllegalStateException("incomplete comparison");
        return "A=AVAILABLE,B=UNAVAILABLE";
    }

    void execute(String strategy, Task task) {
        switch (strategy) {
            case "fixed" -> readBatch("A", "B");  // Eager, predeclared parallel workflow.
            case "step" -> {
                decide("choose A");
                readBatch("A");
                decide("observe A");
                if (task == Task.COMPARE || observations.get("A") != Status.AVAILABLE) {
                    readBatch("B");
                    decide("observe B");
                }
            }
            case "plan" -> {
                decide("plan independent reads");
                readBatch("A", "B");
                decide("summarize plan results");
            }
            default -> throw new IllegalArgumentException("unknown strategy");
        }
    }

    public static void main(String[] args) {
        if (args.length != 2 || !(args[1].equals("healthy") || args[1].equals("timeout")))
            throw new IllegalArgumentException("expected compare|first healthy|timeout");
        Task task = switch (args[0]) {
            case "compare" -> Task.COMPARE;
            case "first" -> Task.FIRST_AVAILABLE;
            default -> throw new IllegalArgumentException("expected compare|first");
        };
        for (String strategy : List.of("fixed", "step", "plan")) {
            var lab = new ArchitectureLab(args[1].equals("timeout"));
            lab.execute(strategy, task);
            System.out.printf("%s result=%s decisions=%d reads=%d virtualMs=%d events=%s%n",
                    strategy, lab.result(task), lab.decisionTurns, lab.reads, lab.virtualMs, lab.events);
        }
    }
}
