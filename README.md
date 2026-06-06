# market-intel

独立市场情报系统：面向全 A 复盘，构建“市场 → 行业/主题 → 个股 → 持仓 → 复盘留痕”的个人投研工作流。

定位：不是自动交易系统，不输出买卖指令；它是给人和 agent 共用的市场雷达、投研地图、风险识别器和复盘中枢。

- CLI：给自动化流程和人工复盘使用，输出稳定 JSON。
- GUI：后续可选界面，展示热点、异动、资金追捧、宏观/行业/个股/消息联动。
- 独立项目：不依赖外部私有系统，默认只读取本仓库数据、示例数据和用户提供的 runtime 文件。

竞争力不放在替代行情/交易/社区 App，而放在“个人复盘操作系统”：把全 A 热点、行业/主题池、个人持仓、风险暴露、研究证据、复核清单、agent 命令队列和 journal 留痕串成每天可执行的闭环。

## 竞争力与边界

市场上成熟股票 App 已经覆盖了实时行情、交易入口、资讯流、社区讨论、研报检索、条件选股和基础诊股。`market-intel` 不和这些能力正面对拼，核心差异是：

- **个人复盘闭环**：从全 A 复盘池、主题链路、行情/持仓输入、风险暴露、复核清单到 journal 留痕，形成每天可重复执行的流程。
- **agent-native**：所有核心命令输出稳定 JSON、readiness 状态、下一步命令队列和完成标准，方便外部 agent 接力，而不是依赖截图或页面点击。
- **持仓优先**：不只看市场热度，也检查个人持仓是否被复盘池覆盖、是否重复暴露、是否缺行情或缺上下文。
- **全 A 兼容**：默认目标是全 A 复盘，不局限于 AI 主题；AI 池只是种子样例，后续行业、概念、指数成分和持仓驱动补池都会纳入同一套覆盖状态。
- **证据闭环**：基础清单命中的标的不会直接视为已研究，必须补齐核心逻辑、关键证据和证伪风险，经过 dry-run、runtime 导入和 coverage 复验后才关闭缺口。
- **可解释结构化**：把事实、信号、风险、待验证问题和边界拆开，避免黑盒分数直接变成买卖建议。
- **本地私有数据友好**：默认只使用仓库数据、示例数据和用户提供的 runtime 文件；报告不需要公开个人持仓。

判断一个新功能是否值得做，先看它是否强化这条主线：

- 是否减少日常复盘遗漏，而不是只增加信息量。
- 是否把全 A 覆盖、个人持仓、研究证据和风险暴露连起来。
- 是否输出稳定 JSON、下一步命令和 `done_when`，让 agent 能复跑和接力。
- 是否能进入 journal 留痕，方便下一次验证上一轮假设。

明确不做：

- 不替代行情终端、交易软件、券商 App 或社区资讯流。
- 不输出买卖指令、目标价或仓位建议。
- 不承诺自动化收益；它服务的是复盘质量、风险识别和决策留痕。

首版设计文档：`docs/design.md`

产品定位与竞争力：`docs/product.md`

协作交接文档：`docs/handoff.md`

## 开发工作流

需要 Python 3.10+ 才能执行正式安装和 CI 流程：

```bash
make install
make test
make smoke
make ci
```

常用命令：

- `make install`：安装 editable package 和测试工具。
- `make test`：运行全量 pytest。
- `make smoke`：用模块入口跑 CLI smoke，不要求 console script 已安装。
- `make ci`：模拟 GitHub Actions 的安装、测试和 smoke 流程。

如果本机默认 `python3` 低于 3.10，可以指定解释器：

```bash
make ci PYTHON=python3.10
```

未安装时仍可用模块入口快速运行：

```bash
PYTHONPATH=src python3 -m market_intel.cli focus --mock --text
PYTHONPATH=src python3 -m market_intel.cli dashboard --mock --text
```

## 当前 P0 用法

