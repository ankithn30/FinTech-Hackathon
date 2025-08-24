#!/usr/bin/env python3
"""
Enhanced Data Extraction Engine
==============================

Optimized extraction pipeline with multiple extraction methods and intelligent fallbacks.
Focuses on maximizing data extraction accuracy and completeness.
"""

import os
import re
import json
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import logging
from pathlib import Path

# Import extraction components
from llama_parse import LlamaParse
from dotenv import load_dotenv
import fitz  # PyMuPDF for direct PDF text extraction
import anthropic

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class EnhancedExtractionEngine:
    """
    Multi-method extraction engine that combines:
    1. LlamaCloud parsing (primary)
    2. PyMuPDF direct extraction (fallback)
    3. AI-powered field detection (enhancement)
    4. Pattern-based extraction (backup)
    """
    
    def __init__(self):
        # Initialize LlamaCloud
        self.llama_api_key = os.getenv("LLAMA_CLOUD_API_KEY")
        if self.llama_api_key:
            self.llama_parser = LlamaParse(api_key=self.llama_api_key)
        else:
            self.llama_parser = None
            logger.warning("LlamaCloud API key not found - using fallback methods only")
        
        # Initialize Anthropic for AI enhancement
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        if self.anthropic_api_key:
            self.anthropic_client = anthropic.Anthropic(api_key=self.anthropic_api_key)
        else:
            self.anthropic_client = None
            logger.warning("Anthropic API key not found - AI enhancement disabled")
        
        # Extraction statistics
        self.stats = {
            'documents_processed': 0,
            'extraction_methods_used': [],
            'fields_extracted': 0,
            'confidence_scores': [],
            'errors': []
        }
        
        # Enhanced field patterns for better extraction
        self.field_patterns = {
            'name': [
                r'(?:full\s*)?name[:\s]*([A-Za-z\s\-\'\.]+)',
                r'(?:first|last)\s*name[:\s]*([A-Za-z\s\-\'\.]+)',
                r'applicant[:\s]*([A-Za-z\s\-\'\.]+)',
                r'employee[:\s]*([A-Za-z\s\-\'\.]+)'
            ],
            'phone': [
                r'phone[:\s]*([0-9\-\(\)\s\.x]+)',
                r'telephone[:\s]*([0-9\-\(\)\s\.x]+)',
                r'mobile[:\s]*([0-9\-\(\)\s\.x]+)',
                r'contact[:\s]*([0-9\-\(\)\s\.x]+)',
                r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b'
            ],
            'email': [
                r'e?mail[:\s]*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})',
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            ],
            'address': [
                r'address[:\s]*([A-Za-z0-9\s,\.\-#]+)',
                r'street[:\s]*([A-Za-z0-9\s,\.\-#]+)',
                r'residence[:\s]*([A-Za-z0-9\s,\.\-#]+)',
                r'\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd)'
            ],
            'ssn': [
                r'(?:ssn|social\s*security)[:\s]*([0-9\-]{9,11})',
                r'\b\d{3}-\d{2}-\d{4}\b',
                r'\b\d{9}\b'
            ],
            'date': [
                r'date[:\s]*([0-9\/\-]{8,10})',
                r'birth[:\s]*date[:\s]*([0-9\/\-]{8,10})',
                r'dob[:\s]*([0-9\/\-]{8,10})',
                r'\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b'
            ],
            'employer': [
                r'employer[:\s]*([A-Za-z\s&\.\,Inc]+)',
                r'company[:\s]*([A-Za-z\s&\.\,Inc]+)',
                r'organization[:\s]*([A-Za-z\s&\.\,Inc]+)'
            ],
            'income': [
                r'(?:income|salary|wage)[:\s]*\$?([0-9,\.]+)',
                r'\$[0-9,]+(?:\.\d{2})?'
            ],
            'signature': [
                r'signature[:\s]*([A-Za-z\s\-\'\.]+)',
                r'signed[:\s]*([A-Za-z\s\-\'\.]+)'
            ]
        }
    
    def extract_from_document(self, document_path: str, target_fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Main extraction method that uses multiple approaches for maximum data recovery
        
        Args:
            document_path: Path to the document to extract from
            target_fields: Optional list of specific fields to extract
            
        Returns:
            Dictionary of extracted data with confidence scores
        """
        if not os.path.exists(document_path):
            logger.error(f"Document not found: {document_path}")
            return {}
        
        logger.info(f"Starting enhanced extraction for: {os.path.basename(document_path)}")
        
        extraction_result = {
            'document': os.path.basename(document_path),
            'extracted_data': {},
            'confidence_scores': {},
            'extraction_methods': [],
            'timestamp': datetime.now().isoformat()
        }
        
        # Method 1: LlamaCloud parsing (highest quality)
        if self.llama_parser:
            try:
                llama_data = self._extract_with_llamacloud(document_path, target_fields)
                if llama_data:
                    extraction_result['extracted_data'].update(llama_data)
                    extraction_result['extraction_methods'].append('llamacloud')
                    logger.info(f"LlamaCloud extracted {len(llama_data)} fields")
            except Exception as e:
                logger.warning(f"LlamaCloud extraction failed: {e}")
                self.stats['errors'].append(f"LlamaCloud error: {str(e)}")
        
        # Method 2: Direct PyMuPDF extraction (fallback)
        try:
            pymupdf_data = self._extract_with_pymupdf(document_path, target_fields)
            if pymupdf_data:
                # Merge with existing data, preferring LlamaCloud results
                for key, value in pymupdf_data.items():
                    if key not in extraction_result['extracted_data']:
                        extraction_result['extracted_data'][key] = value
                extraction_result['extraction_methods'].append('pymupdf')
                logger.info(f"PyMuPDF extracted {len(pymupdf_data)} additional fields")
        except Exception as e:
            logger.warning(f"PyMuPDF extraction failed: {e}")
            self.stats['errors'].append(f"PyMuPDF error: {str(e)}")
        
        # Method 3: Pattern-based extraction (backup)
        try:
            pattern_data = self._extract_with_patterns(document_path, target_fields)
            if pattern_data:
                # Merge pattern data
                for key, value in pattern_data.items():
                    if key not in extraction_result['extracted_data']:
                        extraction_result['extracted_data'][key] = value
                extraction_result['extraction_methods'].append('patterns')
                logger.info(f"Pattern extraction found {len(pattern_data)} additional fields")
        except Exception as e:
            logger.warning(f"Pattern extraction failed: {e}")
            self.stats['errors'].append(f"Pattern error: {str(e)}")
        
        # Method 4: AI enhancement (if available)
        if self.anthropic_client and extraction_result['extracted_data']:
            try:
                enhanced_data = self._enhance_with_ai(extraction_result['extracted_data'], document_path)
                if enhanced_data:
                    extraction_result['extracted_data'].update(enhanced_data)
                    extraction_result['extraction_methods'].append('ai_enhancement')
                    logger.info("AI enhancement applied")
            except Exception as e:
                logger.warning(f"AI enhancement failed: {e}")
                self.stats['errors'].append(f"AI enhancement error: {str(e)}")
        
        # Calculate confidence scores
        extraction_result['confidence_scores'] = self._calculate_confidence_scores(
            extraction_result['extracted_data'], 
            extraction_result['extraction_methods']
        )
        
        # Update statistics
        self.stats['documents_processed'] += 1
        self.stats['fields_extracted'] += len(extraction_result['extracted_data'])
        self.stats['extraction_methods_used'].extend(extraction_result['extraction_methods'])
        
        logger.info(f"Extraction complete: {len(extraction_result['extracted_data'])} fields extracted using {extraction_result['extraction_methods']}")
        
        return extraction_result
    
    def _extract_with_llamacloud(self, document_path: str, target_fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Extract data using LlamaCloud parsing"""
        try:
            # Parse document with LlamaParse
            result = self.llama_parser.load_data(document_path)
            
            if not result:
                return {}
            
            # Extract text content
            document_text = result[0].text if hasattr(result[0], 'text') else str(result[0])
            
            # Use AI to extract structured data from the text
            if self.anthropic_client:
                extracted_data = self._ai_extract_from_text(document_text, target_fields)
                return extracted_data
            else:
                # Fallback to pattern extraction from LlamaCloud text
                return self._pattern_extract_from_text(document_text, target_fields)
                
        except Exception as e:
            logger.error(f"LlamaCloud extraction error: {e}")
            return {}
    
    def _extract_with_pymupdf(self, document_path: str, target_fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Extract data using PyMuPDF direct text extraction"""
        try:
            doc = fitz.open(document_path)
            full_text = ""
            
            # Extract text from all pages
            for page_num in range(len(doc)):
                page = doc[page_num]
                full_text += page.get_text() + "\n"
            
            doc.close()
            
            # Extract structured data from text
            return self._pattern_extract_from_text(full_text, target_fields)
            
        except Exception as e:
            logger.error(f"PyMuPDF extraction error: {e}")
            return {}
    
    def _extract_with_patterns(self, document_path: str, target_fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Extract data using regex patterns as backup method"""
        try:
            # First try to get text using PyMuPDF
            doc = fitz.open(document_path)
            full_text = ""
            for page_num in range(len(doc)):
                page = doc[page_num]
                full_text += page.get_text() + "\n"
            doc.close()
            
            return self._pattern_extract_from_text(full_text, target_fields)
            
        except Exception as e:
            logger.error(f"Pattern extraction error: {e}")
            return {}
    
    def _pattern_extract_from_text(self, text: str, target_fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Extract data from text using regex patterns"""
        extracted = {}
        
        # Determine which fields to extract
        fields_to_extract = target_fields if target_fields else self.field_patterns.keys()
        
        for field_type in fields_to_extract:
            if field_type.lower() in self.field_patterns:
                patterns = self.field_patterns[field_type.lower()]
                
                for pattern in patterns:
                    matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
                    if matches:
                        # Take the first reasonable match
                        value = matches[0].strip() if isinstance(matches[0], str) else str(matches[0]).strip()
                        if len(value) > 1 and len(value) < 200:  # Reasonable length
                            extracted[field_type] = value
                            break
        
        return extracted
    
    def _ai_extract_from_text(self, text: str, target_fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Use AI to extract structured data from text"""
        if not self.anthropic_client:
            return {}
        
        try:
            # Create extraction prompt
            fields_prompt = f"specific fields: {', '.join(target_fields)}" if target_fields else "common form fields like name, phone, email, address, SSN, date of birth, employer, income, signature"
            
            prompt = f"""
            Extract {fields_prompt} from the following document text.
            
            Return ONLY a JSON object with the extracted data. Use exact field names when possible.
            Only include fields that have actual values (not empty, N/A, or placeholder text).
            
            Document text:
            {text[:4000]}  # Limit text to avoid token limits
            
            JSON:
            """
            
            response = self.anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse JSON response
            response_text = response.content[0].text.strip()
            
            # Extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_text = response_text[json_start:json_end]
                extracted_data = json.loads(json_text)
                
                # Filter and clean the data
                cleaned_data = {}
                for key, value in extracted_data.items():
                    if value and str(value).strip() not in ["", "N/A", "None", "null", "undefined"]:
                        cleaned_data[key] = str(value).strip()
                
                return cleaned_data
            
        except Exception as e:
            logger.error(f"AI extraction error: {e}")
        
        return {}
    
    def _enhance_with_ai(self, existing_data: Dict[str, Any], document_path: str) -> Dict[str, Any]:
        """Use AI to enhance and validate existing extracted data"""
        if not self.anthropic_client or not existing_data:
            return {}
        
        try:
            prompt = f"""
            Review and enhance the following extracted data from a document.
            
            Current extracted data:
            {json.dumps(existing_data, indent=2)}
            
            Please:
            1. Validate the data format (fix phone numbers, dates, etc.)
            2. Add any missing common fields if you can infer them
            3. Standardize field names (use consistent naming)
            
            Return ONLY a JSON object with the enhanced data:
            """
            
            response = self.anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text.strip()
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_text = response_text[json_start:json_end]
                enhanced_data = json.loads(json_text)
                
                # Only return new/improved fields
                improvements = {}
                for key, value in enhanced_data.items():
                    if key not in existing_data or (value and value != existing_data.get(key)):
                        improvements[key] = value
                
                return improvements
            
        except Exception as e:
            logger.error(f"AI enhancement error: {e}")
        
        return {}
    
    def _calculate_confidence_scores(self, extracted_data: Dict[str, Any], methods_used: List[str]) -> Dict[str, float]:
        """Calculate confidence scores for extracted data"""
        confidence_scores = {}
        
        for field, value in extracted_data.items():
            score = 0.5  # Base score
            
            # Boost score based on extraction methods used
            if 'llamacloud' in methods_used:
                score += 0.3
            if 'ai_enhancement' in methods_used:
                score += 0.2
            if 'pymupdf' in methods_used:
                score += 0.1
            
            # Boost score based on data quality
            if value and len(str(value).strip()) > 2:
                score += 0.1
            
            # Field-specific validation
            if field.lower() in ['phone', 'telephone']:
                if re.match(r'^\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}$', str(value)):
                    score += 0.2
            elif field.lower() in ['email', 'e_mail']:
                if re.match(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$', str(value)):
                    score += 0.2
            elif field.lower() in ['ssn', 'social_security']:
                if re.match(r'^\d{3}-\d{2}-\d{4}$', str(value)):
                    score += 0.2
            
            confidence_scores[field] = min(1.0, score)  # Cap at 1.0
        
        return confidence_scores
    
    def get_extraction_stats(self) -> Dict[str, Any]:
        """Get extraction statistics"""
        return {
            'documents_processed': self.stats['documents_processed'],
            'total_fields_extracted': self.stats['fields_extracted'],
            'extraction_methods_used': list(set(self.stats['extraction_methods_used'])),
            'average_fields_per_document': self.stats['fields_extracted'] / max(self.stats['documents_processed'], 1),
            'error_count': len(self.stats['errors']),
            'errors': self.stats['errors'][-5:]  # Last 5 errors
        }
    
    def batch_extract(self, document_paths: List[str], target_fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Extract data from multiple documents"""
        results = []
        
        logger.info(f"Starting batch extraction for {len(document_paths)} documents")
        
        for doc_path in document_paths:
            try:
                result = self.extract_from_document(doc_path, target_fields)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to extract from {doc_path}: {e}")
                results.append({
                    'document': os.path.basename(doc_path),
                    'extracted_data': {},
                    'error': str(e)
                })
        
        logger.info(f"Batch extraction complete: {len(results)} documents processed")
        return results


def main():
    """Test the enhanced extraction engine"""
    engine = EnhancedExtractionEngine()
    
    # Test with a sample document
    test_docs = []
    
    # Look for test documents
    for folder in ['Documents', 'uploads', '.']:
        if os.path.exists(folder):
            for file in os.listdir(folder):
                if file.lower().endswith('.pdf'):
                    test_docs.append(os.path.join(folder, file))
                    break  # Just test one document
    
    if test_docs:
        print(f"🧪 Testing enhanced extraction with: {test_docs[0]}")
        result = engine.extract_from_document(test_docs[0])
        
        print(f"\n📊 Extraction Results:")
        print(f"Document: {result['document']}")
        print(f"Methods used: {result['extraction_methods']}")
        print(f"Fields extracted: {len(result['extracted_data'])}")
        
        if result['extracted_data']:
            print(f"\n📋 Extracted Data:")
            for field, value in result['extracted_data'].items():
                confidence = result['confidence_scores'].get(field, 0)
                print(f"  {field}: {value} (confidence: {confidence:.2f})")
        
        print(f"\n📈 Engine Stats:")
        stats = engine.get_extraction_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
    else:
        print("❌ No PDF documents found for testing")


if __name__ == "__main__":
    main()
