from transformers import pipeline

# Initialize LLM pipeline
llm_pipeline = pipeline(
    "text-generation",
    model="codellama/CodeLlama-7b-Instruct-hf",
    device_map="auto",
    torch_dtype="auto"
)

def analyze_with_llm(content):
    violations = []
    
    # G2: Stream conversion opportunities
    prompt = f"""
    [INST] <<SYS>>
    Identify Java loops that can be replaced with streams.
    Output JSON: [{{"rule": "G2", "line": number, "description": str, "suggestion": str}}]
    <</SYS>>
    Code:
    {content[:3000]}
    [/INST]
    """
    
    response = llm_pipeline(prompt, max_new_tokens=500)[0]['generated_text']
    violations.extend(parse_llm_response(response))
    
    return violations

def parse_llm_response(text):
    try:
        # Extract JSON from response
        json_str = text.split('[/INST]')[-1].strip()
        return json.loads(json_str)
    except:
        return []