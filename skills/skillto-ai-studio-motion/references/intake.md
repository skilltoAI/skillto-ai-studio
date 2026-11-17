# Motion 录入与导入规范 v1

此规范用于把模板目录、单个来源链接或 .motion 包变成 **Studio「Motion 模版」页面可展示、可筛选的卡片**。建索引不等于录入完成。模板卡片、画幅变体和可制作实例是不同对象。

## 1. 录入契约

使用 `skillto.motion-intake/1` JSON，结构见 `assets/intake.schema.json`；语义校验与事务落库由 `scripts/motion_intake.py` 实施。不能让助手直接写个人库 SQL。目录索引通过 `motion_index.intake_batch()` 转换为同一契约，统一从服务 `sync_index` / `ingest` 写入。

```json
{
  "format": "skillto.motion-intake/1",
  "items": [{
    "id": "example-template:16:9",
    "source": "ExampleSource",
    "sourceUrl": "https://example.com/templates/example-template",
    "title": "示例模板",
    "summary": "来源的准确描述",
    "ratio": "16:9",
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "version": null,
    "poster": "https://example.com/previews/example-landscape.jpg",
    "demo": "https://example.com/previews/example-landscape.mp4",
    "downloadUrl": null,
    "availability": "check-official-page",
    "previewOnly": false,
    "labels": [{"facet":"grammar","value":"对比","method":"source-text","evidence":"来源介绍明确写明：对比表格"}]
  }]
}
```

- 稳定身份为 `source + id`，id 包含来源模板身份和画幅，不用标题作主键。同名横屏与竖屏独立；没有源码编号的预览条目使用来源稳定 previewId。
- 必填 id/title/source/sourceUrl/ratio。未知字段为 null 或未标注，不伪造版本、日期、运行量或下载链接。来源 HTTPS 链接不含登录凭据及查询密钥。
- `sourceCommit` 记录源仓库提交，官方版和公开版差异保存在 sourceEdition/editionNote。来源删除不自动删除用户卡片或成片。
- 批次先完整验证，再事务落库；任一无效项失败则整批不写。预检 `dryRun:true` 返回新增/更新数，重复同步按稳定身份复用卡片 ID。
- 更新来源标签/简介/规格/下载状态；保留已有人工标题、分类、个人标签、评分、收藏和任务历史。已导入原包的实际版本、路径、预览、制作支持不被目录版本覆盖。
- `previewOnly` 仅表示预览/预上线。不得因此产生假 .motion 路径、下载 URL 或可制作状态。无本机原包时 Path 为空且禁用。
- 来源运行次数和发布时间缺失为 null；向量相似度、导入次数和个人评分不得填入来源运行次数。

## 2. 标签维度与证据

受控维度/值以 `assets/index-taxonomy.json` 为准：palette 色系、temperature 色温、background 底色、style 风格、scenario 场景、grammar 表达语法、metric 指标对象、component 动效组件、pace 节奏、layout 布局、input 素材要求、editability 可编辑范围。

一个模板允许每维多值。颜色、冷暖、底色分别记录；“粉丝数/Star数”是 metric，“数字增长”是 grammar，“数字滚动”是 component，不能互相冒充。技术规格用结构化字段，不写成自由标签。

每项维度标签必有 facet/value/evidence/method，method 为 source-text（来源文字）、human（人工判断）、visual-reviewed（实际封面/视频审阅）、package-verified（包内参数/制作验证）。视频证据记录时间码，包内证据记录文件/字段。来源文字标签是候选描述，不是实测制作支持。未标注不等于不支持；不从“高对比”误判“方案对比”。

来源维度标签写 `sourceFacets`，页面「筛选」按维度选择；个人自由标签继续由 tagIds 管理，互不覆盖。修订来源维度用 index `label` 后重新 sync_index，保留人工修订与排除记录。

## 3. 向量规范

向量属于可重建的检索派生数据，不作为卡片真相来源。

