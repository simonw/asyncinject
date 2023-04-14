import inspect
import time

try:
    import graphlib
except ImportError:
    from . import vendored_graphlib as graphlib
import asyncio


class Registry:
    def __init__(self, *fns, parallel=True, timer=None):
        self._registry = {}
        self._graph = None
        self._reversed = None
        self.parallel = parallel
        self.timer = timer
        for fn in fns:
            self.register(fn)

    @classmethod
    def from_dict(cls, d, parallel=True, timer=None):
        instance = cls(parallel=parallel, timer=timer)
        for key, fn in d.items():
            instance.register(fn, name=key)
        return instance

    def register(self, fn, *, name=None):
        self._registry[name or fn.__name__] = fn
        # Clear caches:
        self._graph = None
        self._reversed = None

    def _make_time_logger(self, awaitable):
        async def inner():
            start = time.perf_counter()
            result = await awaitable
            end = time.perf_counter()
            self.timer(awaitable.__name__, start, end)
            return result

        return inner()

    @property
    def graph(self):
        if self._graph is None:
            self._graph = {
                key: set(inspect.signature(fn).parameters.keys())
                for key, fn in self._registry.items()
            }
        return self._graph

    @property
    def reversed(self):
        if self._reversed is None:
            self._reversed = dict(reversed(pair) for pair in self._registry.items())
        return self._reversed

    async def resolve(self, fn, **kwargs):
        if not isinstance(fn, str):
            # It's a fn - is it a registered one?
            name = self.reversed.get(fn)
            if name is None:
                # Special case - since it is not registered we need to
                # introspect its parameters here and use resolve_multi
                params = inspect.signature(fn).parameters.keys()
                to_resolve = {p for p in params if p not in kwargs}
                resolved = await self.resolve_multi(to_resolve, results=kwargs)
                result = fn(**{param: resolved[param] for param in params})
                if asyncio.iscoroutine(result):
                    result = await result
                return result
        else:
            name = fn
        results = await self.resolve_multi([name], results=kwargs)
        return results[name]

    def _plan(self, names, results=None):
        if results is None:
            results = {}

        ts = graphlib.TopologicalSorter()
        to_do = set(names)
        done = set(results.keys())
        while to_do:
            item = to_do.pop()
            dependencies = self.graph.get(item) or set()
            ts.add(item, *dependencies)
            done.add(item)
            # Add any not-done dependencies to the queue
            to_do.update({k for k in dependencies if k not in done})

        return ts

    def _get_awaitable(self, name, results):
        fn = self._registry[name]
        kwargs = {k: v for k, v in results.items() if k in self.graph[name]}

        awaitable_fn = fn

        if not asyncio.iscoroutinefunction(fn):

            async def _awaitable(*args, **kwargs):
                return fn(*args, **kwargs)

            _awaitable.__name__ = fn.__name__
            awaitable_fn = _awaitable

        aw = awaitable_fn(**kwargs)
        if self.timer:
            aw = self._make_time_logger(aw)
        return aw

    async def _execute_sequential(self, results, ts):
        for name in ts.static_order():
            if name not in self._registry:
                continue
            results[name] = await self._get_awaitable(name, results)

    async def _execute_parallel(self, results, ts):
        ts.prepare()
        tasks = []

        def schedule():
            for name in ts.get_ready():
                if name not in self._registry:
                    ts.done(name)
                    continue
                tasks.append(asyncio.create_task(worker(name)))

        async def worker(name):
            res = await self._get_awaitable(name, results)
            results[name] = res
            ts.done(name)
            schedule()

        schedule()
        while tasks:
            await asyncio.gather(*[tasks.pop() for _ in range(len(tasks))])

    async def resolve_multi(self, names, results=None):
        if results is None:
            results = {}

        ts = self._plan(names, results)

        if self.parallel:
            await self._execute_parallel(results, ts)
        else:
            await self._execute_sequential(results, ts)

        return results
