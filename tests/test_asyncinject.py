import asyncio
import pytest
from asyncinject import Registry
from random import random
import time


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


@pytest.mark.asyncio
async def test_optimal_concurrency():
    # https://github.com/simonw/asyncinject/issues/10
    async def a():
        await asyncio.sleep(0.1)

    async def b():
        await asyncio.sleep(0.2)

    async def c(a):
        await asyncio.sleep(0.1)

    async def d(b, c):
        pass

    registry = Registry(a, b, c, d)
    start = time.perf_counter()
    await registry.resolve(d)
    end = time.perf_counter()
    # Should have taken ~0.2s
    assert 0.18 < (end - start) < 0.22


@pytest.mark.asyncio
@pytest.mark.parametrize("use_async", (True, False))
async def test_resolve_unregistered_function(use_async):
    # https://github.com/simonw/asyncinject/issues/13
    async def one():
        return 1

    async def two():
        return 2

    registry = Registry(one, two)

    async def three_async(one, two):
        return one + two

    def three_not_async(one, two):
        return one + two

    fn = three_async if use_async else three_not_async
    result = await registry.resolve(fn)
    assert result == 3

    # Test that passing parameters works too
    result2 = await registry.resolve(fn, one=2)
    assert result2 == 4


@pytest.mark.asyncio
async def test_register():
    registry = Registry()

    # Mix in a non-async function too:
    def one():
        return "one"

    async def two_():
        return "two"

    async def three(one, two):
        return one + two

    registry.register(one)

    # Should raise an error if you don't use name=
    with pytest.raises(TypeError):
        registry.register(two_, "two")

    registry.register(two_, name="two")

    result = await registry.resolve(three)

    assert result == "onetwo"


@pytest.mark.asyncio
@pytest.mark.parametrize("parallel", (True, False))
async def test_just_sync_functions(parallel):
    def one():
        return 1

    def two():
        return 2

    def three(one, two):
        return one + two

    timed = []

    registry = Registry(
        one, two, three, parallel=parallel, timer=lambda *args: timed.append(args)
    )
    result = await registry.resolve(three)
    assert result == 3

    assert {t[0] for t in timed} == {"two", "one", "three"}


@pytest.mark.asyncio
@pytest.mark.parametrize("use_string_name", (True, False))
async def test_registry_from_dict(use_string_name):
    async def _one():
        return 1

    async def _two():
        return 2

    async def _three(one, two):
        return one + two

    registry = Registry.from_dict({"one": _one, "two": _two, "three": _three})
    if use_string_name:
        result = await registry.resolve("three")
    else:
        result = await registry.resolve(_three)
    assert result == 3
