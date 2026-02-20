"""
Local LLM inference for JD extraction (degree 0-3, domain 1-14).
Model can be switched via env JD_EXTRACT_MODEL. Smaller = faster, may trade quality.
"""

import os

# Optional: reduce logging from transformers
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

# Smaller = faster. Set env JD_EXTRACT_MODEL to switch (e.g. HuggingFaceTB/SmolLM-135M-Instruct for ~0.14B).
_DEFAULT_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"  # 0.5B; or "HuggingFaceTB/SmolLM-135M-Instruct" for 135M
_MODEL_ID = os.environ.get("JD_EXTRACT_MODEL", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL
_tokenizer = None
_model = None


def _get_model_and_tokenizer():
    global _tokenizer, _model
    if _model is not None:
        return _tokenizer, _model
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    # Use GPU when CUDA is available unless QWEN_USE_GPU=0. PyTorch nightly cu128 supports sm_120 (Blackwell).
    use_gpu = os.environ.get("QWEN_USE_GPU", "1").lower() not in ("0", "false", "no") and torch.cuda.is_available()
    if use_gpu:
        device = "cuda"
        try:
            print(f"[Qwen] Using GPU: {torch.cuda.get_device_name(0)}")
        except Exception:
            pass
    else:
        device = "cpu"
        print("[Qwen] Using CPU.")

    _tokenizer = AutoTokenizer.from_pretrained(_MODEL_ID, trust_remote_code=True)
    _model = AutoModelForCausalLM.from_pretrained(
        _MODEL_ID,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16 if device == "cuda" else torch.float32,
        device_map="auto" if device == "cuda" else None,
    )
    if device == "cpu":
        _model = _model.to(device)
    _model.eval()
    return _tokenizer, _model


def generate(prompt: str, max_new_tokens: int = 1024) -> str:
    """
    Run the configured instruct model on a single user prompt; return the assistant reply.
    Works with Qwen2.5 and SmolLM (and any model that has apply_chat_template).
    """
    tokenizer, model = _get_model_and_tokenizer()
    messages = [{"role": "user", "content": prompt}]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    inputs = tokenizer(text, return_tensors="pt")
    import torch
    device = next(model.parameters()).device
    inputs = {k: v.to(device) for k, v in inputs.items()}
    input_len = inputs["input_ids"].shape[1]

    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id,
        )

    # Decode only the newly generated tokens (model-agnostic)
    new_tokens = out[0][input_len:]
    reply = tokenizer.decode(new_tokens, skip_special_tokens=True)
    return reply.strip()