本仓库已实现离线复盘池查询的最小 CLI/core。`all-a` 是面向全 A 的默认目标 universe，目前以种子覆盖运行；`ai-energy` 保留为可用主题池，后续会逐步接入行业/概念/指数成分数据扩展全 A 覆盖。

```bash
PYTHONPATH=src python3 -m market_intel.cli pool list --pool all-a --json
PYTHONPATH=src python3 -m market_intel.cli pool coverage --text
PYTHONPATH=src python3 -m market_intel.cli pool coverage --mock --text
PYTHONPATH=src python3 -m market_intel.cli pool coverage --pool ai-energy --json
PYTHONPATH=src python3 -m market_intel.cli pool list --pool ai-energy --json
PYTHONPATH=src python3 -m market_intel.cli pool explain 002837 --json
PYTHONPATH=src python3 -m market_intel.cli pool explain 002837 --text
PYTHONPATH=src python3 -m market_intel.cli hotspots --mock --json
PYTHONPATH=src python3 -m market_intel.cli holdings impact --mock --json
PYTHONPATH=src python3 -m market_intel.cli portfolio review --mock --text
PYTHONPATH=src python3 -m market_intel.cli portfolio explain 300308 --mock --text
PYTHONPATH=src python3 -m market_intel.cli brief --mock --json
PYTHONPATH=src python3 -m market_intel.cli brief --mock --text
PYTHONPATH=src python3 -m market_intel.cli watchlist --mock --text
PYTHONPATH=src python3 -m market_intel.cli map --mock --text
PYTHONPATH=src python3 -m market_intel.cli daily --mock --text
PYTHONPATH=src python3 -m market_intel.cli dashboard --mock --text
PYTHONPATH=src python3 -m market_intel.cli dashboard --text
PYTHONPATH=src python3 -m market_intel.cli focus --mock --text
```

正式安装 console script 需要 Python 3.10+：

```bash
python3 -m pip install -e .
market-intel pool explain 002837 --json
market-intel pool explain 002837 --text
market-intel pool coverage --text
market-intel pool coverage --runtime --text
market-intel hotspots --mock --json
market-intel holdings impact --mock --json
market-intel portfolio review --mock --text
market-intel portfolio explain 300308 --mock --text
market-intel brief --mock --json
market-intel brief --mock --text
market-intel watchlist --mock --text
market-intel map --mock --text
market-intel daily --mock --text
market-intel dashboard --mock --text
market-intel dashboard --text
market-intel focus --mock --text
market-intel focus --mock --text --pool ai-energy
```

日常使用建议先初始化 runtime 文件：

```bash
market-intel init runtime --json
```

可以直接从 CSV 导入 runtime：

```bash
market-intel import schema --json
market-intel import quotes examples/quotes.csv.example --runtime --json
market-intel import holdings examples/holdings.csv.example --runtime --json
market-intel import universe examples/a_share_universe.csv.example --runtime --json
market-intel import research examples/research_notes.csv.example --runtime --json
market-intel dashboard --text
market-intel agent plan --json
market-intel agent briefing --text
market-intel agent run --json
market-intel status runtime --json
market-intel validate runtime --json
market-intel pool coverage --runtime --text
market-intel daily --runtime --text
market-intel portfolio review --runtime --text
market-intel portfolio explain 002837 --runtime --text
market-intel journal save --runtime --json
market-intel journal latest --text
market-intel journal compare --json
market-intel journal timeline --text
```

导入命令的 JSON 输出是 agent-friendly 合同：

- `ok=true` 且 `errors=[]` 表示导入可用。
- `warnings` 表示可继续但需要复核的默认值或数据问题。
- `data.preview` 给出前 5 条规范化记录。
- `data.canonical_schema` 给出写入 JSON 的标准字段。
- `data.next_commands` 给出导入后的建议命令。

`status runtime` 是 agent/readiness 入口：

