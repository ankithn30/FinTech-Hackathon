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
        self.similarity_threshold = 0.95  # Require very high similarity for strict matching
        self.strict_matching = True  # Only fill fields with exclusive matches
        
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
        Find the best matching field name using strict semantic similarity.
        Only returns matches with very high confidence to prevent incorrect assignments.
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
        second_best_score = 0.0
        
        extracted_normalized = self._normalize_field_name(extracted_key)
        extracted_lower = extracted_key.lower()
        
        # Try exact match first (highest priority)
        for field_name in available_fields:
            if extracted_normalized == self._normalize_field_name(field_name):
                best_match = field_name
                best_score = 1.0
                break
        
        # If no exact match, try strict pattern matching
        if not best_match and self.strict_matching:
            # Check against known patterns with strict requirements
            for pattern_key, pattern_words in self.field_patterns.items():
                # Only proceed if extracted key strongly indicates this pattern
                extracted_pattern_matches = sum(1 for word in pattern_words if word in extracted_lower)
                if extracted_pattern_matches == 0:
                    continue
                
                # Find fields that match this pattern
                for field_name in available_fields:
                    field_lower = field_name.lower()
                    field_pattern_matches = sum(1 for word in pattern_words if word in field_lower)
                    
                    if field_pattern_matches > 0:
                        # Calculate strict similarity score
                        score = difflib.SequenceMatcher(None, extracted_lower, field_lower).ratio()
                        
                        # Additional boost for pattern matches
                        pattern_boost = min(extracted_pattern_matches, field_pattern_matches) * 0.1
                        score += pattern_boost
                        
                        if score > best_score:
                            second_best_score = best_score
                            best_score = score
                            best_match = field_name
                        elif score > second_best_score:
                            second_best_score = score
        
        # If still no match, try very strict general similarity matching
        if not best_match:
            for field_name in available_fields:
                score = difflib.SequenceMatcher(None, extracted_normalized, 
                                              self._normalize_field_name(field_name)).ratio()
                if score > best_score:
                    second_best_score = best_score
                    best_score = score
                    best_match = field_name
                elif score > second_best_score:
                    second_best_score = score
        
        # Apply strict matching criteria
        if self.strict_matching and best_match:
            # Require very high similarity threshold
            if best_score < self.similarity_threshold:
                logger.info(f"Rejecting match '{extracted_key}' -> '{best_match}' (score {best_score:.3f} < threshold {self.similarity_threshold})")
                best_match = None
            
            # Ensure the match is significantly better than alternatives (exclusive matching)
            elif second_best_score > 0 and (best_score - second_best_score) < 0.2:
                logger.info(f"Rejecting ambiguous match '{extracted_key}' -> '{best_match}' (best: {best_score:.3f}, second: {second_best_score:.3f})")
                best_match = None
        
        # Cache the result
        if best_match:
            self.semantic_cache[cache_key] = best_match
            logger.info(f"Strict semantic match: '{extracted_key}' -> '{best_match}' (score: {best_score:.3f})")
        else:
            logger.info(f"No exclusive match found for '{extracted_key}' - leaving unfilled for safety")
        
        return best_match
    
    def map_data_to_fields(self, extracted_data: Dict[str, Any], form_path: str) -> Dict[str, Any]:
        """
        Maps extracted data to actual form field names using strict semantic matching.
        Only fills fields with exclusive matches, leaves uncertain matches empty.
        
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
        
        logger.info(f"STRICT MATCHING: Processing {len(extracted_data)} data keys against {len(available_field_names)} form fields")
        logger.info(f"Available form fields: {available_field_names}")
        logger.info(f"Extracted data keys: {list(extracted_data.keys())}")
        
        # Map each extracted data key to a form field
        for extracted_key, value in extracted_data.items():
            if not extracted_key or value is None:
                continue
            
            # Find best matching field using strict criteria
            matched_field = self.semantic_match(extracted_key, available_field_names)
            
            if matched_field:
                # Convert value to string for PDF form compatibility
                mapped_data[matched_field] = str(value)
                logger.info(f"✅ FILLED: '{extracted_key}' -> '{matched_field}' = '{value}'")
            else:
                unmapped_keys.append(extracted_key)
                logger.info(f"❌ SKIPPED: '{extracted_key}' = '{value}' (no exclusive match found)")
        
        # Log final mapping results
        logger.info(f"STRICT MAPPING RESULTS:")
        logger.info(f"  ✅ Fields filled: {len(mapped_data)}")
        logger.info(f"  ❌ Fields skipped: {len(unmapped_keys)}")
        logger.info(f"  📊 Fill rate: {len(mapped_data)}/{len(extracted_data)} ({(len(mapped_data)/len(extracted_data)*100):.1f}%)")
        
        if mapped_data:
            logger.info(f"  Filled fields: {list(mapped_data.keys())}")
        if unmapped_keys:
            logger.info(f"  Skipped keys: {unmapped_keys}")
        
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
