"""Model profiles — auto-detected configuration per model family."""

PROFILES = {
    "qwen": {
        "stop": ["<|im_end|>"],
        "text_tool_fix": True,
        "temp_default": 0.15,
    },
    "llama": {
        "stop": ["<|eot_id|>"],
        "text_tool_fix": False,
        "temp_default": 0.2,
    },
    "mistral": {
        "stop": ["</s>"],
        "text_tool_fix": False,
        "temp_default": 0.15,
    },
    "phi": {
        "stop": ["<|end|>"],
        "text_tool_fix": True,
        "temp_default": 0.1,
    },
    "gemma": {
        "stop": ["<end_of_turn>"],
        "text_tool_fix": False,
        "temp_default": 0.15,
    },
    "deepseek": {
        "stop": ["<|end▁of▁sentence|>"],
        "text_tool_fix": False,
        "temp_default": 0.15,
    },
}

_DEFAULT_PROFILE = {
    "stop": ["<|im_end|>"],
    "text_tool_fix": True,
    "temp_default": 0.15,
}


def detect_profile(model_name: str) -> dict:
    """Auto-detect model profile from model name."""
    lower = model_name.lower()
    for key, profile in PROFILES.items():
        if key in lower:
            return profile
    return _DEFAULT_PROFILE
