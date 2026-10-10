# 完整信息与数据格式

content.json由宿主看图后生成。脚本不假装执行OCR。示例是格式说明，不代表实测招聘信息：

```json
{
  "source_url": "https://www.douyin.com/note/作品ID",
  "transcription_reviewed": true,
  "cards": [
    {
      "source_image": "01.webp",
      "title": "原图主标题",
      "subtitle": "原图副标题",
      "blocks": [
        {
          "heading": "原图企业名称",
          "fields": [
            {"label": "特点优势", "text": "完整原句，不精简"},
            {"label": "岗位方向", "text": "完整列表，保留顺序"},
            {"label": "适合人群", "text": "2027届及以后毕业"}
          ]
        }
      ],
      "footer": "原图底部完整文案"
    }
  ]
}
```

title、subtitle、footer不存在时用空字符串；不要把存在的文本置空。无字段结构的段落使用空label和完整text。每个原图可包含任意数量blocks/fields。表格可逐行录入为字段，保留表头、值、单位及注释；照片/图表承载信息时应将原图/局部保存为插图并用块字段 `image` 加入（相对manifest所在目录的本地文件路径），不得仅用主标题替代。

`transcription-review.md`应按原图逐项确认：标题、副标题、块数量、各字段、数字/条件、底部、图表/照片信息。标明疑字，不改写陌生缩写。例如原图写yl科技，应按原字照录；另行指出含义待确认。原图模糊而影响信息时不能设置已核对true。

一个manifest对应一个content；source_image必须按manifest的index顺序一一对应。完整性检查阻断缺图、假文件名、不确定源图总数和未经看图核对的文字。

content锁定后，图文排版不做语义改写。渲染HTML中每个文字节点与该JSON逐项比较，不使用“总体意思相近”作为通过标准。脚本无法判断OCR漏字，所以原图核对必须先完成。
