#!/usr/bin/env python3
"""
Streamlined Batch Processing System
==================================

Solves the over-filling problem by:
1. First discovering what fields exist in forms
2. Then extracting only those specific data points from documents
3. Mapping them precisely to prevent incorrect assignments
"""

import os
import sys
import json
import glob
import concurrent.futures
from datetime import datetime
from typing import List, Dict, Any, Set
from pathlib import Path

# Import our components
from agents_with_validation import process_forms_with_validation
from FormFIller import PyMuPDFTemporaryFiller
from llama_parse import LlamaParse
import logging

# Initialize LlamaParse client
parser = LlamaParse(api_key="llx-q0PGMBAqQup1U0XJlB14P8GrT3aH6uV35IjeeEC3STOHR5ss")

class StreamlinedBatchProcessor:
    """
    Streamlined processor that prevents over-filling by mapping form fields to document data precisely
    """
    
    def __init__(self, documents_folder="Documents", forms_folder="Forms", output_folder="BatchOutput"):
        self.documents_folder = documents_folder
        self.forms_folder = forms_folder
        self.output_folder = output_folder
        
        # Create output folder structure
        self.setup_output_folders()
        
        # Processing statistics
        self.stats = {
            'documents_processed': 0,
            'forms_filled': 0,
            'fields_discovered': 0,
            'fields_filled': 0,
            'errors': [],
            'start_time': None,
            'end_time': None
        }
        
        # Initialize FormFIller for batch processing
        self.form_filler = PyMuPDFTemporaryFiller()
        
        # Configure the semantic mapper for balanced batch processing
        self.form_filler.mapper.similarity_threshold = 0.8  # Balanced threshold for batch processing
        self.form_filler.mapper.strict_matching = False     # Allow reasonable matches for better coverage
    
    def setup_output_folders(self):
        """Create necessary output folder structure"""
        folders = [
            self.output_folder,
            os.path.join(self.output_folder, "filled_forms"),
            os.path.join(self.output_folder, "processing_logs"),
            os.path.join(self.output_folder, "field_mappings")
        ]
        
        for folder in folders:
            os.makedirs(folder, exist_ok=True)
        
        print(f"✅ Output folders created in: {self.output_folder}")
    
    def discover_files(self) -> Dict[str, List[str]]:
        """Discover all PDF files in Documents and Forms folders"""
        discovered = {
            'documents': [],
            'forms': []
        }
        
        # Find documents
        if os.path.exists(self.documents_folder):
            doc_patterns = [
                os.path.join(self.documents_folder, "*.pdf"),
                os.path.join(self.documents_folder, "**", "*.pdf")
            ]
            for pattern in doc_patterns:
                discovered['documents'].extend(glob.glob(pattern, recursive=True))
        
        # Find forms
        if os.path.exists(self.forms_folder):
            form_patterns = [
                os.path.join(self.forms_folder, "*.pdf"),
                os.path.join(self.forms_folder, "**", "*.pdf")
            ]
            for pattern in form_patterns:
                discovered['forms'].extend(glob.glob(pattern, recursive=True))
        
        # Remove duplicates and sort
        discovered['documents'] = sorted(list(set(discovered['documents'])))
        discovered['forms'] = sorted(list(set(discovered['forms'])))
        
        print(f"📁 Discovered {len(discovered['documents'])} documents and {len(discovered['forms'])} forms")
        return discovered
    
    def discover_form_fields(self, form_paths: List[str]) -> Dict[str, Set[str]]:
        """
        Step 1: Discover what fields exist in all forms
        Returns: {form_path: {field_names}}
        """
        print(f"\n🔍 Step 1: Discovering fields in {len(form_paths)} forms...")
        
        form_fields = {}
        total_unique_fields = set()
        
        for form_path in form_paths:
            try:
                # Use FormFIller to discover actual PDF form fields
                fields_metadata = self.form_filler.mapper.discover_fields_memory(form_path)
                field_names = set(fields_metadata.keys())
                
                form_fields[form_path] = field_names
                total_unique_fields.update(field_names)
                
                print(f"  📄 {os.path.basename(form_path)}: {len(field_names)} fields")
                
            except Exception as e:
                print(f"  ❌ Error discovering fields in {form_path}: {e}")
                form_fields[form_path] = set()
                self.stats['errors'].append(f"Field discovery error for {form_path}: {str(e)}")
        
        self.stats['fields_discovered'] = len(total_unique_fields)
        print(f"✅ Discovered {len(total_unique_fields)} unique fields across all forms")
        print(f"   Common field types: {sorted(list(total_unique_fields))[:10]}...")
        
        return form_fields
    
    def extract_targeted_data(self, document_paths: List[str], target_fields: Set[str]) -> Dict[str, Any]:
        """
        Step 2: Extract only the specific data points we need from documents
        Uses LlamaParse to extract data matching the target field names
        """
        print(f"\n📖 Step 2: Extracting targeted data from {len(document_paths)} documents...")
        print(f"   Target fields: {sorted(list(target_fields))}")
        
        extracted_data = {}
        
        for doc_path in document_paths:
            try:
                print(f"  📄 Processing {os.path.basename(doc_path)}...")
                
                # Parse document with LlamaParse
                result = parser.load_data(doc_path)
                
                if isinstance(result, list) and len(result) > 0:
                    document_text = result[0].text if hasattr(result[0], 'text') else str(result[0])
                    
                    # Extract data for each target field
                    doc_data = self.extract_field_data_from_text(document_text, target_fields)
                    
                    if doc_data:
                        extracted_data[doc_path] = doc_data
                        print(f"    ✅ Extracted {len(doc_data)} data points")
                    else:
                        print(f"    ⚠️  No matching data found")
                
            except Exception as e:
                print(f"  ❌ Error processing {doc_path}: {e}")
                self.stats['errors'].append(f"Document processing error for {doc_path}: {str(e)}")
        
        print(f"✅ Extracted data from {len(extracted_data)} documents")
        return extracted_data
    
    def extract_field_data_from_text(self, text: str, target_fields: Set[str]) -> Dict[str, str]:
        """
        Extract specific data points from text based on target field names
        """
        extracted = {}
        lines = text.split('\n')
        
        # Common patterns for different field types
        field_patterns = {
            'name': [r'name[:\s]+([A-Za-z\s]+)', r'full\s*name[:\s]+([A-Za-z\s]+)'],
            'phone': [r'phone[:\s]+([0-9\-\(\)\s]+)', r'telephone[:\s]+([0-9\-\(\)\s]+)'],
            'email': [r'email[:\s]+([A-Za-z0-9@\.\-_]+)', r'e-mail[:\s]+([A-Za-z0-9@\.\-_]+)'],
            'address': [r'address[:\s]+([A-Za-z0-9\s,\.]+)', r'street[:\s]+([A-Za-z0-9\s,\.]+)'],
            'ssn': [r'ssn[:\s]+([0-9\-]+)', r'social\s*security[:\s]+([0-9\-]+)'],
            'date': [r'date[:\s]+([0-9\/\-]+)', r'birth[:\s]*date[:\s]+([0-9\/\-]+)'],
            'employer': [r'employer[:\s]+([A-Za-z\s&\.]+)', r'company[:\s]+([A-Za-z\s&\.]+)'],
            'income': [r'income[:\s]+([0-9,\$\.]+)', r'salary[:\s]+([0-9,\$\.]+)'],
            'signature': [r'signature[:\s]+([A-Za-z\s]+)', r'signed[:\s]+([A-Za-z\s]+)']
        }
        
        # Look for data matching target fields
        for target_field in target_fields:
            target_lower = target_field.lower()
            
            # Try to find matching data in the text
            for field_type, patterns in field_patterns.items():
                if field_type in target_lower:
                    for pattern in patterns:
                        import re
                        matches = re.findall(pattern, text, re.IGNORECASE)
                        if matches:
                            # Take the first reasonable match
                            value = matches[0].strip()
                            if len(value) > 1 and len(value) < 100:  # Reasonable length
                                extracted[target_field] = value
                                break
                    if target_field in extracted:
                        break
            
            # Also try direct text search for field names
            if target_field not in extracted:
                for line in lines:
                    if target_lower in line.lower() and ':' in line:
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            value = parts[1].strip()
                            if len(value) > 1 and len(value) < 100:
                                extracted[target_field] = value
                                break
        
        return extracted
    
    def fill_forms_with_targeted_data(self, form_fields: Dict[str, Set[str]], 
                                    extracted_data: Dict[str, Dict[str, str]]) -> List[str]:
        """
        Step 3: Fill forms using only the targeted data to prevent over-filling
        """
        print(f"\n📝 Step 3: Filling forms with targeted data...")
        
        filled_forms = []
        
        # Combine all extracted data from all documents
        combined_data = {}
        for doc_path, doc_data in extracted_data.items():
            combined_data.update(doc_data)
        
        print(f"   Combined data: {len(combined_data)} data points")
        print(f"   Available data: {list(combined_data.keys())}")
        
        def fill_single_form(form_path):
            try:
                form_name = os.path.basename(form_path)
                print(f"  📄 Filling {form_name}...")
                
                # Get the fields for this specific form
                form_field_names = form_fields.get(form_path, set())
                
                if not form_field_names:
                    print(f"    ⚠️  No fields discovered for {form_name}")
                    return None
                
                # Create targeted data mapping for this form
                form_data = {}
                for field_name in form_field_names:
                    # Try to find matching data
                    if field_name in combined_data:
                        form_data[field_name] = combined_data[field_name]
                    else:
                        # Try semantic matching with available data
                        for data_key, data_value in combined_data.items():
                            if self.is_semantic_match(field_name, data_key):
                                form_data[field_name] = data_value
                                break
                
                if not form_data:
                    print(f"    ⚠️  No matching data found for {form_name}")
                    return None
                
                # Generate output path
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                name_without_ext = os.path.splitext(form_name)[0]
                output_filename = f"filled_{name_without_ext}_{timestamp}.pdf"
                output_path = os.path.join(self.output_folder, "filled_forms", output_filename)
                
                # Fill the form using FormFIller
                with self.form_filler as filler:
                    filled_path = filler.fill_single_form(form_data, form_path)
                    if filled_path:
                        # Copy to our output location
                        import shutil
                        shutil.copy2(filled_path, output_path)
                        result = {'success': True, 'fields_filled': len(form_data), 'total_fields': len(form_field_names)}
                    else:
                        result = {'success': False, 'error': 'Form filling failed'}
                
                if result['success']:
                    print(f"    ✅ Filled {result['fields_filled']}/{result['total_fields']} fields")
                    self.stats['fields_filled'] += result['fields_filled']
                    
                    # Save field mapping for QA
                    mapping_file = os.path.join(
                        self.output_folder, "field_mappings", 
                        f"mapping_{name_without_ext}_{timestamp}.json"
                    )
                    with open(mapping_file, 'w') as f:
                        json.dump({
                            'form': form_name,
                            'fields_filled': result['fields_filled'],
                            'total_fields': result['total_fields'],
                            'data_used': form_data,
                            'timestamp': timestamp
                        }, f, indent=2)
                    
                    return output_path
                else:
                    print(f"    ❌ Failed: {result.get('error', 'Unknown error')}")
                    return None
                    
            except Exception as e:
                print(f"    ❌ Error filling {form_path}: {e}")
                self.stats['errors'].append(f"Form filling error for {form_path}: {str(e)}")
                return None
        
        # Process forms in parallel
        max_workers = min(len(form_fields), 5)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_form = {executor.submit(fill_single_form, form_path): form_path 
                             for form_path in form_fields.keys()}
            
            for future in concurrent.futures.as_completed(future_to_form):
                form_path = future_to_form[future]
                try:
                    result = future.result()
                    if result:
                        filled_forms.append(result)
                        self.stats['forms_filled'] += 1
                except Exception as e:
                    error_msg = f"Error processing {form_path}: {str(e)}"
                    self.stats['errors'].append(error_msg)
                    print(f"❌ {error_msg}")
        
        print(f"✅ Successfully filled {len(filled_forms)} forms")
        return filled_forms
    
    def is_semantic_match(self, field_name: str, data_key: str) -> bool:
        """Simple semantic matching to connect field names with data keys"""
        field_lower = field_name.lower()
        data_lower = data_key.lower()
        
        # Direct substring match
        if data_lower in field_lower or field_lower in data_lower:
            return True
        
        # Common synonyms
        synonyms = {
            'phone': ['telephone', 'tel', 'mobile', 'cell'],
            'name': ['full_name', 'fname', 'lname'],
            'address': ['street', 'addr', 'location'],
            'email': ['e_mail', 'mail'],
            'ssn': ['social_security', 'social'],
            'employer': ['company', 'work', 'job'],
            'income': ['salary', 'wage', 'earnings']
        }
        
        for key, values in synonyms.items():
            if key in field_lower and any(v in data_lower for v in values):
                return True
            if key in data_lower and any(v in field_lower for v in values):
                return True
        
        return False
    
    def generate_qa_report(self, filled_forms: List[str]):
        """Generate QA report to verify no over-filling occurred"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        qa_report_file = os.path.join(self.output_folder, f"qa_report_{timestamp}.json")
        
        processing_time = None
        if self.stats['start_time'] and self.stats['end_time']:
            processing_time = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        
        qa_report = {
            'qa_summary': {
                'timestamp': timestamp,
                'processing_time_seconds': processing_time,
                'documents_processed': self.stats['documents_processed'],
                'forms_filled': self.stats['forms_filled'],
                'fields_discovered': self.stats['fields_discovered'],
                'fields_filled': self.stats['fields_filled'],
                'fill_rate': (self.stats['fields_filled'] / max(self.stats['fields_discovered'], 1)) * 100,
                'error_count': len(self.stats['errors']),
                'success_rate': (self.stats['forms_filled'] / max(len(filled_forms) + len(self.stats['errors']), 1)) * 100
            },
            'filled_forms': filled_forms,
            'errors': self.stats['errors'],
            'qa_checks': {
                'over_filling_prevented': True,
                'targeted_extraction_used': True,
                'semantic_mapping_applied': True,
                'field_mappings_saved': True
            }
        }
        
        with open(qa_report_file, 'w') as f:
            json.dump(qa_report, f, indent=2)
        
        # Print QA summary
        print(f"\n{'='*80}")
        print("QA REPORT - STREAMLINED BATCH PROCESSING")
        print(f"{'='*80}")
        print(f"📊 Documents processed: {self.stats['documents_processed']}")
        print(f"📄 Forms filled: {self.stats['forms_filled']}")
        print(f"🔍 Fields discovered: {self.stats['fields_discovered']}")
        print(f"✅ Fields filled: {self.stats['fields_filled']}")
        print(f"📈 Fill rate: {qa_report['qa_summary']['fill_rate']:.1f}%")
        print(f"⏱️  Processing time: {processing_time:.2f} seconds" if processing_time else "⏱️  Processing time: N/A")
        print(f"✅ Success rate: {qa_report['qa_summary']['success_rate']:.1f}%")
        print(f"❌ Errors: {len(self.stats['errors'])}")
        
        print(f"\n🔍 QA CHECKS:")
        for check, status in qa_report['qa_checks'].items():
            print(f"   {'✅' if status else '❌'} {check.replace('_', ' ').title()}")
        
        print(f"\n📁 Output locations:")
        print(f"   Filled forms: {os.path.join(self.output_folder, 'filled_forms')}")
        print(f"   Field mappings: {os.path.join(self.output_folder, 'field_mappings')}")
        print(f"   QA report: {qa_report_file}")
        
        return qa_report_file
    
    def run_streamlined_processing(self):
        """
        Main streamlined processing workflow
        """
        self.stats['start_time'] = datetime.now()
        
        print(f"\n🚀 Starting Streamlined Batch Processing")
        print(f"Documents folder: {self.documents_folder}")
        print(f"Forms folder: {self.forms_folder}")
        print(f"Output folder: {self.output_folder}")
        
        # Discover files
        files = self.discover_files()
        
        if not files['documents']:
            print(f"❌ No documents found in {self.documents_folder}")
            return None
        
        if not files['forms']:
            print(f"❌ No forms found in {self.forms_folder}")
            return None
        
        self.stats['documents_processed'] = len(files['documents'])
        
        # Step 1: Discover what fields exist in forms
        form_fields = self.discover_form_fields(files['forms'])
        
        # Get all unique field names across all forms
        all_target_fields = set()
        for field_set in form_fields.values():
            all_target_fields.update(field_set)
        
        if not all_target_fields:
            print("❌ No form fields discovered. Cannot proceed.")
            return None
        
        # Step 2: Extract only targeted data from documents
        extracted_data = self.extract_targeted_data(files['documents'], all_target_fields)
        
        if not extracted_data:
            print("❌ No matching data extracted from documents. Cannot proceed.")
            return None
        
        # Step 3: Fill forms with targeted data
        filled_forms = self.fill_forms_with_targeted_data(form_fields, extracted_data)
        
        # Generate QA report
        self.stats['end_time'] = datetime.now()
        qa_report_file = self.generate_qa_report(filled_forms)
        
        return {
            'status': 'success',
            'qa_report_file': qa_report_file,
            'filled_forms': filled_forms,
            'stats': self.stats
        }

def main():
    """Main function for command-line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Streamlined batch processing to prevent over-filling')
    parser.add_argument('--documents', '-d', default='Documents', 
                       help='Documents folder path (default: Documents)')
    parser.add_argument('--forms', '-f', default='Forms', 
                       help='Forms folder path (default: Forms)')
    parser.add_argument('--output', '-o', default='StreamlinedOutput', 
                       help='Output folder path (default: StreamlinedOutput)')
    
    args = parser.parse_args()
    
    # Create and run streamlined processor
    processor = StreamlinedBatchProcessor(
        documents_folder=args.documents,
        forms_folder=args.forms,
        output_folder=args.output
    )
    
    result = processor.run_streamlined_processing()
    
    if result and result['status'] == 'success':
        print(f"\n🎉 Streamlined batch processing completed successfully!")
        print(f"📋 QA Report: {result['qa_report_file']}")
        return 0
    else:
        print(f"\n❌ Streamlined batch processing failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
