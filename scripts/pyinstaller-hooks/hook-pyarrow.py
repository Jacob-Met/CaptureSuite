# SPDX-License-Identifier: GPL-3.0-only
"""Keep local Arrow/Parquet support without unused remote service transports."""
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

# The standalone CLI accepts local session packages. Arrow filesystem imports
# these optional transports under ImportError guards; none is a CLI feature.
excludedimports = [
    "pyarrow.flight", "pyarrow._flight", "pyarrow.libarrow_python_flight", "pyarrow._s3fs",
    "pyarrow._gcsfs", "pyarrow._azurefs", "pyarrow._hdfs",
]
hiddenimports = collect_submodules(
    "pyarrow", filter=lambda name: "tests" not in name
    and not any(name == item or name.startswith(item + ".") for item in excludedimports)
)
def local_only(item):
    return not any(part in Path(item[0]).name for part in
                   ("arrow_flight", "arrow_python_flight", "arrow_s3", "arrow_gcs", "arrow_azure"))

# Versioned native libraries can also be classified as data by PyInstaller.
datas = [item for item in collect_data_files("pyarrow") if local_only(item)]
binaries = [item for item in collect_dynamic_libs("pyarrow") if local_only(item)]
