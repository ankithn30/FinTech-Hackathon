import os
import json
import pdfrw
from pydantic import BaseModel, Field
from llama_cloud_services import LlamaParse
from dotenv import load_dotenv
from typing import Dict, Any, Type

load_dotenv()

class UserInfo(BaseModel):
    name: str = Field(description="Full name of person")
    name_of_dependent: str = Field(description="Name of dependent")
    age_of_dependent: str = Field(description="Age of dependent")
    dropdown: str = Field(description="Dropdown selection")
    option_1: bool = Field(description="Option 1 selected")
    option_2: bool = Field(description="Option 2 selected")
    option_3: bool = Field(description="Option 3 selected")

class ContactInfo(BaseModel):
    """Schema for extracting contact information from text"""
    full_name: str = Field(description="Complete full name of the person")
    first_name: str = Field(description="First name only")
    last_name: str = Field(description="Last name only")
    street_address: str = Field(description="Street address including number and street name")
    city: str = Field(description="City name")
    state: str = Field(description="State or province")
    zip_code: str = Field(description="ZIP or postal code")
    phone_number: str = Field(description="Primary phone number")
    email: str = Field(description="Email address")
    company: str = Field(description="Company or organization name")
    job_title: str = Field(description="Job title or position")
    additional_info: str = Field(description="Any other relevant contact information")

def get_parser():
    if not os.getenv("LLAMA_CLOUD_API_KEY"):
        raise ValueError("LLAMA_CLOUD_API_KEY environment variable not set")
    return LlamaParse()

def extract_pdf_fields_and_values(pdf_path: str) -> Dict[str, Any]:
    """Extract field names and values from a filled PDF form"""
    try:
        pdf = pdfrw.PdfReader(pdf_path)
        if not (pdf.Root.AcroForm and pdf.Root.AcroForm.Fields):
            return {}
        
        field_data = {}
        for field in pdf.Root.AcroForm.Fields:
            name = field.T if hasattr(field, 'T') else None
            if not name:
                continue
                
            # Clean up field name - remove parentheses and normalize
            clean_name = str(name).strip('()')
            
            # Get field value and type
            value = field.V if hasattr(field, 'V') else None
            field_type = field.FT if hasattr(field, 'FT') else None
            
            # Process value based on field type
            if field_type == '/Btn':  # Button/checkbox
                field_data[clean_name] = str(value) == '/On' if value else False
            elif field_type in ['/Tx', '/Ch']:  # Text or Choice
                field_data[clean_name] = str(value).strip('()') if value else ""
            else:
                field_data[clean_name] = str(value).strip('()') if value else ""
                
        return field_data
    except Exception as e:
        print(f"Error extracting PDF fields: {e}")
        return {}

def create_dynamic_schema_from_pdf(pdf_path: str) -> Type[BaseModel]:
    """Create a dynamic Pydantic schema based on PDF form fields"""
    field_data = extract_pdf_fields_and_values(pdf_path)
    
    fields = {}
    for field_name, value in field_data.items():
        # Normalize field name for Python variable naming
        python_field_name = field_name.lower().replace(' ', '_').replace('\t', '_')
        
        # Determine field type based on value
        if isinstance(value, bool):
            field_type = bool
            description = f"Boolean field: {field_name}"
        elif isinstance(value, str) and value.isdigit():
            field_type = str  # Keep as string for form filling
            description = f"Numeric text field: {field_name}"
        else:
            field_type = str
            description = f"Text field: {field_name}"
        
        fields[python_field_name] = (field_type, Field(description=description))
    
    # Create dynamic schema class
    DynamicSchema = type('DynamicFormSchema', (BaseModel,), fields)
    return DynamicSchema

def create_dynamic_schema(schema_data):
    """Original function for manual schema creation"""
    fields = {}
    for field_name, field_info in schema_data.items():
        field_type = str if field_info.get('type') == 'string' else list[str] if field_info.get('type') == 'list' else str
        description = field_info.get('description', '')
        fields[field_name] = (field_type, Field(description=description))
    DynamicSchema = type('DynamicSchema', (BaseModel,), fields)
    return DynamicSchema

def extract_contact_info_from_text(text_content: str) -> Dict[str, Any]:
    """Extract contact information from large blocks of text using LlamaParse"""
    try:
        parser = get_parser()
        
        # Use LlamaParse with structured extraction for contact information
        extraction_result = parser.get_json_result(
            text_content,
            result_type="json",
            parsing_instruction="""
            Extract contact information from this text. Look for:
            - Full names (first and last names)
            - Street addresses (including apartment/suite numbers)
            - Cities, states, and ZIP codes
            - Phone numbers (any format)
            - Email addresses
            - Company names and job titles
            - Any other relevant contact details
            
            Return the information in a structured JSON format with clear field names.
            If information is not found, use empty strings for those fields.
            """
        )
        
        return extraction_result
    except Exception as e:
        print(f"Error extracting contact info from text: {e}")
        return {}

def extract_contact_info_from_pdf(pdf_path: str) -> Dict[str, Any]:
    """Extract contact information from PDF using LlamaParse text extraction"""
    try:
        parser = get_parser()
        
        # Parse PDF to extract text content
        documents = parser.load_data(pdf_path)
        
        if not documents:
            return {}
        
        # Combine all text content
        full_text = "\n".join([doc.text for doc in documents])
        
        # Extract contact information from the text
        contact_info = extract_contact_info_from_text(full_text)
        
        return contact_info
    except Exception as e:
        print(f"Error extracting contact info from PDF: {e}")
        return {}

def parse_pdf_with_dynamic_schema(pdf_path: str) -> Dict[str, Any]:
    """Parse a PDF using LlamaParse with a dynamically created schema based on the PDF's form fields"""
    try:
        # For filled PDFs, we extract the fields directly from the PDF form data
        # This preserves the actual field values and structure
        extracted_data = extract_pdf_fields_and_values(pdf_path)
        
        # If no form fields found, try text extraction for contact info
        if not extracted_data:
            print("No form fields found, attempting text extraction...")
            extracted_data = extract_contact_info_from_pdf(pdf_path)
        
        return extracted_data
    except Exception as e:
        print(f"Error parsing PDF with dynamic schema: {e}")
        return {}