- `data.readiness.state` 为 `ready`、`degraded` 或 `blocked`。
- `data.validation` 复用 runtime 校验结果。
- `data.freshness` 检查行情日期是否过旧。
- `data.next_actions` 给出按优先级排序的下一步命令和是否可执行。

`agent plan` 是 agent 工作流入口：

- `data.state` 表示当前状态：`blocked`、`degraded`、`ready_needs_archive`、`ready_needs_second_archive` 或 `ready_with_compare`。
- `data.execution.next_runnable_command` 给出下一条可直接执行的命令；runtime 可用时优先进入 `market-intel agent briefing --text`。
- `data.steps` 给出完整步骤队列；`runnable=false` 表示需要人工提供文件或修正数据。
- `data.journal.can_compare` 表示是否已有至少两份日报留档可对比。
- `data.agent_contract.stable_fields` 给出适合外部 agent 依赖的稳定字段。
- `daily --json` 根级 `data.agent_contract.stable_fields` 标明日报的稳定读取路径，适合外部 agent 直接消费 `data.validation`、`data.brief`、`data.map`、`data.watchlist`、`data.portfolio_review`、`data.risk_register`、`data.review_tasks`、`data.security_review_queue`、`data.journal_actions` 和 `data.next_questions`。
- `data.risk_register` 把风险标签整理成可复核登记表，包含严重度、涉及标的、证据、复核问题、命令和完成标准。
- `data.review_path` 按风险优先级整理当天复盘路线，包含每步命令、是否可执行、涉及风险和完成标准。
- `data.security_risk_profile` 按标的聚合风险登记、证据、复核问题、记录命令和单票命令，方便直接看某只票为什么排在前面。
- `data.review_tasks[].note_prerequisite` 与 `data.security_review_queue[].note_prerequisite` 会标明记录复盘笔记前是否需要先保存日报留档；agent 应先执行其中的 `archive_command`，再执行对应的 `journal note`。
- `data.command_queue` 把日报里的复核、留档和记录命令整理成扁平队列；agent 应按 `rank` 执行，跳过 `runnable=false` 的命令，并尊重 `requires_prior_command`。

`dashboard` 是日常第一屏工作台：

- 默认面向 `all-a`，复用 `agent run` 的只读复盘结果，把全市场扫描、持仓压力、证据缺口、行动队列和交接压缩到一屏。
- `dashboard --mock --text` 是离线试跑入口，不读取 runtime、不暴露个人持仓，用示例行情和示例持仓展示完整工作台合同。
- `data.coverage_context` 会在第一屏展示 `all-a` 的覆盖底座、A 股基础清单是否接入、行业/概念/指数字段覆盖率、覆盖缺口和下一步命令。
- `data.review_plan` 和 `data.action_lane` 会把 `coverage_review` 排在热点/持仓复核前，先确认覆盖边界再看市场结论。
- `data.market_pulse` 汇总全市场板块、候选复盘标的、覆盖状态、why_now 和下一条只读 JSON 命令。
- `data.portfolio_pulse` 汇总个人持仓重点、变化持仓、缺行情/缺热点上下文、重复暴露和持仓复核命令。
- `data.evidence_gaps` 只列未覆盖或待补的证据项，方便先处理数据阻塞、foundation/draft 覆盖和未读单票。
- `data.action_lane` 给出下一组可接力命令，标明 `runnable`、`requires_manual`、`already_read` 和完成标准。
- `data.review_plan` 把全市场扫描、持仓复核、证据缺口和人工留档压成有顺序的执行清单，每步都有 `json_command`、`step_type`、`done_when` 和相关标的。
- `data.handoff` 保留 agent 接手提示、下一条只读命令、人工确认项和记录模板。
- `dashboard` 仍是只读复盘入口，不写 journal，不生成买卖指令、目标价或仓位建议。

`agent briefing` 是日常复盘工作台入口：

