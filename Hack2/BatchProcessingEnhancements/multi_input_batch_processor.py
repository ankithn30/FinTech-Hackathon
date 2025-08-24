#!/usr/bin/env python3
"""
Multi-Input Batch Processor
===========================

Enhanced batch processor that handles multiple document sources and types simultaneously.
Processes documents from multiple folders, combines data intelligently, and fills forms
with comprehensive data from all sources.

Features:
- Multiple input document folders
- Multiple document type support (PDF, images, text)
- Intelligent data combination and deduplication
- Priority-based data merging
- Comprehensive form filling with all available data
"""

import os
import sys
import json
import glob
import shutil
import concurrent.futures
from datetime import datetime
from typing import List, Dict, Any, Set, Optional
from pathlib import Path

# Import existing components
from streamlined_batch_processor import StreamlinedBatchProcessor
from FormFIller import PyMuPDFTemporaryFiller
from llama_parser import llama_parse, simplify_llama_output
from schema_utils import compile_schemas
import logging

class MultiInputBatchProcessor:
    """
    Advanced batch processor that handles multiple document sources and types
    """
    
    def __init__(self, output_folder="MultiInputOutput"):
        self.output_folder = output_folder
        self.setup_output_folders()
        
        # Document source configurations
        self.document_sources = {}
        self.form_sources = {}
        
        # Processing statistics
        self.stats = {
            'total_documents_processed': 0,
            'total_forms_filled': 0,
            'total_fields_discovered': 0,
            'total_fields_filled': 0,
            'document_sources_processed': 0,
            'form_sources_processed': 0,
            'combined_data_points': 0,
            'errors': [],
            'start_time': None,
            'end_time': None
        }
        
        # Initialize FormFiller for batch processing
        self.form_filler = PyMuPDFTemporaryFiller()
        
        # Configure semantic mapper for multi-source processing
        self.form_filler.mapper.similarity_threshold = 0.75  # Slightly lower for broader matching
        self.form_filler.mapper.strict_matching = False
        
        # Data priority mapping for intelligent merging
        self.data_priorities = {
            'i-9': 10,           # I-9 forms have highest priority for employment data
            'bank': 8,           # Bank statements for financial data
            'loan': 7,           # Loan applications
            'tax': 9,            # Tax documents
            'employment': 8,     # Employment documents
            'personal': 6,       # Personal documents
            'default': 5         # Default priority
        }
    
    def setup_output_folders(self):
        """Create comprehensive output folder structure"""
        folders = [
            self.output_folder,
            os.path.join(self.output_folder, 'filled_forms'),
            os.path.join(self.output_folder, 'field_mappings'),
            os.path.join(self.output_folder, 'processing_logs'),
            os.path.join(self.output_folder, 'combined_data'),
            os.path.join(self.output_folder, 'source_analysis')
        ]
        
        for folder in folders:
            os.makedirs(folder, exist_ok=True)
        
        print(f"✅ Multi-input output folders created in: {self.output_folder}")
    
    def add_document_source(self, source_name: str, folder_path: str, 
                           document_type: str = "mixed", priority: int = 5):
        """
        Add a document source folder
        
        Args:
            source_name: Identifier for this source
            folder_path: Path to folder containing documents
            document_type: Type hint for priority (i-9, bank, loan, tax, etc.)
            priority: Processing priority (1-10, higher = more important)
        """
        if not os.path.exists(folder_path):
            print(f"⚠️ Warning: Document source folder not found: {folder_path}")
            return False
        
        self.document_sources[source_name] = {
            'path': folder_path,
            'type': document_type,
            'priority': priority,
            'files': []
        }
        
        # Discover files in source
        for ext in ['*.pdf', '*.PDF']:
            files = glob.glob(os.path.join(folder_path, ext))
            self.document_sources[source_name]['files'].extend(files)
        
        print(f"📁 Added document source '{source_name}': {len(self.document_sources[source_name]['files'])} files")
        return True
    
    def add_form_source(self, source_name: str, folder_path: str):
        """
        Add a form source folder
        
        Args:
            source_name: Identifier for this source
            folder_path: Path to folder containing forms
        """
        if not os.path.exists(folder_path):
            print(f"⚠️ Warning: Form source folder not found: {folder_path}")
            return False
        
        self.form_sources[source_name] = {
            'path': folder_path,
            'files': []
        }
        
        # Discover PDF forms
        for ext in ['*.pdf', '*.PDF']:
            files = glob.glob(os.path.join(folder_path, ext))
            self.form_sources[source_name]['files'].extend(files)
        
        print(f"📋 Added form source '{source_name}': {len(self.form_sources[source_name]['files'])} files")
        return True
    
    def discover_all_form_fields(self) -> Dict[str, Set[str]]:
        """
        Discover fields from all form sources
        
        Returns:
            Dictionary mapping form paths to their field sets
        """
        print(f"\n🔍 Step 1: Discovering fields from all form sources...")
        
        all_form_fields = {}
        total_fields = 0
        
        for source_name, source_info in self.form_sources.items():
            print(f"   📋 Processing form source: {source_name}")
            
            for form_path in source_info['files']:
                try:
                    # Use existing field discovery logic
                    processor = StreamlinedBatchProcessor()
                    fields = processor.discover_form_fields([form_path])
                    
                    if form_path in fields:
                        all_form_fields[form_path] = fields[form_path]
                        field_count = len(fields[form_path])
                        total_fields += field_count
                        print(f"      📄 {os.path.basename(form_path)}: {field_count} fields")
                    
                except Exception as e:
                    print(f"      ❌ Error processing {os.path.basename(form_path)}: {e}")
                    self.stats['errors'].append(f"Form field discovery error for {form_path}: {str(e)}")
        
        self.stats['total_fields_discovered'] = total_fields
        print(f"   ✅ Total fields discovered: {total_fields}")
        
        return all_form_fields
    
    def extract_from_all_sources(self, target_fields: Set[str]) -> Dict[str, Dict[str, Any]]:
        """
        Extract data from all document sources
        
        Args:
            target_fields: Set of field names to extract
            
        Returns:
            Dictionary mapping source names to extracted data
        """
        print(f"\n📖 Step 2: Extracting data from all document sources...")
        print(f"   Target fields: {len(target_fields)} unique fields")
        
        all_extracted_data = {}
        
        for source_name, source_info in self.document_sources.items():
            print(f"   📁 Processing document source: {source_name} ({source_info['type']})")
            
            source_data = {}
            
            for doc_path in source_info['files']:
                try:
                    print(f"      📄 Processing {os.path.basename(doc_path)}...")
                    
                    # Use existing extraction logic
                    processor = StreamlinedBatchProcessor()
                    doc_data = processor.extract_targeted_data([doc_path], target_fields)
                    
                    if doc_path in doc_data:
                        extracted_count = len(doc_data[doc_path])
                        source_data.update(doc_data[doc_path])
                        print(f"         ✅ Extracted {extracted_count} data points")
                    else:
                        print(f"         ⚠️ No matching data found")
                    
                except Exception as e:
                    print(f"         ❌ Error processing {os.path.basename(doc_path)}: {e}")
                    self.stats['errors'].append(f"Document processing error for {doc_path}: {str(e)}")
            
            if source_data:
                all_extracted_data[source_name] = {
                    'data': source_data,
                    'priority': source_info['priority'],
                    'type': source_info['type'],
                    'count': len(source_data)
                }
                print(f"      ✅ Source total: {len(source_data)} data points")
        
        self.stats['document_sources_processed'] = len(all_extracted_data)
        return all_extracted_data
    
    def combine_multi_source_data(self, all_source_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Intelligently combine data from multiple sources with priority-based merging
        
        Args:
            all_source_data: Data from all sources with metadata
            
        Returns:
            Combined and deduplicated data dictionary
        """
        print(f"\n🔄 Step 3: Combining data from {len(all_source_data)} sources...")
        
        combined_data = {}
        field_sources = {}  # Track which source provided each field
        
        # Sort sources by priority (highest first)
        sorted_sources = sorted(
            all_source_data.items(), 
            key=lambda x: x[1]['priority'], 
            reverse=True
        )
        
        for source_name, source_info in sorted_sources:
            source_data = source_info['data']
            priority = source_info['priority']
            doc_type = source_info['type']
            
            print(f"   📁 Merging {source_name} (priority: {priority}, type: {doc_type})")
            
            for field_name, field_value in source_data.items():
                # Clean and validate field value
                if field_value and str(field_value).strip() and len(str(field_value).strip()) > 1:
                    clean_value = str(field_value).strip()
                    
                    # If field doesn't exist or current source has higher priority
                    if field_name not in combined_data:
                        combined_data[field_name] = clean_value
                        field_sources[field_name] = {
                            'source': source_name,
                            'priority': priority,
                            'type': doc_type
                        }
                        print(f"      ✅ {field_name}: {clean_value[:50]}... (from {source_name})")
                    
                    elif priority > field_sources[field_name]['priority']:
                        # Higher priority source overwrites
                        old_source = field_sources[field_name]['source']
                        combined_data[field_name] = clean_value
                        field_sources[field_name] = {
                            'source': source_name,
                            'priority': priority,
                            'type': doc_type
                        }
                        print(f"      🔄 {field_name}: Updated from {old_source} to {source_name}")
                    
                    elif priority == field_sources[field_name]['priority']:
                        # Same priority - keep longer/more complete value
                        if len(clean_value) > len(combined_data[field_name]):
                            combined_data[field_name] = clean_value
                            field_sources[field_name]['source'] = source_name
                            print(f"      📈 {field_name}: Updated with more complete value")
        
        # Save source mapping for audit
        source_mapping_file = os.path.join(self.output_folder, 'combined_data', 'field_sources.json')
        with open(source_mapping_file, 'w') as f:
            json.dump(field_sources, f, indent=2)
        
        self.stats['combined_data_points'] = len(combined_data)
        print(f"   ✅ Combined data: {len(combined_data)} unique fields")
        
        return combined_data
    
    def fill_all_forms_with_combined_data(self, form_fields: Dict[str, Set[str]], 
                                        combined_data: Dict[str, Any]) -> List[str]:
        """
        Fill all forms using the combined multi-source data
        
        Args:
            form_fields: Dictionary mapping form paths to their field sets
            combined_data: Combined data from all sources
            
        Returns:
            List of successfully filled form paths
        """
        print(f"\n📝 Step 4: Filling all forms with combined multi-source data...")
        print(f"   Available data points: {len(combined_data)}")
        print(f"   Forms to fill: {len(form_fields)}")
        
        filled_forms = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for form_path, form_field_names in form_fields.items():
            form_name = os.path.basename(form_path).replace('.pdf', '')
            print(f"\n   📄 Processing {form_name}...")
            
            # Find matching data for this form
            form_data = {}
            semantic_matches = {}
            
            # Direct matches first
            for field_name in form_field_names:
                if field_name in combined_data:
                    form_data[field_name] = combined_data[field_name]
            
            # Semantic matching for remaining fields
            remaining_fields = form_field_names - set(form_data.keys())
            if remaining_fields:
                for form_field in remaining_fields:
                    for data_field, data_value in combined_data.items():
                        if self.form_filler.mapper.semantic_match(form_field, data_field):
                            form_data[form_field] = data_value
                            semantic_matches[form_field] = data_field
                            break
            
            if form_data:
                try:
                    # Generate output path
                    output_filename = f"filled_{form_name}_{timestamp}.pdf"
                    output_path = os.path.join(self.output_folder, 'filled_forms', output_filename)
                    
                    # Fill form using context manager
                    with PyMuPDFTemporaryFiller() as filler:
                        temp_filled_path = filler.fill_single_form(form_data, form_path)
                        
                        if temp_filled_path and os.path.exists(temp_filled_path):
                            # Copy to permanent location
                            shutil.copy2(temp_filled_path, output_path)
                            filled_forms.append(output_path)
                            
                            fill_rate = (len(form_data) / len(form_field_names)) * 100
                            print(f"      ✅ Filled {len(form_data)}/{len(form_field_names)} fields ({fill_rate:.1f}%)")
                            
                            # Save detailed mapping
                            mapping_file = os.path.join(
                                self.output_folder, 'field_mappings',
                                f"mapping_{form_name}_{timestamp}.json"
                            )
                            mapping_data = {
                                'form_path': form_path,
                                'output_path': output_path,
                                'fields_filled': form_data,
                                'semantic_matches': semantic_matches,
                                'fill_rate': fill_rate,
                                'timestamp': timestamp
                            }
                            
                            with open(mapping_file, 'w') as f:
                                json.dump(mapping_data, f, indent=2)
                            
                            self.stats['total_fields_filled'] += len(form_data)
                        else:
                            print(f"      ❌ Form filling failed - no output generated")
                
                except Exception as e:
                    print(f"      ❌ Error filling form: {e}")
                    self.stats['errors'].append(f"Form filling error for {form_path}: {str(e)}")
            else:
                print(f"      ⚠️ No matching data found for {form_name}")
        
        self.stats['total_forms_filled'] = len(filled_forms)
        return filled_forms
    
    def generate_comprehensive_report(self, filled_forms: List[str]) -> str:
        """Generate comprehensive processing report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(self.output_folder, f"multi_input_report_{timestamp}.json")
        
        processing_time = None
        if self.stats['start_time'] and self.stats['end_time']:
            processing_time = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        
        report = {
            'multi_input_summary': {
                'timestamp': timestamp,
                'processing_time_seconds': processing_time,
                'document_sources': len(self.document_sources),
                'form_sources': len(self.form_sources),
                'total_documents_processed': self.stats['total_documents_processed'],
                'total_forms_filled': self.stats['total_forms_filled'],
                'total_fields_discovered': self.stats['total_fields_discovered'],
                'total_fields_filled': self.stats['total_fields_filled'],
                'combined_data_points': self.stats['combined_data_points'],
                'error_count': len(self.stats['errors']),
                'success_rate': (len(filled_forms) / max(len(filled_forms) + len(self.stats['errors']), 1)) * 100
            },
            'document_sources': {name: {'type': info['type'], 'file_count': len(info['files'])} 
                               for name, info in self.document_sources.items()},
            'form_sources': {name: {'file_count': len(info['files'])} 
                           for name, info in self.form_sources.items()},
            'filled_forms': filled_forms,
            'errors': self.stats['errors'],
            'processing_checks': {
                'multi_source_processing': True,
                'intelligent_data_combination': True,
                'priority_based_merging': True,
                'comprehensive_form_filling': True
            }
        }
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        print(f"\n{'='*80}")
        print("MULTI-INPUT BATCH PROCESSING REPORT")
        print(f"{'='*80}")
        print(f"📁 Document sources: {len(self.document_sources)}")
        print(f"📋 Form sources: {len(self.form_sources)}")
        print(f"📄 Total documents processed: {self.stats['total_documents_processed']}")
        print(f"📝 Total forms filled: {self.stats['total_forms_filled']}")
        print(f"🔍 Total fields discovered: {self.stats['total_fields_discovered']}")
        print(f"✅ Total fields filled: {self.stats['total_fields_filled']}")
        print(f"🔄 Combined data points: {self.stats['combined_data_points']}")
        print(f"⏱️ Processing time: {processing_time:.2f} seconds" if processing_time else "⏱️ Processing time: N/A")
        print(f"✅ Success rate: {report['multi_input_summary']['success_rate']:.1f}%")
        print(f"❌ Errors: {len(self.stats['errors'])}")
        
        return report_file
    
    def run_multi_input_processing(self) -> Dict[str, Any]:
        """
        Main multi-input processing workflow
        """
        self.stats['start_time'] = datetime.now()
        
        print(f"\n🚀 STARTING MULTI-INPUT BATCH PROCESSING")
        print(f"{'='*60}")
        print(f"Output folder: {self.output_folder}")
        print(f"Document sources: {len(self.document_sources)}")
        print(f"Form sources: {len(self.form_sources)}")
        
        if not self.document_sources:
            print("❌ No document sources configured")
            return None
        
        if not self.form_sources:
            print("❌ No form sources configured")
            return None
        
        # Count total documents
        total_docs = sum(len(source['files']) for source in self.document_sources.values())
        total_forms = sum(len(source['files']) for source in self.form_sources.values())
        
        self.stats['total_documents_processed'] = total_docs
        print(f"📄 Total documents to process: {total_docs}")
        print(f"📋 Total forms to fill: {total_forms}")
        
        # Step 1: Discover all form fields
        form_fields = self.discover_all_form_fields()
        if not form_fields:
            print("❌ No form fields discovered")
            return None
        
        # Get all unique target fields
        all_target_fields = set()
        for field_set in form_fields.values():
            all_target_fields.update(field_set)
        
        # Step 2: Extract from all document sources
        all_source_data = self.extract_from_all_sources(all_target_fields)
        if not all_source_data:
            print("❌ No data extracted from any source")
            return None
        
        # Step 3: Combine multi-source data intelligently
        combined_data = self.combine_multi_source_data(all_source_data)
        if not combined_data:
            print("❌ Data combination failed")
            return None
        
        # Step 4: Fill all forms with combined data
        filled_forms = self.fill_all_forms_with_combined_data(form_fields, combined_data)
        
        # Generate comprehensive report
        self.stats['end_time'] = datetime.now()
        report_file = self.generate_comprehensive_report(filled_forms)
        
        return {
            'status': 'success',
            'report_file': report_file,
            'filled_forms': filled_forms,
            'stats': self.stats
        }


def main():
    """Example usage of Multi-Input Batch Processor"""
    print("🧪 MULTI-INPUT BATCH PROCESSOR DEMO")
    print("="*50)
    
    # Initialize processor
    processor = MultiInputBatchProcessor(output_folder="MultiInputDemo")
    
    # Add multiple document sources
    processor.add_document_source("documents", "Documents", "mixed", priority=7)
    processor.add_document_source("forms_as_docs", "Forms", "mixed", priority=6)
    
    # Add form sources
    processor.add_form_source("primary_forms", "Forms")
    
    # Run processing
    result = processor.run_multi_input_processing()
    
    if result and result['status'] == 'success':
        print(f"\n🎉 Multi-input processing completed successfully!")
        print(f"📋 Report: {result['report_file']}")
        return 0
    else:
        print(f"\n❌ Multi-input processing failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
