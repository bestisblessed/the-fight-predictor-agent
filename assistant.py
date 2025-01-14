import openai
import time
import requests
import os

openai.api_key = os.getenv("OPENAI_API_KEY")
assistant_mma_handicapper = 'asst_zahT75OFBs5jgi346C9vuzKa'

if not openai.api_key:
    print("API key is required to run the chatbot.")
    exit()

print("MMA AI Chatbot initialized. Type 'exit' to quit.")

client = openai.OpenAI(api_key=openai.api_key)
thread_id = None

while True:
    user_question = input("You: ")
    if user_question.lower() == 'exit':
        print("Exiting chatbot. Goodbye!")
        break

    if thread_id is None:
        thread = client.beta.threads.create()
        thread_id = thread.id
        print(f"New conversation started with Thread ID: {thread_id}")

    message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=user_question
    )

    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_mma_handicapper
    )

    print("Processing...")
    while run.status != "completed":
        time.sleep(2)
        run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)

    messages = client.beta.threads.messages.list(thread_id=thread_id)
    for message in reversed(messages.data):
        if hasattr(message.content[0], 'text'):
            print(f"AI: {message.content[0].text.value}")
        elif hasattr(message.content[0], 'image_file'):
            print("AI: [Image file received]")
            file_id = message.content[0].image_file.file_id
            file_url = f"https://api.openai.com/v1/files/{file_id}/content"
            headers = {"Authorization": f"Bearer {openai.api_key}"}

            print("Downloading image...")
            image_data = requests.get(file_url, headers=headers)

            if image_data.status_code == 200:
                filename = f"data/assistant_image_{int(time.time())}.png"
                with open(filename, "wb") as f:
                    f.write(image_data.content)
                print(f"Image saved as {filename}")
            else:
                print("Failed to download the image.")
        else:
            print("AI: [Unsupported content type]")
