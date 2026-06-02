from __future__ import annotations

import json
import os
from urllib import request


MODEL = os.getenv("SGLANG_MODEL", "Qwen/Qwen2.5-0.5B-Instruct")
BASE_URL = os.getenv("SGLANG_BASE_URL", "http://127.0.0.1:30000/v1")


def chat(prompt: str) -> str:
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 128,
        "temperature": 0.2,
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{BASE_URL}/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=60) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


if __name__ == "__main__":
    print(chat(
        "Reply with exactly one short sentence about JSON recognizers, "
        "and include this equation form in the sentence: tokens = scan(json)."
    ))
