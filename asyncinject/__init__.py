import inspect

try:
    import graphlib
except ImportError:
    from . import vendored_graphlib as graphlib
import asyncio


class AsyncRegistry:
    def __init__(self, *fns, parallel=True, log=None):
        self._registry = {}
        self._graph = None
        self.parallel = parallel
        self.log = log or (lambda *args: None)
        for fn in fns:
            self.register(fn)

    def register(self, fn):
        self._registry[fn.__name__] = fn
        # Clear _graph cache:
        self._graph = None

    @property
    def graph(self):
        if self._graph is None:
            self._graph = {
                key: {
                    p
                    for p in inspect.signature(fn).parameters.keys()
                    if not p.startswith("_")
                }
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

    async def resolve_multi(self, names, results=None):
        if results is None:
            results = {}

        # Come up with an execution plan, just for these nodes
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

        self.log("Resolving {}".format(names))

        for node_group in plan:
            awaitable_names = [name for name in node_group if name in self._registry]
            self.log("  Run {}".format(sorted(awaitable_names)))
            awaitables = [
                self._registry[name](
                    **{k: v for k, v in results.items() if k in self.graph[name]},
                )
                for name in awaitable_names
            ]
            if self.parallel:
                awaitable_results = await asyncio.gather(*awaitables)
            else:
                awaitable_results = (await fn() for fn in awaitables)
            results.update(dict(zip(awaitable_names, awaitable_results)))

        return results
