# 自修室检索扩展数据

第 1 周的 36 条小样本适合逐步调试。第 2 周起，用这套公开数据比较关键词/向量召回、按需查证及地点简介。扩展集包含原有 36 个 ID。

| 文件 | 内容 | 使用方式 |
| --- | --- | --- |
| [places.json](places.json) | 194 个地点，含原编号、简体名称、繁体名称、英文名称、简体地址、地区、经纬度及 CSDI 对象号 | 以地点 ID 为检索对象，支持地名改写、跨语言匹配和直线半径筛选 |
| [evidence.json](evidence.json) | 79 张带来源和适用范围的证据卡，涉及 40 个不同地点 | 按 `place_id` 关联，`text` 可建文本索引；生成时带上 `scope`、适用时段、来源和定位 |
| [dev-cases.json](dev-cases.json) | 12 道带参考地点、证据和答案的公开开发题 | 覆盖地点别名、半径、预约、费用、设施、时段和未知事实。两道周末题属于同一问题组。答案不进检索索引或提示词。 |

## 覆盖率决定可以回答什么

36 张卡是**学生自修室普通时刻表**，覆盖 36 家公共图书馆，范围限 1–2 月、6–12 月的普通非节假日。特别日期、考试季、临时通告和实时余座需要独立查证。另 36 张卡是同馆的**分馆级设施**。例如快照中 36 家都列出分馆 Wi-Fi，但只有 8 家的卡片记录育婴间；未列出的设施应标成“当前资料未确认”。分馆有 Wi-Fi 不等同于某个自修座位一定能连上。

其余 7 张卡为 4 家青年中心的自修室说明、2 张同中心其他空间的干扰材料，以及 1 张上水自修室的历史官方回复。上水在 2025 年 9 月的资料中有 178 个座位，该数字不能充当实时余座。194 个地点中有 154 个当前只有基础地点信息，不能从名称和坐标推断其预约、设施或开放情况。可以利用“存在地点但缺少资料”的案例检查 Agent 是否会越界作答。

## 三个可以马上运行的数据检查

仓库根目录下在 PowerShell 执行：

```powershell
$root = 'data/hk-study-rooms/search-v2'
$places = (Get-Content "$root/places.json" -Raw -Encoding UTF8 | ConvertFrom-Json).records
$docs = (Get-Content "$root/evidence.json" -Raw -Encoding UTF8 | ConvertFrom-Json).documents
$places | Where-Object district -eq '油尖旺' | Select-Object id,name
$docs | Where-Object place_id -eq 'N07' | Select-Object id,scope,text
$docs | Where-Object id -eq 'power:M02' | Select-Object source_url,text
```

若要运行课程 Java 子串检索基线，可执行 `py -3 examples/day-01/run.py "油尖旺" --dataset expanded --limit 6`。它使用简体名称、地区与地址；向量与证据查证仍是课程实验。

第一条查询得到 E01–E06 共六家；入门子集只包含 E01 与 E06。第二条应看到康城自修室和同中心 Ucafe 各一张卡。“青年想给笔记本接电、用免费网络复习，需要预约吗？”可以由 `youth:N07` 回答，但 `aux:N07-cafe` 只支持咖啡区自身的服务。第三条用于练习区分容量、更新时间与实时空位。

## 教学实验与效果评估

两种检索器使用同一份地点与证据文本，按地点聚合或去重后比较排名。对明确条件分别标“证据支持”“证据反驳”“证据不足”；存在未覆盖地点时，可报告“已核实的候选”，避免把它写成全港唯一答案。证据检索单独检查分馆/自修室/其他空间是否混淆。坐标能支持直线距离；需要步行时间时仍缺少路网或路径服务。

12 道开发题用于接线与回归。评估多查询泛化时，另按地点、意图与改写组留出新题，分别报告可答和不可答组的分母、检索前五相关性、简介事实支持情况。大规模索引容量、生产 QPS / P99 需要真实规模、请求分布、冷热比例、模型和网络条件；重复同一小语料只适合查链路机制。

## 来源与构建口径

- 地点编号和简体字段来自香港特别行政区政府教育局经 DATA.GOV.HK 发布的[简体清单](https://data.gov.hk/tc-data/dataset/hk-edb-studyroom-study-room-info/resource/2e072fa1-55d2-4b66-b55b-24950ca8f06a)。简繁 CSV 按唯一编号关联；繁体地点名称经 Unicode 规范化、去空白后与[教育局 CSDI 自修室图层](https://portal.csdi.gov.hk/csdi-webpage/dataset/edb_rcd_1633320468580_185)唯一匹配，再核对地区。194/194 均匹配成功。坐标取图层 Point 转 WGS84 的几何，保留七位小数。原始 CSV 与空间图层查询结果的 SHA-256 在数据文件中。数据来源为政府、教育局、DATA.GOV.HK 和 CSDI Portal，原数据知识产权归政府及相关机构。使用受 [DATA.GOV.HK 条款](https://data.gov.hk/en/terms-and-conditions)和 [CSDI 条款](https://portal.csdi.gov.hk/csdi-webpage/doc/TNC)约束。
- 普通时段以康文署香港公共图书馆[学生自修室时刻表](https://www.hkpl.gov.hk/tc/locations/opening-hours-04.html)按分馆分组核对。通过康文署[图书馆空间图层](https://data.gov.hk/en-data/dataset/hk-lcsd-csdi-libraries)定位 36 个分馆官网，在“服務及設施”栏抽取课程选用的设施事实，保存每馆 URL 与页面快照哈希。列表没有抽取的项目不作否定标签。
- 青年中心资料由[香港青年协会](https://youthspot21.hkfyg.org.hk/center/ls/)的设施页逐项核对，按空间分开归纳。上水的座位和充电事实见[康文署 2025 年 9 月书面回复](https://www.districtcouncils.gov.hk/north/doc/2024_2027/en/committee_meetings_doc/cicrc/28777/n_cicrc_2025_025_response_lcsd_ch.pdf)。每张卡保留详细来源。以上均为公开资料的课程快照，实际到访时应另查最新安排。

若要让自修室与同楼的体育馆、街市一起参与召回，可使用[香港多类别 POI 数据集](../../hk-poi/mixed-v1/README.md)。
