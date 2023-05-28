import os
import json
import openai
import time
import re
from pathlib import Path

# Load configuration files
with open("validator_config.json", "r") as f:
    config = json.load(f)

# Extract variables from config
app_name = config["app_name"]
api_key = config["api_key"]
gpt_model_name = config.get("gpt_model_name", "gpt-4")
gpt3_model_name = config.get("gpt3_model_name", "gpt-3.5-turbo")
tokens_limit = config.get("tokens_limit", 4096)
temperature = config.get("temperature", 0.8)

# Set API key for OpenAI
openai.api_key = api_key

# Map of file paths to their contents
file_map = {}

def remove_triple_backticks(text):
    return re.sub(r'```(.*?)```(\r\n|\n)?', r'\1', text, flags=re.DOTALL).replace('\r\n', '\n').strip('\n')

def api_call_with_retry(model, messages, max_tokens, temperature):
    for i in range(10):  # 10 retries
        try:
            response = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return remove_triple_backticks(response["choices"][0]["message"]["content"].strip())
        except Exception as e:
            print(f"API call failed: {e}. Retrying in {i} second/s...")
            time.sleep(i)  # wait for i seconds before retrying
    raise Exception("API call failed after 10 attempts")

def load_file_map(root_path):
    print("Loading files...")
    for file_path in Path(root_path).rglob('*'):
        if file_path.is_file():
            with open(file_path, 'r') as f:
                content = f.read()
            file_map[str(file_path)] = content
    print("Files loaded successfully.")

def summarise_code(file_path, code):
    print(f"Summarising code for file: {file_path}...")
    prompt = f"As an advanced code development AI, summarise the following code..."
    return api_call_with_retry(
        model=gpt3_model_name,
        messages=[{
            "role": "user",
            "content": prompt
        }],
        max_tokens=tokens_limit,
        temperature=temperature,
    )
    
def manage_files(summaries):
    print("Managing files...")
    prompt = f"As an advanced code development AI, determine if any files need to be created or deleted based on the following context:\n\nContext:\n{summaries}"
    actions = api_call_with_retry(
        model=gpt_model_name,
        messages=[{
            "role": "user",
            "content": prompt
        },{
            "role": "user",
            "content": "There are 3 allowed reply formats: 1 - 'Create: {Path/to/The/NewFileName.extension}', 2 - 'Delete: {path/to/the/fileNameToDelete.extension}', 3 - 'No change required'. Be conservative in your changes."
        },{
            "role": "user",
            "content": """Provide the entire list of corrections separated by a newline (using \n). Example correct format:
            Create: /Path/To/FileName.Extension
            Delete: /Path/To/OtherFileName.Extension
            Create: /Path/To/Another/FileName2.Extension
            Delete: /Path/To/FileName3.Extension.

            Only reply with "No change required", if no changes are required for any files. Very Important - Do not provide any descriptions, only the list.
            """
        }],
        max_tokens=tokens_limit,
        temperature=temperature,
    )
    for action in actions.split('\n'):
        if action.startswith('Create:'):
            filename = action.split(' ')[1]
            print(f"Creating file: {filename}")
            open(filename, 'w').close()
        elif action.startswith('Delete:'):
            filename = action.split(' ')[1]
            print(f"Deleting file: {filename}")
            os.remove(filename)
    print("File management complete.")

def fix_errors(file_path, content, context):
    print(f"Correcting errors for file: {file_path}...")
    prompt = f"As an advanced code development AI, correct any errors present in the following code. Remove any references to non-existent code and generate any missing code as needed, given the context of the whole application:\n\nContext:\n{context}\n\nCode:\n{content}"
    response = api_call_with_retry(
        model=gpt_model_name,
        messages=[{
            "role": "user",
            "content": prompt
        },
        {
            "role": "user",
            "content": "Generate only the required, fully-formed, output code. Do not generate any other text. Do not provide any descriptions. Backticks, comments or file names above the code are not permitted."
        }],
        max_tokens=tokens_limit,
        temperature=temperature,
    )
    print(f"Errors in {file_path} have been corrected.")
    return response

def validate_and_fix(root_path):
    load_file_map(root_path)
    summaries = {file_path: summarise_code(file_path, content) for file_path, content in file_map.items()}
    manage_files("\n\n".join([f"File: {fp}\nSummary:\n{s}" for fp, s in summaries.items()]))
    for file_path, content in file_map.items():
        context = "\n\n".join([f"File: {fp}\nSummary:\n{s}" for fp, s in summaries.items() if fp != file_path])
        fixed_content = fix_errors(file_path, content, context)
        with open(file_path, 'w') as f:
            f.write(fixed_content)
        # Updating the file summary after fixing the file
        summaries[file_path] = summarise_code(file_path, fixed_content)
        print(f"Validated and fixed file: {file_path}")

root_path = os.path.join(os.getcwd(), app_name)
validate_and_fix(root_path)

print("Validation and corrections complete.")