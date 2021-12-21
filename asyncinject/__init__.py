import asyncio
from functools import wraps
import inspect

try:
    import graphlib
except ImportError:
    from . import vendored_graphlib as graphlib


def inject(fn):
    "Mark method as having dependency-injected parameters"
    fn._inject = True
    return fn


def _make_method(method):
    parameters = inspect.signature(method).parameters

    @wraps(method)
    async def inner(self, **kwargs):
        # Any parameters not provided by kwargs are resolved from registry
        to_resolve = [
            p
            for p in parameters
            # Not already provided
            if p not in kwargs
            # Not self
            and p != "self"
            # Doesn't have a default value
            and parameters[p].default is inspect._empty
        ]
        missing = [p for p in to_resolve if p not in self._registry]
        assert (
            not missing
        ), "The following DI parameters could not be found in the registry: {}".format(
            missing
        )

        results = {}
        results.update(kwargs)
        if to_resolve:
            resolved_parameters = await resolve(self, to_resolve, results)
            results.update(resolved_parameters)
        return await method(
            self, **{k: v for k, v in results.items() if k in parameters}
        )

    return inner


class AsyncInject:
    def _log(self, message):
        pass

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Decorate any items that are 'async def' methods
        cls._registry = {}
        inject_all = getattr(cls, "_inject_all", False)
        for name in dir(cls):
            value = getattr(cls, name)
            if inspect.iscoroutinefunction(value) and (
                inject_all or getattr(value, "_inject", None)
            ):
                setattr(cls, name, _make_method(value))
                cls._registry[name] = getattr(cls, name)
        # Gather graph for later dependency resolution
        graph = {
            key: {
                p
                for p in inspect.signature(method).parameters.keys()
                if p != "self" and not p.startswith("_")
            }
            for key, method in cls._registry.items()
        }
        cls._graph = graph


class AsyncInjectAll(AsyncInject):
    _inject_all = True


async def resolve(instance, names, results=None):
    if results is None:
        results = {}

    # Come up with an execution plan, just for these nodes
    ts = graphlib.TopologicalSorter()
    to_do = set(names)
    done = set()
    while to_do:
        item = to_do.pop()
        dependencies = instance._graph.get(item) or set()
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

    instance._log(
        "Resolving {} in {}>".format(names, repr(instance).split(" object at ")[0])
    )

    for node_group in plan:
        awaitable_names = [name for name in node_group if name in instance._registry]
        instance._log("  Run {}".format(awaitable_names))
        awaitables = [
            instance._registry[name](
                instance,
                _results=results,
                **{k: v for k, v in results.items() if k in instance._graph[name]},
            )
            for name in awaitable_names
        ]
        awaitable_results = await asyncio.gather(*awaitables)
        results.update(dict(zip(awaitable_names, awaitable_results)))

    return results
