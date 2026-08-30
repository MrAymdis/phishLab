"""网页邮箱合成 EML（二期 #13-#16）：Node 构建 → Python email 解析回环校验。

- 中文头字段 RFC 2047 / 附件中文名 RFC 2231 / CRLF 行尾 / multipart 结构
- 纯 ASCII 头不编码；超长主题折行 ≤ 78 字节且解析回环无损
- 选择器链求值（fake DOM）；zip 安装包含新资产
"""
import base64
import io
import json
import subprocess
import zipfile
from email import message_from_bytes, policy
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

HARNESS = Path(__file__).resolve().parent / "webmail_eml_harness.js"


def _harness() -> dict:
    r = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _parse(case: str) -> "message_from_bytes":
    data = _harness()
    return message_from_bytes(base64.b64decode(data[case]["emlB64"]), policy=policy.default)


def test_eml_roundtrip_chinese_headers_attachments():
    msg = _parse("roundtrip")
    assert str(msg["X-PhishLab-Source"]) == "webmail-synthesis"
    assert str(msg["Subject"]) == "紧急：账号验证通知（八月）"
    assert str(msg["From"]) == "张三 <zhangsan@corp.com>"
    assert str(msg["To"]) == "victim@corp.com"
    assert str(msg["Cc"]) == "李四 <lisi@corp.com>"
    assert msg.is_multipart() and msg.get_content_type() == "multipart/mixed"
    body = msg.get_body(preferencelist=("html",))
    assert body.get_content_type() == "text/html"
    assert "链接" in str(body.get_content())
    atts = {a.get_filename(): a for a in msg.iter_attachments()}
    assert set(atts) == {"八月工资单.xlsx", "报告.txt"}
    assert atts["报告.txt"].get_payload(decode=True).decode("utf-8") == "hello 附件"
    assert atts["八月工资单.xlsx"].get_content_type().startswith("application/vnd.openxmlformats")


def test_eml_crlf_line_endings():
    data = _harness()
    raw = base64.b64decode(data["roundtrip"]["emlB64"])
    assert b"\r\n" in raw
    assert b"\n" not in raw.replace(b"\r\n", b"")  # 无裸 LF


def test_eml_ascii_headers_not_encoded():
    data = _harness()
    raw = base64.b64decode(data["ascii"]["emlB64"])
    head = raw.split(b"\r\n\r\n", 1)[0].decode()
    assert "=?" not in head
    assert "Salary Slip" in head
    msg = message_from_bytes(raw, policy=policy.default)
    assert str(msg["Subject"]) == "Salary Slip"


def test_eml_long_subject_folded_and_roundtrips():
    data = _harness()
    raw = base64.b64decode(data["fold"]["emlB64"])
    head = raw.split(b"\r\n\r\n", 1)[0].decode()
    for line in head.split("\r\n"):
        assert len(line.encode()) <= 78, line[:60]
    msg = message_from_bytes(raw, policy=policy.default)
    assert str(msg["Subject"]) == data["fold"]["subject"]  # 折行拼接无损


def test_eml_attachment_mime_fallback_and_rfc2231():
    msg = _parse("fallback")
    att = next(msg.iter_attachments())
    assert att.get_filename() == "附件.bin"
    assert att.get_content_type() == "application/octet-stream"
    assert att.get_payload(decode=True).decode("utf-8") == "bin-data"


def test_adapter_selector_chain_resolution():
    ch = _harness()["chain"]
    assert ch == {
        "firstHit": "B text",
        "attr": "http://x/a",
        "itemAttr": "item-href",
        "title": "测试标题",
        "cssallFirst": "first-non-empty",
        "blankSkip": "B text",      # 空白文本跳过，落第二选择器
        "empty": "",
    }


def test_webmail_zip_includes_synthesis_assets():
    r = TestClient(app).get("/report/v1/plugin/webmail.zip")
    assert r.status_code == 200
    names = set(zipfile.ZipFile(io.BytesIO(r.content)).namelist())
    assert {"eml.js", "adapters.js", "content.js", "background.js", "manifest.json"} <= names