- `data.state` 表示当前 briefing 状态：`blocked`、`degraded_needs_history`、`degraded_with_history`、`ready_needs_history` 或 `ready_with_history`。
- `data.runtime.validation` 给出 runtime 校验问题的精简明细；blocked 状态下可直接看到缺文件、坏 JSON 或缺字段等错误。
- `data.daily` 汇总今日最强热点、观察项、持仓复核、风险和数据告警；观察项和持仓重点项会带可继续深入的单票命令。
- `data.daily.risk_register` 是 compact 后的风险登记表，适合 agent 先按严重度和涉及标的数决定复核顺序。
- `data.daily.review_path` 是 compact 后的风险优先复盘路线，适合 agent 直接按 `rank` 接力执行。
- `data.daily.security_risk_profile` 是 compact 后的标的风险画像，适合 agent 在单票复核前先读取关联风险、证据和记录前置条件。
- `data.daily.review_tasks` 给出今天可照着执行的复核任务，每项包含依据、命令、完成标准和可复制的 `journal note` 记录命令。
- `data.daily.security_review_queue` 给出今天优先核对的标的队列，按持仓复核、观察清单和风险上下文合并排序，并带单票复核笔记命令。
- `data.daily.journal_actions` 给出保存日报、查看最近留档、查看笔记和时间线的入口；mock 日报会标记保存动作为不可直接执行。
- `data.daily.command_queue` 是 compact 后的日报命令队列，包含 `command`、`json_command`、`runnable`、`state_effect`、`requires_prior_command` 和完成标准。
- `data.daily.portfolio_exposure` 汇总重复链路和重复主题暴露，并列出涉及持仓，方便先看组合是否过度扎堆。
- `data.daily.validation.warnings/errors` 给出精简后的数据问题明细，包含 `code`、`symbol/path`、缺失字段和短原因，方便 agent 不跳转也能定位问题。
- `data.current_change` 对比当前 runtime daily 与最近一份日报留档，适合在保存当前日报前先看变化集中在哪里。
- `data.security_review_queue` 合并数据告警、持仓复核、观察清单和当前变化，给出今天优先核对的标的、原因、风险标签和深入命令。
- `data.history` 汇总 journal timeline/compare 的留档状态、最近转折和最近一条用户复盘笔记。
- `data.review_focus` 给出按优先级排序的复核焦点，每个焦点都带依据和可继续执行的命令。
- `data.review_checklist` 给出可照着执行的复核清单，每项包含依据、命令和完成标准。
- `data.journal_prompt` 给出当天留档模板，覆盖数据质量、市场结构、组合暴露、标的复核和当前变化；每段都带可复制的 `journal note` 命令骨架。
- `data.command_queue` 把下一步命令展开成 agent 可执行队列，包含 `command`、`json_command`、`purpose`、`input_context`、`read_fields`、`output_use`、`done_when`、`state_effect`、`related_focus` 和是否会写入状态。
- `data.next_commands` 给出下一组可直接运行的 CLI 命令。

`agent run` 是只读自动复核入口：

