# social-image-remix · 社交图文二创 Skill v0.2.1

将抖音/小红书/快手图文链接，通过客户浏览器提取图片，逐张读取完整信息，以**整组统一风格**输出3:4图片，并默认输出配文、文章和3个标题。面向Codex和WorkBuddy等能执行本地Skill的工具。

## 这一版能做什么

- 浏览器链接提取、图片下载、数量/尺寸/哈希记录。
- 抖音内置当前图集DOM规则；快手新增内置atlas图集规则；小红书提供选择器模式，尚未验证实际链接。
- 图片理解由宿主看图能力完成，不捏造OCR输出；冻结完整文字后再排版。
- 四套固定文字模板：同一任务整组共用，跨任务轮换；1080×1440 PNG，DOM文字一致性/溢出检查。
- 配套文章创作规范、客户隔离的输出与模板历史、本地安装和ZIP打包。

默认二创遵循用户认可的两次实际案例：参考原图的信息框架，重新设计配色、标题、卡片与插画，保留全部内容，使视觉明显不同。同组统一设计，不同任务换风格。优先使用宿主真实生图能力，固定文字脚本作为备用与纠错方式。详见 [二创案例与提示词](references/remix-examples.md)。

评论口令、看主页/简介、领取资料、私信及绿色通道入口等引导语明确删除，不能改写进图片或文字。默认精准清理确认的水印、制作/发布机构署名、Logo、软广及导流；保留主题企业、必要来源和免责声明。先完整转录，再记录删除项并核对成品，详见 [内容清理规则](references/content-cleanup.md)。

默认二创图片验收后，按图片语义输出不超过5段、总计200字以内的微信贴图号配文，保存caption.txt；默认另生成580–620字文章正文和3个标题，运行统一交付检查。详见 [配文规则](references/wechat-caption.md)。

支持指定原图页码，如只二创第2、3张；也可先分析完整图集，推荐不影响连贯性的组合。配文和文章严格限定最终所选图片，不混入未选页事实。详见 [选图与连贯性规则](references/image-selection.md)。

无需parse-video；不要求手工复制Cookie。不自动发布。

## 安装

需要Python 3.10+、Chrome、Node.js/npm以及已连接的OpenCLI Browser Bridge扩展。

```powershell
git clone https://github.com/Gelen5/social-image-remix.git
cd social-image-remix
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
npm install -g @jackwener/opencli
opencli doctor
```

OpenCLI扩展的安装和配对见 [OpenCLI官方仓库](https://github.com/jackwener/opencli)。`doctor`必须显示浏览器扩展连接成功；npm包安装不等于扩展已连接。客户在Chrome中自行登录需要的平台。脚本不读取或导出Cookie。

**Codex：**把完整仓库目录放到用户Skill目录中的 `social-image-remix` 文件夹，或使用已有技能安装器从该GitHub仓库根目录安装。不要只复制SKILL.md。Windows常用位置为用户目录下 `.agents/skills/social-image-remix`；以客户端实际发现路径为准。重新打开客户端并确认技能出现。

**WorkBuddy：**执行 `python scripts/package_skill.py --output dist/social-image-remix-v0.2.1.zip`，在技能界面导入ZIP。技能文件导入不会自动安装Python依赖、Chromium或OpenCLI扩展；完成运行环境后再试用。需要调用时告诉助手依赖已安装的Python绝对路径。云端运行没有本机Chrome登录状态时，不可宣称能复用本机浏览器。

安装命令只在客户要求安装时执行；本仓库不改动任何客户的其他Skill。

## 使用示例

```text
使用 social-image-remix：把这条抖音图文链接的全部图片二创成3:4。
原图信息不要删减；这条链接的所有图片用同一套风格。
再根据图片内容写一篇相关文章。
```

执行细节在 [SKILL.md](SKILL.md)。输出写到单独的任务目录，禁止把Cookie、图片临时签名链接、客户素材提交到GitHub。

## 独立脚本

```powershell
python scripts/browser_extract.py doctor
python scripts/browser_extract.py extract --url "https://v.douyin.com/分享码/" --output runs/demo/source
# 宿主看图后创建完整content.json、transcription-review.md
python scripts/render_cards.py validate --content runs/demo/content.json --manifest runs/demo/source/manifest.json
python scripts/render_cards.py render --content runs/demo/content.json --manifest runs/demo/source/manifest.json --output runs/demo/remix
```

`--selector`与`--expected-count`用于页面自动识别不足的情况，参见 [浏览器提取](references/browser.md)。正文schema及示例见 [内容格式](references/content.md)。首次渲染后逐张查看实际PNG，不以脚本返回成功代替视觉检查。

## 测试与边界

```powershell
python -m unittest discover -s tests -v
python scripts/package_skill.py --output dist/social-image-remix-v0.2.1.zip
```

这套测试检查完整性阻断、模板整组一致、历史轮换、文字保真及真实PNG渲染。真实平台验证记录见 [VALIDATION.md](VALIDATION.md)。跨机器Codex/WorkBuddy导入、登录过期、懒加载、大批量处理仍需现场验收。

交付检查：`python scripts/check_delivery.py --content 任务目录/content.json --manifest 任务目录/source/manifest.json --image-report 本次图片目录/review.json --text-root 本次文字目录`。格式与验收见 [交付说明](references/delivery.md)。

源码MIT许可证；平台图片和文字权利属于原作者。仓库不包含客户账号、API Key或原作者的图像素材。
