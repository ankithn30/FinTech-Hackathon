import os
import json
import logging
from typing import Dict, List, Any, Optional
from openai import OpenAI
import fitz  # PyMuPDF for PDF processing
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OpenAIExtractionAgent:
    """
    OpenAI-powered extraction agent that extracts structured data from documents
    and saves it to JSON files for the form-filling agent to use.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the extraction agent with OpenAI API key
        
        Args:
            api_key: OpenAI API key. If None, will try to get from environment variable
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable or pass api_key parameter.")
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4o-mini"  # Using cost-effective model for extraction
        
        # Create output directory for extracted data
        self.output_dir = "extracted_data"
        os.makedirs(self.output_dir, exist_ok=True)
        
        logger.info(f"OpenAI Extraction Agent initialized with model: {self.model}")
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """
        Extract text content from PDF file using PyMuPDF
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Extracted text content
        """
        try:
            doc = fitz.open(pdf_path)
            text_content = ""
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                text_content += page.get_text()
                text_content += "\n\n"  # Add page separator
            
            doc.close()
            logger.info(f"Successfully extracted text from {pdf_path} ({len(text_content)} characters)")
            return text_content
            
        except Exception as e:
            logger.error(f"Error extracting text from {pdf_path}: {str(e)}")
            raise
    
    def create_extraction_prompt(self, document_text: str, extraction_schema: Optional[Dict] = None) -> str:
        """
        Create a structured prompt for OpenAI to extract data from document text
        
        Args:
            document_text: The text content of the document
            extraction_schema: Optional schema defining what fields to extract
            
        Returns:
            Formatted prompt for OpenAI
        """
        base_prompt = """
You are an expert data extraction agent. Your task is to extract structured information from the provided document text.

Extract the following types of information when available:
- Personal Information: Full name, date of birth, SSN, phone number, email address
- Address Information: Current address, previous addresses, mailing address
- Employment Information: Employer name, job title, employment duration, salary/income
- Financial Information: Bank account details, loan amounts, assets, liabilities
- Contact Information: Emergency contacts, references
- Document Metadata: Document type, date, reference numbers

IMPORTANT INSTRUCTIONS:
1. Only extract information that is explicitly stated in the document
2. Do not make assumptions or infer information not present
3. Return data in valid JSON format
4. Use null for missing fields
5. Normalize phone numbers to (XXX) XXX-XXXX format when possible
6. Normalize dates to YYYY-MM-DD format when possible
7. Extract monetary amounts as numbers without currency symbols

Document Text:
{document_text}

