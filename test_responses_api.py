#!/usr/bin/env python3
"""
Quick test script for the OpenAI Responses API with Code Interpreter.
Run: python test_responses_api.py
"""

import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("Error: Set OPENAI_API_KEY environment variable")
    print("  export OPENAI_API_KEY='your-key-here'")
    exit(1)

from openai import OpenAI
client = OpenAI(api_key=api_key)

# Test query - doesn't require datasets
test_query = input("\nEnter a test query (or press Enter for default): ").strip()
if not test_query:
    test_query = "Write a simple Python function to calculate a fighter's win rate given wins and total fights, then test it with 15 wins out of 20 fights."

print(f"\n{'='*60}")
print(f"Query: {test_query}")
print(f"Model: gpt-5-mini")
print(f"{'='*60}")
print("\nProcessing...")

try:
    response = client.responses.create(
        model="gpt-5-mini",
        instructions="You are an MMA analyst assistant. Be concise and helpful.",
        input=[{"role": "user", "content": test_query}],
        tools=[{"type": "code_interpreter", "container": {"type": "auto"}}],
        max_output_tokens=1000
        # Note: temperature not supported by gpt-5-mini (reasoning model)
    )
    
    print(f"\nResponse ID: {response.id}")
    print(f"Status: {response.status}")
    print(f"\n{'='*60}")
    print("OUTPUT:")
    print(f"{'='*60}\n")
    
    for output_item in response.output:
        if output_item.type == "message":
            for content in output_item.content:
                if hasattr(content, 'text'):
                    print(content.text)
        elif output_item.type == "code_interpreter_call":
            print(f"\n[Code Executed]")
            print(f"```python\n{output_item.code}\n```")
            if output_item.outputs:
                for out in output_item.outputs:
                    if out.type == "logs":
                        print(f"\nOutput: {out.logs}")
                    elif out.type == "image":
                        print(f"\nImage URL: {out.url}")

    print(f"\n{'='*60}")
    if response.usage:
        print(f"Tokens - Input: {response.usage.input_tokens}, Output: {response.usage.output_tokens}")
    print("Test completed successfully!")
    
except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()
