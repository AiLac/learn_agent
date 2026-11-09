import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.concurrent.TimeoutException;

class RoomSearch {
    record Room(String id, String name, String district, String address) {
        boolean matches(String term) {
            return name.contains(term) || district.contains(term) || address.contains(term);
        }
    }

    record SearchResult(int totalMatched, List<Room> returned) {}

    static SearchResult search(List<Room> rooms, String term, int limit) {
        List<Room> matches = rooms.stream()
                .filter(room -> room.matches(term))
                .sorted(Comparator.comparing(Room::id))
                .toList();
        return new SearchResult(matches.size(), matches.stream().limit(limit).toList());
    }

    static List<Room> readSnapshot(boolean injectTimeout) throws IOException, TimeoutException {
        if (injectTimeout) {
            throw new TimeoutException("injected before reading the directory");
        }
        List<Room> rooms = new ArrayList<>();
        var reader = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
        for (String line; (line = reader.readLine()) != null;) {
            String[] fields = line.split("\t", -1);
            if (fields.length != 4) {
                throw new IOException("invalid snapshot row");
            }
            rooms.add(new Room(fields[0], fields[1], fields[2], fields[3]));
        }
        return rooms;
    }

    public static void main(String[] args) throws IOException {
        if (args.length != 3) {
            throw new IllegalArgumentException("expected query, limit, and normal|timeout");
        }
        String query = args[0].strip();
        int limit = Integer.parseInt(args[1]);
        if (query.isEmpty() || limit < 1 || limit > 36) {
            throw new IllegalArgumentException("query must be nonblank; limit must be 1..36");
        }
        try {
            List<Room> rooms = readSnapshot("timeout".equals(args[2]));
            SearchResult result = search(rooms, query, limit);
            System.out.printf("status=OK scanned=%d totalMatched=%d returned=%d%n",
                    rooms.size(), result.totalMatched(), result.returned().size());
            for (Room room : result.returned()) {
                System.out.printf("%s | %s | %s | %s%n",
                        room.id(), room.name(), room.district(), room.address());
            }
        } catch (TimeoutException e) {
            System.out.println("status=TIMEOUT totalMatched=unknown returned=unknown");
            System.exit(2);
        }
    }
}
