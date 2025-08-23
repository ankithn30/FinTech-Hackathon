
# Commented out IPython magic to ensure Python compatibility.
# %pip install -Uq llama-cloud-services

import os
from getpass import getpass

if not os.getenv("LLAMA_CLOUD_API_KEY"):
  os.environ['LLAMA_CLOUD_API_KEY'] = getpass("Add your LlamaCloud API Key: ")

"""## Create an Extractor Agent"""

from llama_cloud_services import LlamaExtract
from pydantic import BaseModel, Field

# Initialize client
extractor = LlamaExtract()

# Define schema using Pydantic
class Resume(BaseModel):
    name: str = Field(description="Full name of candidate")
    email: str = Field(description="Email address")
    phone_number: str = Field(description="candidates phone number")
    location: str = Field(description="Location of candidate")



# Create extraction agent
agent = extractor.create_agent(name="xyzzz-parser", data_schema=Resume)

# Extract data from document
result = agent.extract("/content/Personal.pdf")

result.data

# """## Manage Agents"""

# from llama_cloud_services import LlamaExtract

# # Initialize client
# extractor = LlamaExtract()

# # List all agents
# agents = extractor.list_agents()

# print(agents)

# # Get specific agent
# agent = extractor.get_agent(id="ccabaf82-53a5-4c98-a9af-67ffc9fa042f") # or id as param

# # Delete agent
# extractor.delete_agent(agent.id)

# """## Batch Extraction"""

# agent = extractor.get_agent(name="resume-parser")

# # Queue multiple files for extraction
# jobs = await agent.queue_extraction(["data/resume1.pdf", "data/resume2.pdf"])

# # Check job status
# for job in jobs:
#     status = agent.get_extraction_job(job.id).status
#     print(f"Job {job.id}: {status}")

# # Get results when complete
# results = [agent.get_extraction_run_for_job(job.id) for job in jobs]

# for result in results:
#     print(result.data)

# """## Updating Schemas"""

# from pydantic import BaseModel, Field

# agent = extractor.get_agent(name="resume-parser")

# # Define schema using Pydantic
# class Resume(BaseModel):
#     name: str = Field(description="Full name of candidate")
#     email: str = Field(description="Email address")
#     skills: list[str] = Field(description="Technical skills and technologies")
#     location: str = Field(description="Location of candidate")
#     education: str = Field(description="Education of candidate")

# # Update schema
# agent.data_schema = Resume

# # Save changes
# agent.save()

# result = agent.extract("data/resume2.pdf")

# result.data

# """## Error Handling && Custom Config"""

# from llama_cloud_services import LlamaExtract
# from llama_cloud.core.api_error import ApiError
# from llama_cloud import ExtractConfig


# extract = LlamaExtract(
#     project_id="36f21170-06b6-4170-8096-93008c0d5ea2",
#     organization_id="c187045b-1900-4b81-af35-5e8d3f05ed7a",
# )

# try:
#     agent = extract.get_agent(name="resume-parser")
#     if agent:
#         extract.delete_agent(agent_id=agent.id)

# except ApiError as e:
#     if e.status_code == 404:
#         pass
#     else:
#         raise


# # extract one object per page
# extract_config = ExtractConfig(
#     extraction_mode="FAST", # FAST, BALANCED, MULTIMODAL, PREMIUM
#     system_prompt="this is an resume for the company 'ACME'",
#     extraction_target="PER_PAGE", # PER_DOC, PER_PAGE
#     use_reasoning=False,
#     cite_sources=False
# )

# agent = extract.create_agent(name="resume-parser", data_schema=Resume, config=extract_config)

# result = agent.extract("data/merged.pdf")

# from pprint import pprint

# pprint(result.data)

