# 红黑 / 橙黑文章排版

来源：[Gelen5/customer-write](https://github.com/Gelen5/customer-write/tree/main/references/templates)，固定版本660a613c72c22eb269fd47f8e8e6056eebb15052。upstream保留两套样文正文、规范说明、MIT许可证及provenance.json，仅用于样式参考。绝不能复制样文中的个人经历、成绩、导语或结论到客户文章；引用规范不覆盖本Skill的500字上限、来源、清理及交付规则。

主题名是red-black（红黑）和orange-black（橙黑），不是橙红。正文黑色#000000、16px、行高2.0，彩色强调分别#C00000与#E67E17，不在同篇混用。普通段落左右内缩0、段距18px；已存在的注释段可降级为14px灰字、灰竖条及12px左内缩，不新增注释内容。

默认同一篇正文输出两版，用户指定主题时只输出对应版；只影响文章HTML，不改变二创图片风格或短配文。标题单独选择并填到公众号标题栏，不写入正文。两版正文文字与article.txt一致，不插入样文文案、按钮、页脚、机构名或导流。

## 实现

正文确认不超过500字后，宿主根据语义为重点规划article-layout.json，emphasis记录1起算段号、0起算字符区间[start,end)以及tone（accent或black）。红黑版与橙黑版均须同时包含accent彩色加粗和black黑色加粗：accent在红黑版对应#C00000、橙黑版对应#E67E17，black固定为#000000。两类重点分别用于不同信息，不把文章做成只有一种粗体颜色。段落按article.txt空行分隔，区间必须准确引用原文，不能通过查找替换改字；同段区间不能重叠，单块≤15字符，彩色最多4处，总加粗≤15%。按实际内容选择重点，不机械每句加粗或为达到比例硬凑。notes可列已有注释段号，默认空数组。

```json
{"emphasis":[{"paragraph":1,"start":0,"end":8,"tone":"accent"}],"notes":[]}
```

这是格式示例，实际位置按文章确定。未提供layout时保留纯正文，主题强调不自动制造事实；完整创作流程应按内容生成重点方案。

```text
python scripts/article_layout.py --article "任务文字目录/article.txt" --layout "任务文字目录/article-layout.json" --theme both --output "任务文字目录/article-layout"
```

--theme支持both/red-black/orange-black。若用户指定单主题，同时将content.article_theme设为对应名称；默认省略或both。不要把“橙红”悄悄映射成混色主题，先说明仓库实际名称。

## 产物与验收

- article-red-black.html、article-orange-black.html：仅所选主题，纯section片段、内联样式，文字用span leaf包裹，供粘贴公众号正文。
- article-preview.html：本地预览、切换样式与320/375/430px阅读宽度，复制按钮只复制正文HTML，不含控制区。浏览器不允许剪贴板时提示手动复制。
- article-layout-report.json：正文哈希、主题、文件哈希、文字一致性及手机横向溢出检查，不宣称自动审美判断或实际微信粘贴验收。

生成后实际查看两版，检查重点、间距、换行和手机阅读效果。text-review.json增加article_layout_reviewed=true、article_layout_report（相对文字目录）、article_layout_report_sha256（报告哈希），完成真实查看才标记。交付检查会阻断旧正文、错主题、混色/不兼容标签、漏字/新增标题、过期复核或旧HTML。只按最终清单交付；预览页含脚本，不能整页粘贴到公众号。

纯HTML无法在聊天消息里自动保留公众号富文本；通过预览页复制或使用客户端支持的导入方式，粘贴后仍需实际预览。Skill不自动发布。
