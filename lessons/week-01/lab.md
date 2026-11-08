# 第 1 周 · 实践讲义｜把模型接到一个真实的 Java 工具上

## 实验目标与准备

用 JDK 17+、Maven 和你熟悉的 JSON 库建立 Java 命令行项目。建议用 JUnit 5；从仓库根目录读取[已提交的名录](../../data/hk-study-rooms/library-study-rooms.json)。选择一个支持工具调用的模型，密钥放在本地环境变量。仓库提供课件与输入数据，下面的类名、测试名和输出路径都是你要实现的练习约定。

## 第一次上机的 90 分钟

1. **20 分钟，核对输入。** Windows PowerShell 在仓库根目录执行下列命令。第一次先看数据的顶层结构，记录编号、地区、地址分别来自哪里。
2. **40 分钟，实现本地检索。** 建议用 `record Room(String id, String name, String district, String address)`。读顶层 `records` 数组，按名称、地区、地址匹配，按 ID 去重；并列时按 ID 排序。先处理空查询和无命中。
3. **30 分钟，写人工答案。** 查花园街的地址，再从下方官方时间表找普通 11 月周六和周日 19:00 的答案。将适用对象写成“学生自修室”，同时注明只核实了常规安排。

```powershell
$rooms = (Get-Content -Raw -Encoding UTF8 data/hk-study-rooms/library-study-rooms.json | ConvertFrom-Json).records
$rooms.Count
$rooms | Where-Object district -eq '油尖旺' | Select-Object id,name,address
```

预期计数为 36，油尖旺包含 `E01` 和 `E06`。比较地址时以 JSON 原文为准，保留繁简及异体字符。此命令用于查看数据，自己的检索入口用 Java 实现。

**Java 检索最小实现。** 在自己的类中加入下面的方法和前述 `Room` 记录，使用包 `java.util`、`java.util.stream.Stream`。调用前先让 JSON 解析器取出顶层 `records`，映射为 `List<Room>`。这段实现刻意从精确子串匹配起步，第 2 周可保留作基线。

```java
static List<Room> search(List<Room> rooms, String query, int limit) {
    if (query == null || query.isBlank() || limit < 1 || limit > 2) {
        throw new IllegalArgumentException("query and limit out of bounds");
    }
    String term = query.strip();
    Map<String, Room> matches = new TreeMap<>();
    for (Room room : rooms) {
        if (Stream.of(room.name(), room.district(), room.address())
                .anyMatch(field -> field.contains(term))) {
            matches.putIfAbsent(room.id(), room);
        }
    }
    return matches.values().stream().limit(limit).toList();
}
```

可以在截断前读取 `matches.size()` 作为命中总数；上面的方法只返回展示列表。

## 余下的上机时间

- **90 分钟，接入工具。** 写工具描述、JSON Schema 和执行分派。建议先允许一个工具，每次最多返回两条记录，并附命中总数。用下面的参数定义起步。
- **2 小时，跑通真实调用。** 发出带工具声明的模型请求，读取它实际返回的工具名、参数与调用 ID；本地执行后保留模型上一轮完整消息，并按供应商协议回传工具结果。以 Anthropic Messages 为例，`tool_use.id` 对应后续 `tool_result.tool_use_id`。再次请求模型得到地址答复。存一份去掉凭据的轨迹。
- **3 小时，建题与测试。** 写 4 道开发题，覆盖名称、地区、时间、证据缺失。第 2 周调参前另锁定 8 道留出题及参考证据，成对改写放在同一组。课件公开演示的题放开发集；留出题可用其他馆或独立问题组。答案文件留在评测端，生成时只给查询。

```json
{"type":"object","properties":{"query":{"type":"string","minLength":1},"limit":{"type":"integer","minimum":1,"maximum":2}},"required":["query"],"additionalProperties":false}
```

**验收。** `search("花园街")` 包含 `E06`，`search("油尖旺")` 返回两家，空字符串触发参数错误。提交一次真实工具轨迹：用户消息、模型请求、本地执行结果、带调用 ID 的回传和最终答复。尚无模型接入时，用脚本响应跑通单测，并将“真实调用”标为待补。[官方时刻表](https://www.hkpl.gov.hk/tc/locations/opening-hours-04.html)

[本周理论讲义](./theory.md) · [本周每日课程](./daily.md) · [课程总目录](../../README.md)
