"""Tests for the in-process event bus (README §3.6)."""

import asyncio

from jarvis.app.events import (
    EventBus,
    JobCompleted,
    JobStarted,
    ResponseReady,
    UtteranceReceived,
)


async def test_fan_out_to_multiple_subscribers():
    bus = EventBus()
    seen_a: list[str] = []
    seen_b: list[str] = []

    async def a(event):
        seen_a.append(event.topic)

    async def b(event):
        seen_b.append(event.topic)

    bus.subscribe("response.ready", a)
    bus.subscribe("response.ready", b)

    await bus.publish(ResponseReady(trace_id="t1", text="hi"))
    await bus.drain()

    assert seen_a == ["response.ready"]
    assert seen_b == ["response.ready"]


async def test_wildcards():
    bus = EventBus()
    jobs: list[str] = []
    everything: list[str] = []

    async def on_job(event):
        jobs.append(event.topic)

    async def on_any(event):
        everything.append(event.topic)

    bus.subscribe("job.*", on_job)
    bus.subscribe("*", on_any)

    await bus.publish(JobStarted(trace_id="t1", job_id="j1"))
    await bus.publish(JobCompleted(trace_id="t1", job_id="j1", summary="done"))
    await bus.publish(
        UtteranceReceived(trace_id="t2", text="hi", area="kitchen", speaker_id="household")
    )
    await bus.drain()

    assert jobs == ["job.started", "job.completed"]
    assert everything == ["job.started", "job.completed", "utterance.received"]


async def test_failing_subscriber_does_not_break_others_or_publisher():
    bus = EventBus()
    survived: list[str] = []

    async def boom(event):
        raise RuntimeError("observer blew up")

    async def ok(event):
        survived.append(event.topic)

    bus.subscribe("response.ready", boom)
    bus.subscribe("response.ready", ok)

    # publish must not raise even though a handler does
    await bus.publish(ResponseReady(trace_id="t1", text="hi"))
    await bus.drain()

    assert survived == ["response.ready"]


async def test_slow_subscriber_does_not_stall_publisher():
    bus = EventBus()
    gate = asyncio.Event()
    completed = False

    async def slow(event):
        nonlocal completed
        await gate.wait()
        completed = True

    bus.subscribe("response.ready", slow)

    await bus.publish(ResponseReady(trace_id="t1", text="hi"))
    # publish returned while the handler is still blocked on the gate
    assert completed is False

    gate.set()
    await bus.drain()
    assert completed is True
