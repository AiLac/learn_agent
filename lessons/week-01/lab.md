# 第 1 周实践讲义｜亲手运行、拆开再接好一个 Agent

## 准备与第一条轨迹

在仓库根目录打开 PowerShell，准备 Python 3.9+ 和 JDK 17+，用 `java -version` 核对。下面命令都可以离线运行，Linux/macOS 把 `py -3` 换为 `python3`。

```powershell
py -3 examples/agent-loop/run.py sun
```

应看到以下三行。运行前先遮住最后一行，只用中间的观察推一次结论。

```text
mode=scripted case=sun
c1 lookup_hours -> FOUND hours:E06 SUN 09:00-17:00 | rounds=1 toolAttempts=1
c2 finish -> DONE closed at 19:00 [hours:E06] | rounds=2 toolAttempts=1
```

打开 [AgentHost.java](../../examples/agent-loop/AgentHost.java)，依次在 `step`、`lookup`、`finish` 打断点。第一处收到的字段为调用 ID、动作名、参数、引用。第二处把 `observedHours` 从 false 改成 true。最后一处检查同一个范围内的时间条件。Python [驱动程序](../../examples/agent-loop/run.py)从[课程快照](../../data/hk-study-rooms/search-v2/evidence.json)选取 `hours:E06` 的星期切片，把值交给 Java 工具；初始模型消息中没有时段。驱动程序负责把 Java 的观察送回下一轮。离线运行时，`scripted` 按教学情景提出动作，用来稳定复现分支。

## 做三个能解释因果关系的改动

1. **先变输入。** 跑 `sat` 和 `sun`，记录模型轮数、工具尝试数、时段与结论。对象相同且调用次数相同，区别来自证据切片。如果结果仍一样，优先查星期映射与 `finish` 的区间判断。
2. **再变观察。** 跑 `timeout`。工具已经消耗一次尝试，但没有观测到时段。第二轮允许生成“本次未核实”。把它跟 `early` 放在一起看，后者根本没查就申请提交肯定结论，宿主应拒绝。为两个结果写不同的业务提示。
3. **最后变决策。** 跑 `wrong`。工具与数据均成功，模型提交了错误判断。在自己的副本里临时跳过 `finish` 中检查区间的那一行，重跑一次 `wrong`，记录谁放过了错误；恢复该行再跑。这个小实验展示引用有效与结论有效的区别。

| 场景参数 | 必须观察到的终态或原因 | 能检验的问题 |
| --- | --- | --- |
| `ambiguous` | ASK_USER、0 次工具尝试 | 缺星期时开发者是否允许模型追问 |
| `forbidden` | REJECTED、unknown_tool | 模型说要订场时宿主会不会执行 |
| `repeat` | LIMIT、tool_attempts，已执行 2 次 | 新调用 ID 能否绕过业务预算 |
| `replay` | REJECTED、replayed_call_id | 同一调用 ID 的重放是否会再次调用工具 |

另外试 `missing-day` 和 `skip`。前者故意在缺星期时读，宿主返回 NEED_DAY，实际查表次数保持 0；后者在明确星期、没有尝试取证时直接报未知，宿主拒绝。只有观察到本次读取真的失败，才允许这道已知星期题降级。

## 一份不用 SDK 也能看懂的线上消息

下面是入门适配器使用的消息形状，为讲解手写。第一轮请求含 system、用户问题和 tools，服务返回 assistant；宿主执行后，再发起一次模型请求，在原历史末尾追加下列两条。工具结果与断言均可由程序解析。

```json
[
  {"role":"assistant","content":null,"tool_calls":[{"id":"c1","type":"function","function":{"name":"lookup_hours","arguments":"{\"place\":\"E06\"}"}}]},
  {"role":"tool","tool_call_id":"c1","content":"{\"status\":\"FOUND\",\"detail\":\"hours:E06 SUN 09:00-17:00\"}"}
]
```

`arguments` 和 `content` 在这种线上格式里是字符串，解码后才得到对象。用相同 ID 配对很重要，应用可以同时保存业务地点 E06、证据 hours:E06，两者都无法替代本轮调用的 c1。

## 把决策者换成真实模型

当前示例同时提供脚本决策与模型接口。下例适用于提供 Chat Completions 兼容格式、支持 `tools` 和 `tool_choice=required` 的服务。把模型名、完整 HTTPS 请求 URL 和密钥放入本地环境变量 `AGENT_MODEL`、`AGENT_CHAT_URL`、`AGENT_API_KEY`。只把它们发往自己信任的服务地址。

```powershell
py -3 examples/agent-loop/run.py sat --live
py -3 examples/agent-loop/run.py ambiguous --live
```

真实调用需要自己的模型访问权限。每轮模型返回一个函数提议，Python 将提议交给与回放相同的 Java 宿主；观察消息用 `tool_call_id` 关联。提供商若返回多个候选工具调用或普通文本，这个入门适配器会报错；记为接口或策略不兼容。模型输出错误被 Java 拒绝也要保留，不能改作成功样例。没有密钥可以做完离线作业，但“模型能否主动选对工具”一栏须标为未测。

## 从空实现练一次（约 2 小时）

在自己的练习分支清空 `finish` 的方法体。先写出四个输入和预期：没有观察、来源 ID 错、周日答开放、周日答关闭。按“先验有没有证据，再验引用，再验时间，最后渲染”的顺序重写；把前面几条命令当回归测试。接着把固定流程写成另一方法：星期未知直接追问，已知则查表一次并判区间。对同一道题记录两种方案的模型轮数，结合第 2 周实验继续比较。

**提交自己的作业。** 一条成功轨迹、一条失败轨迹、一次你有意破坏后修好的断言，以及 120 字说明“下一个动作是谁决定的，执行和验收是谁负责的”。只保存公开事实与可观测动作。

[当日课程](daily.md) · [本周理论](theory.md)
