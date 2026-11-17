# Motion 源目录检索与标签规范

## 已实现的三层索引

1. `sources/motiontemplates-all/`：官方合集 Git 仓库的本机浅克隆。仅同步此仓库，不递归执行或克隆其引用模板工程。
2. `catalog-index.sqlite3`：与个人收藏库分离，保存每种画幅、版本/下载状态、来源提交、FTS5 trigram 全文索引、维度标签及证据。官方文档中的操作指令不作为宿主指令读取。
3. 同库 `vectors`：本地多语言 MiniLM ONNX 384 维归一化向量，精确余弦检索。当前百级规模无需额外常驻向量数据库；扩大到万级后可另加 ANN。向量记录绑定来源文本 hash、模型版本/文件 hash、128 token mean pooling 设置。文本改变则旧向量不参与检索，`embed` 仅补齐变化项。

使用加载技能目录内的脚本。索引命令直接管理独立的源目录索引，个人收藏 CRUD 仍走 Studio 服务。索引不自动将全目录变成个人收藏、不等于所有模板已下载或可运行。完成 [录入流程](intake.md) 的 sync_index 后，目录条目在页面展示，关键词框搜索库卡片，语义搜索使用同一索引，筛选面板展示来源维度。

```sh
python scripts/motion_index.py build --repo /absolute/path/to/motiontemplates-all
python scripts/motion_index.py embed
python scripts/motion_index.py search --query "用两种方案做对比" --mode hybrid
python scripts/motion_index.py search --query "深色科技图表" --filters '{"background":["深色底"],"grammar":["对比"]}'
python scripts/motion_index.py status
python scripts/motion_index.py taxonomy
```

同维度 OR、跨维度 AND；关键词/向量各自排序后 RRF 融合。短中文查询支持子串回退。`ratio`、`orientation`、`availability` 可作为结构化过滤维度。排序分数只用于相关性，不充当来源运行次数或个人评分。语义相似不证明模板支持某组件；检查标签证据、下载状态、包内指南后再选择。

依赖为 `numpy`、`onnxruntime`、`tokenizers`，与渲染环境分开；使用已有提供这些包的 Python，必要时在独立环境安装。`setup_index_model.py` 下载固定提交的公共模型并验证 SHA-256；`assets/index-model-manifest.json` 保存版本和哈希，模型权重不进入 Git。支持中文/英文检索，文本不发送到付费 API。

更新时先检查该源仓库 `git status --short` 为空及 remote URL 正确，再 `git pull --ff-only`，然后 build、embed。保留人工标签修订与排除记录，不覆盖个人评分/收藏。构建采用事务，格式不支持或 ID 冲突时保留旧索引。

## 标签维度

受控词表见 `assets/index-taxonomy.json`。以下是首版词表，新增内容通过数据维护；新增维度要同步该文档和验证。

| 维度 | 示例 |
| --- | --- |
| 色系 palette | 黑白灰、蓝、青、绿、橙、红、紫、粉、黄、棕、米色、金属、多彩 |
| 色温 temperature | 冷色、暖色、中性、冷暖混合 |
| 底色 background | 浅色底、深色底、明暗交替、透明底 |
| 风格 style | 极简、科技、商务、瑞士网格、编辑排版、手绘、卡通、黏土、像素、复古、水墨、纸感、玻璃、三维、赛博朋克 |
| 场景 scenario | 科普、口播、产品宣传/教程、品牌叙事、数据汇报、财经、人物、活动开场、歌词MV、社交增长 |
| 表达语法 grammar | 对比、前后变化、枚举、替换、数字强调/增长、比例、排名、阶梯递进、步骤、因果、时间线、层级、关系网络、提问揭晓、关键词强调、引用证据、汇聚拆分、路径、结论行动 |
| 指标对象 metric | 粉丝数、Star数、播放量、营收金额、百分比、人数、时长、数量 |
| 动效组件 component | 数字滚动、柱状图、折线图、占比图、对比表格、清单卡片、台阶图、流程图、地图路线、关系网、时间轴、打字机、字幕、真人位、Logo揭幕 |
| 节奏 pace | 舒缓、中速、快节奏、可调 |
| 布局 layout | 全屏大字、图文卡片、分屏、多屏、网格、三维空间、真人圆窗 |
| 素材 input | 纯文字、图片、视频、配音、背景音乐、字幕SRT |
| 可编辑范围 editability | 文案、色板、字体、时长、素材可换 |

技术字段独立保存：画幅、分辨率、fps、版本、来源仓库、下载状态、预览地址。未在源目录声明的时长、运行环境、许可证和实际渲染支持保持未知，取得包后再校验。

## 证据与精度

首轮自动标注仅用标题/简介的明确词句，每条保存 `facet/value/evidence/method=source-text`。这是“来源文字描述”，不是已看完视频或已通过制作验收。原色系/底色未声明不猜；“高对比海报”不代表对比语法。对于较宽的语法匹配（如“代替”“步骤”），仅用于候选召回，需结合实际场景确认。

“粉丝数”是指标语义，“数字增长”是表达方式，“数字滚动”是动效组件；三者不能互相冒充。Star 数也不是模板运行量。推荐检索“数字增长 + 人数/Star数”，再检查组件是否支持计数器、图标、单位与位数。

人工确认使用 `label --id ... --facet grammar --value 对比 --evidence "包内场景 X / 视频 00:03-00:06"`，记录为 human。纠正错误标签用 `--delete`，重建保留排除。改标签不会改原目录或来源向量；全文索引包含人工标签。

下一轮可对封面采样底色/色系，并对视频关键片段、包内场景指南建立场景级标签；需保留图像/时间码或参数字段证据。当前未执行这轮视觉审阅，不将模板主题词直接认作全部画面的配色。
