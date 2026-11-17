# SKillto.ai|工作台 本地猫抓界面

本目录是用于 xifangczy/cat-catch 的界面与本机集成 overlay。猫抓 GPL-3.0 许可及作者信息必须随组合分发保留；不得把品牌修改表述为全部代码的原始作者变更。欢迎页品牌为 SKillto.ai|工作台，开源归属独立显示在 credits.html 与上游 LICENSE 中。

从本 skill 的 scripts/build_cat_extension.py 运行，明确指定未经修改的上游源码和稳定的目标目录。上游固定为 019c465794b5871701383e4485c0e9ee7be2f840。构建只替换本 overlay、明确的 manifest/init/background 集成位置和品牌图标，不安装 Chrome，不改变浏览器 Preferences 或权限策略。现有运行副本更新前先比较并备份，不能覆盖其他任务的改动。

主界面仅提供下载、同步到工作台两个输出。完整普通视频由 Chrome 保存；选段由本机 FFmpeg 精确导出，可能需要先下载完整源文件。仅下载片段使用独立 exports 表/目录，不向拉片 records 添加记录；工作台目标才写拉片。当前简化导出支持 MP4/WebM 等普通视频，HLS/DASH 清单在编辑器明确标为暂不支持，不把清单文件冒充完整视频。

同步与选段导出通过 Bearer 认证、连续 offset 的有界二进制数据块传入同一本机服务；任务生成内部路径，不依赖 Chrome 下载目录，不传递浏览器身份缓存。传输期间需保持编辑页；处理完成后复用或打开工作台标签页定位到成片。
