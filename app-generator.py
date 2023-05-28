import os
import json
from pathlib import Path
import openai
import re
import time
from progress.bar import Bar

# Load configuration files
with open("config.json", "r") as f:
    config = json.load(f)

# Load frontend and backend file lists
with open("frontend_files.txt", "r") as f:
    frontend_files = [line.strip() for line in f.readlines()]

with open("backend_files.txt", "r") as f:
    backend_files = [line.strip() for line in f.readlines()]

print("Load variables")

# Extract variables from config
app_name = config["app_name"]
app_description = config["app_description"]
api_key = config["api_key"]
gpt_model_name = config.get("gpt_model_name", "gpt-4")
tokens_limit = config.get("tokens_limit", 4096)
temperature = config.get("temperature", 0.8)
frontend_platform = config.get("frontend_platform", "React")
backend_platform = config.get("backend_platform", "Node.js")
save_prompt_logs = config.get("save_prompt_logs", False)
prompt_logs_path = config.get("prompt_logs_path", "logs.txt")

# Set API key for OpenAI
openai.api_key = api_key

print("Create folder structure")

# Create folder structure
base_dirs = [app_name]
for file_path in frontend_files:
    dir_path = os.path.dirname(file_path)
    if dir_path:
        base_dirs.append(os.path.join(app_name, 'frontend', dir_path))
for file_path in backend_files:
    dir_path = os.path.dirname(file_path)
    if dir_path:
        base_dirs.append(os.path.join(app_name, 'backend', dir_path))
for d in set(base_dirs):
    os.makedirs(d, exist_ok=True)

# Create progress bar
total_files = len(frontend_files) + len(backend_files)
bar = Bar("Generating App", max=total_files)

def remove_triple_backticks(text):
    return re.sub(r'```(.*?)```(\r\n|\n)?', r'\1', text, flags=re.DOTALL).replace('\r\n', '\n').strip('\n')

# Function to log prompts to file
def log_prompt(prompt_logs_path, prompt_messages):
    with open(prompt_logs_path, "a") as log_file:
        current_time = time.strftime("%H:%M:%S", time.localtime())
        log_file.write(("\n\n" + current_time + " - ").join(prompt_messages) + "\n")

# Function to call GPT
def call_gpt(prompt, model_name, tokens_limit, platform_type, last_files, frontend_platform, backend_platform, app_name, app_description, temperature):
    try:
        platform = frontend_platform if platform_type == "frontend" else backend_platform
        prompt_tokens = len(prompt.split())
        if prompt_tokens > tokens_limit:
            raise ValueError(f"The prompt has {prompt_tokens} tokens, which exceed the token limit of {tokens_limit}.")
        
        last_files_context = "\n".join([f"File: {f[0]}\nContent:\n{f[1]}" for f in last_files])

        prompt_messages = [ {
                "role": "user",
                "content": f"""As an expert in modern web application development, your task is to generate plaintext code. The requirements are as follows:
                                - Create one component or file per output. Very important, generate only one file per output.
                                - Do not combine components or files.
                                - Do not come up with any new files, or references to any files (such as a component or non-library class), that are not within the provided file structure. Only files within the provided file structure are permitted.
                                - There is no need for explanations, just code. Do not provide explanations.
                                - Provide the plaintext file contents only.
                                - Be creative and thorough if an exact response is not known.
                                - All imports must reference code that exists within the provided file structure.
                                The application context is as follows:
                                - Platform: {platform}
                                - App name: {app_name}
                                - App description: {app_description}"""
            },
            {"role": "user", "content": prompt}]

        if len(last_files) > 1 and len(last_files[1][1]) > 1:  # Ensure that there are at least two files
            prompt_messages.append({
                "role": "user",
                "content": f"To provide some context for your current task, here are the previously generated files:\n{last_files_context}"
            })

        if save_prompt_logs:
            log_prompt(prompt_logs_path, [message["content"] for message in prompt_messages])

        response = openai.ChatCompletion.create(
            model=model_name,
            messages=prompt_messages,
            max_tokens=tokens_limit,
            temperature=temperature,
        )

        return response["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return str(e)

# Function to generate code and save it to a file
def generate_code(file_path, model_name, platform_type, last_files, tokens_limit, frontend_platform, backend_platform, app_name, app_description, temperature):
    file_structure = "\n".join(frontend_files) if platform_type == 'frontend' else "\n".join(backend_files)
    prompt = f"File: {os.path.basename(file_path)}, Purpose: {platform_type}, File structure: {file_structure}"
    output = call_gpt(prompt, model_name, tokens_limit, platform_type, last_files, frontend_platform, backend_platform, app_name, app_description, temperature)
    output = remove_triple_backticks(output)
    with open(file_path, "w") as f:
        f.write(output)
    time.sleep(0.01)
    return output

last_files = [("", ""), ("", "")]

frontend_files_with_path = [(os.path.join(app_name, 'frontend', file_path), "frontend") for file_path in frontend_files]
backend_files_with_path = [(os.path.join(app_name, 'backend', file_path), "backend") for file_path in backend_files]

print("\nGenerate frontend ...")

for file_path, platform_type in frontend_files_with_path:
    output = generate_code(file_path, gpt_model_name, platform_type, last_files, tokens_limit, frontend_platform, backend_platform, app_name, app_description, temperature)
    bar.next()
    print(f" - generated file {file_path}")
    if len(last_files) >= 3:  # Keep only the last three files
        last_files.pop(0)
    last_files.append((file_path, output))

print("\n\nGenerate backend ...")
if len(last_files) >= 3:
    last_files.pop(0)

for file_path, platform_type in backend_files_with_path:
    output = generate_code(file_path, gpt_model_name, platform_type, last_files, tokens_limit, frontend_platform, backend_platform, app_name, app_description, temperature)
    bar.next()
    print(f" - generated file {file_path}")
    if len(last_files) >= 3:  # Keep only the last three files
        last_files.pop(0)
    last_files.append((file_path, output))

bar.finish()

print("App generation complete!")