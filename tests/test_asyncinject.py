import asyncio
import pytest
from asyncinject import Registry
from random import random

from pprint import pprint


@pytest.fixture
def complex_registry():
    async def log():
        return []

    async def d(log):
        await asyncio.sleep(0.1 + random() * 0.5)
        log.append("d")

    async def c(log):
        await asyncio.sleep(0.1 + random() * 0.5)
        log.append("c")

    async def b(log, c, d):
        log.append("b")

    async def a(log, b, c):
        log.append("a")

    async def go(log, a):
        log.append("go")
        return log

    return Registry(log, d, c, b, a, go)


@pytest.mark.asyncio
async def test_complex(complex_registry):
    result = await complex_registry.resolve("go")
    # 'c' should only be called once
    assert tuple(result) in (
        # c and d could happen in either order
        ("c", "d", "b", "a", "go"),
        ("d", "c", "b", "a", "go"),
    )


@pytest.mark.asyncio
async def test_with_parameters():
    async def go(calc1, calc2, param1):
        return param1 + calc1 + calc2

    async def calc1():
        return 5

    async def calc2():
        return 6

    registry = Registry(go, calc1, calc2)
    result = await registry.resolve(go, param1=4)
    assert result == 15

    # Should throw an error if that parameter is missing
    with pytest.raises(TypeError) as e:
        result = await registry.resolve(go)
        assert "go() missing 1 required positional" in e.args[0]


@pytest.mark.asyncio
async def test_parameters_passed_through():
    async def go(calc1, calc2, param1):
        return calc1 + calc2

    async def calc1():
        return 5

    async def calc2(param1):
        return 6 + param1

    registry = Registry(go, calc1, calc2)
    result = await registry.resolve(go, param1=1)
    assert result == 12


@pytest.mark.asyncio
async def test_ignore_default_parameters():
    async def go(calc1, x=5):
        return calc1 + x

    async def calc1():
        return 5

    registry = Registry(go, calc1)
    result = await registry.resolve(go)
    assert result == 10


@pytest.mark.asyncio
async def test_timer(complex_registry):
    collected = []
    complex_registry.timer = lambda name, start, end: collected.append(
        (name, start, end)
    )
    await complex_registry.resolve("go")
    assert len(collected) == 6
    names = [c[0] for c in collected]
    starts = [c[1] for c in collected]
    ends = [c[2] for c in collected]
    assert all(isinstance(n, float) for n in starts)
    assert all(isinstance(n, float) for n in ends)
    assert names[0] == "log"
    assert names[5] == "go"
    assert sorted(names[1:5]) == ["a", "b", "c", "d"]


@pytest.mark.asyncio
async def test_parallel(complex_registry):
    collected = []
    complex_registry.timer = lambda name, start, end: collected.append(
        (name, start, end)
    )
    # Run it once in parallel=True mode
    await complex_registry.resolve("go")
    parallel_timings = {c[0]: (c[1], c[2]) for c in collected}
    # 'c' and 'd' should have started within 0.05s
    c_start, d_start = parallel_timings["c"][0], parallel_timings["d"][0]
    assert abs(c_start - d_start) < 0.05

    # And again in parallel=False mode
    collected.clear()
    complex_registry.parallel = False
    await complex_registry.resolve("go")
    serial_timings = {c[0]: (c[1], c[2]) for c in collected}
    # 'c' and 'd' should have started at least 0.1s apart
    c_start_serial, d_start_serial = serial_timings["c"][0], serial_timings["d"][0]
    assert abs(c_start_serial - d_start_serial) > 0.1
