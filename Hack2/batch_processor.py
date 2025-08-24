#!/usr/bin/env python3
"""
Batch Processing System for FinTech Document Processing
Processes bulk documents and fills multiple forms in parallel
"""

import os
import sys
import json
import glob
import shutil
import concurrent.futures
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

# Import our workflow components
from agents_with_validation import process_forms_with_validation
from pdfwriter import fill_pdf_from_llama
from schema_utils import compile_schemas

class BatchProcessor:
    """
    Batch processor for handling bulk document processing and form filling
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
            'errors': [],
            'start_time': None,
            'end_time': None
        }
    
    def setup_output_folders(self):
        """Create necessary output folder structure"""
        folders = [
            self.output_folder,
            os.path.join(self.output_folder, "filled_forms"),
            os.path.join(self.output_folder, "processing_logs"),
            os.path.join(self.output_folder, "validation_reports")
        ]
        
        for folder in folders:
            os.makedirs(folder, exist_ok=True)
        
        print(f"✅ Output folders created in: {self.output_folder}")
    
    def discover_files(self) -> Dict[str, List[str]]:
        """
        Discover all PDF files in Documents and Forms folders
        """
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
    
    def process_documents_batch(self, document_paths: List[str]) -> Dict[str, Any]:
        """
        Process a batch of documents using the complete workflow
        """
        print(f"\n🔄 Processing {len(document_paths)} documents...")
        
        try:
            # Execute complete workflow with validation
            workflow_result = process_forms_with_validation(document_paths)
            
            if workflow_result['status'] == 'success':
                self.stats['documents_processed'] += len(document_paths)
                
                # Save processing results
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                results_file = os.path.join(
                    self.output_folder, 
                    "processing_logs", 
                    f"workflow_results_{timestamp}.json"
                )
                
                with open(results_file, 'w') as f:
                    json.dump(workflow_result, f, indent=2)
                
                print(f"✅ Document processing completed. Results saved to: {results_file}")
                return workflow_result
            else:
                error_msg = f"Document processing failed: {workflow_result.get('message', 'Unknown error')}"
                self.stats['errors'].append(error_msg)
                print(f"❌ {error_msg}")
                return workflow_result
                
        except Exception as e:
            error_msg = f"Error in document processing: {str(e)}"
            self.stats['errors'].append(error_msg)
            print(f"❌ {error_msg}")
            return {'status': 'error', 'message': error_msg}
    
    def fill_forms_batch(self, form_paths: List[str], compiled_schema: Dict[str, Any]) -> List[str]:
        """
        Fill multiple forms in parallel using the compiled schema
        """
        print(f"\n📄 Filling {len(form_paths)} forms in parallel...")
        
        def fill_single_form(form_path):
            try:
                # Extract field data from compiled schema
                form_data = {}
                for field in compiled_schema.get('fields', []):
                    field_name = field.get('name', '')
                    field_meaning = field.get('meaning', '')
                    if field_name and field_meaning:
                        form_data[field_name] = field_meaning
                
                # Generate output path
                base_name = os.path.basename(form_path)
                name_without_ext = os.path.splitext(base_name)[0]
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"filled_{name_without_ext}_{timestamp}.pdf"
                output_path = os.path.join(self.output_folder, "filled_forms", output_filename)
                
                # Fill the form
                success = fill_pdf_from_llama(form_data, form_path, output_path)
                
                if success:
                    print(f"✅ Filled: {base_name} -> {output_filename}")
                    return output_path
                else:
                    print(f"❌ Failed to fill: {base_name}")
                    return None
                    
            except Exception as e:
                print(f"❌ Error filling form {form_path}: {e}")
                self.stats['errors'].append(f"Form filling error for {form_path}: {str(e)}")
                return None
        
        # Process forms in parallel
        filled_forms = []
        max_workers = min(len(form_paths), 5)  # Limit concurrent processes
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all form filling tasks
            future_to_form = {executor.submit(fill_single_form, form_path): form_path 
                             for form_path in form_paths}
            
            # Collect results as they complete
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
        
        print(f"✅ Successfully filled {len(filled_forms)} out of {len(form_paths)} forms")
        return filled_forms
    
    def generate_batch_report(self, workflow_result: Dict[str, Any], filled_forms: List[str]):
        """
        Generate a comprehensive batch processing report
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(self.output_folder, f"batch_report_{timestamp}.json")
        
        # Calculate processing time
        processing_time = None
        if self.stats['start_time'] and self.stats['end_time']:
            processing_time = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        
        report = {
            'batch_processing_summary': {
                'timestamp': timestamp,
                'processing_time_seconds': processing_time,
                'documents_processed': self.stats['documents_processed'],
                'forms_filled': self.stats['forms_filled'],
                'total_errors': len(self.stats['errors']),
                'success_rate': (self.stats['forms_filled'] / max(len(filled_forms) + len(self.stats['errors']), 1)) * 100
            },
            'workflow_results': workflow_result,
            'filled_forms': filled_forms,
            'errors': self.stats['errors'],
            'output_locations': {
                'filled_forms': os.path.join(self.output_folder, "filled_forms"),
                'processing_logs': os.path.join(self.output_folder, "processing_logs"),
                'validation_reports': os.path.join(self.output_folder, "validation_reports")
            }
        }
        
        # Save report
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        print(f"\n{'='*80}")
        print("BATCH PROCESSING COMPLETE")
        print(f"{'='*80}")
        print(f"📊 Documents processed: {self.stats['documents_processed']}")
        print(f"📄 Forms filled: {self.stats['forms_filled']}")
        print(f"⏱️  Processing time: {processing_time:.2f} seconds" if processing_time else "⏱️  Processing time: N/A")
        print(f"✅ Success rate: {report['batch_processing_summary']['success_rate']:.1f}%")
        print(f"❌ Errors: {len(self.stats['errors'])}")
        print(f"📁 Output folder: {self.output_folder}")
        print(f"📋 Full report: {report_file}")
        
        if self.stats['errors']:
            print(f"\n⚠️  Errors encountered:")
            for i, error in enumerate(self.stats['errors'][:5], 1):  # Show first 5 errors
                print(f"  {i}. {error}")
            if len(self.stats['errors']) > 5:
                print(f"  ... and {len(self.stats['errors']) - 5} more errors (see full report)")
        
        return report_file
    
    def run_batch_processing(self):
        """
        Main batch processing workflow
        """
        self.stats['start_time'] = datetime.now()
        
        print(f"\n🚀 Starting Batch Processing")
        print(f"Documents folder: {self.documents_folder}")
        print(f"Forms folder: {self.forms_folder}")
        print(f"Output folder: {self.output_folder}")
        
        # Step 1: Discover files
        files = self.discover_files()
        
        if not files['documents']:
            print(f"❌ No documents found in {self.documents_folder}")
            return None
        
        if not files['forms']:
            print(f"❌ No forms found in {self.forms_folder}")
            return None
        
        # Step 2: Process documents
        workflow_result = self.process_documents_batch(files['documents'])
        
        if workflow_result['status'] != 'success':
            print("❌ Document processing failed. Cannot proceed with form filling.")
            return None
        
        # Step 3: Fill forms
        compiled_schema = workflow_result.get('compiled_schema', {})
        filled_forms = self.fill_forms_batch(files['forms'], compiled_schema)
        
        # Step 4: Generate report
        self.stats['end_time'] = datetime.now()
        report_file = self.generate_batch_report(workflow_result, filled_forms)
        
        return {
            'status': 'success',
            'report_file': report_file,
            'filled_forms': filled_forms,
            'stats': self.stats
        }

def main():
    """
    Main function for command-line usage
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Batch process documents and fill forms')
    parser.add_argument('--documents', '-d', default='Documents', 
                       help='Documents folder path (default: Documents)')
    parser.add_argument('--forms', '-f', default='Forms', 
                       help='Forms folder path (default: Forms)')
    parser.add_argument('--output', '-o', default='BatchOutput', 
                       help='Output folder path (default: BatchOutput)')
    
    args = parser.parse_args()
    
    # Create and run batch processor
    processor = BatchProcessor(
        documents_folder=args.documents,
        forms_folder=args.forms,
        output_folder=args.output
    )
    
    result = processor.run_batch_processing()
    
    if result and result['status'] == 'success':
        print(f"\n🎉 Batch processing completed successfully!")
        print(f"📋 Report: {result['report_file']}")
        return 0
    else:
        print(f"\n❌ Batch processing failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
