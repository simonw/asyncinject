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
        self.parallel = parallel
        self.timer = timer
        for fn in fns:
            self.register(fn)

    def register(self, fn):
        self._registry[fn.__name__] = fn
        # Clear _graph cache:
        self._graph = None

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

    async def resolve(self, fn, **kwargs):
        try:
            name = fn.__name__
        except AttributeError:
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
        aw = self._registry[name](
            **{k: v for k, v in results.items() if k in self.graph[name]},
        )
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
