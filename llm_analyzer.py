# llm_analyzer.py (updated without transformers)
import os
import requests
import json

HUGGINGFACE_API = "https://api-inference.huggingface.co/models/codellama/CodeLlama-7b-Instruct-hf"

def analyze_with_llm(content):
    headers = {
        "Authorization": f"Bearer {os.getenv('HUGGINGFACE_TOKEN')}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""
    [INST] <<SYS>>
    You are a Java code reviewer. Identify only these violations:
    1. Replace loops with streams (Rule G2)
    2. Unnecessary interfaces (Rule G9)
    Output JSON: [{{"rule": "G2|G9", "line": number, "description": str, "suggestion": str}}]
    <</SYS>>
    Code:
    {content[:1500]}  # Only first 1500 chars
    [/INST]
    """
    
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 300,
            "return_full_text": False
        }
    }
    
    try:
        response = requests.post(HUGGINGFACE_API, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        
        # Handle Hugging Face API response format
        if isinstance(result, list) and len(result) > 0:
            return result[0].get('generated_text', [])
        return []
    except Exception as e:
        print(f"LLM API error: {e}")
        return []

def parse_llm_output(text):
    try:
        # Find JSON in response
        start = text.find('[')
        end = text.rfind(']') + 1
        return json.loads(text[start:end])
    except:
        return []