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

The idea is to simplify executing parallel `asyncio` operations by allowing them to be collected in a class, with the names of parameters to the class methods specifying which other methods should be executed first.

This then allows the library to create and execute a plan for executing various dependent methods in parallel.

Here's an example, using the [httpx](https://www.python-httpx.org/) HTTP library.

```python
from asyncinject import AsyncInjectAll
import httpx

async def get(url):
    async with httpx.AsyncClient() as client:
        return (await client.get(url)).text

class FetchThings(AsyncInjectAll):
    async def example(self):
        return await get("http://www.example.com/")

    async def simonwillison(self):
        return await get("https://simonwillison.net/search/?tag=empty")

    async def both(self, example, simonwillison):
        return example + "\n\n" + simonwillison


combined = await FetchThings().both()
print(combined)
```
If you run this in `ipython` (which supports top-level await) you will see output that combines HTML from both of those pages.

The HTTP requests to `www.example.com` and `simonwillison.net` will be performed in parallel.

The library will notice that `both()` takes two arguments which are the names of other `async def` methods on that class, and will construct an execution plan that executes those two methods in parallel, then passes their results to the `both()` method.

### Parameters are passed through

Your dependent methods can require keyword arguments which are passed to the original method.

```python
class FetchWithParams(AsyncInjectAll):
    async def get_param_1(self, param1):
        return await get(param1)

    async def get_param_2(self, param2):
        return await get(param2)

    async def both(self, get_param_1, get_param_2):
        return get_param_1 + "\n\n" + get_param_2


combined = await FetchWithParams().both(
    param1 = "http://www.example.com/",
    param2 = "https://simonwillison.net/search/?tag=empty"
)
print(combined)
```
### Parameters with default values are ignored

You can opt a parameter out of the dependency injection mechanism by assigning it a default value:

```python
class IgnoreDefaultParameters(AsyncInjectAll):
    async def go(self, calc1, x=5):
        return calc1 + x

    async def calc1(self):
        return 5

print(await IgnoreDefaultParameters().go())
# Prints 10
```

### AsyncInject and @inject

The above example illustrates the `AsyncInjectAll` class, which assumes that every `async def` method on the class should be treated as a dependency injection method.

You can also specify individual methods using the `AsyncInject` base class an the `@inject` decorator:

```python
from asyncinject import AsyncInject, inject

class FetchThings(AsyncInject):
    @inject
    async def example(self):
        return await get("http://www.example.com/")

    @inject
    async def simonwillison(self):
        return await get("https://simonwillison.net/search/?tag=empty")

    @inject
    async def both(self, example, simonwillison):
        return example + "\n\n" + simonwillison
```
### The resolve() function

If you want to execute a set of methods in parallel without defining a third method that lists them as parameters, you can do so using the `resolve()` function. This will execute the specified methods (in parallel, where possible) and return a dictionary of the results.

```python
from asyncinject import resolve

fetcher = FetchThings()
results = await resolve(fetcher, ["example", "simonwillison"])
```
`results` will now be:
```json
{
    "example": "contents of http://www.example.com/",
    "simonwillison": "contents of https://simonwillison.net/search/?tag=empty"
}
```
### Debug logging

You can assign a `_log` method to your class or instance to see the execution plan when it runs. Your `_log` method should take a single `message` argument - the easiest way to do this is to use `print`:
```python
fetcher = FetchThings()
fetcher._log = print
combined = await fetcher.both()
```
This will output:
```
Resolving ['example', 'simonwillison'] in <__main__.FetchThings>
  Run ['example', 'simonwillison']
```

## Development

To contribute to this library, first checkout the code. Then create a new virtual environment:

    cd asyncinject
    python -m venv venv
    source venv/bin/activate

Or if you are using `pipenv`:

    pipenv shell

Now install the dependencies and test dependencies:

    pip install -e '.[test]'

To run the tests:

    pytest
