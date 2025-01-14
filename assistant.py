# from openai import OpenAI
# import os

# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# # 1. Configure your OpenAI API key

# # 2. Specify your assistant/model ID
# ASSISTANT_ID = "asst_zahT75OFBs5jgi346C9vuzKa"  # e.g. "ft:gpt-3.5-turbo:some-id"

# # A quick introduction
# print("Welcome to the Fight Analysis Assistant!")
# print("Ask questions about fights, fighters, or predictions.")
# print("Type 'exit' or 'quit' to leave.\n")

# # 3. Simple loop for user input
# while True:
#     user_input = input("You: ")

#     if user_input.lower() in ("exit", "quit"):
#         print("Assistant: Goodbye!")
#         break

#     try:
#         response = client.chat.completions.create(# response = openai.Chat.create(
#             model=ASSISTANT_ID,
#             messages=[{"role": "user", "content": user_input}],
#             temperature=0.7)
#         assistant_msg = response.choices[0].message.content
#         print("Assistant:", assistant_msg)

#     except Exception as e:
#         print("Error:", e)


from openai import OpenAI
import os
import time

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 2. Specify your assistant/model ID
ASSISTANT_ID = "asst_zahT75OFBs5jgi346C9vuzKa"  # Use the correct assistant ID

# A quick introduction
print("Welcome to the Fight Analysis Assistant!")
print("Ask questions about fights, fighters, or predictions.")
print("Type 'exit' or 'quit' to leave.\n")

def create_thread_and_run(user_input):
    # Create a new thread
    thread = client.beta.threads.create()
    
    # Submit a message and start a run
    client.beta.threads.messages.create(
        thread_id=thread.id, role="user", content=user_input
    )
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=ASSISTANT_ID,
    )
    return thread, run

def wait_on_run(run, thread):
    # Wait for the run to complete
    while run.status in ("queued", "in_progress"):
        run = client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id,
        )
        time.sleep(0.5)
    return run

def get_response(thread):
    # Get the list of messages in the thread
    messages = client.beta.threads.messages.list(thread_id=thread.id, order="asc")
    return messages

# 3. Simple loop for user input
while True:
    user_input = input("You: ")
    
    if user_input.lower() in ("exit", "quit"):
        print("Assistant: Goodbye!")
        break
    
    try:
        # Create a thread and run for the user input
        thread, run = create_thread_and_run(user_input)
        
        # Wait for the run to complete
        run = wait_on_run(run, thread)
        
        # Retrieve and print the response
        messages = get_response(thread)
        for message in messages:
            if message.role == "assistant":
                print("Assistant:", message.content[0].text.value)
    
    except Exception as e:
        print("Error:", e)