- 当前模型固定为 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`，384 维 float32、L2 归一化；128 token、attention-mask mean pooling。文件哈希/提交见 `assets/index-model-manifest.json`。
- 输入是同一画幅的标题和来源简介；不混入目录内的助手指令、凭据、个人评分或运行次数。全文索引另纳入标签，避免人工改标签必须重算所有向量。
- 每条绑定文档 ID、输入文本 SHA-256、模型提交与文件 hash、池化/归一化配置。模型不符或文本 hash 变化的旧向量不参与检索；embed 增量补齐。
- 关键词与向量结果 RRF 融合；维度过滤先于排序。页面语义搜索读取相同来源 indexId 并显示对应库卡片；语义命中不代表已验证的功能。
- 无依赖/无向量时保留已录入卡片和关键词搜索，明确语义搜索不可用，不阻塞录入。当前本机通过 `runtime.local.json` 的 indexPython 选择已有 numpy/onnxruntime/tokenizers 的解释器。

## 4. 封面、视频与本地文件

- poster 是该条画幅实际封面，优先静态 JPG/PNG/WebP；来源仅有 GIF 时可显示，但标明其为来源预览。禁止横竖屏互借封面、用无关占位图伪装真实模板。
- 建议封面长边 640–1280 px；保留原比例。来源尺寸未知可先录入，不虚报已检查。宽高和码率是采样/转码建议，不是凭空重生成图像的理由。
- demo 是可播放预览视频；源文件严格大于 40 MB（40,000,000 bytes）必须转为 MP4 H.265/HEVC（hvc1 标记、yuv420p）+ AAC，横屏限 1280×720、竖屏限 720×1280，原比例缩小、偶数宽高，不裁切、不拉伸、不放大。小于等于阈值不强制重编码。只保留校验后的 720p 派生视频，临时大源文件在成功、失败或取消后清除；不把大原版作为长期本地资产。来源 demo URL 和 .motion 原包不改动。
- 正式录入/同步提交后返回 mediaJob，后台检查源大小并按上述规则处理；dryRun 不访问媒体、不排任务。完成需轮询该任务及 mediaResults；失败可用 retry 重试；mediaError 表示元数据已写入但媒体未排队，调用 prepare_previews 补齐。既有大缓存用 prepare_previews 处理；重复任务复用版本化派生缓存，不重复转码。检查编码、比例、尺寸、完整时长和音轨后原子发布；编码失败不以原版冒充处理成功。
- 预览首次加载也使用相同处理器；未知大小下载后按实际字节判断。源下载仍有 512 MiB 上限与主机/重定向限制。后台小视频仅 HEAD 检查、不提前下载；打开预览时才缓存。未支持 HEVC 的浏览器需给出播放失败提示，不偷偷改变编码要求。
- 卡片 4:3 容器 contain，原画完整居中，静态封面模糊低饱和压暗铺底。详情按原比例观看。
- 来源封面加载失败使用中性灰底；无 poster 有 demo 时使用受限同源 `/api/motions/poster/<id>` 抽帧。卡片视频仅在悬停/聚焦时加载播放、离开释放；不为所有卡片预下载视频。
- 远程图片可按当前页面 HTTPS 图片策略显示；视频经登记来源的受限同源入口，不放宽为任意 URL 代理。不支持的媒体主机显示来源入口，后续按主机与重定向契约显式接入；不能为播放放开所有签名 URL。
- 原包 Path 必须为实际存在的本机绝对 `.motion` 文件。解包目录单列；目录录入不自动下载/运行全部包。完整性检查和已验证适配决定 renderable。

## 5. 实施流程与验收门槛

1. 读取来源并保留提交/原目录，列出模板、画幅变体、预上线项的实际计数。MotionGit 当前目录用 `motion_index.py build --repo <clone>`；其他来源转换为同样 intake JSON。
2. 按上述契约规范化，建立有证据的标签；可生成向量，但不得以生成向量代替录入。
3. 调用服务预检：`motion_cli.py sync_index --json '{"dryRun":true}'`。通用批量文件用 `motion_cli.py ingest --file <request.json>`，请求形如 `{"batch":<intake JSON>,"dryRun":true}`。
4. 正式调用相同动作并设 dryRun=false。记录 received/created/updated 和 indexId→itemId 映射；失败修复数据后重试，不删旧库重新灌入。
5. 核对 GET `/api/motions/catalog`：每条源 ID 恰好对应一张卡、计数一致、旧任务/评分/原包仍在。重复导入验证零新增。
6. 在 `/?section=motions` 实际刷新验证总数、横竖屏封面、来源状态、关键词/维度筛选、语义搜索及详情。缺图/失败需记录，不把 HTTP 200 当作图片已成功显示。
7. 交付页面 URL、源条目数量与分组、导入报告、媒体抽检结果和未验证范围。**页面可见才算录入完成**。

此模块共用 Studio 服务，不受 URL 中 table 参数限制；table 参数保留表格模块上下文，Motion 卡片存放独立 motions 数据根目录。

官方 motiontemplates/all 的 GitHub Release 视频已接入：只允许该仓库 releases/download 路径，以及该路径产生的 release-assets.githubusercontent.com 临时签名重定向；不能保存/输出签名 URL，也不开放任意 GitHub 仓库或任意查询 URL。
