from __future__ import annotations

import json
from typing import Any

from groq import Groq

SYSTEM = """You are the XAUUSD AI Signal Lab copilot.
You answer questions about the CURRENT app state and the app's RECORDED signal journal.
Use only the supplied context. Never invent prices, signals, timestamps, or outcomes.
Do not change Entry, SL, TP, or R:R. Do not claim a signal was missed unless the journal/context supports that conclusion.
When asked whether the user missed a signal, distinguish between:
1) recorded qualified signals in the journal,
2) recorded alerts that were sent,
3) conditions currently showing WAIT/WATCH/BUY/SELL,
4) signals that happened before this app had the necessary history/streaming data, which cannot be verified.
Be concise but useful. Give specific timestamps and numbers when present.
This is market analysis/research support, not a guarantee of future performance.
"""


def _prompt(question: str, context: dict[str, Any]) -> str:
    return (
        "Answer the user's question using this structured live context and recent journal.\n\n"
        f"USER QUESTION:\n{question}\n\n"
        "CONTEXT:\n"
        + json.dumps(context, indent=2, default=str)
    )


def answer(api_key: str, model: str, question: str, context: dict[str, Any]) -> str:
    if not api_key:
        raise ValueError("Groq API key is empty. Add it in the sidebar.")
    if not question.strip():
        raise ValueError("Enter a question first.")

    client = Groq(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0.15,
            max_completion_tokens=900,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": _prompt(question, context)},
            ],
        )
    except Exception as exc:
        raise RuntimeError(f"Groq chat request failed: {exc}") from exc

    return response.choices[0].message.content or "Groq returned an empty response."
