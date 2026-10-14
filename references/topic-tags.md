# 五个内容匹配话题标签

默认在图片、配文、文章和标题之外单独交付5个话题标签，保存topics.txt与topics.json；标签及数据说明不计入配文200字/5段，也不计入文章正文的500字上限。用户明确不需要时记录省略，不声称完整交付检查通过。

只基于最终所选/重组后保留的信息生成候选，不蹭无关热点、不带回导流。先由宿主实际理解内容，提取约8–15个候选，逐项写来源页与具体匹配理由；信息范围较小可以少一些，至少5个真正相关的词才能交付，不为凑5个编无关标签。

## 语义候选

tag-candidates.json包含当前content_sha256、relevance_reviewed（实际核对才true）、candidates；每个候选包含keyword（不带#，不含空格，≤24字符）、relevance_score（0–1的规则分，不是平台推荐概率）、source_indices、reason。至少.6视为相关候选，按相关性优先，分值相同才参考微信指数热度。标签不自动证明在微信话题系统已有对应入口，发布时由客户选择平台实际可用的话题。

```json
{
  "content_sha256":"当前内容哈希",
  "relevance_reviewed":true,
  "candidates":[{"keyword":"留学生实习","relevance_score":0.95,"source_indices":[2,3],"reason":"选中页均介绍实习企业与岗位"}]
}
```

以上只有结构示例，实际至少提供5个独立相关候选。

## 指数数据与真实性

微信指数是热度指标，不把它称为真实搜索次数，也不能拿其他平台搜索量替代。当前实现数据导入，不包含未验证的实时自动查询API。客户可提供微信指数截图/导出结果；宿主若能真实操作微信界面或有已经实测的数据服务，可取得结果后按同一格式导入，记录具体来源。不默认购买、调用收费服务或上传客户凭据。

数据在文字输出目录内保存index-input.json及本地证据（截图、原始导出或API返回）。宿主先查看/核对证据再转录，不凭候选词猜指数。provider来源同样需要实际原始返回，不能仅因配置有Key就声称查询成功。

```json
{
  "metric":"wechat_index",
  "source_reviewed":true,
  "period_days":7,
  "as_of":"实际数据日期",
  "source":{"kind":"screenshot","name":"实际来源名称","evidence_file":"evidence.png","evidence_sha256":"文件实际哈希"},
  "records":[{"keyword":"实际查询词","value":123}]
}
```

数值123只是格式示例，严禁用于客户交付。统一周期7/30/90天、同一数据日期；日期不能在未来，超过30天需刷新。数值需来自证据，缺失用无记录，不补0；有数据的真实0可以记录。关键词必须与候选完全匹配，不能给长尾词套一个热门大词的指数。

## 执行与降级

```text
python scripts/topic_tags.py --content "任务目录/content.json" --candidates "任务文字目录/tag-candidates.json" --output "任务文字目录"
```

有核验数据再加 `--index-input "任务文字目录/index-input.json"`。来源证据要位于该目录内，便于交付复核；账号密钥不写入任何产物。

- 5词都有记录：provided_index，说明已参考导入的微信指数热度，不是搜索次数。
- 部分记录：partial_index，明确哪些缺失，不补造。
- 无有效数据：unverified_index，只推荐内容标签，并展示“未验证微信指数”；不能包装成微信热度排名。

无数据时不能静默切到其他热搜服务。若客户明确只接受有真实指数的结果，应暂停指数部分说明所缺证据，不能用降级结果冒充达标。

生成后宿主核对5词确实贴合最终成品，text-review.json增加topics_reviewed=true、topics_sha256（topics.json哈希）。check_delivery.py检查当前内容/范围、5词唯一性、标签文本、指数状态、证据日期/哈希和复核版本，将tags文件及数据边界说明加入交付清单。脚本不自动证明截图或第三方数据真实，也不保证话题标签带来推荐。
