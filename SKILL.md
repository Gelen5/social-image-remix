---
name: social-image-remix
description: 从抖音、小红书、快手图文链接通过浏览器提取图片，完整保留图内信息，以整组统一风格重新排版为3:4图片，并按需创作相关文章。适用于链接图文二创、保留全部文字的换版式和配套文章。
---

# 社交图文二创

目标：把分享链接中的图文变成可交付的图片与文章。浏览器实际打开页面；文字完整识别后锁定；同一条链接只选择一个视觉模板，应用到全部图片。不同链接/任务轮换模板。

## 不可丢失的约束

- 默认**只改变视觉表达，不删减输入图片的信息**。保留标题、副标题、所有实体名称、完整描述、条件、数字、单位、时间、每个字段和底部文案。重复出现的适合人群等条件也逐项保留。用户明确要求精简时才改变此默认。
- **同一链接的一组图片风格必须一致**：同一模板、配色、字体、标题层级、装饰语言和页边距。不要每张随机换风格。跨任务轮换由脚本的历史记录实现。
- 默认每张原图对应一张二创图，严格3:4。优先输出1080×1440 PNG。文字放不下就调整字号/间距，仍放不下应报告需要分页，不能通过删字解决。
- 下载图片不等于理解图片。使用当前宿主的看图工具逐张查看；必要时用已有OCR辅助，并逐字回看。不根据标题臆测图内内容。陌生缩写、原图疑似错字照录并在独立核对记录注明，不静默改成猜测。
- 不把原图的招聘、薪资、产品宣传等陈述当作当前已证实事实。排版保留原文；配套文章标明资料来源，新增实时事实需查证。
- 提取、识别、排版、文章、发布是不同状态。只报告真实完成的阶段。该Skill不自动发布或联系他人。

## 执行

路径均相对本Skill目录。执行前解析为绝对路径，兼容Windows路径空格。无需安装其他Skill，不使用parse-video。

### 1. 环境与浏览器

运行 `python scripts/browser_extract.py doctor`。需要Python、requests、Pillow、Playwright，以及可连接客户浏览器的OpenCLI扩展。安装方法见 [README.md](README.md)。OpenCLI是外部依赖，不随Skill打包；尚未准备好时说明实际缺项。不要承诺只安装Markdown就能联网看图。

如果宿主已经提供受控浏览器工具，可以直接使用它；沿用下面的完整性要求，并写出同格式manifest。没有可用浏览器就先配置浏览器，不能悄悄切换付费解析API。

### 2. 提取完整图集

读取 [references/browser.md](references/browser.md)。默认用现有浏览器登录状态，不导出、显示或上传Cookie。网页要求登录/验证码时，让客户在浏览器里完成，之后继续。

```text
python scripts/browser_extract.py extract --url "分享链接或整段分享文案" --output "任务目录/source"
```

脚本支持三平台链接识别，抖音当前网页有内置图片规则；小红书/快手需要从当前作品DOM确定选择器并传 `--selector`。未实测的平台不宣称已验证。页面总张数自动读不到时，查看作品轮播计数，再传 `--expected-count N`。图片懒加载时，先通过浏览器逐张翻页加载，再执行提取。

要求 `manifest.json` 中 `complete: true`，作品ID/页面与输入一致，下载张数与页面总张数相同，顺序正确、无头像/推荐作品。失败、缺图或计数不明时停止排版，保留明确原因。详情见浏览器参考。

### 3. 逐张识别并冻结完整文字

查看manifest中全部本地图片。读取 [references/content.md](references/content.md)，写 `content.json` 和 `transcription-review.md`。

- 将每张图的标题、副标题、正文分块、字段及底部文案逐字录入，不合并重复字段。
- `source_image` 与manifest文件一一对应，顺序不变。背景装饰可改变，承载信息的图表/照片必须转成完整数据/说明或保留为图中插图，不能漏掉。
- `transcription-review.md` 列出逐图字段核对、数字核对、疑字与如何处理。未识别清楚的字先注明并请求确认，不能将猜测标成已核对。
- 逐项对照原图后，才设置 `transcription_reviewed: true`。此标记是人工/Agent看图核对声明，不是脚本OCR证明。

```text
python scripts/render_cards.py validate --content "任务目录/content.json" --manifest "任务目录/source/manifest.json"
```

### 4. 整组统一排版

读取 [references/design.md](references/design.md)。默认使用脚本固定文字渲染，避免将中文正文全部交给生图导致漏字、数字变化。

```text
python scripts/render_cards.py render --content "任务目录/content.json" --manifest "任务目录/source/manifest.json" --output "任务目录/remix"
```

脚本给本任务选择一个模板，整组复用，跨任务轮换。可用 `--template editorial-blue|paper-plum|sage-dossier|warm-magazine` 指定风格，或 `--history 路径` 指定客户独立的模板历史。相同任务再次渲染会沿用已有模板。非本地执行环境没有历史时，明确跨任务去重的限制。

图片多模态理解用宿主看图能力；固定文字输出由Playwright截图生成。仅当用户要插画/摄影等新增视觉或明确要生图时，使用宿主真实可用的生图工具；整组先锁定同一设计规范，正文仍建议固定文字合成。不能用模拟调用或假图片代替。

渲染后查看每张PNG，核对文字可读、无重叠/截断、3:4、整组风格一致。`review.json` 校验的是尺寸、布局溢出及DOM文字与content完全一致，不能证明content与原图相同；两个检查都要完成。正文太密时报告可读性问题，不为通过尺寸检查牺牲内容。

### 5. 配套文章与交付

用户只要图片就只交图片；要求文章或完整流程时，读取 [references/article.md](references/article.md)，用宿主实际模型基于冻结内容创作 `article.md`，保留来源关系，标清新增建议与原图信息。

交付图片、文章（如请求）、content.json、核对记录、manifest及review.json。给可点击本地文件路径，报告真实通过的检查，以及仍受登录/平台变化影响的部分。不要把单条抖音成功描述成三平台全部稳定。
