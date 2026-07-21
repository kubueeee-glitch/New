import asyncio
import unittest
from types import SimpleNamespace

from jarvis.core.bus import Bus
from jarvis.core.scheduler import Scheduler
from jarvis.skills.loader import SkillRegistry


class LoaderTest(unittest.TestCase):
    def setUp(self):
        self.reg = SkillRegistry()

    def test_frontmattery_bez_ciala(self):
        names = self.reg.names()
        self.assertEqual(names, ["note_add", "time", "web_search"])
        for meta in self.reg.frontmatters():
            self.assertTrue(meta.description)
            # frontmatter to tylko name+description — treść pliku nie wycieka
            self.assertNotIn("\n", meta.description)

    def test_pelny_plik_dopiero_na_zadanie(self):
        full = self.reg.load_full("time")
        self.assertIn("# time", full)

    def test_skill_time_dziala(self):
        answer = self.reg.run("time", {}, ctx=None)
        self.assertIn("Jest ", answer)

    def test_skill_note_add_pisze_do_vaulta(self):
        lines = []
        ctx = SimpleNamespace(vault=SimpleNamespace(daily_append=lines.append))
        answer = self.reg.run("note_add", {"text": "kupić mleko"}, ctx)
        self.assertEqual(answer, "Zanotowane.")
        self.assertEqual(lines, ["- kupić mleko"])

    def test_nieznany_skill(self):
        with self.assertRaises(KeyError):
            self.reg.run("hack_pentagon", {}, None)


class SchedulerTest(unittest.TestCase):
    def test_nigdy_wiecej_niz_3_rownolegle(self):
        async def flow():
            bus = Bus()
            sched = Scheduler(bus, max_workers=3)
            await sched.start()
            running, peak = [0], [0]

            async def job():
                running[0] += 1
                peak[0] = max(peak[0], running[0])
                await asyncio.sleep(0.02)
                running[0] -= 1
                return "ok"

            for i in range(7):
                await sched.submit(f"job{i}", job)
            await sched._queue.join()
            await sched.stop()
            return peak[0]

        self.assertEqual(asyncio.run(flow()), 3)

    def test_task_done_publikowany_proaktywnie(self):
        async def flow():
            bus = Bus()
            done = []
            bus.subscribe("task.done", lambda t, p: done.append(p))
            sched = Scheduler(bus, max_workers=3)
            await sched.start()

            async def scan():
                return "dwa nowe wpisy w autostarcie"

            await sched.submit("skan", scan)
            await sched._queue.join()
            await sched.stop()
            return done

        done = asyncio.run(flow())
        self.assertEqual(done[0].status, "done")
        self.assertIn("autostarcie", done[0].summary)

    def test_pauza_wstrzymuje_zadania(self):
        async def flow():
            bus = Bus()
            sched = Scheduler(bus, max_workers=3)
            sched.pause()
            await sched.start()
            ran = []

            async def job():
                ran.append(1)

            await sched.submit("job", job)
            await asyncio.sleep(0.05)
            paused_state = list(ran)
            sched.resume()               # wyjście z gry — zadania wracają
            await sched._queue.join()
            await sched.stop()
            return paused_state, ran

        paused_state, ran = asyncio.run(flow())
        self.assertEqual(paused_state, [])
        self.assertEqual(ran, [1])


if __name__ == "__main__":
    unittest.main()