- 它先生成 `agent briefing`，再按 briefing 和 daily 的 command queue 执行只读 JSON 命令。
- `data.review_digest` 按市场结构、组合压力、标的复核、风险观察、变化跟踪、数据质量和下一步归并结果，适合作为第一读取区。
- `data.review_digest.data_repair_plan` 把数据错误/告警转成按 symbol 和修复类型整理的只读修复计划；不会自动改 runtime 文件。
- `data.review_digest.portfolio_pressure` 汇总重复链路/主题，并标出每组里的变化成员、组级复核问题和只读 JSON 命令。
- `data.review_digest.holding_dashboard` 从股民持仓视角汇总优先级分布、相对留档变化、缺行情/缺热点上下文、主题重叠、首要核对问题和单票 JSON 命令。
- `data.review_digest.change_tracking` 同时压缩当前 runtime 相比最近留档的变化，以及最近两份留档之间的历史转折。
- `data.review_digest.security_workbench` 按单票汇总复核原因、变化角色、重复暴露、风险标签、只读命令和记录前置条件。
- `data.review_digest.security_cards` 按 symbol 生成单票复核卡片，聚合优先级、行情/热点、风险、暴露、证据、待补点、下一条只读 JSON 命令、记录模板和下次观察。
- `data.review_digest.evidence_checklist` 把数据质量、变化、重点持仓、组合压力和市场结构转成证据充分性清单，列出已有证据、待补证据、覆盖状态、只读 JSON 命令和记录模板。
- `data.review_digest.hypothesis_board` 把证据清单转成可证伪观察假设，包含支持证据、薄弱点、验证步骤、失效信号、只读 JSON 命令和记录模板；它不是交易指令。
- `data.review_digest.journal_draft` 给出可编辑的五段复盘草稿、预填充 `journal note` 命令、命令模板和保存日报前置；它不会自动写入 journal。
- `data.review_digest.attention_queue` 把数据修复、变化核对、重点持仓、风险复核和人工留档整理成带 `rank`、`json_command`、`runnable`、`requires_manual`、`already_read`、`linked_result`/`linked_context`、`journal_note` 与完成标准的关注队列；`journal_note` 会给出分区、预填记录命令和保存日报前置。
- `data.review_digest.followup_watch` 把数据质量、变化持仓、重点持仓、组合压力和市场结构转成下次观察计划，包含观察标的、核对问题、只读 JSON 命令和记录模板；没有历史变化时也会覆盖重点持仓和集中暴露。
- `data.review_digest.review_completion` 汇总本轮复盘是否可收尾，标出数据、证据、假设、关注队列、留档草稿和下次观察的状态、阻塞数量、人工确认项和下一条只读 JSON 命令。
- `data.review_digest.review_handoff` 把接手复盘需要的最小上下文聚合到一起，包含接手提示、待读 JSON 命令、人工确认项、记录模板和下次观察项。
- `data.results` 给出已执行命令、摘要、关键观察、错误和告警；不会嵌入完整大 payload。
- `data.skipped` 给出跳过原因；保存日报和记录复盘笔记这类写入命令会被跳过。
- `data.manual_followups` 汇总需要人工确认后再运行的写入命令。
- `data.agent_contract.stable_fields` 标明外部 agent 可依赖的执行结果字段。

`agent next` 是紧凑接手入口：

- 它复用 `agent run` 的只读复核结果，只返回 `review_handoff`、`review_completion` 和 `security_cards`。
- `data.review_handoff.command_chain` 给出去重后的继续复盘命令链，区分只读步骤和人工确认步骤。
- `--symbol <代码>` 可以只输出某只持仓的单票卡片和相关命令链，适合快速接手单票复核。
- foundation 持仓会在 `security_cards.cards[].research_workflow` 和 `review_handoff.manual_items[].workflow_steps` 中给出 `pool research -> import research --dry-run -> import research --runtime -> coverage` 的补证据路径；`review_handoff.command_chain` 会把这些步骤展开成只读/人工混合命令链。它仍要求人工填写核心逻辑、关键证据和证伪风险。
- 适合外部 agent 或用户在上一次复盘后快速接手，不必从完整 digest 里重新拼命令。

也可以手工编辑：

- `data/runtime/quotes.json`
- `data/runtime/holdings.json`

之后每天可以直接跑：

```bash
market-intel validate runtime --json
market-intel agent plan --text
market-intel agent plan --json
market-intel dashboard --text
market-intel dashboard --json
market-intel agent briefing --text
market-intel agent briefing --json
market-intel agent run --text
market-intel agent run --json
market-intel status runtime --text
market-intel focus --runtime --text
market-intel daily --runtime --text
market-intel portfolio review --runtime --text
market-intel portfolio explain 002837 --runtime --text
market-intel brief --runtime --text
market-intel scan --runtime --text
market-intel watchlist --runtime --text
market-intel map --runtime --text
market-intel pool explain 002837 --runtime --text
market-intel hotspots --runtime --json
market-intel holdings impact --runtime --json
```

`validate runtime` 会检查：

