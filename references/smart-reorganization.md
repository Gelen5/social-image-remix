# 智能重组模式

用户说“智能重组”“你帮我去冗余并调整页数”“自动优化后直接做”等时启用mode=smart，授权在所选范围内自主选择组织方式与页数，无需重复询问是否允许合并。只要求方案时先给方案不制作；普通二创仍为faithful，一张选中原图对应一张成品。用户指定第2、3张时，智能重组也只能使用这两张，其他页仅用于判断依赖，不能混入事实。

## 自主判断

看完整组，冻结所选页的全部信息清单，再比较至少两个真实可行方案：保留原结构，以及按主题/流程/比较维度合并重组。逐一说明信息完整性、衔接、冗余、手机字号与每页密度的取舍。选择当前约束下较合理的方案，不称为算法保证的全局最优。

可合并等价重复描述、通用重复条件、重复封面；清理广告、引导和没有事实内容的空话；将同主题的信息合并，重排顺序并用保留信息改写表达。重复的适用条件可以统一显示，但必须明确覆盖哪些对象，不能误扩大范围。独有事实、名单、数字、限定条件、例外、必要来源和免责声明不可删除。涉及矛盾或无法辨别的含义时先确认，不以猜测补全。

5张变3张是允许的结果，不是必须的目标。没有明显冗余或压缩后难读，就保留5张；必要时增加页数也要有可读性依据，不为凑目标页数缩成小字或删事实。3:4、整组统一、文字正确及无溢出检查仍执行。

## 内容结构与覆盖记录

完整manifest保持真实源图数量。content.json写mode=smart、selected_indices，以及source_facts：每个信息项有唯一id、source_indices、原文text、kind（fact/promotion/filler）、action（retained/merged_duplicate/removed）。非保留项必须写reason；merged_duplicate写duplicate_of指向同类retained项。真实实质信息不得标removed，去重等价性由宿主逐项复核。source_facts必须完整，不得在清单阶段先漏掉不方便保留的内容；原始完整转录保存在source-content.json。

cards的title/subtitle/blocks/footer格式不变；智能模式改用source_indices（允许多源页）及fact_ids（该成品覆盖的retained信息ID），不再使用单个source_image。所有retained项必须至少被一张成品覆盖，每张来源限定所选范围。图片型信息仍需完整转录或保留插图；插图遵循本地路径规则。

reorganization含reviewed（完成真实语义复核才true）、alternatives（至少两个id/page_count/reason方案）、chosen（选中id）、reason（具体取舍）。输出页数与方案一致，清单覆盖所选全部页，去重指向有效；脚本可核验这些结构，不能自动证明源图转录完整或语义等价。

示例结构片段：

```json
{
  "mode": "smart",
  "selected_indices": [1, 2],
  "source_facts": [
    {"id":"a","source_indices":[1],"text":"2027届可申请","kind":"fact","action":"retained"},
    {"id":"b","source_indices":[2],"text":"2027届可申请","kind":"fact","action":"merged_duplicate","duplicate_of":"a","reason":"同一对象的同一条件重复出现"}
  ],
  "reorganization": {
    "reviewed":true,
    "alternatives":[{"id":"original","page_count":2,"reason":"原页各重复同一条件"},{"id":"merged","page_count":1,"reason":"同一条件统一表达，保持适用对象"}],
    "chosen":"merged","reason":"没有独有信息损失，单页清晰可读"
  }
}
```

这只是结构示例，必须补充实际cards，不代表任意原图可以合并。

## 交付

每张重组成品在分组/去重完成后，按最终保留内容重新执行 [disclaimer.md](disclaimer.md) 的语义判断。具体企业/岗位推荐及招聘条件等需添加固定提示语；通用方法页不默认新增。原有必要声明不能去重掉限定条件，判断和实际布局逐张核查。

用原有validate/render/check_delivery脚本。智能图片报告及逐图image_checks使用source_indices数组而非source_index；text-review.json另有reorganization_reviewed=true，notes记录实际覆盖、去重等价性、条件作用域和衔接复核。保留模式兼容旧字段。

配文、文章和贴图号/文章各3个标题基于最终保留信息及成品，不能带回已删除广告/空话或未选页信息。字数和段数规则不变。交付简述“原范围5张→成品3张”及合并/清理理由，给源页映射和核对记录；发现遗漏、歧义或排版失败就重做方案或回到保留结构，不能声称成功。
