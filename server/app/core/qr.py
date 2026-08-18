"""二维码渲染：链接 → PNG 字节（演练邮件附件/正文使用）。"""
import io

import qrcode
from qrcode.image.pil import PilImage


def render_qr_png(data: str, box_size: int = 8, border: int = 2) -> bytes:
    """渲染二维码 PNG（纠错等级 M，适合黑白打印与扫描）。"""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img: PilImage = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
