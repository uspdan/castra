"""bluerange-spec — challenge manifest schema (v1).

Public surface used by the platform. Import paths under
``bluerange_spec.<submodule>`` are also stable; this module re-exports
the most common types.
"""

from .artifact import Artifact
from .author import Author
from .canonical import canonical_json, manifest_sha256, sha256_file
from .container import Container
from .flag import (
    AttackChainFlag,
    ChainOfCustodyFlag,
    CloudMisconfigFinding,
    CloudMisconfigFlag,
    ExactFlag,
    Flag,
    FlagType,
    LlmSignalFlag,
    MultiPartFlag,
    RegexFlag,
    SigmaRuleFlag,
    YaraRuleFlag,
)
from .hint import Hint
from .load import (
    LoadError,
    ManifestNotFound,
    ManifestParseError,
    ManifestValidationError,
    load_manifest,
    load_manifest_text,
)
from .manifest import ChallengeManifest, SPEC_VERSION
from .tests import TestCase, TestExpected
from .validators import (
    ValidationContext,
    ValidationResult,
    Validator,
    ValidatorConfigError,
    ValidatorError,
    ValidatorTimeoutError,
)

__all__ = [
    "Artifact",
    "AttackChainFlag",
    "Author",
    "ChainOfCustodyFlag",
    "ChallengeManifest",
    "CloudMisconfigFinding",
    "CloudMisconfigFlag",
    "Container",
    "ExactFlag",
    "Flag",
    "FlagType",
    "Hint",
    "LlmSignalFlag",
    "LoadError",
    "ManifestNotFound",
    "ManifestParseError",
    "ManifestValidationError",
    "MultiPartFlag",
    "RegexFlag",
    "SigmaRuleFlag",
    "SPEC_VERSION",
    "TestCase",
    "TestExpected",
    "ValidationContext",
    "ValidationResult",
    "Validator",
    "ValidatorConfigError",
    "ValidatorError",
    "ValidatorTimeoutError",
    "YaraRuleFlag",
    "canonical_json",
    "load_manifest",
    "load_manifest_text",
    "manifest_sha256",
    "sha256_file",
]