- runtime 文件是否存在。
- JSON 结构是否正确。
- 行情/持仓必填字段是否完整。
- symbol 是否能匹配到当前复盘池。
- 是否有重复 symbol。
- 持仓是否缺行情，行情是否不在持仓里。

`pool coverage` 是复盘池覆盖度自检：给出 pool 范围、状态、A 股数量、市场分布、层级分布、数据质量标记、覆盖缺口和下一步命令。当前 `all-a` 会明确标记为 seed 覆盖，提醒 agent 和人不要把它当作完整全 A 结论。

`data.data_quality_queue` 会把 `invalid_symbol`、`column_shift_suspected`、`missing_role`、`unknown_layer`、`duplicate_symbol_exposure` 等标记压成有优先级的清理队列。每项包含 `flag`、`severity`、`affected_count`、`samples`、`suggested_action`、`done_when` 和复验命令，方便人或 agent 先清最影响覆盖可信度的问题。

可以先用 A 股基础清单扩展 `all-a` 的底座覆盖。CSV 支持 `symbol/name/industry/concepts/index_membership/listing_status`，也支持常见中文列名如 `证券代码/证券名称/行业/概念/指数成分/上市状态`。基础清单只代表“代码、名称、行业、概念、指数成分”的覆盖，不等于研究证据完成；匹配到基础清单的持仓会进入待复核覆盖队列。

```bash
market-intel import universe examples/a_share_universe.csv.example --runtime --json
market-intel pool coverage --text
market-intel pool coverage --runtime --text
```

`market-intel init runtime --json` 也会生成 `data/runtime/a_share_universe.csv` 和 `data/runtime/research_notes.csv` 模板。需要临时叠加额外清单时，仍可使用 `MARKET_INTEL_A_SHARE_UNIVERSE_PATHS=...`。

研究证据用 `research_notes_v1` CSV 维护，支持 `symbol/name/status/thesis/evidence/invalidation/updated_at/source`，也支持常见中文列名如 `证券代码/证券名称/状态/核心逻辑/关键证据/证伪风险/更新日期/来源`。只有 `status=reviewed` 且核心逻辑、关键证据、证伪风险三项齐全时，基础清单命中的持仓才会从 `foundation` 升级为 `confirmed`。

```bash
market-intel import research examples/research_notes.csv.example --runtime --json
market-intel pool coverage --runtime --text
market-intel agent next --text
```

需要临时叠加研究证据时，可使用 `MARKET_INTEL_RESEARCH_NOTES_PATHS=...`，不会改主复盘池。

如果 coverage 里出现 `foundation_research_missing`，可以先导出待办草稿，再人工补齐三项证据后导入：

```bash
market-intel pool research --runtime --output data/runtime/research_notes.todo.csv --json
market-intel import research data/runtime/research_notes.todo.csv --dry-run --json
market-intel import research data/runtime/research_notes.todo.csv --runtime --json
market-intel pool coverage --runtime --text
```

`pool research` 只导出 foundation 持仓的研究证据草稿，不自动生成研究结论。

`scan` 是全 A / 复盘池扫描入口：只要求行情源，持仓源可选；有 A 股基础清单时按行业、概念、指数成分聚合，没有基础清单时退回当前复盘池链路。它输出 `sector_groups` 和 `candidate_securities`，每个候选都包含 `why_now`、`checklist`、`coverage_state`、`research_status`、后续命令和完成标准。`scan` 用来回答“今天全市场哪些板块和标的值得复盘”，不生成买卖动作、目标价或仓位建议。

```bash
market-intel scan --runtime --text
market-intel scan --quotes-file data/runtime/quotes.json --json
```

传入持仓源后，它还会检查个人持仓是否已被复盘池覆盖：

```bash
market-intel pool coverage --runtime --text
market-intel pool coverage --holdings-file data/runtime/holdings.json --json
```

