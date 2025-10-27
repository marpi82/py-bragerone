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
      status = param_store.get("P5.s40")  # e.g., 0b00001010 = 10

      # Check individual bits
      bit_0 = bool(status & (1 << 0))  # False (pump off)
      bit_1 = bool(status & (1 << 1))  # True (heater on)
      bit_3 = bool(status & (1 << 3))  # True (alarm active)

Writing Parameters
------------------

Number Values
~~~~~~~~~~~~~

.. code-block:: python

   # Write a new value
   await api_client.set_parameter(
       device_id=device_id,
       pool="P4",
       chan="v",
       idx=1,
       value=22.5
   )

Status Bits
~~~~~~~~~~~

.. code-block:: python

   # Read-modify-write pattern for bits
   current = param_store.get("P5.s40")

   # Set bit 3 to True
   new_value = current | (1 << 3)

   # Set bit 3 to False
   new_value = current & ~(1 << 3)

   # Write back
   await api_client.set_parameter(
       device_id=device_id,
       pool="P5",
       chan="s",
       idx=40,
       value=new_value
   )
