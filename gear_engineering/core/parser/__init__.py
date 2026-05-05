import warnings

warnings.warn(
    "The deterministic NLP parsers in core.parser are deprecated "
    "and will be removed in a future version. Please use the AI Planning Layer "
    "(core.llm_client) for component parameter extraction.",
    DeprecationWarning,
    stacklevel=2
)