未覆盖持仓会进入 `data.expansion_queue`，每项包含 `symbol/name`、候选补池行、必填字段、复核问题、后续命令和完成标准。这个队列是“补池任务”，不会自动写入池子文件；补入前需要人工或 agent 先确认行业/主题链路、角色和核心逻辑。

可以把补池任务导出成可编辑 CSV 草稿：

```bash
market-intel pool expansion --runtime --output data/runtime/pool_expansion.csv --json
market-intel pool expansion --review-file data/runtime/pool_expansion.csv --text
MARKET_INTEL_POOL_EXTRA_PATHS=data/runtime/pool_expansion.csv market-intel pool coverage --runtime --text
```

`pool expansion` 只写候选草稿，不会改主池。编辑 CSV 时至少要补齐 `section`、`level` 和 `desc`，再用 `--review-file` 检查草稿是否还有 blocker。通过 review 后，用 `MARKET_INTEL_POOL_EXTRA_PATHS=...` 把草稿叠加到默认复盘池上验证覆盖缺口是否消失。`status=candidate` 或仍含“待确认”的补池行会被记为 `draft_pool_matches`，代表“已临时覆盖但还要复核”，不会被当成正式覆盖完成。`MARKET_INTEL_POOL_PATH=...` 仍可用于完全替换默认池，适合测试一个独立 pool CSV。

`watchlist` 是盘中盯盘清单：把热点领涨标的和持仓标的合并去重，标出链路、涨幅、成交放大、回落、风险和是否持仓。

`portfolio review` 是从持仓出发的复盘清单：逐个持仓汇总链路暴露、行情、热点上下文、风险标签和待复核问题，并展开重复链路/重复主题涉及的持仓，适合盘后检查“我手上的票今天需要看什么”。

`portfolio explain <symbol>` 是单票持仓复核：针对某个持仓代码展开行情、热点、链路、风险、相关持仓和复核问题。它和 `pool explain` 的区别是：`pool explain` 解释公司在池子里的定位，`portfolio explain` 解释当前持仓上下文。

`map` 是链路地图：按行业/主题层级聚合热点、持仓暴露、重复暴露和风险复核点，适合复盘时先看结构。当前种子池包含算力、运力、存力、电力、人才密度等 AI 相关层级，后续会扩展到全 A 行业和概念层级。

`daily` 是复盘总入口：先做数据检查，再合并 `brief`、`map`、`watchlist`、组合暴露和 `portfolio review`，并生成今日复核任务，输出一份适合每天留档和 agent 读取的报告。

`dashboard` 是推荐的日常第一屏：复用 `agent run` 的结果，但只保留全市场、持仓、证据缺口、行动队列、复盘计划和交接信息，适合人快速扫一眼，也适合 agent 读取稳定 contract 后继续执行。

`focus` 是日常第一屏入口：复用 `daily` 的完整计算，但只保留最强链路、数据状态、组合压力、优先标的和下一步命令，适合快速回答“今天先看什么”。每个优先标的会给出 `why_now`、`checklist`、`note_command`、`journal_ready`、`done_when` 和下一条命令，让人可以照着复核并留痕，也让 agent 能直接接力执行。

`journal` 是日报留档：保存完整 `daily` JSON，并提供列表、最近一次读取和两份日报对比入口，方便后续做历史复盘和趋势对比。

当前本机 `python3` 若低于 3.10，可先使用 `PYTHONPATH=src python3 -m market_intel.cli ...` 跑测试和验证。

也可以传入手工 JSON，不必只用 mock：

