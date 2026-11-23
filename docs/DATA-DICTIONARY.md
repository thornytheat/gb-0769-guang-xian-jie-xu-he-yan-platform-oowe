# 轨迹、接头与判损字段

A、B 的 CSV 必填 `event,distance,unit,loss_db`，设计清单必填 `joint,distance,unit,limit_db`。字段可换列序，UTF-8 首行 BOM 会清理。ID 为原形字符串，按来源和 ID 分键。同键比较归一距离与损耗，完全相同保留首行，冲突整组隔离。记录保留起始物理行和原值。空白单元格、哨兵及 JSON null 分别校验。空文件、全空行、仅表头分别为 `EMPTY_FILE`、`BLANK_FILE`、`HEADER_ONLY`。每源最多 350 个正文记录、250,000 字符。

距离单位可为 mm、m 或 km，归一成整数毫米。采集损耗 dB 支持有符号值，精确到毫 dB。配置 `length_m` 为光路总长，`zero_a_m/zero_b_m` 为两向测量偏置。统一链程 A = A 原读数减 A 起偏，B = 全长减去 B 原读数扣掉 B 起偏的结果。校准有效范围是闭区间 `[0,L]`。出界测量归隔离，出界设计仍在清单中并标缺证。设计本来就在 A 端坐标系。

双端事件按链程和 ID 排序。一对一单调配对先最大化数量，再最小化距离差总和，最后依照同状态优先配对、保留较早 A 端、再保留较早 B 端的固定遍历作稳定裁决。容差 `pair_tol_m` 含等号。配对中点的分辨率为半毫米。配对双方的读数取带符号平均作为净损耗，保留单向负值和原行。通过阈值含等号，净值为负记录无效净增益。

设计点与配对中点再次按相同优化目标一对一对齐，使用 `design_tol_m`。每接头以自己的 `limit_db` 判定，损耗模块的 `reference_limit_db` 用于单独预览。单端或孤配均保留。运行清单含源 SHA-256、校准参数、时间 UTC、耗时、版本、证据。快照摘要可用排序键、紧凑 JSON 和 UTF-8 重算。

## 盘留登记册（可选第四源 slack.csv）

表头固定为 `coil_id,route_m,length_m,kind`，列序可调、首行 BOM 会清理，解析与隔离规则同轨迹源（重复行 `DUPLICATE_EVENT`、同键冲突整组 `CONFLICTING_EVENT`、每源 350 行上限）。`kind` 仅允许 `COIL`（盘留，长度为正整数毫米）与 `CLEAR`（无盘留确认，长度必须为 0，否则 `CLEAR_NOT_ZERO`）；未知类型记 `BAD_KIND`。里程按米解析、归一毫米，越出 `[0,length_m]` 抛 `SLACK_OUTSIDE_LINK`。

登记册按路由里程排序后给每条附 `cumulative_mm`（仅 COIL 累加）。仪表链程转路由里程时，扣减读数已越过的盘留累计长度（半毫米整数运算，闭区间：盘留仪表位置等于读数时即扣减）。登记册覆盖边界是最后一条登记（COIL 或 CLEAR）的路由里程；边界之外的设计点判 `PENDING_SLACK_RECORDS`，`evidence_ready=false`。无登记册时完全沿用遗留对账行为。对账行附 `slack_covered`、`coil_ids`、`evidence_ready`，汇总附 `pending_slack`、`ready_count` 与 `slack` 登记册视图。

补录接口 `POST /api/inspections/<id>/slack` 接收 `{"slack":"CSV 文本"}`；留档身份按 SPEC、全部源摘要（含 slack）与设置重算，原始 `material` 随快照持久化以便重算。身份变化新建档案（201），身份不变复用旧档（200）；旧档案与旧核验包永不改写。
