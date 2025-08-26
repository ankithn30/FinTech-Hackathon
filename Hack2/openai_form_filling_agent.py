import os
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from openai import OpenAI
import fitz  # PyMuPDF for PDF processing
from datetime import datetime
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OpenAIFormFillingAgent:
    """
    OpenAI-powered form filling agent that reads extracted data from JSON files
    and intelligently fills PDF forms using semantic field mapping.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the form filling agent with OpenAI API key
        
        Args:
            api_key: OpenAI API key. If None, will try to get from environment variable
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable or pass api_key parameter.")
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4o-mini"  # Using cost-effective model for form filling
        
        # Create output directory for filled forms (use Forms folder)
        self.output_dir = "Forms"
        os.makedirs(self.output_dir, exist_ok=True)
        
        logger.info(f"OpenAI Form Filling Agent initialized with model: {self.model}")
    
    def load_extracted_data(self, json_path: str) -> Dict[str, Any]:
        """
        Load extracted data from JSON file created by extraction agent
        
        Args:
            json_path: Path to the JSON file containing extracted data
            
        Returns:
            Extracted data dictionary
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Handle both direct extracted data and wrapped format
            if "extracted_data" in data:
                extracted_data = data["extracted_data"]
            else:
                extracted_data = data
            
            logger.info(f"Loaded extracted data from {json_path}")
            return extracted_data
            
        except Exception as e:
            logger.error(f"Error loading extracted data from {json_path}: {str(e)}")
            raise
    
    def extract_form_fields(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        Extract form fields from PDF using PyMuPDF
        
        Args:
            pdf_path: Path to the PDF form
            
        Returns:
            List of form field dictionaries
        """
        try:
            doc = fitz.open(pdf_path)
            form_fields = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Get form fields (widgets) from the page
                widgets = page.widgets()
                
                for widget in widgets:
                    field_info = {
                        "field_name": widget.field_name,
                        "field_type": widget.field_type_string,
                        "field_value": widget.field_value,
                        "page_number": page_num,
                        "rect": list(widget.rect),  # Field position
                        "field_flags": widget.field_flags
                    }
                    form_fields.append(field_info)
            
            doc.close()
            logger.info(f"Extracted {len(form_fields)} form fields from {pdf_path}")
            return form_fields
            
        except Exception as e:
            logger.error(f"Error extracting form fields from {pdf_path}: {str(e)}")
            raise
    
    def create_field_mapping_prompt(self, form_fields: List[Dict], extracted_data: Dict[str, Any]) -> str:
        """
        Create a prompt for OpenAI to map extracted data to form fields
        
        Args:
            form_fields: List of form field information
            extracted_data: Extracted data from documents
            
        Returns:
            Formatted prompt for OpenAI
        """
        # Flatten extracted data for easier matching
        flattened_data = self._flatten_dict(extracted_data)
        
        # Create detailed form schema analysis
        form_schema_text = "FORM SCHEMA ANALYSIS:\n"
        for field in form_fields:
            form_schema_text += f"- Field: '{field['field_name']}'\n"
            form_schema_text += f"  Type: {field['field_type']}\n"
            form_schema_text += f"  Current Value: {field.get('field_value', 'empty')}\n"
            form_schema_text += f"  Page: {field.get('page_number', 0)}\n\n"
        
        # Create structured extracted data view
        extracted_data_text = "AVAILABLE EXTRACTED DATA:\n"
        for category, data in extracted_data.items():
            if isinstance(data, dict):
                extracted_data_text += f"\n{category.upper()}:\n"
                for key, value in data.items():
                    if value is not None and str(value).strip():
                        extracted_data_text += f"  - {key}: {value}\n"
            else:
                if data is not None and str(data).strip():
                    extracted_data_text += f"- {category}: {data}\n"
        
        prompt = f"""
You are an expert form filling agent. Your task is to analyze the form schema first, then intelligently map extracted data to the appropriate form fields.

STEP 1: ANALYZE THE FORM SCHEMA
{form_schema_text}

STEP 2: REVIEW AVAILABLE DATA
{extracted_data_text}

STEP 3: INTELLIGENT FIELD MAPPING
Based on the form schema analysis and available data, create intelligent mappings:

MAPPING RULES:
1. FIRST analyze what each form field is asking for based on its name and type
2. THEN find the most appropriate data from the extracted information
3. Use exact field names from the form schema
4. Consider semantic meaning (e.g., "first_name" field should get first name data)
5. Handle different data formats appropriately:
   - Names: Split full names if needed (full_name → first_name, last_name)
   - Addresses: Map complete addresses or individual components
   - Dates: Convert to appropriate format (MM/DD/YYYY, YYYY-MM-DD, etc.)
   - Financial: Map income, assets, account numbers to appropriate fields
6. Only map data that makes logical sense for each field
7. Leave fields unmapped if no appropriate data is available

EXAMPLES OF GOOD MAPPINGS:
- Form field "employee_first_name" ← extracted "personal_info.first_name"
- Form field "current_address" ← extracted "address_info.current_address"  
- Form field "employer_name" ← extracted "employment_info.employer_name"
- Form field "annual_income" ← extracted "employment_info.annual_income"

Return a JSON object with detailed field mappings:
{{
    "schema_analysis": {{
        "total_form_fields": {len(form_fields)},
        "field_types_found": ["text", "checkbox", "number"],
        "key_fields_identified": ["name_fields", "address_fields", "income_fields"]
    }},
    "field_mappings": {{
        "exact_field_name_1": "mapped_value_1",
        "exact_field_name_2": "mapped_value_2"
    }},
    "mapping_rationale": {{
        "exact_field_name_1": "Mapped personal_info.first_name to first name field",
        "exact_field_name_2": "Mapped address_info.current_address to address field"
    }},
    "mapping_confidence": {{
        "exact_field_name_1": 0.95,
        "exact_field_name_2": 0.87
    }},
    "unmapped_fields": ["field_name_3", "field_name_4"],
    "unused_data": ["data_key_1", "data_key_2"]
}}

Provide high confidence scores (0.8-1.0) for exact semantic matches, medium (0.5-0.8) for reasonable matches, and low (0.2-0.5) for uncertain matches.
"""
        
        return prompt
    
    def map_fields_with_openai(self, form_fields: List[Dict], extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use OpenAI to intelligently map extracted data to form fields
        
        Args:
            form_fields: List of form field information
            extracted_data: Extracted data from documents
            
        Returns:
            Field mapping results
        """
        try:
            prompt = self.create_field_mapping_prompt(form_fields, extracted_data)
            
            logger.info("Sending field mapping request to OpenAI...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert form filling agent. Map extracted data to PDF form fields intelligently and return valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Low temperature for consistent mapping
                max_tokens=2000,
                response_format={"type": "json_object"}  # Ensure JSON response
            )
            
            mapping_result = json.loads(response.choices[0].message.content)
            logger.info(f"Successfully generated field mappings for {len(mapping_result.get('field_mappings', {}))} fields")
            
            return mapping_result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response from OpenAI: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error calling OpenAI API for field mapping: {str(e)}")
            raise
    
    def get_user_confirmation_for_mappings(self, field_mappings: Dict[str, str], mapping_confidence: Dict[str, float], mapping_rationale: Dict[str, str]) -> Dict[str, str]:
        """
        Get user confirmation for high-confidence mappings (90%+)
        
        Args:
            field_mappings: Dictionary mapping field names to values
            mapping_confidence: Dictionary with confidence scores
            mapping_rationale: Dictionary with mapping explanations
            
        Returns:
            Dictionary with confirmed field mappings
        """
        confirmed_mappings = {}
        
        print("\n" + "="*80)
        print("🤔 USER CONFIRMATION REQUIRED FOR HIGH-CONFIDENCE MAPPINGS")
        print("="*80)
        
        high_confidence_mappings = {
            field: value for field, value in field_mappings.items()
            if mapping_confidence.get(field, 0.0) >= 0.90
        }
        
        if not high_confidence_mappings:
            print("ℹ️  No high-confidence mappings (90%+) found. Proceeding with all mappings.")
            return field_mappings
        
        print(f"Found {len(high_confidence_mappings)} high-confidence mappings that need confirmation:")
        print()
        
        for field_name, mapped_value in high_confidence_mappings.items():
            confidence = mapping_confidence.get(field_name, 0.0)
            rationale = mapping_rationale.get(field_name, "No rationale provided")
            
            print(f"🎯 Field: {field_name}")
            print(f"   Value: '{mapped_value}'")
            print(f"   Confidence: {confidence:.1%}")
            print(f"   Rationale: {rationale}")
            
            while True:
                try:
                    response = input(f"   ❓ Confirm this mapping? (y/n/skip): ").strip().lower()
                    if response in ['y', 'yes']:
                        confirmed_mappings[field_name] = mapped_value
                        print(f"   ✅ Confirmed: {field_name} = '{mapped_value}'")
                        break
                    elif response in ['n', 'no']:
                        print(f"   ❌ Rejected: {field_name} will not be filled")
                        break
                    elif response in ['s', 'skip']:
                        print(f"   ⏭️  Skipped: {field_name} will not be filled")
                        break
                    else:
                        print("   Please enter 'y' (yes), 'n' (no), or 'skip'")
                except KeyboardInterrupt:
                    print("\n   ⏭️  Skipping remaining confirmations...")
                    break
            print()
        
        # Add all low-confidence mappings without confirmation
        low_confidence_mappings = {
            field: value for field, value in field_mappings.items()
            if mapping_confidence.get(field, 0.0) < 0.90
        }
        
        confirmed_mappings.update(low_confidence_mappings)
        
        print(f"📊 Final mapping summary:")
        print(f"   High-confidence confirmed: {len([f for f in high_confidence_mappings if f in confirmed_mappings])}")
        print(f"   Low-confidence auto-included: {len(low_confidence_mappings)}")
        print(f"   Total fields to fill: {len(confirmed_mappings)}")
        print("="*80)
        
        return confirmed_mappings

    def fill_pdf_form(self, pdf_path: str, field_mappings: Dict[str, str], output_path: str, mapping_confidence: Dict[str, float] = None, mapping_rationale: Dict[str, str] = None) -> bool:
        """
        Fill PDF form with mapped field values, with user confirmation for high-confidence mappings
        
        Args:
            pdf_path: Path to the input PDF form
            field_mappings: Dictionary mapping field names to values
            output_path: Path for the output filled PDF
            mapping_confidence: Optional confidence scores for mappings
            mapping_rationale: Optional rationale for mappings
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get user confirmation for high-confidence mappings
            if mapping_confidence and mapping_rationale:
                confirmed_mappings = self.get_user_confirmation_for_mappings(
                    field_mappings, mapping_confidence, mapping_rationale
                )
            else:
                confirmed_mappings = field_mappings
            
            if not confirmed_mappings:
                print("⚠️  No field mappings confirmed. Creating empty form.")
                # Still create the output file but don't fill any fields
                doc = fitz.open(pdf_path)
                doc.save(output_path)
                doc.close()
                return True
            
            doc = fitz.open(pdf_path)
            filled_fields = 0
            skipped_fields = 0
            
            print(f"\n📝 Filling form with {len(confirmed_mappings)} confirmed mappings...")
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                widgets = page.widgets()
                
                for widget in widgets:
                    field_name = widget.field_name
                    
                    if field_name in confirmed_mappings:
                        field_value = str(confirmed_mappings[field_name])
                        
                        try:
                            # Set the field value
                            widget.field_value = field_value
                            widget.update()
                            filled_fields += 1
                            print(f"   ✅ Filled '{field_name}' = '{field_value}'")
                            
                        except Exception as e:
                            print(f"   ❌ Failed to fill '{field_name}': {str(e)}")
                            skipped_fields += 1
            
            # Save the filled PDF
            doc.save(output_path)
            doc.close()
            
            print(f"\n📊 Form filling completed:")
            print(f"   ✅ Fields filled: {filled_fields}")
            print(f"   ❌ Fields skipped: {skipped_fields}")
            print(f"   💾 Saved to: {output_path}")
            
            logger.info(f"Successfully filled {filled_fields} fields and saved to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error filling PDF form: {str(e)}")
            return False
    
    def fill_form_from_json(self, pdf_path: str, json_path: str, output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Complete form filling workflow: load JSON data, map fields, fill form
        
        Args:
            pdf_path: Path to the PDF form to fill
            json_path: Path to the JSON file with extracted data
            output_path: Optional output path for filled PDF
            
        Returns:
            Dictionary containing filling results
        """
        try:
            logger.info(f"Starting form filling: {pdf_path} with data from {json_path}")
            
            # Generate output path if not provided
            if not output_path:
                base_name = os.path.splitext(os.path.basename(pdf_path))[0]
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"{base_name}_filled_{timestamp}.pdf"
                output_path = os.path.join(self.output_dir, output_filename)
            
            # Step 1: Load extracted data
            extracted_data = self.load_extracted_data(json_path)
            
            # Step 2: Extract form fields
            form_fields = self.extract_form_fields(pdf_path)
            
            if not form_fields:
                return {
                    "success": False,
                    "error": "No form fields found in PDF",
                    "pdf_path": pdf_path,
                    "json_path": json_path
                }
            
            # Step 3: Map fields using OpenAI
            mapping_result = self.map_fields_with_openai(form_fields, extracted_data)
            
            # Step 4: Fill the PDF form with user confirmation for high-confidence mappings
            field_mappings = mapping_result.get("field_mappings", {})
            mapping_confidence = mapping_result.get("mapping_confidence", {})
            mapping_rationale = mapping_result.get("mapping_rationale", {})
            
            success = self.fill_pdf_form(
                pdf_path, 
                field_mappings, 
                output_path, 
                mapping_confidence, 
                mapping_rationale
            )
            
            if success:
                result = {
                    "success": True,
                    "input_pdf": pdf_path,
                    "input_json": json_path,
                    "output_pdf": output_path,
                    "fields_mapped": len(field_mappings),
                    "total_form_fields": len(form_fields),
                    "mapping_result": mapping_result,
                    "filling_timestamp": datetime.now().isoformat()
                }
                
                logger.info(f"Form filling completed successfully. Mapped {len(field_mappings)}/{len(form_fields)} fields")
                return result
            else:
                return {
                    "success": False,
                    "error": "Failed to fill PDF form",
                    "pdf_path": pdf_path,
                    "json_path": json_path,
                    "mapping_result": mapping_result
                }
                
        except Exception as e:
            logger.error(f"Form filling failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "pdf_path": pdf_path,
                "json_path": json_path,
                "filling_timestamp": datetime.now().isoformat()
            }
    
    def fill_multiple_forms(self, pdf_paths: List[str], json_path: str) -> Dict[str, Any]:
        """
        Fill multiple PDF forms with the same extracted data
        
        Args:
            pdf_paths: List of PDF form paths to fill
            json_path: Path to the JSON file with extracted data
            
        Returns:
            Dictionary containing batch filling results
        """
        logger.info(f"Starting batch form filling: {len(pdf_paths)} forms with data from {json_path}")
        
        results = []
        successful_fills = 0
        failed_fills = 0
        
        for pdf_path in pdf_paths:
            result = self.fill_form_from_json(pdf_path, json_path)
            results.append(result)
            
            if result["success"]:
                successful_fills += 1
            else:
                failed_fills += 1
        
        return {
            "success": successful_fills > 0,
            "total_forms": len(pdf_paths),
            "successful_fills": successful_fills,
            "failed_fills": failed_fills,
            "individual_results": results,
            "batch_timestamp": datetime.now().isoformat()
        }
    
    def preview_field_mapping(self, pdf_path: str, json_path: str) -> Dict[str, Any]:
        """
        Preview how fields would be mapped without actually filling the form
        
        Args:
            pdf_path: Path to the PDF form
            json_path: Path to the JSON file with extracted data
            
        Returns:
            Dictionary containing mapping preview
        """
        try:
            logger.info(f"Generating field mapping preview for {pdf_path}")
            
            # Load extracted data and form fields
            extracted_data = self.load_extracted_data(json_path)
            form_fields = self.extract_form_fields(pdf_path)
            
            if not form_fields:
                return {
                    "success": False,
                    "error": "No form fields found in PDF"
                }
            
            # Generate mapping using OpenAI
            mapping_result = self.map_fields_with_openai(form_fields, extracted_data)
            
            # Add form field details for preview
            field_details = {field["field_name"]: field for field in form_fields}
            
            preview_result = {
                "success": True,
                "pdf_path": pdf_path,
                "json_path": json_path,
                "total_form_fields": len(form_fields),
                "mapped_fields": len(mapping_result.get("field_mappings", {})),
                "mapping_result": mapping_result,
                "field_details": field_details,
                "preview_timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Generated mapping preview: {preview_result['mapped_fields']}/{preview_result['total_form_fields']} fields mapped")
            return preview_result
            
        except Exception as e:
            logger.error(f"Error generating field mapping preview: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "pdf_path": pdf_path,
                "json_path": json_path
            }
    
    def _flatten_dict(self, d: Dict[str, Any], parent_key: str = '', sep: str = '_') -> Dict[str, Any]:
        """
        Flatten nested dictionary for easier field matching
        
        Args:
            d: Dictionary to flatten
            parent_key: Parent key for nested items
            sep: Separator for nested keys
            
        Returns:
            Flattened dictionary
        """
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)

