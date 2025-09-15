import os
import json
from llama_parser import llama_parse
from schema_utils import compile_schemas
import anthropic

# Initialize the Anthropic client with your API key
client = anthropic.Anthropic(api_key="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")

def generate_schema(form_path: str) -> dict:
    """
    Sub-Agent: Generates a schema for a given financial form using Claude 4 Sonnet.
    """
    try:
        # For a real implementation, you'd extract text from the PDF
        # Here, we'll use a placeholder string as input to the model.
        # In a production environment, you would use a library like PyPDF2 to extract text from the form.
        mock_form_content = f"This is a financial form for {os.path.basename(form_path)}. It requires a full name, a residential address, and a numerical value for the amount."

        # Define the system prompt and the user prompt for Sub-Agent
        system_prompt = """You are a Sub-Agent specialized in document analysis.

Your task:
1. Read the entire financial form provided.
2. Identify all the distinct headers/fields present in the form.
3. For each header, determine its meaning based on context.
4. Create a schema in the following exact format:

I want to extract these fields:
Header Name 1: Meaning of this header
Header Name 2: Meaning of this header
Header Name 3: Meaning of this header
Header Name 4: Meaning of this header
...

Rules:
- Do NOT include sample values from the form.
- If a header's meaning is unclear, infer the most logical interpretation.
- Only return the schema — no explanations, no extra text."""
        
        user_prompt = f"Analyze this financial form and create a schema:\n\n{mock_form_content}"

        # Call the Claude API to get a schema
        response = client.messages.create(
            model="claude-sonnet-4-20250514",  # Using Claude 4 Sonnet
            max_tokens=1000,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )

        # Get the raw text response from Claude
        ai_generated_schema = response.content[0].text
        
        # Add form name for identification
        schema_with_name = f"Form: {os.path.basename(form_path)}\n{ai_generated_schema}"
        
        return schema_with_name
    except Exception as e:
        print(f"Error generating schema for {form_path}: {e}")
        return f"Form: {os.path.basename(form_path)}\nI want to extract these fields:\nError: Unable to process form"

def process_forms(form_paths: list[str]) -> list[dict]:
    """
    Main Agent: Orchestrates the form processing workflow by managing multiple Sub-Agents.
    """
    try:
        # Main Agent system prompt
        main_agent_prompt = """You are the Main Agent. Your job is to manage multiple incoming financial forms and assign each form to a dedicated Sub-Agent for processing.

Steps to follow:
1. You will receive multiple financial forms as input.
2. For each form, create a Sub-Agent.
3. Pass the full content of one form to each Sub-Agent.
4. Wait for each Sub-Agent to return a schema of headers and their meanings.
5. Combine all schemas into a single response at the end.

Do not attempt to read or extract data yourself — delegate this task entirely to the Sub-Agents."""
        
        print(f"Main Agent: Processing {len(form_paths)} financial forms...")
        
        # Sub-agent schema generation
        schemas = [generate_schema(path) for path in form_paths]
        compiled_schema = compile_schemas(schemas)

        # Call LlamaParse to extract structured JSON
        parsed_data = llama_parse(form_paths, compiled_schema)
        
        print(f"Main Agent: Successfully processed {len(parsed_data)} forms with schemas")
        return parsed_data
        
    except Exception as e:
        print(f"Main Agent Error: {e}")
        return []