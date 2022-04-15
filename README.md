# asyncinject

[![PyPI](https://img.shields.io/pypi/v/asyncinject.svg)](https://pypi.org/project/asyncinject/)
[![Changelog](https://img.shields.io/github/v/release/simonw/asyncinject?include_prereleases&label=changelog)](https://github.com/simonw/asyncinject/releases)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/simonw/asyncinject/blob/main/LICENSE)

Run async workflows using pytest-fixtures-style dependency injection

## Installation

Install this library using `pip`:

    $ pip install asyncinject

## Usage

This library is inspired by [pytest fixtures](https://docs.pytest.org/en/6.2.x/fixture.html).

The idea is to simplify executing parallel `asyncio` operations by allowing them to be defined using a collection of functions, where the function arguments represent dependent functions that need to be executed first.

The library can then create and execute a plan for executing the required functions in parallel in the most efficient sequence possible.

Here's an example, using the [httpx](https://www.python-httpx.org/) HTTP library.

```python
from asyncinject import AsyncRegistry
import httpx


async def get(url):
    async with httpx.AsyncClient() as client:
        return (await client.get(url)).text

async def example():
    return await get("http://www.example.com/")

async def simonwillison():
    return await get("https://simonwillison.net/search/?tag=empty")

async def both(example, simonwillison):
    return example + "\n\n" + simonwillison

registry = AsyncRegistry(example, simonwillison, both)
combined = await registry.resolve(both)
print(combined)
```
If you run this in `ipython` (which supports top-level await) you will see output that combines HTML from both of those pages.

The HTTP requests to `www.example.com` and `simonwillison.net` will be performed in parallel.

The library notices that `both()` takes two arguments which are the names of other registered `async def` functions, and will construct an execution plan that executes those two functions in parallel, then passes their results to the `both()` method.

### Parameters are passed through

Your dependent functions can require keyword arguments which have been passed to the `.resolve()` call:

```python
async def get_param_1(param1):
    return await get(param1)

async def get_param_2(param2):
    return await get(param2)

async def both(get_param_1, get_param_2):
    return get_param_1 + "\n\n" + get_param_2


combined = await AsyncRegistry(get_param_1, get_param_2, both).resolve(
    both,
    param1 = "http://www.example.com/",
    param2 = "https://simonwillison.net/search/?tag=empty"
)
print(combined)
```
### Parameters with default values are ignored

You can opt a parameter out of the dependency injection mechanism by assigning it a default value:

```python
async def go(calc1, x=5):
    return calc1 + x

async def calc1():
    return 5

print(await AsyncRegistry(calc1, go).resolve(go))
# Prints 10
```

### Debug logging

You can pass a `log=` callable to the `AsyncRegistry` constructor.  Your function should take a single `message` argument - the easiest way to do this is to use `print`:
```python
combined = await AsyncRegistry(
    get_param_1, get_param_2, both, log=print
).resolve(
    both,
    param1 = "http://www.example.com/",
    param2 = "https://simonwillison.net/search/?tag=empty"
)
```
This will output:
```
Resolving ['both']
  Run []
  Run ['get_param_2', 'get_param_1']
  Run ['both']
```
## Development

To contribute to this library, first checkout the code. Then create a new virtual environment:

    cd asyncinject
    python -m venv venv
    source venv/bin/activate

Now install the dependencies and test dependencies:

    pip install -e '.[test]'

To run the tests:

    pytest
