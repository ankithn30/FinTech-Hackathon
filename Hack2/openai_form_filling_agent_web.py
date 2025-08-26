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

class OpenAIFormFillingAgentWeb:
    """
    Web-compatible OpenAI-powered form filling agent that reads extracted data from JSON files
    and intelligently fills PDF forms using semantic field mapping without interactive prompts.
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
        
        logger.info(f"OpenAI Form Filling Agent (Web) initialized with model: {self.model}")
    
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
            
            print(f"\n🔍 ANALYZING FORM SCHEMA: {os.path.basename(pdf_path)}")
            print("="*60)
            
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
            
            print(f"📊 Form Schema Analysis Complete:")
            print(f"   Total fields found: {len(form_fields)}")
            
            # Group fields by type for analysis
            field_types = {}
            for field in form_fields:
                field_type = field['field_type']
                if field_type not in field_types:
                    field_types[field_type] = 0
                field_types[field_type] += 1
            
            print(f"   Field types: {dict(field_types)}")
            print("="*60)
            
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

CRITICAL MAPPING RULES:
1. FIRST analyze what each form field is asking for based on its name and type
2. THEN find the most appropriate data from the extracted information
3. ONLY map fields where there is a clear semantic match between form field and extracted data
4. Use exact field names from the form schema
5. Skip fields if no appropriate data is available or if confidence is low
6. Handle different data formats appropriately:
   - Names: Split full names if needed (full_name → first_name, last_name)
   - Addresses: Map complete addresses or individual components
   - Dates: Convert to appropriate format (MM/DD/YYYY, YYYY-MM-DD, etc.)
   - Financial: Map income, assets, account numbers to appropriate fields
7. Only include mappings where you are confident the data matches the field purpose

EXAMPLES OF GOOD MAPPINGS:
- Form field "employee_first_name" ← extracted "personal_info.first_name" (confidence: 0.95)
- Form field "current_address" ← extracted "address_info.current_address" (confidence: 0.90)
- Form field "employer_name" ← extracted "employment_info.employer_name" (confidence: 0.92)

EXAMPLES OF MAPPINGS TO SKIP:
- Form field "tax_year" ← extracted "personal_info.first_name" (no semantic match)
- Form field "spouse_name" ← extracted "employment_info.employer_name" (wrong context)

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
    "high_confidence_mappings": {{
        "exact_field_name_1": "mapped_value_1"
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
            
            print("\n🤖 SENDING FIELD MAPPING REQUEST TO OPENAI...")
            print("="*60)
            
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
            
            print("📥 FIELD MAPPING RESULTS:")
            print("="*60)
            print(json.dumps(mapping_result, indent=2))
            print("="*60)
            
            logger.info(f"Successfully generated field mappings for {len(mapping_result.get('field_mappings', {}))} fields")
            
            return mapping_result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response from OpenAI: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error calling OpenAI API for field mapping: {str(e)}")
            raise
    
    def process_mappings_for_web(self, field_mappings: Dict[str, str], mapping_confidence: Dict[str, float], mapping_rationale: Dict[str, str]) -> Dict[str, Any]:
        """
        Process mappings for web interface - auto-approve high-confidence, return details for UI
        
        Args:
            field_mappings: Dictionary mapping field names to values
            mapping_confidence: Dictionary with confidence scores
            mapping_rationale: Dictionary with mapping explanations
            
        Returns:
            Dictionary with processed mappings and details for UI
        """
        confirmed_mappings = {}
        high_confidence_mappings = {}
        medium_confidence_mappings = {}
        low_confidence_mappings = {}
        
        print("\n" + "="*80)
        print("🔍 PROCESSING MAPPINGS FOR WEB INTERFACE")
        print("="*80)
        
        for field_name, mapped_value in field_mappings.items():
            confidence = mapping_confidence.get(field_name, 0.0)
            rationale = mapping_rationale.get(field_name, "No rationale provided")
            
            if confidence >= 0.90:
                # Auto-approve high-confidence mappings for web
                high_confidence_mappings[field_name] = {
                    "value": mapped_value,
                    "confidence": confidence,
                    "rationale": rationale,
                    "status": "auto_approved"
                }
                confirmed_mappings[field_name] = mapped_value
                print(f"✅ AUTO-APPROVED (90%+): {field_name} = '{mapped_value}' ({confidence:.1%})")
                
            elif confidence >= 0.70:
                # Include medium-confidence mappings
                medium_confidence_mappings[field_name] = {
                    "value": mapped_value,
                    "confidence": confidence,
                    "rationale": rationale,
                    "status": "medium_confidence"
                }
                confirmed_mappings[field_name] = mapped_value
                print(f"📊 INCLUDED (70-89%): {field_name} = '{mapped_value}' ({confidence:.1%})")
                
            else:
                # Skip low-confidence mappings
                low_confidence_mappings[field_name] = {
                    "value": mapped_value,
                    "confidence": confidence,
                    "rationale": rationale,
                    "status": "skipped_low_confidence"
                }
                print(f"⏭️  SKIPPED (<70%): {field_name} = '{mapped_value}' ({confidence:.1%})")
        
        print(f"\n📊 Web Processing Summary:")
        print(f"   ✅ Auto-approved (90%+): {len(high_confidence_mappings)}")
        print(f"   📊 Medium confidence (70-89%): {len(medium_confidence_mappings)}")
        print(f"   ⏭️  Skipped (<70%): {len(low_confidence_mappings)}")
        print(f"   📝 Total fields to fill: {len(confirmed_mappings)}")
        print("="*80)
        
        return {
            "confirmed_mappings": confirmed_mappings,
            "high_confidence_mappings": high_confidence_mappings,
            "medium_confidence_mappings": medium_confidence_mappings,
            "low_confidence_mappings": low_confidence_mappings,
            "processing_summary": {
                "auto_approved_count": len(high_confidence_mappings),
                "medium_confidence_count": len(medium_confidence_mappings),
                "skipped_count": len(low_confidence_mappings),
                "total_to_fill": len(confirmed_mappings)
            }
        }
    
    def fill_pdf_form_web(self, pdf_path: str, field_mappings: Dict[str, str], output_path: str, mapping_details: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Fill PDF form with mapped field values for web interface
        
        Args:
            pdf_path: Path to the input PDF form
            field_mappings: Dictionary mapping field names to values
            output_path: Path for the output filled PDF
            mapping_details: Optional mapping details for reporting
            
        Returns:
            Dictionary with filling results and details
        """
        try:
            if not field_mappings:
                print("⚠️  No field mappings to process. Creating empty form.")
                # Still create the output file but don't fill any fields
                doc = fitz.open(pdf_path)
                doc.save(output_path)
                doc.close()
                return {
                    "success": True,
                    "fields_filled": 0,
                    "fields_skipped": 0,
                    "output_path": output_path,
                    "message": "No fields mapped - empty form created"
                }
            
            doc = fitz.open(pdf_path)
            filled_fields = 0
            skipped_fields = 0
            fill_details = []
            
            print(f"\n📝 FILLING FORM WITH {len(field_mappings)} CONFIRMED MAPPINGS...")
            print("="*60)
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                widgets = page.widgets()
                
                for widget in widgets:
                    field_name = widget.field_name
                    
                    if field_name in field_mappings:
                        field_value = str(field_mappings[field_name])
                        
                        try:
                            # Set the field value
                            widget.field_value = field_value
                            widget.update()
                            filled_fields += 1
                            
                            fill_details.append({
                                "field_name": field_name,
                                "value": field_value,
                                "status": "filled",
                                "page": page_num
                            })
                            
                            print(f"   ✅ Filled '{field_name}' = '{field_value}'")
                            
                        except Exception as e:
                            skipped_fields += 1
                            fill_details.append({
                                "field_name": field_name,
                                "value": field_value,
                                "status": "error",
                                "error": str(e),
                                "page": page_num
                            })
                            print(f"   ❌ Failed to fill '{field_name}': {str(e)}")
            
            # Save the filled PDF
            doc.save(output_path)
            doc.close()
            
            print(f"\n📊 FORM FILLING COMPLETED:")
            print(f"   ✅ Fields filled: {filled_fields}")
            print(f"   ❌ Fields skipped: {skipped_fields}")
            print(f"   💾 Saved to: {output_path}")
            print("="*60)
            
            logger.info(f"Successfully filled {filled_fields} fields and saved to {output_path}")
            
            return {
                "success": True,
                "fields_filled": filled_fields,
                "fields_skipped": skipped_fields,
                "output_path": output_path,
                "fill_details": fill_details,
                "mapping_details": mapping_details
            }
            
        except Exception as e:
            logger.error(f"Error filling PDF form: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "output_path": output_path
            }
    
    def fill_form_from_json_web(self, pdf_path: str, json_path: str, output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Complete web-compatible form filling workflow: load JSON data, map fields, fill form
        
        Args:
            pdf_path: Path to the PDF form to fill
            json_path: Path to the JSON file with extracted data
            output_path: Optional output path for filled PDF
            
        Returns:
            Dictionary containing filling results with web-friendly details
        """
        try:
            logger.info(f"Starting web form filling: {pdf_path} with data from {json_path}")
            
            # Generate output path if not provided
            if not output_path:
                base_name = os.path.splitext(os.path.basename(pdf_path))[0]
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"{base_name}_filled_{timestamp}.pdf"
                output_path = os.path.join(self.output_dir, output_filename)
            
            # Step 1: Load extracted data
            extracted_data = self.load_extracted_data(json_path)
            
            # Step 2: Extract form fields (with schema analysis)
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
            
            # Step 4: Process mappings for web (auto-approve high-confidence)
            field_mappings = mapping_result.get("field_mappings", {})
            mapping_confidence = mapping_result.get("mapping_confidence", {})
            mapping_rationale = mapping_result.get("mapping_rationale", {})
            
            web_processing = self.process_mappings_for_web(
                field_mappings, mapping_confidence, mapping_rationale
            )
            
            # Step 5: Fill the PDF form
            fill_result = self.fill_pdf_form_web(
                pdf_path, 
                web_processing["confirmed_mappings"], 
                output_path,
                web_processing
            )
            
            if fill_result["success"]:
                result = {
                    "success": True,
                    "input_pdf": pdf_path,
                    "input_json": json_path,
                    "output_pdf": output_path,
                    "fields_mapped": len(web_processing["confirmed_mappings"]),
                    "total_form_fields": len(form_fields),
                    "schema_analysis": mapping_result.get("schema_analysis", {}),
                    "mapping_summary": web_processing["processing_summary"],
                    "high_confidence_mappings": web_processing["high_confidence_mappings"],
                    "medium_confidence_mappings": web_processing["medium_confidence_mappings"],
                    "skipped_mappings": web_processing["low_confidence_mappings"],
                    "fill_details": fill_result.get("fill_details", []),
                    "filling_timestamp": datetime.now().isoformat()
                }
                
                logger.info(f"Web form filling completed successfully. Mapped {result['fields_mapped']}/{len(form_fields)} fields")
                return result
            else:
                return {
                    "success": False,
                    "error": fill_result.get("error", "Failed to fill PDF form"),
                    "pdf_path": pdf_path,
                    "json_path": json_path,
                    "mapping_result": mapping_result
                }
                
        except Exception as e:
            logger.error(f"Web form filling failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "pdf_path": pdf_path,
                "json_path": json_path,
                "filling_timestamp": datetime.now().isoformat()
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
    # Test the web form filling agent
    try:
        # Initialize agent (make sure OPENAI_API_KEY is set in environment)
        agent = OpenAIFormFillingAgentWeb()
        
        # Test with fss4 data
        test_pdf = "Forms/fw4.pdf"
        test_json = "Documents/fss4_extracted_20250826_004527.json"
        
        if os.path.exists(test_pdf) and os.path.exists(test_json):
            print("🧪 Testing web-compatible form filling...")
            
            result = agent.fill_form_from_json_web(test_pdf, test_json)
            
            if result["success"]:
                print(f"\n✅ Web form filling successful!")
                print(f"📄 Output: {result['output_pdf']}")
                print(f"📊 Fields filled: {result['fields_mapped']}/{result['total_form_fields']}")
                print(f"🎯 High-confidence auto-approved: {result['mapping_summary']['auto_approved_count']}")
            else:
                print(f"\n❌ Web form filling failed: {result['error']}")
        else:
            print(f"Test files not found:")
            print(f"  PDF: {test_pdf}")
            print(f"  JSON: {test_json}")
            
    except Exception as e:
        print(f"❌ Error testing web form filling agent: {str(e)}")
        print("Make sure to set the OPENAI_API_KEY environment variable.")