Return the extracted data as a JSON object with the following structure:
{{
    "personal_info": {{
        "full_name": "string or null",
        "first_name": "string or null",
        "last_name": "string or null",
        "date_of_birth": "YYYY-MM-DD or null",
        "ssn": "string or null",
        "phone_number": "(XXX) XXX-XXXX or null",
        "email": "string or null"
    }},
    "address_info": {{
        "current_address": "string or null",
        "street_address": "string or null",
        "city": "string or null",
        "state": "string or null",
        "zip_code": "string or null",
        "previous_address": "string or null",
        "mailing_address": "string or null"
    }},
    "employment_info": {{
        "employer_name": "string or null",
        "job_title": "string or null",
        "employment_duration": "string or null",
        "annual_income": "number or null",
        "monthly_income": "number or null"
    }},
    "financial_info": {{
        "bank_name": "string or null",
        "account_number": "string or null",
        "loan_amount": "number or null",
        "assets": "number or null",
        "liabilities": "number or null"
    }},
    "document_metadata": {{
        "document_type": "string or null",
        "document_date": "YYYY-MM-DD or null",
        "reference_number": "string or null"
    }},
    "additional_fields": {{}}
}}
"""
        
        if extraction_schema:
            schema_text = f"\n\nAdditional extraction requirements:\n{json.dumps(extraction_schema, indent=2)}"
            base_prompt += schema_text
        
        return base_prompt.format(document_text=document_text[:8000])  # Limit text to avoid token limits
    
    def extract_data_with_openai(self, document_text: str, extraction_schema: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Use OpenAI API to extract structured data from document text
        
        Args:
            document_text: The text content of the document
            extraction_schema: Optional schema defining what fields to extract
            
        Returns:
            Extracted data as a dictionary
        """
        try:
            prompt = self.create_extraction_prompt(document_text, extraction_schema)
            
            print("\n" + "="*80)
            print("🤖 SENDING REQUEST TO OPENAI API...")
            print("="*80)
            print(f"Model: {self.model}")
            print(f"Document text length: {len(document_text)} characters")
            print("="*80)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert data extraction agent. Extract structured information from documents and return valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Low temperature for consistent extraction
                max_tokens=2000,
                response_format={"type": "json_object"}  # Ensure JSON response
            )
            
            # Get the raw JSON response
            raw_json_response = response.choices[0].message.content
            
            print("\n" + "="*80)
            print("📥 RAW OPENAI RESPONSE (JSON):")
            print("="*80)
            print(raw_json_response)
            print("="*80)
            
            # Parse the JSON
            extracted_data = json.loads(raw_json_response)
            
            print("\n" + "="*80)
            print("📊 PARSED EXTRACTED DATA:")
            print("="*80)
            print(json.dumps(extracted_data, indent=2, ensure_ascii=False))
            print("="*80)
            
            # Count and display field statistics
            field_count = self._count_non_null_fields(extracted_data)
            print(f"\n✅ EXTRACTION SUCCESSFUL!")
            print(f"📈 Total non-null fields extracted: {field_count}")
            print(f"🏷️  Top-level categories: {list(extracted_data.keys())}")
            
            return extracted_data
            
        except json.JSONDecodeError as e:
            print(f"\n❌ JSON PARSING ERROR: {str(e)}")
            print(f"Raw response: {response.choices[0].message.content}")
            logger.error(f"Failed to parse JSON response from OpenAI: {str(e)}")
            raise
        except Exception as e:
            print(f"\n❌ OPENAI API ERROR: {str(e)}")
            logger.error(f"Error calling OpenAI API: {str(e)}")
            raise
    
    def save_extracted_data(self, extracted_data: Dict[str, Any], source_file: str) -> str:
        """
        Save extracted data to a JSON file
        
        Args:
            extracted_data: The extracted data dictionary
            source_file: Path to the source document
            
        Returns:
            Path to the saved JSON file
        """
        try:
            # Create filename based on source file and timestamp
            base_name = os.path.splitext(os.path.basename(source_file))[0]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            json_filename = f"{base_name}_extracted_{timestamp}.json"
            json_path = os.path.join(self.output_dir, json_filename)
            
            # Add metadata to the extracted data
            extraction_metadata = {
                "extraction_timestamp": datetime.now().isoformat(),
                "source_file": source_file,
                "extraction_agent": "OpenAI Extraction Agent",
                "model_used": self.model
            }
            
            final_data = {
                "metadata": extraction_metadata,
                "extracted_data": extracted_data
            }
            
            # Save to JSON file
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(final_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Extracted data saved to: {json_path}")
            return json_path
            
        except Exception as e:
            logger.error(f"Error saving extracted data: {str(e)}")
            raise
    
    def extract_from_document(self, document_path: str, extraction_schema: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Complete extraction workflow: extract text, process with OpenAI, save to JSON
        
        Args:
            document_path: Path to the document to process
            extraction_schema: Optional schema defining what fields to extract
            
        Returns:
            Dictionary containing extraction results and file paths
        """
        try:
            logger.info(f"Starting extraction from document: {document_path}")
            
            # Step 1: Extract text from document
            if document_path.lower().endswith('.pdf'):
                document_text = self.extract_text_from_pdf(document_path)
            else:
                raise ValueError(f"Unsupported file type: {document_path}")
            
            # Step 2: Extract structured data using OpenAI
            extracted_data = self.extract_data_with_openai(document_text, extraction_schema)
            
            # Step 3: Save extracted data to JSON file
            json_path = self.save_extracted_data(extracted_data, document_path)
            
            # Step 4: Return results
            result = {
                "success": True,
                "source_document": document_path,
                "extracted_data": extracted_data,
                "json_file_path": json_path,
                "extraction_summary": {
                    "total_fields": self._count_non_null_fields(extracted_data),
                    "extraction_timestamp": datetime.now().isoformat()
                }
            }
            
            logger.info(f"Extraction completed successfully. Found {result['extraction_summary']['total_fields']} non-null fields")
            return result
            
        except Exception as e:
            logger.error(f"Extraction failed for {document_path}: {str(e)}")
            return {
                "success": False,
                "source_document": document_path,
                "error": str(e),
                "extraction_timestamp": datetime.now().isoformat()
            }
    
    def extract_from_multiple_documents(self, document_paths: List[str], extraction_schema: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Extract data from multiple documents and combine results
        
        Args:
            document_paths: List of paths to documents to process
            extraction_schema: Optional schema defining what fields to extract
            
        Returns:
            Dictionary containing combined extraction results
        """
        logger.info(f"Starting batch extraction from {len(document_paths)} documents")
        
        results = []
        successful_extractions = 0
        failed_extractions = 0
        combined_data = {}
        
        for doc_path in document_paths:
            result = self.extract_from_document(doc_path, extraction_schema)
            results.append(result)
            
            if result["success"]:
                successful_extractions += 1
                # Merge extracted data (later documents override earlier ones for conflicts)
                self._merge_extracted_data(combined_data, result["extracted_data"])
            else:
                failed_extractions += 1
        
        # Save combined data
        if combined_data:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            combined_filename = f"combined_extraction_{timestamp}.json"
            combined_path = os.path.join(self.output_dir, combined_filename)
            
            combined_metadata = {
                "extraction_timestamp": datetime.now().isoformat(),
                "source_documents": document_paths,
                "successful_extractions": successful_extractions,
                "failed_extractions": failed_extractions,
                "extraction_agent": "OpenAI Extraction Agent",
                "model_used": self.model
            }
            
            final_combined_data = {
                "metadata": combined_metadata,
                "combined_extracted_data": combined_data,
                "individual_results": results
            }
            
            with open(combined_path, 'w', encoding='utf-8') as f:
                json.dump(final_combined_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Combined extraction data saved to: {combined_path}")
        
        return {
            "success": successful_extractions > 0,
            "total_documents": len(document_paths),
            "successful_extractions": successful_extractions,
            "failed_extractions": failed_extractions,
            "combined_data": combined_data,
            "individual_results": results,
            "combined_json_path": combined_path if combined_data else None
        }
    
    def _count_non_null_fields(self, data: Dict[str, Any]) -> int:
        """Count non-null fields in extracted data"""
        count = 0
        for key, value in data.items():
            if isinstance(value, dict):
                count += self._count_non_null_fields(value)
            elif value is not None and value != "":
                count += 1
        return count
    
    def _merge_extracted_data(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """Merge source data into target data, with source taking precedence"""
        for key, value in source.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                self._merge_extracted_data(target[key], value)
            else:
                if value is not None and value != "":  # Only merge non-empty values
                    target[key] = value
                elif key not in target:  # Add key if it doesn't exist
                    target[key] = value

# Example usage and testing
if __name__ == "__main__":
    # Test the extraction agent
    try:
        # Initialize agent (make sure OPENAI_API_KEY is set in environment)
        agent = OpenAIExtractionAgent()
        
        # Test with a sample document
        test_document = "sample_document.pdf"  # Replace with actual document path
        
        if os.path.exists(test_document):
            result = agent.extract_from_document(test_document)
            
            if result["success"]:
                print("✅ Extraction successful!")
                print(f"📄 Source: {result['source_document']}")
                print(f"💾 JSON saved to: {result['json_file_path']}")
                print(f"📊 Fields extracted: {result['extraction_summary']['total_fields']}")
                print("\n📋 Sample extracted data:")
                print(json.dumps(result["extracted_data"], indent=2)[:500] + "...")
            else:
                print(f"❌ Extraction failed: {result['error']}")
        else:
            print(f"Test document not found: {test_document}")
            print("Please provide a valid PDF document path to test the extraction agent.")
            
    except Exception as e:
        print(f"❌ Error testing extraction agent: {str(e)}")
        print("Make sure to set the OPENAI_API_KEY environment variable.")
