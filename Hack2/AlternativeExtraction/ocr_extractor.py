"""
OCR-Based Document Extractor
============================

Advanced OCR extraction for forms that are difficult to parse but have clear visual structure.
Specifically designed for forms like I-9 that have consistent layouts but poor text extraction.

Features:
- High-quality OCR using Tesseract
- Form field detection using computer vision
- Coordinate-based field mapping
- Confidence scoring for extracted data
"""

import os
import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional
import pytesseract
from PIL import Image
import fitz  # PyMuPDF
import re
import json
from dataclasses import dataclass
from enum import Enum

class FieldType(Enum):
    TEXT = "text"
    DATE = "date"
    PHONE = "phone"
    EMAIL = "email"
    SSN = "ssn"
    ADDRESS = "address"
    CHECKBOX = "checkbox"

@dataclass
class ExtractedField:
    name: str
    value: str
    confidence: float
    field_type: FieldType
    coordinates: Tuple[int, int, int, int]  # x, y, width, height
    
class OCRExtractor:
    """
    Advanced OCR extractor for structured forms
    """
    
    def __init__(self):
        self.tesseract_config = '--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,()/-@: '
        
        # Common field patterns for I-9 and similar forms
        self.field_patterns = {
            'name': [
                r'(?:first|last|full)\s*name[:\s]*([A-Za-z\s]+)',
                r'name[:\s]*([A-Za-z\s]{2,30})',
                r'employee\s*name[:\s]*([A-Za-z\s]+)'
            ],
            'phone': [
                r'phone[:\s]*(\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4})',
                r'telephone[:\s]*(\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4})',
                r'(\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4})'
            ],
            'email': [
                r'email[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'e-mail[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
            ],
            'ssn': [
                r'social\s*security[:\s]*([0-9]{3}[-\s]?[0-9]{2}[-\s]?[0-9]{4})',
                r'ssn[:\s]*([0-9]{3}[-\s]?[0-9]{2}[-\s]?[0-9]{4})',
                r'([0-9]{3}[-\s][0-9]{2}[-\s][0-9]{4})'
            ],
            'date': [
                r'date[:\s]*([0-9]{1,2}[/\-][0-9]{1,2}[/\-][0-9]{2,4})',
                r'birth[:\s]*([0-9]{1,2}[/\-][0-9]{1,2}[/\-][0-9]{2,4})',
                r'([0-9]{1,2}[/\-][0-9]{1,2}[/\-][0-9]{2,4})'
            ],
            'address': [
                r'address[:\s]*([0-9]+\s+[A-Za-z\s,]+)',
                r'street[:\s]*([0-9]+\s+[A-Za-z\s,]+)',
                r'([0-9]+\s+[A-Za-z\s,]{10,50})'
            ]
        }
    
    def extract_from_pdf(self, pdf_path: str, dpi: int = 300) -> Dict[str, ExtractedField]:
        """
        Extract structured data from PDF using OCR
        
        Args:
            pdf_path: Path to PDF file
            dpi: Resolution for PDF to image conversion
            
        Returns:
            Dictionary of extracted fields
        """
        try:
            # Convert PDF to images
            images = self._pdf_to_images(pdf_path, dpi)
            
            all_extracted_fields = {}
            
            for page_num, image in enumerate(images):
                print(f"OCR Extractor: Processing page {page_num + 1}")
                
                # Preprocess image for better OCR
                processed_image = self._preprocess_image(image)
                
                # Extract text with coordinates
                ocr_data = self._extract_text_with_coordinates(processed_image)
                
                # Apply pattern matching to extract structured fields
                page_fields = self._extract_structured_fields(ocr_data, page_num)
                
                # Merge with existing fields (higher confidence wins)
                for field_name, field in page_fields.items():
                    if field_name not in all_extracted_fields or field.confidence > all_extracted_fields[field_name].confidence:
                        all_extracted_fields[field_name] = field
            
            print(f"OCR Extractor: Extracted {len(all_extracted_fields)} fields total")
            return all_extracted_fields
            
        except Exception as e:
            print(f"OCR Extractor Error: {e}")
            return {}
    
    def _pdf_to_images(self, pdf_path: str, dpi: int) -> List[np.ndarray]:
        """Convert PDF pages to images"""
        images = []
        
        try:
            doc = fitz.open(pdf_path)
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Convert to image
                mat = fitz.Matrix(dpi/72, dpi/72)
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                
                # Convert to OpenCV format
                nparr = np.frombuffer(img_data, np.uint8)
                image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                images.append(image)
            
            doc.close()
            return images
            
        except Exception as e:
            print(f"PDF to image conversion error: {e}")
            return []
    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for better OCR results
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (1, 1), 0)
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        
        # Morphological operations to clean up
        kernel = np.ones((1, 1), np.uint8)
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        return cleaned
    
    def _extract_text_with_coordinates(self, image: np.ndarray) -> Dict:
        """
        Extract text with bounding box coordinates using Tesseract
        """
        try:
            # Get detailed OCR data
            ocr_data = pytesseract.image_to_data(
                image, 
                config=self.tesseract_config,
                output_type=pytesseract.Output.DICT
            )
            
            return ocr_data
            
        except Exception as e:
            print(f"OCR text extraction error: {e}")
            return {}
    
    def _extract_structured_fields(self, ocr_data: Dict, page_num: int) -> Dict[str, ExtractedField]:
        """
        Extract structured fields using pattern matching on OCR results
        """
        extracted_fields = {}
        
        if not ocr_data or 'text' not in ocr_data:
            return extracted_fields
        
        # Combine all text into a single string for pattern matching
        full_text = ' '.join([text for text in ocr_data['text'] if text.strip()])
        
        # Apply patterns for each field type
        for field_name, patterns in self.field_patterns.items():
            best_match = None
            best_confidence = 0.0
            best_coords = (0, 0, 0, 0)
            
            for pattern in patterns:
                matches = re.finditer(pattern, full_text, re.IGNORECASE)
                
                for match in matches:
                    value = match.group(1) if match.groups() else match.group(0)
                    value = value.strip()
                    
                    if len(value) < 2:  # Skip very short matches
                        continue
                    
                    # Calculate confidence based on pattern specificity and value quality
                    confidence = self._calculate_confidence(field_name, value, pattern)
                    
                    if confidence > best_confidence:
                        best_match = value
                        best_confidence = confidence
                        best_coords = self._find_text_coordinates(value, ocr_data)
            
            if best_match and best_confidence > 0.5:  # Minimum confidence threshold
                field_type = self._determine_field_type(field_name)
                
                extracted_fields[field_name] = ExtractedField(
                    name=field_name,
                    value=best_match,
                    confidence=best_confidence,
                    field_type=field_type,
                    coordinates=best_coords
                )
        
        return extracted_fields
    
    def _calculate_confidence(self, field_name: str, value: str, pattern: str) -> float:
        """
        Calculate confidence score for extracted field
        """
        base_confidence = 0.7
        
        # Boost confidence for specific patterns
        if field_name == 'phone' and re.match(r'\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}', value):
            base_confidence = 0.95
        elif field_name == 'email' and '@' in value and '.' in value:
            base_confidence = 0.95
        elif field_name == 'ssn' and re.match(r'[0-9]{3}[-\s][0-9]{2}[-\s][0-9]{4}', value):
            base_confidence = 0.95
        elif field_name == 'date' and re.match(r'[0-9]{1,2}[/\-][0-9]{1,2}[/\-][0-9]{2,4}', value):
            base_confidence = 0.90
        
        # Reduce confidence for very short or very long values
        if len(value) < 3:
            base_confidence *= 0.5
        elif len(value) > 50:
            base_confidence *= 0.8
        
        return min(base_confidence, 1.0)
    
    def _determine_field_type(self, field_name: str) -> FieldType:
        """Determine the field type based on field name"""
        type_mapping = {
            'phone': FieldType.PHONE,
            'email': FieldType.EMAIL,
            'ssn': FieldType.SSN,
            'date': FieldType.DATE,
            'address': FieldType.ADDRESS,
            'name': FieldType.TEXT
        }
        return type_mapping.get(field_name, FieldType.TEXT)
    
    def _find_text_coordinates(self, text: str, ocr_data: Dict) -> Tuple[int, int, int, int]:
        """
        Find coordinates of text in OCR data
        """
        try:
            for i, ocr_text in enumerate(ocr_data['text']):
                if text.lower() in ocr_text.lower():
                    x = ocr_data['left'][i]
                    y = ocr_data['top'][i]
                    w = ocr_data['width'][i]
                    h = ocr_data['height'][i]
                    return (x, y, w, h)
        except:
            pass
        
        return (0, 0, 0, 0)
    
    def export_results(self, extracted_fields: Dict[str, ExtractedField], output_path: str):
        """
        Export extraction results to JSON
        """
        results = {
            'extraction_method': 'OCR',
            'total_fields': len(extracted_fields),
            'fields': {}
        }
        
        for field_name, field in extracted_fields.items():
            results['fields'][field_name] = {
                'value': field.value,
                'confidence': field.confidence,
                'type': field.field_type.value,
                'coordinates': field.coordinates
            }
        
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"OCR results exported to: {output_path}")

def main():
    """
    Example usage of OCR extractor
    """
    extractor = OCRExtractor()
    
    # Example with I-9 form
    pdf_path = "../Forms/i-9-1.pdf"  # Adjust path as needed
    
    if os.path.exists(pdf_path):
        print(f"Processing {pdf_path} with OCR extraction...")
        
        extracted_fields = extractor.extract_from_pdf(pdf_path)
        
        print("\n=== OCR EXTRACTION RESULTS ===")
        for field_name, field in extracted_fields.items():
            print(f"{field_name}: {field.value} (confidence: {field.confidence:.2f})")
        
        # Export results
        extractor.export_results(extracted_fields, "ocr_extraction_results.json")
        
    else:
        print(f"PDF file not found: {pdf_path}")
        print("Please place an I-9 form or similar document in the Forms folder")

if __name__ == "__main__":
    main()
