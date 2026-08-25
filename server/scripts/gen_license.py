#!/usr/bin/env python3
"""离线授权文件（.lic）生成工具——供应商侧使用，RSA 私钥签名。

首次使用：
    python scripts/gen_license.py --gen-keys --out keys/
    # 生成 keys/vendor_private.pem（私钥，妥善保管）与 keys/vendor_public.pem（公钥）

签发授权：
    python scripts/gen_license.py --key keys/vendor_private.pem \
        --customer 某某公司 --edition flagship --months 12 \
        --license-no PL-2026-0001 --out /tmp/demo.lic

平台侧配置：.env 中设置 LICENSE_PUBLIC_KEY=<vendor_public.pem 内容>（PEM 多行），
然后在管理端「离线导入」上传 .lic 文件。验签失败/重复 license_no 一律拒绝。

签名规范：payload（license_no/customer/edition/months/issued_at）按
sort_keys + 紧凑分隔 JSON 序列化后做 RSA-SHA256（PKCS1v15），base64 附于文件。
"""
import argparse
import base64
import json
import sys
from datetime import date
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

EDITION_CHOICES = ("trial", "standard", "flagship")


def _canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def gen_keys(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    (out / "vendor_private.pem").write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    (out / "vendor_public.pem").write_bytes(key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    print(f"已生成：{out / 'vendor_private.pem'}（私钥，切勿外泄）")
    print(f"已生成：{out / 'vendor_public.pem'}（公钥，配置到平台 LICENSE_PUBLIC_KEY）")


def sign(key_path: Path, customer: str, edition: str, months: int,
         license_no: str, out: Path) -> None:
    if edition not in EDITION_CHOICES:
        sys.exit(f"edition 必须为 {EDITION_CHOICES}")
    if not 1 <= months <= 36:
        sys.exit("months 需在 1-36 之间")
    payload = {
        "license_no": license_no,
        "customer": customer,
        "edition": edition,
        "months": months,
        "issued_at": date.today().isoformat(),
    }
    key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    signature = base64.b64encode(
        key.sign(_canonical(payload).encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    ).decode("ascii")
    lic = dict(payload)
    lic["signature"] = signature
    out.write_text(json.dumps(lic, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已签发：{out}（{customer} / {edition} / {months} 个月 / 编号 {license_no}）")


def main() -> None:
    ap = argparse.ArgumentParser(description="离线授权 .lic 签名工具（供应商侧）")
    ap.add_argument("--gen-keys", action="store_true", help="生成 RSA 密钥对")
    ap.add_argument("--out", type=Path, default=Path("."), help="密钥/授权文件输出目录")
    ap.add_argument("--key", type=Path, help="私钥 PEM 路径（签发时必填）")
    ap.add_argument("--customer", help="客户名称")
    ap.add_argument("--edition", choices=EDITION_CHOICES)
    ap.add_argument("--months", type=int)
    ap.add_argument("--license-no", help="授权编号（防重放唯一键）")
    args = ap.parse_args()

    if args.gen_keys:
        gen_keys(args.out)
        return
    if not (args.key and args.customer and args.edition and args.months and args.license_no):
        ap.error("签发需 --key --customer --edition --months --license-no")
    sign(args.key, args.customer, args.edition, args.months, args.license_no,
         args.out if args.out.suffix else args.out / f"{args.license_no}.lic")


if __name__ == "__main__":
    main()
