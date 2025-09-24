"""Module src/pybragerone/gateway.py."""
from __future__ import annotations

from logging import getLogger
from asyncio import Event, Task, TaskGroup, CancelledError, create_task, gather, sleep, iscoroutine
from collections.abc import Awaitable, Callable, Coroutine, Iterable
from typing import Any, cast

from .api import ApiError, BragerOneApiClient
from .events import EventBus, ParamUpdate
from .ws import RealtimeManager

LOG = getLogger("pybragerone.gateway")

# Typy callbacków
ParametersCb = Callable[[str, dict[str, Any]], Awaitable[None] | None]  # (event_name, payload)
SnapshotCb   = Callable[[dict[str, Any]], Awaitable[None] | None]
GenericCb    = Callable[[str, Any],       Awaitable[None] | None]

class BragerGateway:
    """Orkiestrator: login → WS connect → modules.connect → listen → prime.
    - Autoresubscribe po reconnect.
    - Rejestruje callbacki na konkretne strumienie.
    - Utrzymuje ParamStore (opcjonalnie).
    """
    def __init__(
        self,
        email: str,
        password: str,
        *,
        object_id: int,
        modules: Iterable[str],
        keep_param_store: bool = True,
        origin: str = "https://one.brager.pl",
        referer: str = "https://one.brager.pl/",
    ):
        """Init  .
    
        Args:
        email: TODO.
        password: TODO.
        object_id: TODO.
        modules: TODO.
        keep_param_store: TODO.
        origin: TODO.
        referer: TODO.

        Returns:
        TODO.
        """
        self.email = email
        self.password = password
        self.object_id = object_id
        self.modules = sorted(set(modules))
        self.origin = origin
        self.referer = referer

        self.api: BragerOneApiClient | None = None
        self.ws: RealtimeManager | None = None
        #self.param_store: ParamStore | None = ParamStore() if keep_param_store else None
        #self.state_store: StateStore = StateStore()
        self.bus = EventBus()

        self._tasks: set[Task[Any]] = set()
        self._prime_done = Event()
        self._prime_seq: int | None = None
        self._first_snapshot = Event()   # <- sygnał, że dostaliśmy pierwszy snapshot

        # callbacks
        self._on_parameters_change: list[ParametersCb] = []
        self._on_snapshot: list[SnapshotCb] = []
        self._on_any: list[GenericCb] = []

        # sterowanie cyklem życia
        self._started = False
        self._stop_ev = Event()

    # ---------- Rejestracja callbacków ----------
    def on_parameters_change(self, cb: ParametersCb) -> None:
        """On parameters change.
    
        Args:
        cb: TODO.

        Returns:
        TODO.
        """
        self._on_parameters_change.append(cb)

    def on_snapshot(self, cb: SnapshotCb) -> None:
        """On snapshot.
    
        Args:
        cb: TODO.

        Returns:
        TODO.
        """
        self._on_snapshot.append(cb)

    def on_any(self, cb: GenericCb) -> None:
        """On any.
    
        Args:
        cb: TODO.

        Returns:
        TODO.
        """
        self._on_any.append(cb)

    # ---------- Lifecycle ----------
    async def start(self) -> None:
        """Uruchom przepływ: login → ws → connect → listen → prime."""
        if self._started:
            return
        self._started = True
        self._stop_ev.clear()

        # REST
        self.api = BragerOneApiClient()
        await self.api.ensure_session()
        await self._login()

        # WS
        self.ws = RealtimeManager(token=self.api.token or "", origin=self.origin, referer=self.referer)
        self.ws.on_event(self._ws_dispatch)
        await self.ws.connect()

        # Linkuj sesję WS do modułów (POST /modules/connect)
        sid_ns = self.ws.sid()
        sid_engine = self.ws.engine_sid()
        if not sid_ns:
            raise RuntimeError("Brak namespace SID po połączeniu z WS.")
        ok = await self.api.modules_connect(sid_ns, self.modules, group_id=self.object_id, engine_sid=sid_engine)
        LOG.info("modules.connect: %s (ns_sid=%s, engine_sid=%s)", ok, sid_ns, sid_engine)

        # Subskrypcja i prime
        self.ws.set_group(self.object_id)
        await self.ws.subscribe(self.modules)
        okp, oka = await self._prime_with_retry()

        LOG.debug("prime injected: parameters=%s activity=%s", okp, oka)
        LOG.info("Gateway started: object_id=%s, modules=%s", self.object_id, ",".join(self.modules))

    async def stop(self) -> None:
        """Zatrzymaj: ws disconnect + revoke + zamknij sesję HTTP."""
        self._stop_ev.set()
        try:
            if self.ws:
                await self.ws.disconnect()
        finally:
            if self.api:
                try:
                    await self.api.revoke()
                except Exception:
                    pass
                await self.api.close()
        self._started = False

        await self._cancel_all_tasks()
        LOG.info("Gateway stopped")

    async def __aenter__(self):
        """Aenter  .
    
        Returns:
        TODO.
        """
        await self.start()
        return self

    async def __aexit__(self, *exc):
        """Aexit  .
    
        Args:
        exc: TODO.

        Returns:
        TODO.
        """
        await self.stop()

    # ---------- Operacje ----------
    async def refresh_login(self) -> None:
        """Wymuś ponowne logowanie, np. przy 401 z REST."""
        await self._login()

    async def resubscribe(self) -> None:
        """Wywołaj po reconnect WS (lub ręcznie): ponowne connect + listen + prime."""
        if not (self.api and self.ws):
            return
        sid_ns = self.ws.sid()
        sid_engine = self.ws.engine_sid()
        if not sid_ns:
            return
        ok = await self.api.modules_connect(sid_ns, self.modules, group_id=self.object_id, engine_sid=sid_engine)
        LOG.info("modules.connect (resub): %s", ok)
        await self.ws.subscribe(self.modules)
        okp, oka = await self._prime_with_retry()
        LOG.debug("prime after resubscribe: parameters=%s activity=%s", okp, oka)
        LOG.info("Resubscribed & primed")

    async def ingest_prime_parameters(self, data: dict) -> None:
        """Traktuj odpowiedź z /modules/parameters jak 'snapshot':
        spłaszcz do ParamUpdate i wypchnij na EventBus.
        """
        pairs = self.flatten_parameters(data)
        async def _pub_all():
            """Pub all.
    
            Returns:
            TODO.
            """
            for p in pairs:
                await self.bus.publish(p)
        await _pub_all()

    async def ingest_activity_quantity(self, data: dict | None) -> None:
        """Opcjonalnie: zaloguj / wyemituj ilości aktywności (jeśli chcesz mieć osobny strumień)."""
        # przykładowo nie publikujemy nic na bus teraz; tylko log:
        import logging
        LOG = logging.getLogger("pybragerone.gateway")
        if isinstance(data, dict):
            LOG.debug("activityQuantity: %s", data.get("activityQuantity"))

    # ---------- Wewnętrzne ----------
    async def _login(self) -> None:
        """Login.
    
        Returns:
        TODO.
        """
        assert self.api is not None
        try:
            payload = await self.api.login(self.email, self.password)
            LOG.debug("login payload keys: %s", list(payload.keys()))
        except ApiError as e:
            LOG.error("Login failed: %s", e)
            raise

    async def _prime(self) -> tuple[bool, bool]:
        """Prime.
    
        Returns:
        TODO.
        """
        assert self.api is not None

        ok_params = False
        ok_act = False

        # Uruchom oba requesty równolegle
        async with TaskGroup() as tg:
            t_params = tg.create_task(
                self.api.modules_parameters_prime(self.modules, return_data=True),
                name="prime-parameters",
            )
            t_act = tg.create_task(
                self.api.modules_activity_quantity_prime(self.modules, return_data=True),
                name="prime-activity",
            )

        # Po wyjściu z TG obie odpowiedzi już są gotowe (albo poleci wyjątek z TG)
        st1, data1 = cast(tuple[int, Any | None], t_params.result())
        if st1 in (200, 204) and isinstance(data1, dict):
            await self.ingest_prime_parameters(data1)
            ok_params = True

        st2, data2 = cast(tuple[int, Any | None], t_act.result())
        if st2 in (200, 204):
            await self.ingest_activity_quantity(data2 if isinstance(data2, dict) else None)
            ok_act = True

        # Zaktualizuj wewnętrzne znaczniki po pełnym prime
        self._prime_seq = self.bus.last_seq()
        self._prime_done.set()

        return ok_params, ok_act

    async def _prime_with_retry(self, tries: int = 3) -> tuple[bool, bool]:
        """Prime with retry.
    
        Args:
        tries: TODO.

        Returns:
        TODO.
        """
        delay = 0.2
        for _i in range(tries):
            okp, oka = await self._prime()
            if okp:  # parameters są kluczowe
                return okp, oka
            await sleep(delay)
            delay = min(delay * 2.5, 1.5)
        return False, False

    # ---------- WS routing ----------
    async def _invoke_list(self, cbs: list[Callable], *args, **kwargs):
        """Invoke list.
    
        Args:
        cbs: TODO.
        args: TODO.
        kwargs: TODO.

        Returns:
        TODO.
        """
        for cb in list(cbs):
            try:
                res = cb(*args, **kwargs)
                if iscoroutine(res):
                    await res
            except Exception:
                LOG.exception("Callback error")

    def flatten_parameters(self, payload: dict) -> list[ParamUpdate]:
        """Flatten parameters.
    
        Args:
        payload: TODO.

        Returns:
        TODO.
        """
        out: list[ParamUpdate] = []
        for devid, pools in payload.items():
            if not isinstance(pools, dict): continue
            for pool, entries in pools.items():
                if not isinstance(entries, dict): continue
                for chan_idx, body in entries.items():
                    if not isinstance(chan_idx, str) or len(chan_idx) < 2: continue
                    chan = chan_idx[0]
                    try:
                        idx = int(chan_idx[1:])
                    except ValueError:
                        continue
                    val, meta = None, {}
                    if isinstance(body, dict):
                        if "value" in body:
                            val = body["value"]
                        # resztę potraktuj jako meta (storable, timestamps, average…)
                        meta = {k: v for k, v in body.items() if k != "value"}
                    else:
                        # proste typy - potraktuj jako value
                        val = body
                    out.append(ParamUpdate(
                        devid=str(devid), pool=pool, chan=chan, idx=idx, value=val, meta=meta
                    ))
        return out

    def _ws_dispatch(self, event_name: str, data: Any) -> None:
        # 1) „Any” listeners – odpalamy bezpiecznie w tle
        """Ws dispatch.
    
        Args:
        event_name: TODO.
        data: TODO.

        Returns:
        TODO.
        """
        if self._on_any:
            self._spawn(
                self._invoke_list(self._on_any, event_name, data),
                name="gw-on-any",
            )

        # 2) Snapshot (pełny zrzut) → publikujemy WSZYSTKIE pary + callback snapshot
        if event_name == "snapshot" and isinstance(data, dict):
            # materializuj listę zanim ruszy async (unikasz „zjedzenia” generatora)
            pairs = list(self.flatten_parameters(data))

            async def _pub_all() -> None:
                """Pub all.
    
                Returns:
                TODO.
                """
                for upd in pairs:
                    # zakładam, że flatten_parameters zwraca już ParamUpdate
                    # jeśli zwraca tuple, zbuduj tu ParamUpdate(devid=..., pool=..., ...)
                    await self.bus.publish(upd)

            self._spawn(_pub_all(), name="gw-publish-snapshot")

            if self._on_snapshot:
                self._spawn(
                    self._invoke_list(self._on_snapshot, data),
                    name="gw-on-snapshot",
                )

            self._first_snapshot.set()
            return

        # 3) Inkrementalne zmiany parametrów
        if event_name.endswith("parameters:change") and isinstance(data, dict):
            pairs = list(self.flatten_parameters(data))

            async def _pub_all() -> None:
                """Pub all.
    
                Returns:
                TODO.
                """
                for upd in pairs:
                    await self.bus.publish(upd)

            self._spawn(_pub_all(), name="gw-publish-param-change")

            # surowe callbacki – kompatybilność
            if self._on_parameters_change:
                self._spawn(
                    self._invoke_list(self._on_parameters_change, event_name, data),
                    name="gw-on-params-change",
                )
            return

    # ---------- tasks ----------
    def _spawn(self, coro: Coroutine[Any, Any, Any], *, name: str | None = None) -> Task[Any]:
        """Start a background task and keep a strong reference; log exceptions on completion."""
        task = create_task(coro, name=name)
        self._tasks.add(task)

        def _finalizer(t: Task[Any]) -> None:
            """Finalizer.
    
            Args:
            t: TODO.

            Returns:
            TODO.
            """
            try:
                _ = t.result()  # will raise if task failed
            except CancelledError:
                pass
            except Exception:
                LOG.exception("Background task failed: %s", t.get_name() or "<unnamed>")
            finally:
                self._tasks.discard(t)

        task.add_done_callback(_finalizer)
        return task


    async def _cancel_all_tasks(self) -> None:
        """Cancel and await all tracked background tasks."""
        if not self._tasks:
            return
        for t in list(self._tasks):
            t.cancel()
        await gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
