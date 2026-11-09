import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;
import java.util.Set;

// The Python driver supplies the public snapshot and model proposals.
// Only this host may execute an action or accept a terminal claim.
class AgentHost {
    record Context(String day, String hours, boolean injectTimeout) {}
    record Reply(String kind, String status, String detail) {
        static Reply observation(String status, String detail) {
            return new Reply("OBS", status, detail);
        }
        static Reply end(String status, String detail) {
            return new Reply("END", status, detail);
        }
    }

    static final int MAX_MODEL_TURNS = 4;
    static final int MAX_TOOL_ATTEMPTS = 2;
    final Context context;
    final Set<String> callIds = new HashSet<>();
    int turns, attempts;
    boolean observedHours, readTimedOut;

    AgentHost(Context context) { this.context = context; }

    Reply step(String[] fields) {
        if (++turns > MAX_MODEL_TURNS) return Reply.end("LIMIT", "model_turns");
        if (fields.length != 4 || !fields[0].matches("[A-Za-z0-9_-]{1,128}"))
            return Reply.end("REJECTED", "malformed_call");
        if (!callIds.add(fields[0])) return Reply.end("REJECTED", "replayed_call_id");
        String name = fields[1], arg = fields[2], citation = fields[3];
        return switch (name) {
            case "lookup_hours" -> lookup(arg, citation);
            case "ask_day" -> context.day().equals("UNKNOWN") && arg.isEmpty() && citation.isEmpty()
                    ? Reply.end("ASK_USER", "which_weekend_day")
                    : Reply.end("REJECTED", "unnecessary_or_invalid_question");
            case "finish" -> finish(arg, citation);
            default -> Reply.end("REJECTED", "unknown_tool");
        };
    }

    Reply lookup(String place, String unexpected) {
        if (!place.equals("E06") || !unexpected.isEmpty())
            return Reply.end("REJECTED", "invalid_arguments");
        if (context.day().equals("UNKNOWN"))
            return Reply.observation("NEED_DAY", "choose_saturday_or_sunday");
        if (attempts >= MAX_TOOL_ATTEMPTS) return Reply.end("LIMIT", "tool_attempts");
        attempts++;
        if (context.injectTimeout()) {
            readTimedOut = true;
            return Reply.observation("TIMEOUT", "no_result_received");
        }
        observedHours = true;
        return Reply.observation("FOUND", "hours:E06 " + context.day() + " " + context.hours());
    }

    Reply finish(String claim, String citation) {
        if (context.day().equals("UNKNOWN")) return Reply.end("REJECTED", "day_missing");
        if (claim.equals("unknown") && citation.isEmpty() && !observedHours && readTimedOut)
            return Reply.end("PARTIAL", "hours_unverified");
        if (!observedHours || !citation.equals("hours:E06"))
            return Reply.end("REJECTED", "missing_observed_evidence");
        if (!claim.equals("open") && !claim.equals("closed"))
            return Reply.end("REJECTED", "invalid_claim");
        // Day 1 covers one daytime interval, the ordinary November schedule, at 19:00.
        String[] interval = context.hours().split("-");
        boolean open = interval[0].compareTo("19:00") <= 0 && "19:00".compareTo(interval[1]) < 0;
        if (open != claim.equals("open")) return Reply.end("REJECTED", "claim_conflicts_with_hours");
        return Reply.end("DONE", claim + " at 19:00 [hours:E06]");
    }

    public static void main(String[] args) throws Exception {
        AgentHost host = new AgentHost(new Context(args[0], args[1], Boolean.parseBoolean(args[2])));
        var input = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        for (String line; (line = input.readLine()) != null; ) {
            Reply reply = host.step(line.split("\t", -1));
            // Complete the current transition without starting a fifth model turn.
            if (reply.kind().equals("OBS") && host.turns == MAX_MODEL_TURNS)
                reply = Reply.end("LIMIT", "model_turns");
            System.out.printf("%s\t%s\t%s\t%d\t%d%n", reply.kind(), reply.status(),
                    reply.detail(), host.turns, host.attempts);
            System.out.flush();
            if (reply.kind().equals("END")) return;
        }
    }
}
