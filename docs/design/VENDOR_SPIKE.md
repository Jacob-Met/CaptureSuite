# Vendor Spike Checklist

Run the first time you get access to a vendor SDK — even briefly. Goal is to record semantics before writing a full worker.

## For each of Delsys / Xsens / Infineon / camera

Capture into `docs/design/adapters/<vendor>.md`:

1. Exact product / board / firmware / SDK version and license terms
2. How devices are discovered and what stable identity fields exist
3. Threading / callback model (who owns buffers, can you block?)
4. Timestamp format, units, clock domain, and drift behavior
5. Start / stop / arm semantics and first-sample latency
6. Disconnect / reconnect behavior and sequence numbering
7. Maximum sustained rate and payload sizes observed
8. Whether any "hardware sync" mode is real vs marketing

Do **not** integrate into CaptureSuite during the spike. A standalone console program that prints timestamped samples is enough.
