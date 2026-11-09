import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

// Single-process teaching fixture. A production database must persist the operation key.
class DraftTool {
    record Request(String caseId, String operation, boolean mayDraft) {}
    record Key(String caseId, String operation) {}
    record Draft(String id, Set<String> missing) {}

    final Map<Key, Draft> drafts = new ConcurrentHashMap<>();

    Draft create(Request request, Set<String> missing) {
        if (!request.mayDraft()) throw new IllegalStateException("DENIED");
        if (!request.caseId().equals("DEMO-A") || request.operation().isBlank() || missing.isEmpty())
            throw new IllegalArgumentException("INVALID_ARGUMENT");
        var key = new Key(request.caseId(), request.operation());
        return drafts.compute(key, (ignored, current) -> {
            if (current == null) return new Draft(UUID.randomUUID().toString(), Set.copyOf(missing));
            if (!current.missing().equals(missing)) throw new IllegalStateException("CONFLICT");
            return current;
        });
    }

    record Proposal(String tool, String caseId, Set<String> missingTypes) {}
    record Observation(String status, Set<String> missing) {}

    // One review run retains the material observation used to justify its draft.
    static class ReviewRun {
        final Request request;
        final DraftTool store;
        Set<String> observedMissing;

        ReviewRun(Request request, DraftTool store) {
            this.request = request;
            this.store = store;
        }

        Observation step(Proposal action) {
            if (!request.caseId().equals(action.caseId()) || !request.caseId().equals("DEMO-A"))
                return new Observation("CASE_MISMATCH", Set.of());
            if (action.tool().equals("list_materials") && action.missingTypes().isEmpty()) {
                var missing = new HashSet<>(Set.of("license", "settlement"));
                missing.removeAll(Set.of("license")); // DEMO-A fixture
                observedMissing = Set.copyOf(missing);
                return new Observation("FOUND", observedMissing);
            }
            if (!action.tool().equals("draft_request")) return new Observation("INVALID_ACTION", Set.of());
            if (!request.mayDraft()) return new Observation("DENIED", Set.of());
            if (observedMissing == null || !observedMissing.equals(action.missingTypes()))
                return new Observation("UNSUPPORTED_DRAFT", Set.of());
            store.create(request, observedMissing);
            return new Observation("DRAFTED", observedMissing);
        }
    }

    static void reviewDemo() {
        var store = new DraftTool();
        var read = new Proposal("list_materials", "DEMO-A", Set.of());
        var draft = new Proposal("draft_request", "DEMO-A", Set.of("settlement"));
        for (boolean permission : new boolean[] {false, true}) {
            var run = new ReviewRun(new Request("DEMO-A", "op-7", permission), store);
            var observation = run.step(read);
            var result = run.step(draft);
            System.out.printf("mayDraft=%s missing=%s result=%s count=%d%n",
                    permission, observation.missing(), result.status(), store.drafts.size());
        }
    }

    public static void main(String[] args) {
        if (args.length == 1 && args[0].equals("review")) { reviewDemo(); return; }
        var tool = new DraftTool();
        var readOnly = new Request("DEMO-A", "op-7", false);
        var allowed = new Request("DEMO-A", "op-7", true);
        var missing = Set.of("settlement");
        try { tool.create(readOnly, missing); }
        catch (IllegalStateException ex) { System.out.println(ex.getMessage() + " count=" + tool.drafts.size()); }
        var first = tool.create(allowed, missing); // Assume that the caller lost this response.
        var retry = tool.create(allowed, missing);
        System.out.println("sameDraft=" + first.id().equals(retry.id()) + " count=" + tool.drafts.size());
        try { tool.create(allowed, Set.of("license")); }
        catch (IllegalStateException ex) { System.out.println(ex.getMessage() + " count=" + tool.drafts.size()); }
    }
}
