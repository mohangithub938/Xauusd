import json

SYSTEM="""You explain a structured XAUUSD signal created by deterministic Python rules.
Do not invent or modify prices. Do not change Entry, SL, TP or R:R.
Do not claim certainty or guaranteed profitability.
Return concise sections: Summary, Evidence, Risks, Invalidation.
This is research output, not financial advice."""

def build_prompt(snapshot):
    return "Analyze this structured XAUUSD signal. Numeric trade levels are fixed inputs.\\n"+json.dumps(snapshot,indent=2,default=str)

def list_models(api_key):
    from groq import Groq
    client=Groq(api_key=api_key)
    return [m.id for m in client.models.list().data]

def explain(api_key,model,snapshot):
    if not api_key: raise ValueError("Groq API key is empty.")
    from groq import Groq
    client=Groq(api_key=api_key)
    try:
        r=client.chat.completions.create(
            model=model,
            temperature=0.2,
            max_completion_tokens=700,
            messages=[
                {"role":"system","content":SYSTEM},
                {"role":"user","content":build_prompt(snapshot)},
            ],
        )
    except Exception as exc:
        raise RuntimeError(f"Groq request failed: {exc}") from exc
    return r.choices[0].message.content or "Groq returned an empty response."
