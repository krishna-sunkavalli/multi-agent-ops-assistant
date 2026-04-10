"""
Post-deployment smoke tests for MULTI-AGENT OPS ASSISTANT.

Usage:
    python tests/smoke_test.py https://shiftiq.azdemohub.com
    python tests/smoke_test.py https://ca-opsassistant.braverock-xxx.northcentralus.azurecontainerapps.io

Tests:
    1. GET /              → 200 (static UI)
    2. GET /api/dashboard → 200 + valid JSON with expected keys
    3. WebSocket /ws      → send message, receive agent routing + response
"""
import asyncio
import json
import ssl
import sys
import time

import httpx
import websockets


class SmokeTestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors: list[str] = []

    def ok(self, name: str, detail: str = ""):
        self.passed += 1
        print(f"  ✅ {name}" + (f" — {detail}" if detail else ""))

    def fail(self, name: str, detail: str = ""):
        self.failed += 1
        self.errors.append(f"{name}: {detail}")
        print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))

    def summary(self) -> bool:
        total = self.passed + self.failed
        print(f"\n{'═' * 50}")
        print(f"  Results: {self.passed}/{total} passed")
        if self.errors:
            print(f"  Failures:")
            for e in self.errors:
                print(f"    • {e}")
        print(f"{'═' * 50}")
        return self.failed == 0


async def test_static_ui(base_url: str, result: SmokeTestResult):
    """Test 1: Static UI loads."""
    async with httpx.AsyncClient(verify=False, timeout=15) as client:
        try:
            resp = await client.get(f"{base_url}/")
            if resp.status_code == 200:
                if "ShiftIQ" in resp.text or "shift" in resp.text.lower():
                    result.ok("GET /", f"200 OK, {len(resp.text)} bytes")
                else:
                    result.fail("GET /", f"200 but unexpected content")
            else:
                result.fail("GET /", f"HTTP {resp.status_code}")
        except Exception as e:
            result.fail("GET /", str(e))


async def test_dashboard_api(base_url: str, result: SmokeTestResult):
    """Test 2: Dashboard API returns valid JSON with expected structure."""
    async with httpx.AsyncClient(verify=False, timeout=15) as client:
        try:
            resp = await client.get(f"{base_url}/api/dashboard")
            if resp.status_code != 200:
                result.fail("GET /api/dashboard", f"HTTP {resp.status_code}")
                return

            data = resp.json()

            # Check expected top-level keys
            expected_keys = {"kpis", "shift", "staff", "stations"}
            present = expected_keys & set(data.keys())
            if len(present) >= 2:
                result.ok("GET /api/dashboard", f"200 OK, keys: {sorted(data.keys())}")
            else:
                result.fail(
                    "GET /api/dashboard",
                    f"Missing expected keys. Got: {sorted(data.keys())}",
                )
        except json.JSONDecodeError:
            result.fail("GET /api/dashboard", "Response is not valid JSON")
        except Exception as e:
            result.fail("GET /api/dashboard", str(e))


async def test_websocket_chat(base_url: str, result: SmokeTestResult):
    """Test 3: WebSocket connects, routes message, returns agent response."""
    ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://") + "/ws"

    try:
        ssl_ctx = None
        if ws_url.startswith("wss://"):
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
        async with websockets.connect(ws_url, ssl=ssl_ctx) as ws:
            # Send a simple message
            await ws.send("How are we doing?")

            agent_received = False
            response_text = ""
            done_received = False
            timeout_at = time.time() + 60  # 60s timeout for AI response

            while time.time() < timeout_at:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=30)
                except asyncio.TimeoutError:
                    break

                if msg.startswith("[AGENT:"):
                    agent_received = True
                    agent_name = msg.split(":")[1].rstrip("]")
                    result.ok("WS agent routing", f"Routed to: {agent_name}")
                elif msg.startswith("[DONE]"):
                    done_received = True
                    break
                elif msg.startswith("[SAFETY:"):
                    pass  # Expected safety check
                elif msg.startswith("[SUGGESTIONS:"):
                    pass  # Expected suggestions
                else:
                    response_text += msg

            if not agent_received:
                result.fail("WS agent routing", "No [AGENT:...] frame received")

            if response_text:
                # Check it's not an error message
                is_error = "Resource not found" in response_text or "404" in response_text
                if is_error:
                    result.fail(
                        "WS agent response",
                        f"Agent returned error: {response_text[:200]}",
                    )
                else:
                    result.ok(
                        "WS agent response",
                        f"{len(response_text)} chars, preview: {response_text[:100]}...",
                    )
            else:
                result.fail("WS agent response", "No response text received")

            if done_received:
                result.ok("WS completion", "[DONE] frame received")
            else:
                result.fail("WS completion", "No [DONE] frame received")

    except Exception as e:
        result.fail("WS connection", str(e))


async def main():
    if len(sys.argv) < 2:
        print("Usage: python tests/smoke_test.py <BASE_URL>")
        print("  e.g. python tests/smoke_test.py https://shiftiq.azdemohub.com")
        sys.exit(1)

    base_url = sys.argv[1].rstrip("/")
    print(f"\n{'═' * 50}")
    print(f"  Smoke Tests — {base_url}")
    print(f"{'═' * 50}\n")

    result = SmokeTestResult()

    print("  [1/3] Static UI...")
    await test_static_ui(base_url, result)

    print("  [2/3] Dashboard API...")
    await test_dashboard_api(base_url, result)

    print("  [3/3] WebSocket Chat (may take up to 60s)...")
    await test_websocket_chat(base_url, result)

    success = result.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
