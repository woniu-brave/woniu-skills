# 本地套图批量制作

逐商品单独建立事实和风格。先向用户展示商品、预定图型、张数、款色、缺图或不确定项。用户已确认范围及参数时可直接按其指示执行。支持试做一个商品或一张首图，也可直接做已确认的多款。上游清单仅作输入，任务状态及图片在工作目录中记录。

## 输入

使用 UTF-8 CSV（可由任意表格软件另存）或 JSON。以[表格样例](batch-example.csv)为起点。CSV 每行一个独立款色，并在 `images` 中用 `|` 分隔参考文件路径。JSON 为对象数组，其中 `images` 可为字符串数组。可用字段如下。

- `sku` 是唯一的款色或变体 ID，`name` 是商品名，`images` 是商品证据路径或经用户提供的 HTTPS 链接。相对路径按输入文件目录解析。
- `category`、`claims`、`platform`、`style`、`ratio`、`count`、`language`、`model` 和图型列表均可作为制作资料；最终用逐张制作卡表达实际图型、个数和参数。`eligible` 留空表示可纳入，填 `false` 表示跳过。缺图或文件不可用的行有单独状态。收到 XLSX 时，用当前环境的表格能力读相应工作表，解析可访问的附件，再转换为 CSV 或 JSON 给本地脚本。

## 清单、任务与上游交接

收到上游选品结果或现有表格时，先查看实际字段和记录。把商品编号映射到 `sku`，相同编号的多个视图归同款，实售颜色不同则各建一条。映射款名、商品图、品类、平台、卖点及审核状态，保持上游的可追溯引用。申请只做通过项时跳过待审及未通过行，列明缺图和不在范围的行。价格、库存等字段只在任务明确需要时使用。

把商品清单、待生成任务和成品记录分开。先回填已知信息，并让用户看总览，未明确的卖点标作建议。依用户已给范围或其答复决定比例、模型、语言、试跑或全量、自动推荐图型或自选图型。自选可从预填候选里增删。跨品类选用同一套图型名称，图型不适用时对应替换，仍以选定张数为准。使用云表格时，同类商品可按图型列存放图片，混类可用有顺序的图片列并保留行内的图型映射。任务以 SKU 和单图 ID 去重，状态随实际生成和验收更新。先跑指定一款的任务交付后，等用户决定是否继续其他款。

用户明确要求接入外部表格或从链接读商品资料时，检查当前连接器或浏览工具能否读取指定对象，以及所需的写入和附件能力。只有需要写回时才检查相应授权。保留源清单，以单独的结果表记录任务、图型、进度和逐张成品，已有结果表优先复用。照片和成品附件按连接器支持的上传方式提交，写完回读编号、状态、附件和数量。当前环境未提供所需连接器时，以用户已经给的文件、可读导出或本地清单完成其余工作，明确哪些外部动作未完成。

## 执行

下列命令使用 Python 3.8 或以上版本的标准库和 SQLite。Windows 可用本机 Python 启动方式替换 `python3`，脚本路径填写本包内 [batch.py](../scripts/batch.py) 的实际路径。可在任务工作目录下运行，也可以把每个路径改成绝对路径。任务数据库保存在本地。

```text
python3 path/to/batch.py batch.sqlite3 import products.csv
python3 path/to/batch.py batch.sqlite3 report
python3 path/to/batch.py batch.sqlite3 approve HUB-BLK
python3 path/to/batch.py batch.sqlite3 plan HUB-BLK cards.json
python3 path/to/batch.py batch.sqlite3 pending --sku HUB-BLK
python3 path/to/batch.py batch.sqlite3 start HUB-BLK front
python3 path/to/batch.py batch.sqlite3 record HUB-BLK front --file output/HUB-BLK/front.png
python3 path/to/batch.py batch.sqlite3 record HUB-BLK ports --error "接口位置与实拍不符"
python3 path/to/batch.py batch.sqlite3 pending --retry
python3 path/to/batch.py batch.sqlite3 report --csv results.csv
```

`approve` 可填多个 SKU 或使用 `--all` 确认所有可处理款色。`cards.json` 是当前 SKU 的逐张规划卡数组。每张至少含唯一 `id`，用小写字母、数字和连字符。其余字段按 [逐张规划](production.md) 保存，`pending` 会连同商品资料输出。计划有变化时重新导入该 SKU 的卡片，原内容完全一致的卡保留状态，修改过的卡重新进入待生成，移除的卡不再出现在交付清单。

提交一张图前执行 `start`，用实际媒体工具生成、取得文件并人工或模型核验后才记录 `--file`。脚本记录文件哈希，已完成图被移动或更改时会重新列为缺失。批量中断时先检查仍在运行的外部任务，能取回结果就核验并记录。确定无可回收结果时，给该图记录 `--error`，再用 `pending --retry` 选择失败、已丢失的图片。普通 `pending` 同时列出尚未生成的图片。

`report` 按商品显示进度和问题，`--csv` 输出按图列出的状态、路径与错误，也记录尚未规划或被跳过的商品。交付时按 SKU 分组列出已通过文件和待补项。重跑前保留完成文件，避免覆盖关联到其他 SKU 的输出。

迁移任务目录时，把清单、规划卡、数据库、素材和产物一起移动。位于数据库目录下的路径以相对位置保存，目录外的路径需在新机器上可访问。重导相同清单可刷新缺图状态。已经导入的商品行如需改规格或挂图路径，保存为新一轮任务数据库，避免把已完成旧图误归到新商品事实。
