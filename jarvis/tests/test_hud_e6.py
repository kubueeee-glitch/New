import asyncio
import unittest

from jarvis.core.bus import Bus
from jarvis.core.scheduler import Scheduler
from jarvis.hud.state import HudState
from jarvis.llm.modes import Mode


class HudStateTest(unittest.TestCase):
    def test_snapshot_zbiera_zdarzenia(self):
        async def flow():
            bus = Bus()
            sched = Scheduler(bus)
            state = HudState(bus, sched)
            await bus.publish("mode.changed", {"old": Mode.SLEEP, "new": Mode.ACTIVE})
            await bus.publish("gpu.stats", {"vram_used_mb": 6600, "vram_total_mb": 8192,
                                            "temp_c": 71, "power_w": 148.2, "util_pct": 90})
            await bus.publish("transcript", {"role": "ja", "text": "która godzina"})
            await bus.publish("transcript", {"role": "jarvis", "text": "Jest 14:30."})
            await bus.publish("action.logged", {"action": "open_app", "status": "ok"})
            await bus.publish("latency", 0.412)
            await sched.submit("skan", lambda: asyncio.sleep(0))
            return state.snapshot()

        snap = asyncio.run(flow())
        self.assertEqual(snap["mode"], "active")
        self.assertEqual(snap["gpu"]["temp_c"], 71)          # temperatura na żywo
        self.assertEqual(snap["gpu"]["power_w"], 148.2)      # pobór mocy na żywo
        self.assertEqual(snap["latency_ms"], 412)
        self.assertEqual([m["role"] for m in snap["transcript"]], ["ja", "jarvis"])
        self.assertEqual(snap["actions"][0]["action"], "open_app")
        self.assertEqual(snap["queue"][0]["name"], "skan")

    def test_transkrypt_ograniczony(self):
        async def flow():
            bus = Bus()
            state = HudState(bus)
            for i in range(50):
                await bus.publish("transcript", {"role": "ja", "text": str(i)})
            return state.snapshot()

        snap = asyncio.run(flow())
        self.assertEqual(len(snap["transcript"]), 30)
        self.assertEqual(snap["transcript"][-1]["text"], "49")


if __name__ == "__main__":
    unittest.main()
