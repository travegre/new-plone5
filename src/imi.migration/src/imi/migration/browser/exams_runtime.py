# -*- coding: utf-8 -*-
"""Public Preiskave views independent of catalog/workflow state."""
from .legacy_sites import ExamsPublicView as BaseExamsPublicView
from .legacy_sites import ExamsListView as BaseExamsListView
from .runtime_fixes import ExamsMixin


class ExamsPublicView(ExamsMixin, BaseExamsPublicView):
    pass


class ExamsListView(ExamsMixin, BaseExamsListView):
    pass
