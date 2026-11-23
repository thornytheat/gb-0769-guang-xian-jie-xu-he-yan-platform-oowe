# 光纤接续核验台

验收员从 A、B 两端 OTDR 事件原件和设计清单复算接续损耗。首页比对双端轨迹帧与设计接头，按 `J`、`K` 或使用跳检按钮定位证据。左侧七个入口分别处理采信、校准、配对、判损、对账、留档和签发。

`docker compose up --build` 后访问 `http://localhost:18468/`。本地先执行 `pip install -r requirements.txt`，再运行 `python -m flask --app app.main run --port=18468`，用 `pytest -q` 验收。`FIBER_DB` 设置 SQLite 文件，Compose 的命名卷保留运行记录。

各预览和留档 API 接收 `{"sample":"dirty"}`、`{"sample":"clean"}` 或 `{"traces":{"a":"CSV","b":"CSV","design":"CSV"},"settings":{...}}`。参数示例见 `sample_data/dirty/link.json`。从留档页提交，在签发页下载核验包。

盘留登记册为可选第四源 `slack.csv`（`coil_id,route_m,length_m,kind`，`COIL` 盘留 / `CLEAR` 无盘留确认）。有登记册时，对账把仪表链程扣减盘留后再与路由里程对齐，登记里程之外的接头挂 `PENDING_SLACK_RECORDS`，已确认区段照常验收；同里程接头各认各的双端配对。补录调用 `POST /api/inspections/<id>/slack`：原留档不可变，重算只在身份变化时新建档案，重试不重复建档，旧签发件仍按原证据核验。

- [模块与独立复算](docs/DEPTH.md)
- [字段与规则](docs/DATA-DICTIONARY.md)
