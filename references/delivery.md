# 完整交付检查

默认交付所选3:4图片、caption.txt（1–5段，总计1–200字符）、article.txt（正文580–620字符）、titles.json（3个不同非空单行标题）。统一非空白Unicode字符计数，标点/数字/英文计入，空白不计入；标题、来源说明与字数说明单独交付不计入正文。

仅在宿主实际完成语义/视觉复核后设置true，不为通过脚本伪造标记。脚本没有自动事实或广告识别能力。

## 图片报告

cards每项必须有disclaimer_decision，与当前content逐张判断完全一致；disclaimer按判断为完整固定文案或null，不能缺字段。每个image_checks须有disclaimer_reviewed=true，实际核对语义判断、应加时文字完整清晰无遮挡、原图必要声明保留后才标记。普通及智能模式均执行，见 [disclaimer.md](disclaimer.md)。仅改JSON不能代替真实看图。

智能mode=smart使用每张source_indices数组（多源页）取代source_index/source_image，对应cards的多源映射；逐图image_checks使用相同source_indices。text-review.json还需reorganization_reviewed=true，记录真实的信息覆盖、去重等价性及条件范围检查。普通模式兼容旧字段，其他长度、哈希和质量门禁不变。

固定排版使用实际review.json。生图路径写image-review.json，passed来自真实看图验收，不声称DOM/OCR检查。根字段包括passed、template（本组设计ID）、work_key、content_sha256、cards；每个cards条目包括file（相对输出目录）、source_index、source_image、sha256（输出文件哈希）。页码顺序必须与selected_indices一致，文件实际宽高必须3:4。

## 文案表达门禁

配文不得重复信息分享/招聘免责声明或官方信息兜底句；文章不得以图片页码、这组图、图中资料等指代组织正文。check_delivery.py拦截已知固定表达及常见页码变体，宿主还需逐段检查同义兜底句和脱离图片的独立可读性；正则不等于全面语义判断。核对说明写notes，改文后重建文字签名与文章排版报告，不复用旧版复核。图片提示语判定与本项分开执行。

## text-review.json

默认还需topics.txt（5个独立标签）与topics.json，来源和范围按topic-tags.md。text-review.json记录topics_reviewed=true和topics_sha256，绑定实际核对后的标签版本；交付检查纳入5词、范围、指数状态与证据一致性。标签和数据边界说明单独交付，不计配文/文章字数。

文章排版必须完成：默认红黑/橙黑两套，content.article_theme指定单套时匹配其选择。text-review.json记录article_layout_reviewed=true、article_layout_report（文字目录内的相对路径）、article_layout_report_sha256，绑定实际查看后的排版报告。check_delivery.py核验正文一致性、主题、文件哈希和兼容结构，再把两版HTML及预览加入最终清单；旧复核不能用于新正文或新排版。

必须按 [image-quality.md](image-quality.md) 逐张核查最终图片的文字与排版，增加image_checks，记录实际文件、源页码、图片哈希、text_correct、layout_passed、issues和notes。漏检、有未解决问题或旧版本核对均阻断交付。

记录content_sha256、selected_indices、text_sha256；facts_reviewed、scope_reviewed、titles_reviewed、images_visually_reviewed、cleanup_reviewed只有实际核对后才true；notes写实际逐句/逐图核对说明。

在Skill目录计算：

```text
python -c "import sys; sys.path.insert(0,'scripts'); from check_delivery import text_signature; print(text_signature('任务文字目录'))"
```

content哈希由workflow_common.content_digest(content)计算，work_key由完整作品URL计算。修改选图、图片或文字后重新核对与记录版本，不复用旧通过标记。

```text
python scripts/check_delivery.py --content "任务目录/content.json" --manifest "任务目录/source/manifest.json" --image-report "本次图片目录/review.json" --text-root "本次文字目录"
```

通过时delivery.json列出本次明确文件与字数；失败时passed=false，无可交付清单。仅交付清单文件，不打包整个任务目录。门禁阻断错页、旧PNG、图片哈希变化、过期文字核对、缺标题、超限字数/段数与未完成复核。

用户明确只要图片等局部任务时尊重选择，写partial-delivery.json记录实际文件、省略项与对应检查，不宣称完整门禁通过。文章材料不足可交已完成图片并说明文章待补选，不能伪造完整成功。
