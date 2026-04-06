import asyncio
import json
import threading
import time

import websockets

from config.settings import WS_URL, PI_UNIQUE_CODE, WS_ENABLED
from sync.whitelist_sync_service import WhitelistSyncService


class PiWebSocketListener:
    def __init__(self, status_callback=None, whitelist_updated_callback=None):
        self.status_callback = status_callback
        self.whitelist_updated_callback = whitelist_updated_callback
        self._thread = None
        self._running = False
        self._loop = None

    def start(self):
        if not WS_ENABLED:
            self._set_status("WebSocket uitgeschakeld")
            return

        if not WS_URL:
            self._set_status("WebSocket URL ontbreekt")
            return

        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_thread, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(lambda: None)

    def _set_status(self, message: str):
        print(f"[PI WS] {message}")
        if self.status_callback:
            self.status_callback(message)

    def _notify_whitelist_updated(self):
        if self.whitelist_updated_callback:
            self.whitelist_updated_callback()

    def _run_thread(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._listen_forever())
        finally:
            self._loop.close()

    async def _listen_forever(self):
        while self._running:
            try:
                self._set_status("WebSocket verbinden...")
                async with websockets.connect(WS_URL, ping_interval=20, ping_timeout=20) as websocket:
                    self._set_status("WebSocket verbonden")

                    hello_message = {
                        "type": "register_pi",
                        "pi_unique_code": PI_UNIQUE_CODE,
                    }
                    await websocket.send(json.dumps(hello_message))
                    await self._sync_whitelist_and_ack(websocket, source_label="connect")

                    while self._running:
                        raw = await websocket.recv()
                        await self._handle_message(raw, websocket)

            except Exception as e:
                self._set_status(f"WebSocket fout: {e}")
                await asyncio.sleep(5)

    async def _handle_message(self, raw_message: str, websocket):
        try:
            data = json.loads(raw_message)
        except json.JSONDecodeError:
            self._set_status("Ongeldig WebSocket bericht")
            return

        message_type = data.get("type")

        if message_type == "whitelist_changed":
            target_pi = data.get("pi_unique_code")

            if target_pi and PI_UNIQUE_CODE and target_pi != PI_UNIQUE_CODE:
                return

            self._set_status("Whitelist wijziging ontvangen")
            await self._sync_whitelist_and_ack(websocket, source_label="ws")

        elif message_type == "register_ack":
            ack_message = data.get("message", "WebSocket registratie bevestigd")
            self._set_status(ack_message)

        elif message_type == "whitelist_applied_ack":
            ack_message = data.get("message", "Whitelist bevestiging ontvangen")
            self._set_status(ack_message)

        elif message_type == "ping":
            self._set_status("WebSocket ping ontvangen")

        else:
            self._set_status(f"Onbekend WS berichttype: {message_type}")

    async def _sync_whitelist_and_ack(self, websocket, source_label: str):
        try:
            result = WhitelistSyncService().sync_once()

            conflict_count = result.get("skipped_conflict_count", 0)
            self._set_status(
                f"Whitelist via {source_label.upper()} bijgewerkt ({result['count']} actief, {conflict_count} conflicten) - {time.strftime('%H:%M:%S')}"
            )

            for conflict in result.get("skipped_conflicts", []):
                locker_number = conflict.get("locker_number")
                nfc_code = conflict.get("nfc_code")
                reason = conflict.get("reason")
                print(
                    f"[WHITELIST CONFLICT] locker={locker_number} nfc={nfc_code} reason={reason}"
                )

            await websocket.send(json.dumps({"type": "whitelist_applied"}))
            self._notify_whitelist_updated()
        except Exception as e:
            self._set_status(f"Whitelist sync via {source_label.upper()} fout: {e}")