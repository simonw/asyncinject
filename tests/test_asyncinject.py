import asyncio
import pytest
from asyncinject import AsyncRegistry
from random import random


@pytest.fixture
def complex_registry():
    async def log():
        return []

    async def d(log):
        await asyncio.sleep(random() * 0.1)
        log.append("d")

    async def c(log):
        await asyncio.sleep(random() * 0.1)
        log.append("c")

    async def b(log, c, d):
        log.append("b")

    async def a(log, b, c):
        log.append("a")

    async def go(log, a):
        log.append("go")
        return log

    return AsyncRegistry(log, d, c, b, a, go)


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

    registry = AsyncRegistry(go, calc1, calc2)
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

    registry = AsyncRegistry(go, calc1, calc2)
    result = await registry.resolve(go, param1=1)
    assert result == 12


@pytest.mark.asyncio
async def test_ignore_default_parameters():
    async def go(calc1, x=5):
        return calc1 + x

    async def calc1():
        return 5

    registry = AsyncRegistry(go, calc1)
    result = await registry.resolve(go)
    assert result == 10


@pytest.mark.asyncio
async def test_log(complex_registry):
    collected = []
    complex_registry.log = collected.append
    await complex_registry.resolve("go")
    assert collected == [
        "Resolving ['go']",
        "  Run ['log']",
        "  Run ['c', 'd']",
        "  Run ['b']",
        "  Run ['a']",
        "  Run ['go']",
    ]
