"""
Local study index (encrypted SQLCipher MVP).

Public entry: :class:`LocalStudyIndexService`.
"""

from core.study_index.index_service import LocalStudyIndexService
from core.study_index.port import StudyIndexPort

__all__ = ["LocalStudyIndexService", "StudyIndexPort"]
