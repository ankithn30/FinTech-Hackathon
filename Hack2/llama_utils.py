import os
import json
from pydantic import BaseModel, Field
from llama_cloud_services import LlamaExtract
from dotenv import load_dotenv

load_dotenv()

class ContactInfo(BaseModel):
    name: str = Field(description="Full name of person")
    phone_number: str = Field(description="Phone number")
    address: str = Field(description="Full address or location")
    email: str = Field(description="Email address")

def get_extractor():
    if not os.getenv("LLAMA_CLOUD_API_KEY"):
        raise ValueError("LLAMA_CLOUD_API_KEY environment variable not set")
    return LlamaExtract()

def create_dynamic_schema(schema_data):
    fields = {}
    for field_name, field_info in schema_data.items():
        field_type = str if field_info.get('type') == 'string' else list[str] if field_info.get('type') == 'list' else str
        description = field_info.get('description', '')
        fields[field_name] = (field_type, Field(description=description))
    DynamicSchema = type('DynamicSchema', (BaseModel,), fields)
    return DynamicSchema
