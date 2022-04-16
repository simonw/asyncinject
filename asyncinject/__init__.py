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

        ts.prepare()
        plan = []
        while ts.is_active():
            node_group = ts.get_ready()
            plan.append(node_group)
            ts.done(*node_group)

        return plan

    async def resolve_multi(self, names, results=None):
        if results is None:
            results = {}

        for node_group in self._plan(names, results):
            awaitable_names = [name for name in node_group if name in self._registry]
            awaitables = [
                self._registry[name](
                    **{k: v for k, v in results.items() if k in self.graph[name]},
                )
                for name in awaitable_names
            ]
            if self.timer:
                awaitables = [self._make_time_logger(a) for a in awaitables]
            if self.parallel:
                awaitable_results = await asyncio.gather(*awaitables)
            else:
                awaitable_results = [await fn for fn in awaitables]
            results.update(dict(zip(awaitable_names, awaitable_results)))

        return results
