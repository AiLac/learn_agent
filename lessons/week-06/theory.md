# 第 6 周 · 理论讲义｜MCP 工具边界与可恢复的只读查询

## 一次查询为什么要跨进程

自习室证据查询原来是一个 Java 方法。如果另一套 Agent 客户端也要使用它，可以把参数、结果和错误通过 MCP 暴露出来。客户端先和服务端协商协议及能力，再发现工具，最后按名称和参数调用。工具服务器可以独立更新数据，但多了一条会失败、会等待的传输路径。把同一工具留一份本地调用基线，才能测出这层抽象的成本。

在本课采用的协议版本中，客户端发送 `initialize`，收到响应后发送 `notifications/initialized`；协商了工具能力后可调用 `tools/list` 与 `tools/call`。JSON-RPC 请求 ID 匹配一条请求与响应；模型工具调用 ID 匹配模型消息；业务地点 ID 如 E06 匹配事实。三者可以在同一轨迹中关联，作用各不相同。

## 空结果、执行失败和传输失败

| 本次看到的信号 | 可以解释什么 | Agent 下一步 |
| --- | --- | --- |
| 工具成功，证据列表为空 | 已查询的资料没有该主题 | 说清“此来源未确认”，或查询另一有依据的来源 |
| 已知工具执行失败 | 这次取证没有完成 | 判断是否可重试，保留具体失败类别 |
| RPC 错误或传输超时 | 协议请求被拒，或调用方没有及时拿到结果 | 记录错误层级。超时不能推出服务端从未执行 |
| 工具成功，返回附条件时间 | 只有符合该馆、日期与服务区域时才支持结论 | 校验适用范围，把来源和事实一起回传 |

MCP 工具执行错误可由工具结果的 `isError` 表达。无法找到工具等协议问题可返回 JSON-RPC 错误。网络超时则可能根本没有响应。对用户都说“没有资料”，会把系统可用性故障变成虚假的领域判断。只读取证可按剩余时限做有限重试；一味重试会挤占生成完整答案所需的时间。

## 对照两种源码设计

Spring AI 的工具执行管理器从模型消息里提取工具请求并组装回传历史。LangGraph 的 `ToolNode` 处在状态图节点里，读 `_run_one` 和 `_execute_tool_sync`，找出工具选择、异常处理、消息封装三处。思考：如果 SDK 已经将异常变成工具消息，你的业务层再捕获和重试，会不会把它算成一次成功、或启动第二层重试？[Spring AI 源码](https://github.com/spring-projects/spring-ai/blob/9993102c830c132b88cb6857c0cdf41a22747432/spring-ai-model/src/main/java/org/springframework/ai/model/tool/DefaultToolCallingManager.java) · [LangGraph 源码](https://github.com/langchain-ai/langgraph/blob/e5e37b5d70dbfd93c7006bd90a658c6179a95946/libs/prebuilt/langgraph/prebuilt/tool_node.py)

自检：同一调用 ID 被重新观察到是否足以证明任务完成？还需有执行结果或检查点，才能判断是只派发了请求，还是已经取得证据。[MCP 生命周期](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle) · [MCP 工具规范](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)

[本周实践讲义](./lab.md) · [课程总目录](../../README.md)
