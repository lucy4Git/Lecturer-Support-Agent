from .contracts import *
from .integrity import CitationIntegrityGuard
from .prompt_builder import PromptBuilder
from .router import ModelRouter
from .source_discovery import CrossrefSourceDiscovery, OpenAlexSourceDiscovery, CompositeSourceDiscovery
from .task_classifier import TeachingTaskClassifier

__all__ = [
    "CitationIntegrityGuard",
    "PromptBuilder",
    "ModelRouter",
    "CrossrefSourceDiscovery",
    "OpenAlexSourceDiscovery",
    "CompositeSourceDiscovery",
    "TeachingTaskClassifier",
]
