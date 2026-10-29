"""
File input handler — save uploaded file to temp and return path.
"""

import os
import tempfile

TMP_DIR = tempfile.gettempdir()


def save_upload(uploaded_file) -> tuple[str, str]:
    """Save a Flask FileStorage to a temp file.

    Returns (tmp_path, original_basename_without_ext).
    """
    suffix = os.path.splitext(uploaded_file.filename)[1] or ".wav"
    tmp_path = os.path.join(TMP_DIR, f"upload{suffix}")
    uploaded_file.save(tmp_path)
    basename = os.path.splitext(uploaded_file.filename)[0]
    return tmp_path, basename
