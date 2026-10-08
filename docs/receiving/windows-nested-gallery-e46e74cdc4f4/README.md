# Windows nested-gallery test receiving

[Independent receiving](INDEPENDENT_RECEIVING.md) records the exact source, failed hosted baseline, actual Windows assertion runs, negative controls and remaining hosted gate.

## Reproduce the filesystem witness

On Windows with Python 3.11 or later, copy the complete native directory to a new disposable receiving workspace and run:

~~~powershell
py -3.11 receive_windows_links.py
~~~

The receiver uses the accompanying source-payload.json to reconstruct and hash both exact source versions, then executes their affected assertion statements against real links. It creates a new timestamped directory for each run. This is a filesystem assertion witness; it does not import Qt or invoke the gallery, and it cannot replace the required proposed-head Python 3.12 platform suite.

Original raw evidence remains unchanged. The raw hosted log is explicitly marked non-text for Git so its original CRLF content is retained.
