Parameter Format
================

Parameters use a structured addressing scheme:

Address Format
--------------

.. code-block:: text

   P<pool_number>.<channel><index>

   Examples:
   - P4.v1    → Pool 4, value channel, index 1
   - P5.s40   → Pool 5, status channel, index 40
   - P6.u13   → Pool 6, unit channel, index 13

Channels
--------

.. list-table::
   :header-rows: 1
   :widths: 10 20 70

   * - Channel
     - Name
     - Purpose
   * - ``v``
     - Value
     - Primary reading or setpoint
   * - ``s``
     - Status
     - Binary status bitmask (use bit extraction)
   * - ``u``
     - Unit
     - Unit code or enum index
   * - ``n``
     - Min
     - Minimum allowed value
   * - ``x``
     - Max
     - Maximum allowed value
   * - ``t``
     - Type
     - Data type identifier

Status Bits
-----------

.. tip::
   **Extracting status bits:**

   .. code-block:: python

      # P5.s40 holds a bitmask
      status_fam = param_store.get_family("P5", 40)
      status = status_fam.status_raw if status_fam else 0  # e.g., 0b00001010 = 10

      # Check individual bits
      bit_0 = bool(status & (1 << 0))  # False (pump off)
      bit_1 = bool(status & (1 << 1))  # True (heater on)
      bit_3 = bool(status & (1 << 3))  # True (alarm active)

Writing Parameters
------------------

Parameter write helpers are not part of the public API yet.

For now, treat this library as read-first (prime via REST + deltas via WebSocket) and use it primarily for state sync.
