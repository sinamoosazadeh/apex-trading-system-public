"""Tests for core foundation - Phase 1."""
import pytest
import asyncio
from decimal import Decimal
from apex.core.types.primitives import Price, Probability
from apex.core.events import EventBus, Event
from apex.core.types.enums import EventType

def test_price_immutability_and_validation():
    with pytest.raises(ValueError):
        Price(Decimal("-100"))
    
    p1 = Price(Decimal("100.50"))
    p2 = Price(Decimal("50.25"))
    result = p1 + p2
    assert result.value == Decimal("150.75")

def test_probability_bounds():
    with pytest.raises(ValueError):
        Probability(1.5)
    
    prob = Probability(0.8)
    # استفاده از approx برای حل مشکل دقت اعشاری
    assert prob.complement().value == pytest.approx(0.2)

@pytest.mark.asyncio
async def test_event_bus_publish_subscribe():
    bus = EventBus()
    received_events = []
    
    async def handler(event: Event):
        received_events.append(event)
        
    bus.subscribe(EventType.NEW_TICK, handler)
    
    event = Event(event_type=EventType.NEW_TICK, payload={"data": 1})
    await bus.publish(event)
    
    assert len(received_events) == 1
    assert received_events[0].payload["data"] == 1
