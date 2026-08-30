"""机器指纹：部署绑定用（授权文件与运行机器强关联，防代码/库被拷贝到别处照常运行）。

组成：/etc/machine-id + hostname + 非回环网卡 MAC（排序后拼接）→ sha256。
纯标准库实现，不依赖 psutil；进程内缓存（机器指纹变化需重启才生效，可接受）。
"""
import hashlib
import socket
from functools import lru_cache
from pathlib import Path

_MACHINE_ID_PATHS = ("/etc/machine-id", "/var/lib/dbus/machine-id")


def _machine_id() -> str:
    for p in _MACHINE_ID_PATHS:
        try:
            v = Path(p).read_text().strip()
            if v:
                return v
        except OSError:
            continue
    return ""


def _macs() -> list[str]:
    """非回环网卡 MAC 列表（含虚拟网卡；排序保证稳定）。"""
    macs = []
    net_dir = Path("/sys/class/net")
    if net_dir.is_dir():
        for nic in sorted(net_dir.iterdir()):
            if nic.name == "lo":
                continue
            try:
                mac = (nic / "address").read_text().strip()
            except OSError:
                continue
            if mac and mac != "00:00:00:00:00:00":
                macs.append(mac)
    return macs


@lru_cache(maxsize=1)
def get_machine_code() -> str:
    parts = [socket.gethostname(), _machine_id(), *sorted(_macs())]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