```bash
market-intel hotspots --quotes-file data/runtime/quotes.json --json
market-intel holdings impact --holdings-file data/runtime/holdings.json --json
market-intel portfolio review --quotes-file data/runtime/quotes.json --holdings-file data/runtime/holdings.json --text
market-intel portfolio explain 002837 --quotes-file data/runtime/quotes.json --holdings-file data/runtime/holdings.json --text
market-intel brief --quotes-file data/runtime/quotes.json --holdings-file data/runtime/holdings.json --json
market-intel brief --quotes-file data/runtime/quotes.json --holdings-file data/runtime/holdings.json --text
market-intel watchlist --quotes-file data/runtime/quotes.json --holdings-file data/runtime/holdings.json --text
market-intel map --quotes-file data/runtime/quotes.json --holdings-file data/runtime/holdings.json --text
market-intel daily --quotes-file data/runtime/quotes.json --holdings-file data/runtime/holdings.json --text
market-intel focus --quotes-file data/runtime/quotes.json --holdings-file data/runtime/holdings.json --text
```

日报留档：

```bash
market-intel journal save --runtime --json
market-intel journal list --text
market-intel journal latest --json
market-intel journal latest --text
market-intel journal note --section market_structure --text "记录今天的复盘观察"
market-intel journal notes --section current_change --text
market-intel journal notes --query "组合暴露" --json
market-intel journal compare --json
market-intel journal compare --text
market-intel journal compare --base <entry_id> --current <entry_id> --json
market-intel journal timeline --json
market-intel journal timeline --text
```

`journal note` 会把用户复盘笔记追加到最近一份日报留档；也可以用 `--entry-id` 指定留档，用 `--file <path>` 保存较长笔记。`journal notes` 可以集中查看最近的用户复盘笔记，并支持 `--section` 或 `--query` 筛选。

`journal compare` 默认对比最近两份日报留档；也可以显式指定 `--base` 和 `--current`。JSON 中的稳定字段包括：

- `data.base_entry` / `data.current_entry`：两份留档的元信息。
- `data.changes.risk_flags`：风险标签新增、减少和保持。
- `data.changes.watchlist`：观察项新增、减少、字段变化和数量变化。
- `data.changes.portfolio_review`：持仓复核新增、减少、优先级变化、风险变化和数量变化。
- `data.changes.hotspots`：热点链路新增、减少、字段变化和当前最强链路。
- `data.changes.validation`：数据检查摘要、告警代码和错误代码变化。
- `data.next_commands`：可继续执行的命令。

`journal timeline` 默认读取最近 5 份日报留档，按时间从旧到新输出历史点和相邻转折；每个历史点会带最近复盘笔记摘要。它适合回答“最近几次复盘里，热点、风险、持仓复核和我的主观观察怎么变了”。JSON 中的稳定字段包括：

- `data.found` / `data.can_compare`：是否已有留档、是否至少两份可形成转折。
- `data.points[]`：每份留档的 `entry_id`、`trade_date`、风险数量、观察数量、持仓复核摘要和当前最强热点。
- `data.points[].latest_note`：该留档最近一条用户复盘笔记摘要。
- `data.transitions[]`：相邻留档之间的风险、观察项、持仓复核、热点和数据检查变化摘要。
- `data.next_commands`：继续查看单份日报或进入精确 compare 的命令。

`quotes.json` 可以是数组，也可以是 `{ "quotes": [...] }`；`holdings.json` 可以是数组，也可以是 `{ "holdings": [...] }`。

CSV 导入支持常见中英文列名。示例：

```bash
market-intel import quotes examples/quotes.csv.example --dry-run --json
market-intel import holdings examples/holdings.csv.example --dry-run --json
market-intel import research examples/research_notes.csv.example --dry-run --json
market-intel import quotes quotes.csv --output data/runtime/quotes.json --json
market-intel import holdings holdings.csv --output data/runtime/holdings.json --json
market-intel import universe a_share_universe.csv --output data/runtime/a_share_universe.csv --json
market-intel import research research_notes.csv --output data/runtime/research_notes.csv --json
```

可参考：

- `examples/quotes.example.json`
- `examples/holdings.example.json`
- `examples/quotes.csv.example`
- `examples/holdings.csv.example`
- `examples/a_share_universe.csv.example`：跨金融、消费、医药、周期、TMT、制造、能源等板块的公开样例基础清单，不包含个人持仓。
- `examples/research_notes.csv.example`
