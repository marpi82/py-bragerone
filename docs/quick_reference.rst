Quick Reference
===============

A quick reference guide for common patterns and usage in pybragerone.

.. seealso::
   - :doc:`getting_started` - Installation and basic setup
   - :doc:`architecture_guide` - Deep dive into architecture
   - :doc:`api_reference` - Complete API documentation

Essential Concepts
------------------

.. important::
   **Always fetch initial data via REST API** when starting up or after reconnecting WebSocket.
   WebSocket only sends updates, never the full state!

.. tip::
   **Two modes for ParamStore:**

   - **Lightweight mode** (runtime): Simple key→value storage, fast and minimal overhead
   - **Asset-aware mode** (setup): Rich metadata with labels, units, and translations

Key Workflows
-------------

.. note::
   **For Home Assistant integration:**

   1. **Setup phase** (config flow): Use asset-aware mode to discover entities
   2. **Runtime phase**: Switch to lightweight mode for performance
   3. **After reconnect**: Always re-fetch data from REST API

Detailed Guides
---------------

.. toctree::
   :maxdepth: 2

   core_components
   paramstore_usage
   ha_integration
   parameter_format
   best_practices
