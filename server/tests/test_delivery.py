"""投递引擎单元测试：发送间隔抖动（time_jitter_sec）接线。"""
from types import SimpleNamespace

from worker.tasks.delivery import _inter_target_delay_sec


def test_inter_target_delay_uses_campaign_jitter():
    """演练配置 time_jitter_sec>0 时逐封间隔取 0~N 秒（防识别高级设置）。"""
    assert _inter_target_delay_sec(SimpleNamespace(time_jitter_sec=120)) == (0.0, 120.0)
    assert _inter_target_delay_sec(SimpleNamespace(time_jitter_sec=600)) == (0.0, 600.0)


def test_inter_target_delay_falls_back_to_builtin():
    """未配置（0/None/缺字段）回退内置小幅抖动 (0.5, 3.0)。"""
    for v in (0, None):
        assert _inter_target_delay_sec(SimpleNamespace(time_jitter_sec=v)) == (0.5, 3.0)
    assert _inter_target_delay_sec(SimpleNamespace()) == (0.5, 3.0)
