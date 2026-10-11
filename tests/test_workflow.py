import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from browser_extract import extract_url, decode_json, dom_query
from render_cards import validate, choose_style, card_html, locked_text, render


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        from PIL import Image
        Image.new("RGB", (100, 200), "white").save(self.root / "01.png")
        self.manifest = {"complete": True, "expected_count": 1,
                         "source_url": "https://www.douyin.com/note/123", "errors": [],
                         "images": [{"index": 1, "file": "01.png", "width": 100, "height": 200,
                                     "sha256": hashlib.sha256((self.root / "01.png").read_bytes()).hexdigest()}]}
        self.content = {"source_url": self.manifest["source_url"], "transcription_reviewed": True,
                        "cards": [{"source_image": "01.png", "title": "留学生实习", "subtitle": "完整信息",
                                   "blocks": [{"heading": "企业 & 测试", "fields": [
                                       {"label": "特点优势", "text": "原文含<特殊符号>、完整长句，不做删减。"},
                                       {"label": "岗位方向", "text": "研发、产品、运营"},
                                       {"label": "适合人群", "text": "2027届及以后毕业"}]}],
                                   "footer": "【留学生专属1v1私信沟通】"}]}

    def tearDown(self):
        self.tmp.cleanup()

    def test_selected_pages_exclude_unselected_and_reject_bad_scope(self):
        original = copy.deepcopy(self.content["cards"][0])
        for index in (2, 3):
            name = f"{index:02d}.png"
            (self.root / name).write_bytes((self.root / "01.png").read_bytes())
            self.manifest["images"].append(dict(self.manifest["images"][0], index=index, file=name))
        self.manifest["expected_count"] = 3
        self.content["selected_indices"] = [2, 3]
        self.content["cards"] = [dict(original, source_image=f"{i:02d}.png") for i in (2, 3)]
        self.assertEqual(len(validate(self.content, self.manifest, self.root)), 2)
        for bad in ([], [0], [4], [2, 2], [3, 2], [True], "2,3"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate(dict(self.content, selected_indices=bad), self.manifest, self.root)
        with self.assertRaises(ValueError):
            validate(dict(self.content, cards=[original, self.content["cards"][1]]), self.manifest, self.root)
        (self.root / "content.json").write_text(json.dumps(self.content), encoding="utf-8")
        (self.root / "manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        args = argparse.Namespace(content=self.root / "content.json", manifest=self.root / "manifest.json",
                                  output=self.root / "selected", history=self.root / "history.json",
                                  template=None, font_file=None)
        self.assertEqual(render(args), 0)
        report = json.loads((self.root / "selected/review.json").read_text())
        self.assertEqual([c["source_index"] for c in report["cards"]], [2, 3])
        self.assertEqual([c["source_image"] for c in report["cards"]], ["02.png", "03.png"])
        self.assertEqual(len(list((self.root / "selected").glob("*.png"))), 2)

    def test_platform_routes_and_domain_boundary(self):
        self.assertEqual(extract_url("复制打开 https://v.douyin.com/abc/ 文案")[1], "douyin")
        self.assertEqual(extract_url("https://xhslink.cn/abc")[1], "xiaohongshu")
        self.assertEqual(extract_url("https://v.kuaishou.com/abc")[1], "kuaishou")
        with self.assertRaises(ValueError):
            extract_url("https://douyin.com.evil.example/abc")

    def test_count_unknown_missing_or_false_approval_blocks(self):
        self.assertEqual(len(validate(self.content, self.manifest, self.root)), 1)
        for change in ({"complete": False}, {"expected_count": None}, {"expected_count": 2}, {"expected_count": True}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate(self.content, dict(self.manifest, **change), self.root)
        with self.assertRaises(ValueError):
            validate(dict(self.content, transcription_reviewed=False), self.manifest, self.root)
        with self.assertRaises(ValueError):
            validate(dict(self.content, cards=[]), self.manifest, self.root)

    def test_asset_change_and_wrong_source_block(self):
        wrong = copy.deepcopy(self.content)
        wrong["cards"][0]["source_image"] = "other.png"
        with self.assertRaises(ValueError):
            validate(wrong, self.manifest, self.root)
        (self.root / "01.png").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            validate(self.content, self.manifest, self.root)

    def test_history_rotates_between_tasks_but_retry_stays(self):
        history_path = self.root / "history.json"
        first_output = self.root / "first"
        first_output.mkdir()
        style, _ = choose_style(self.content, first_output, history_path)
        history_path.write_text(json.dumps({"last_template": style["template"], "jobs": []}))
        (first_output / "style.json").write_text(json.dumps(style))
        retry, _ = choose_style(self.content, first_output, history_path)
        following, _ = choose_style(self.content, self.root / "second", history_path)
        self.assertEqual(style["template"], retry["template"])
        self.assertNotEqual(style["template"], following["template"])

    def test_json_notices_and_selector_is_data(self):
        self.assertEqual(decode_json('{"images":[]}\nUpdate available'), {"images": []})
        query = dom_query("xiaohongshu", 'img[data-x="a"];alert(1)//')
        self.assertIn('"selector":', query)
        self.assertIn('document.querySelectorAll(opt.selector)', query)

    def test_overflow_blocks_without_recording_success(self):
        self.content["cards"][0]["blocks"][0]["fields"][0]["text"] = "完整原文不能删减" * 2000
        (self.root / "content.json").write_text(json.dumps(self.content, ensure_ascii=False), encoding="utf-8")
        (self.root / "manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        args = argparse.Namespace(content=self.root / "content.json", manifest=self.root / "manifest.json",
                                  output=self.root / "out", history=self.root / "history.json",
                                  template=None, font_file=None)
        with self.assertRaisesRegex(ValueError, "禁止删字"):
            render(args)
        self.assertFalse(json.loads((self.root / "out/review.json").read_text())["passed"])
        self.assertFalse((self.root / "history.json").exists())
        self.assertFalse((self.root / "out/01.png").exists())

    def test_real_render_verbatim_and_consistent_series(self):
        self.content["cards"].append(copy.deepcopy(self.content["cards"][0]))
        (self.root / "02.png").write_bytes((self.root / "01.png").read_bytes())
        second = dict(self.manifest["images"][0], index=2, file="02.png")
        self.manifest["images"].append(second)
        self.manifest["expected_count"] = 2
        self.content["cards"][1]["source_image"] = "02.png"
        (self.root / "content.json").write_text(json.dumps(self.content, ensure_ascii=False), encoding="utf-8")
        (self.root / "manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        args = argparse.Namespace(content=self.root / "content.json", manifest=self.root / "manifest.json",
                                  output=self.root / "out", history=self.root / "history.json",
                                  template=None, font_file=None)
        self.assertEqual(render(args), 0)
        report = json.loads((self.root / "out/review.json").read_text())
        self.assertTrue(report["passed"])
        self.assertEqual(len(report["cards"]), 2)
        self.assertTrue(all(c["text_match"] for c in report["cards"]))
        for index in (1, 2):
            markup = (self.root / f"out/{index:02d}.html").read_text(encoding="utf-8")
            self.assertIn("2027届及以后毕业", markup)
            self.assertIn("原文含&lt;特殊符号&gt;", markup)
            self.assertIn("#2375bd", markup)


if __name__ == "__main__":
    unittest.main()
