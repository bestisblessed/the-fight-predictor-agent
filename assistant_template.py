import os, requests, openai, time
from dotenv import load_dotenv
from PIL import Image

load_dotenv()
client = openai.OpenAI()

# Upload datasets
file_ids = []
for path in ['data/fighter_info.csv', 'data/event_data_sherdog.csv']:
    if os.path.exists(path):
        f = client.files.create(file=open(path, 'rb'), purpose='assistants')
        file_ids.append(f.id)

query = input("Enter MMA question: ")

# Prepare request
params = {
    "model": "gpt-5-mini",
    "instructions": "You are The Fight Agent. Use the datasets for analysis.",
    "input": [{"role": "user", "content": query}],
    "max_output_tokens": 5000,
    "reasoning": {"effort": "medium"},
    "include": ["code_interpreter_call.outputs"]
}
if file_ids:
    params["tools"] = [{"type": "code_interpreter", "container": {"type": "auto", "file_ids": file_ids}}]

# Get and display response
resp = client.responses.create(**params)
for out in resp.output:
    if out.type == "message":
        for c in out.content:
            if hasattr(c, 'text'): 
                print(f"\nAI: {c.text}")
            elif hasattr(c, 'refusal'):
                print(f"\nAI Refusal: {c.refusal}")
    elif out.type == "code_interpreter_call":
        if hasattr(out, 'input'):
            print(f"\n[Code Interpreter]: Running analysis...")
        
        # Ensure outputs is iterable even if None
        outputs = getattr(out, 'outputs', []) or []
        for i, ci_out in enumerate(outputs):
            if ci_out.type == "logs":
                print(f"\n[Code Interpreter Logs]:\n{ci_out.logs}") 
            elif ci_out.type == "image":
                img_path = f"data/img_{int(time.time())}_{i}.png"
                os.makedirs('data', exist_ok=True)
                
                url = ci_out.url
                if url.startswith('data:'):
                    import base64
                    header, encoded = url.split(",", 1)
                    data = base64.b64decode(encoded)
                    with open(img_path, "wb") as f: f.write(data)
                else:
                    with open(img_path, "wb") as f: f.write(requests.get(url).content)
                
                print(f"[Image generated and saved to {img_path}]")
                Image.open(img_path).show()
