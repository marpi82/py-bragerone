Best Practices
==============

Logging & Debugging
-------------------

.. code-block:: python

   # Use single-line JSON for logs
   import json
   logger.debug(f"Event: {json.dumps(event.model_dump(), separators=(',', ':'))}")

   # Dump large payloads to files
   with open("param_store.json", "w") as f:
       json.dump(param_store.to_dict(), f, indent=2)

.. tip::
   **CLI debugging flags:**

   - ``--debug`` → Verbose logging
   - ``--raw-ws`` → Show raw WebSocket payloads
   - ``--dump-store`` → Save ParamStore to JSON

Error Handling
--------------

.. warning::
   **Never let EventBus consumers crash!**

   .. code-block:: python

      async def safe_consumer():
          async for event in event_bus.subscribe():
              try:
                  await process_event(event)
              except Exception as e:
                  logger.error(f"Event processing failed: {e}", exc_info=True)
                  # Continue processing other events

Performance Tips
----------------

- **Rate limiting:** Use ``asyncio.Semaphore`` for write operations
- **Retry logic:** Add exponential backoff for REST prime (200/500/800ms)
- **Lightweight mode:** Always use in production runtime
- **Batch updates:** Group entity updates to reduce overhead
