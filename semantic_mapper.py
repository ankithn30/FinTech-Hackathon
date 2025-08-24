"""
Temporary Semantic Mapper
========================

Handles semantic field mapping to prevent incorrect field assignments.
Solves the core problem: Input {"Phone": "313-478-9080", "SSN": "123-45-6789"}
should map correctly to form fields, not assign all values to the first field.
"""

import difflib
import hashlib
import re
from typing import Dict, List, Optional, Tuple, Any
import logging
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class TemporarySemanticMapper:
    """
    Semantic field mapper that uses in-memory storage only.
    Maps extracted data keys to actual PDF form field names using similarity matching.
    """
    
    def __init__(self):
        self.session_fields: Dict[str, Dict[str, Any]] = {}  # {form_hash: {field_name: metadata}}
        self.semantic_cache: Dict[str, str] = {}  # {extracted_key: best_field_name}
        self.similarity_threshold = 0.6
        
        # Common field name patterns for better matching
        self.field_patterns = {
            'phone': ['phone', 'telephone', 'tel', 'mobile', 'cell', 'contact'],
            'ssn': ['ssn', 'social', 'security', 'social_security', 'ss_number'],
            'name': ['name', 'full_name', 'first_name', 'last_name', 'fname', 'lname'],
            'address': ['address', 'street', 'addr', 'location', 'residence'],
            'email': ['email', 'e_mail', 'mail', 'electronic_mail'],
            'date': ['date', 'birth_date', 'dob', 'birthday', 'born'],
            'zip': ['zip', 'postal', 'zipcode', 'postal_code'],
            'state': ['state', 'province', 'region'],
            'city': ['city', 'town', 'municipality'],
            'employer': ['employer', 'company', 'work', 'job', 'employment'],
            'income': ['income', 'salary', 'wage', 'earnings', 'pay'],
            'signature': ['signature', 'sign', 'signed', 'autograph']
        }
    
    def _generate_form_hash(self, form_path: str) -> str:
        """Generate a unique hash for the form based on path and modification time"""
        try:
            import os
            stat = os.stat(form_path)
            content = f"{form_path}_{stat.st_mtime}_{stat.st_size}"
            return hashlib.md5(content.encode()).hexdigest()
        except Exception:
            # Fallback to just path hash
            return hashlib.md5(form_path.encode()).hexdigest()
    
    def discover_fields_memory(self, form_path: str) -> Dict[str, Any]:
        """
        Discover form fields using PyMuPDF without any persistence.
        Returns field metadata in memory only.
        """
        form_hash = self._generate_form_hash(form_path)
        
        # Check if already discovered in this session
        if form_hash in self.session_fields:
            logger.debug(f"Using cached field discovery for {form_path}")
            return self.session_fields[form_hash]
        
        fields_metadata = {}
        
        try:
            # Open PDF with PyMuPDF
            doc = fitz.open(form_path)
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Get form widgets (form fields)
                widgets = page.widgets()
                
                for widget in widgets:
                    field_name = widget.field_name
                    if field_name:
                        # Extract field metadata
                        field_info = {
                            'name': field_name,
                            'type': widget.field_type_string,
                            'page': page_num,
                            'rect': widget.rect,
                            'value': widget.field_value or '',
                            'max_length': getattr(widget, 'text_maxlen', 0),
                            'flags': widget.field_flags,
                            'normalized_name': self._normalize_field_name(field_name)
                        }
                        
                        fields_metadata[field_name] = field_info
                        logger.debug(f"Discovered field: {field_name} (type: {field_info['type']})")
            
            doc.close()
            
            # Store in session memory
            self.session_fields[form_hash] = fields_metadata
            logger.info(f"Discovered {len(fields_metadata)} fields in {form_path}")
            
        except Exception as e:
            logger.error(f"Error discovering fields in {form_path}: {e}")
            # Return empty dict on error
            fields_metadata = {}
        
        return fields_metadata
    
    def _normalize_field_name(self, field_name: str) -> str:
        """Normalize field name for better matching"""
        if not field_name:
            return ""
        
        # Convert to lowercase and replace common separators
        normalized = field_name.lower()
        normalized = re.sub(r'[_\-\s\.]+', '', normalized)  # Remove all separators
        normalized = re.sub(r'[^\w]', '', normalized)
        
        return normalized
    
    def semantic_match(self, extracted_key: str, available_fields: List[str]) -> Optional[str]:
        """
        Find the best matching field name using semantic similarity.
        Returns field name with similarity score > threshold, or None.
        """
        if not extracted_key or not available_fields:
            return None
        
        # Check cache first
        cache_key = f"{extracted_key}_{hash(tuple(sorted(available_fields)))}"
        if cache_key in self.semantic_cache:
            return self.semantic_cache[cache_key]
        
        best_match = None
        best_score = 0.0
        
        extracted_normalized = self._normalize_field_name(extracted_key)
        
        # Try exact match first
        for field_name in available_fields:
            if extracted_normalized == self._normalize_field_name(field_name):
                best_match = field_name
                best_score = 1.0
                break
        
        # If no exact match, try pattern matching
        if not best_match:
            extracted_lower = extracted_key.lower()
            
            # Check against known patterns
            for pattern_key, pattern_words in self.field_patterns.items():
                if any(word in extracted_lower for word in pattern_words):
                    # Find fields that match this pattern
                    for field_name in available_fields:
                        field_lower = field_name.lower()
                        if any(word in field_lower for word in pattern_words):
                            score = difflib.SequenceMatcher(None, extracted_lower, field_lower).ratio()
                            if score > best_score and score > self.similarity_threshold:
                                best_match = field_name
                                best_score = score
        
        # If still no match, try general similarity matching
        if not best_match:
            for field_name in available_fields:
                score = difflib.SequenceMatcher(None, extracted_normalized, 
                                              self._normalize_field_name(field_name)).ratio()
                if score > best_score and score > self.similarity_threshold:
                    best_match = field_name
                    best_score = score
        
        # Cache the result
        if best_match:
            self.semantic_cache[cache_key] = best_match
            logger.debug(f"Semantic match: '{extracted_key}' -> '{best_match}' (score: {best_score:.3f})")
        else:
            logger.warning(f"No semantic match found for '{extracted_key}' in available fields")
        
        return best_match
    
    def map_data_to_fields(self, extracted_data: Dict[str, Any], form_path: str) -> Dict[str, Any]:
        """
        Maps extracted data to actual form field names using semantic matching.
        
        Takes: {"Phone": "313-478-9080", "SSN": "123-45-6789"}
        Returns: {"Phone_Number_1": "313-478-9080", "SSN_Field": "123-45-6789"}
        """
        if not extracted_data:
            return {}
        
        # Discover form fields
        form_fields = self.discover_fields_memory(form_path)
        
        if not form_fields:
            logger.warning(f"No form fields discovered in {form_path}")
            return {}
        
        available_field_names = list(form_fields.keys())
        mapped_data = {}
        unmapped_keys = []
        
        logger.info(f"Mapping {len(extracted_data)} data keys to {len(available_field_names)} form fields")
        
        # Map each extracted data key to a form field
        for extracted_key, value in extracted_data.items():
            if not extracted_key or value is None:
                continue
            
            # Find best matching field
            matched_field = self.semantic_match(extracted_key, available_field_names)
            
            if matched_field:
                # Convert value to string for PDF form compatibility
                mapped_data[matched_field] = str(value)
                logger.debug(f"Mapped: {extracted_key} -> {matched_field} = '{value}'")
            else:
                unmapped_keys.append(extracted_key)
                logger.warning(f"Could not map key: {extracted_key}")
        
        # Log mapping results
        logger.info(f"Successfully mapped {len(mapped_data)} fields, {len(unmapped_keys)} unmapped")
        if unmapped_keys:
            logger.warning(f"Unmapped keys: {unmapped_keys}")
        
        return mapped_data
    
    def get_field_suggestions(self, extracted_key: str, form_path: str, limit: int = 5) -> List[Tuple[str, float]]:
        """
        Get top field name suggestions with similarity scores for manual mapping.
        Returns list of (field_name, similarity_score) tuples.
        """
        form_fields = self.discover_fields_memory(form_path)
        
        if not form_fields:
            return []
        
        available_fields = list(form_fields.keys())
        suggestions = []
        
        extracted_normalized = self._normalize_field_name(extracted_key)
        
        for field_name in available_fields:
            score = difflib.SequenceMatcher(None, extracted_normalized, 
                                          self._normalize_field_name(field_name)).ratio()
            suggestions.append((field_name, score))
        
        # Sort by score descending and return top results
        suggestions.sort(key=lambda x: x[1], reverse=True)
        return suggestions[:limit]
    
    def clear_session_cache(self) -> None:
        """Clear all session data from memory"""
        fields_count = len(self.session_fields)
        cache_count = len(self.semantic_cache)
        
        self.session_fields.clear()
        self.semantic_cache.clear()
        
        logger.debug(f"Cleared session cache: {fields_count} field sets, {cache_count} semantic mappings")
    
    def get_session_stats(self) -> Dict[str, int]:
        """Get current session statistics"""
        return {
            'forms_processed': len(self.session_fields),
            'cached_mappings': len(self.semantic_cache),
            'total_fields_discovered': sum(len(fields) for fields in self.session_fields.values())
        }
