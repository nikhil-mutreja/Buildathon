# Realtime WebSocket Event Broker
import logging

logger = logging.getLogger(__name__)

class WebSocketEventBroker:
    def __init__(self):
        # VULNERABILITY (CWE-775): Unbounded connection pool memory leak
        self.connections = []

    def register_client(self, websocket):
        self.connections.append(websocket)

    def broadcast_event(self, payload: str):
        for ws in self.connections:
            ws.send(payload)