# Example usage and testing
if __name__ == "__main__":
    # Test the form filling agent
    try:
        # Initialize agent (make sure OPENAI_API_KEY is set in environment)
        agent = OpenAIFormFillingAgent()
        
        # Test with sample files
        test_pdf = "sample_form.pdf"  # Replace with actual form path
        test_json = "extracted_data/sample_extracted.json"  # Replace with actual JSON path
        
        if os.path.exists(test_pdf) and os.path.exists(test_json):
            # Preview field mapping
            preview = agent.preview_field_mapping(test_pdf, test_json)
            
            if preview["success"]:
                print("✅ Field mapping preview generated!")
                print(f"📄 Form: {preview['pdf_path']}")
                print(f"📊 Fields mapped: {preview['mapped_fields']}/{preview['total_form_fields']}")
                print("\n📋 Sample mappings:")
                mappings = preview["mapping_result"].get("field_mappings", {})
                for field, value in list(mappings.items())[:5]:  # Show first 5 mappings
                    print(f"  {field}: {value}")
                
                # Fill the form
                result = agent.fill_form_from_json(test_pdf, test_json)
                
                if result["success"]:
                    print(f"\n✅ Form filled successfully!")
                    print(f"💾 Output saved to: {result['output_pdf']}")
                else:
                    print(f"\n❌ Form filling failed: {result['error']}")
            else:
                print(f"❌ Preview failed: {preview['error']}")
        else:
            print(f"Test files not found:")
            print(f"  PDF: {test_pdf}")
            print(f"  JSON: {test_json}")
            print("Please provide valid file paths to test the form filling agent.")
            
    except Exception as e:
        print(f"❌ Error testing form filling agent: {str(e)}")
        print("Make sure to set the OPENAI_API_KEY environment variable.")
