# Realtime WebSocket Event Broker
import logging

logger = logging.getLogger(__name__)

class WebSocketEventBroker:
    def __init__(self):
        # VULNERABILITY (CWE-775): Unbounded connection pool memory leak
        # FIXED (CWE-775): Use WeakSet to prevent unbounded memory leak
        from weakref import WeakSet
        self.connections = WeakSet()

    def register_client(self, websocket):
        self.connections.add(websocket)

    def broadcast_event(self, payload: str):
        for ws in self.connections:
            ws.send(payload)
