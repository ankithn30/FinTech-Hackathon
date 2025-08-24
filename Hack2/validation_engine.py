import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

class ValidationEngine:
    """
    Core validation engine implementing tiered automation model for document processing.
    
    This engine applies confidence score thresholds and business rules to extracted data
    to determine final disposition with comprehensive audit trail for compliance.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None, human_review_queue: Optional[List] = None):
        """
        Initialize the ValidationEngine with dependencies.
        
        Args:
            logger: Logger instance for audit trail (creates default if None)
            human_review_queue: Queue for human-in-the-loop review (creates default if None)
        """
        self.logger = logger or self._create_default_logger()
        self.human_review_queue = human_review_queue or []
        
        # Define high-risk fields requiring mandatory human review
        self.mandatory_review_fields = {
            'total_amount', 'credit_amount', 'debit_amount', 'loan_amount',
            'principal_amount', 'interest_rate', 'apr', 'monthly_payment',
            'legal_declaration', 'compliance_statement', 'signature_date',
            'social_security_number', 'tax_id', 'account_number', 'routing_number',
            'authorization', 'consent', 'agreement', 'terms_acceptance'
        }
        
        # Confidence thresholds
        self.HIGH_CONFIDENCE_THRESHOLD = 98.0
        self.MEDIUM_CONFIDENCE_THRESHOLD = 90.0
        
        self.logger.info("ValidationEngine initialized with tiered automation model")
    
    def _create_default_logger(self) -> logging.Logger:
        """Create a default logger for validation audit trail."""
        logger = logging.getLogger('ValidationEngine')
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def validate_document(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main validation method implementing three-tiered automation logic.
        
        Args:
            extracted_data: JSON output from LlamaParse API containing extracted fields
            
        Returns:
            Dict containing validation summary with counts and flagged fields
        """
        validation_start_time = datetime.now()
        self.logger.info(f"Starting document validation at {validation_start_time}")
        
        # Initialize validation summary
        validation_summary = {
            'total_fields': 0,
            'auto_approved_count': 0,
            'auto_validated_count': 0,
            'flagged_for_review_count': 0,
            'flagged_fields': [],
            'validation_timestamp': validation_start_time.isoformat(),
            'processing_details': []
        }
        
        # Extract fields from the data structure
        fields_to_validate = self._extract_fields_from_data(extracted_data)
        validation_summary['total_fields'] = len(fields_to_validate)
        
        self.logger.info(f"Processing {len(fields_to_validate)} fields for validation")
        
        # Process each field through tiered validation
        for field_name, field_data in fields_to_validate.items():
            field_result = self._validate_field(field_name, field_data)
            validation_summary['processing_details'].append(field_result)
            
            # Update summary counts
            if field_result['processing_status'] == 'auto_approved':
                validation_summary['auto_approved_count'] += 1
            elif field_result['processing_status'] == 'auto_validated':
                validation_summary['auto_validated_count'] += 1
            elif field_result['processing_status'] == 'flagged_for_review':
                validation_summary['flagged_for_review_count'] += 1
                validation_summary['flagged_fields'].append({
                    'field_name': field_name,
                    'reason': field_result['reason_for_status'],
                    'extracted_value': field_result['extracted_value'],
                    'confidence_score': field_result.get('confidence_score', 'N/A')
                })
        
        # Log final summary
        self.logger.info(f"Validation completed: {validation_summary['auto_approved_count']} auto-approved, "
                        f"{validation_summary['auto_validated_count']} auto-validated, "
                        f"{validation_summary['flagged_for_review_count']} flagged for review")
        
        return validation_summary
    
    def _extract_fields_from_data(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract fields from various data structures that might come from LlamaParse.
        
        Args:
            extracted_data: Raw extracted data from LlamaParse
            
        Returns:
            Dict of field_name -> field_data mappings
        """
        fields = {}
        
        # Handle different possible data structures
        if 'fields' in extracted_data:
            # Schema-based structure from our agents
            for field in extracted_data.get('fields', []):
                if isinstance(field, dict) and 'header' in field:
                    field_name = field['header'].lower().replace(' ', '_')
                    fields[field_name] = {
                        'value': field.get('meaning', ''),
                        'confidence_score': field.get('confidence_score', 85.0),  # Default confidence
                        'raw_data': field
                    }
        
        # Handle direct field mappings
        elif isinstance(extracted_data, dict):
            for key, value in extracted_data.items():
                if key not in ['metadata', 'document_info', 'processing_info']:
                    fields[key.lower().replace(' ', '_')] = {
                        'value': value,
                        'confidence_score': 85.0,  # Default confidence
                        'raw_data': {'field': key, 'value': value}
                    }
        
        # If no fields found, create some sample fields for demonstration
        if not fields:
            self.logger.warning("No fields found in extracted data, creating sample fields")
            fields = {
                'applicant_name': {'value': 'Sample Name', 'confidence_score': 95.0},
                'total_amount': {'value': '1000.00', 'confidence_score': 92.0},
                'signature_date': {'value': '2024-01-15', 'confidence_score': 88.0}
            }
        
        return fields
    
    def _validate_field(self, field_name: str, field_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply tiered validation logic to a single field.
        
        Args:
            field_name: Name of the field being validated
            field_data: Field data including value and confidence score
            
        Returns:
            Dict containing validation result for this field
        """
        extracted_value = field_data.get('value', '')
        confidence_score = field_data.get('confidence_score', 0.0)
        
        # Initialize field result
        field_result = {
            'field_name': field_name,
            'extracted_value': extracted_value,
            'confidence_score': confidence_score,
            'processing_status': '',
            'reason_for_status': '',
            'validation_timestamp': datetime.now().isoformat()
        }
        
        # TIER 3: Check for mandatory human review fields first
        if self._is_mandatory_review_field(field_name):
            field_result['processing_status'] = 'flagged_for_review'
            field_result['reason_for_status'] = 'Compliance-critical field requiring mandatory human review'
            
            # Add to human review queue
            self.human_review_queue.append({
                'field_name': field_name,
                'value': extracted_value,
                'reason': 'Mandatory review - compliance critical',
                'priority': 'HIGH',
                'timestamp': datetime.now().isoformat()
            })
            
            self.logger.warning(f"Field '{field_name}' flagged for mandatory human review")
            return field_result
        
        # TIER 1: High-Confidence Automation (>98.0%)
        if confidence_score > self.HIGH_CONFIDENCE_THRESHOLD:
            field_result['processing_status'] = 'auto_approved'
            field_result['reason_for_status'] = f'High confidence score ({confidence_score}%) - automatic approval'
            
            self.logger.info(f"Field '{field_name}' auto-approved with {confidence_score}% confidence")
            return field_result
        
        # TIER 2: Rule-Based Validation (90.0% - 98.0%)
        if confidence_score >= self.MEDIUM_CONFIDENCE_THRESHOLD:
            business_rule_result = self._apply_business_rules(field_name, field_data, extracted_value)
            
            if business_rule_result['passed']:
                field_result['processing_status'] = 'auto_validated'
                field_result['reason_for_status'] = f'Medium confidence ({confidence_score}%) + business rule validation passed'
                
                self.logger.info(f"Field '{field_name}' auto-validated after business rule check")
            else:
                field_result['processing_status'] = 'flagged_for_review'
                field_result['reason_for_status'] = f'Business rule validation failed: {business_rule_result["reason"]}'
                
                # Add to human review queue
                self.human_review_queue.append({
                    'field_name': field_name,
                    'value': extracted_value,
                    'reason': f'Business rule failed: {business_rule_result["reason"]}',
                    'priority': 'MEDIUM',
                    'timestamp': datetime.now().isoformat()
                })
                
                self.logger.warning(f"Field '{field_name}' flagged due to business rule failure")
            
            return field_result
        
        # Below medium confidence threshold - flag for review
        field_result['processing_status'] = 'flagged_for_review'
        field_result['reason_for_status'] = f'Low confidence score ({confidence_score}%) below threshold'
        
        # Add to human review queue
        self.human_review_queue.append({
            'field_name': field_name,
            'value': extracted_value,
            'reason': f'Low confidence score: {confidence_score}%',
            'priority': 'LOW',
            'timestamp': datetime.now().isoformat()
        })
        
        self.logger.info(f"Field '{field_name}' flagged due to low confidence score")
        return field_result
    
    def _is_mandatory_review_field(self, field_name: str) -> bool:
        """
        Check if a field requires mandatory human review.
        
        Args:
            field_name: Name of the field to check
            
        Returns:
            bool: True if field requires mandatory review
        """
        field_name_lower = field_name.lower()
        
        # Check exact matches
        if field_name_lower in self.mandatory_review_fields:
            return True
        
        # Check partial matches for compliance-related fields
        compliance_keywords = ['legal', 'compliance', 'declaration', 'consent', 'authorization', 
                             'agreement', 'signature', 'ssn', 'social_security', 'tax_id']
        
        return any(keyword in field_name_lower for keyword in compliance_keywords)
    
    def _apply_business_rules(self, field_name: str, field_data: Dict[str, Any], extracted_value: str) -> Dict[str, Any]:
        """
        Apply business rules for medium-confidence fields.
        
        Args:
            field_name: Name of the field
            field_data: Complete field data
            extracted_value: Extracted value to validate
            
        Returns:
            Dict with 'passed' boolean and 'reason' string
        """
        # Business Rule 1: Invoice total amount validation
        if 'total' in field_name.lower() and 'amount' in field_name.lower():
            return self._validate_invoice_total(field_data, extracted_value)
        
        # Business Rule 2: Date format validation
        if 'date' in field_name.lower():
            return self._validate_date_format(extracted_value)
        
        # Business Rule 3: Numeric field validation
        if any(keyword in field_name.lower() for keyword in ['amount', 'rate', 'percent', 'number']):
            return self._validate_numeric_field(extracted_value)
        
        # Business Rule 4: Required field validation
        if any(keyword in field_name.lower() for keyword in ['name', 'address', 'phone', 'email']):
            return self._validate_required_field(extracted_value)
        
        # Default: pass if no specific rule applies
        return {'passed': True, 'reason': 'No specific business rule applicable'}
    
    def _validate_invoice_total(self, field_data: Dict[str, Any], total_amount: str) -> Dict[str, Any]:
        """
        Validate invoice total against sum of line items.
        
        Args:
            field_data: Field data that might contain line items
            total_amount: Total amount to validate
            
        Returns:
            Dict with validation result
        """
        try:
            total = float(total_amount.replace('$', '').replace(',', ''))
            
            # For demonstration, assume validation passes if total > 0
            # In real implementation, you'd sum line items from the document
            if total > 0:
                return {'passed': True, 'reason': 'Total amount validation passed'}
            else:
                return {'passed': False, 'reason': 'Total amount must be greater than zero'}
                
        except (ValueError, AttributeError):
            return {'passed': False, 'reason': 'Invalid total amount format'}
    
    def _validate_date_format(self, date_value: str) -> Dict[str, Any]:
        """Validate date format."""
        try:
            # Try common date formats
            from datetime import datetime
            for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%m-%d-%Y', '%d/%m/%Y']:
                try:
                    datetime.strptime(date_value, fmt)
                    return {'passed': True, 'reason': 'Valid date format'}
                except ValueError:
                    continue
            
            return {'passed': False, 'reason': 'Invalid date format'}
        except:
            return {'passed': False, 'reason': 'Date validation error'}
    
    def _validate_numeric_field(self, value: str) -> Dict[str, Any]:
        """Validate numeric fields."""
        try:
            # Remove common currency symbols and separators
            clean_value = value.replace('$', '').replace(',', '').replace('%', '').strip()
            float(clean_value)
            return {'passed': True, 'reason': 'Valid numeric format'}
        except (ValueError, AttributeError):
            return {'passed': False, 'reason': 'Invalid numeric format'}
    
    def _validate_required_field(self, value: str) -> Dict[str, Any]:
        """Validate required fields are not empty."""
        if value and value.strip():
            return {'passed': True, 'reason': 'Required field has value'}
        else:
            return {'passed': False, 'reason': 'Required field is empty'}
    
    def get_human_review_queue(self) -> List[Dict[str, Any]]:
        """
        Get all items currently in the human review queue.
        
        Returns:
            List of items flagged for human review
        """
        return self.human_review_queue.copy()
    
    def clear_human_review_queue(self) -> int:
        """
        Clear the human review queue and return count of cleared items.
        
        Returns:
            int: Number of items that were cleared
        """
        count = len(self.human_review_queue)
        self.human_review_queue.clear()
        self.logger.info(f"Cleared {count} items from human review queue")
        return count
    
    def export_audit_log(self, filepath: str) -> bool:
        """
        Export audit log to file for compliance purposes.
        
        Args:
            filepath: Path to save the audit log
            
        Returns:
            bool: True if export successful
        """
        try:
            # In a real implementation, you'd export actual log records
            audit_data = {
                'export_timestamp': datetime.now().isoformat(),
                'human_review_queue': self.human_review_queue,
                'validation_engine_config': {
                    'high_confidence_threshold': self.HIGH_CONFIDENCE_THRESHOLD,
                    'medium_confidence_threshold': self.MEDIUM_CONFIDENCE_THRESHOLD,
                    'mandatory_review_fields': list(self.mandatory_review_fields)
                }
            }
            
            with open(filepath, 'w') as f:
                json.dump(audit_data, f, indent=2)
            
            self.logger.info(f"Audit log exported to {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to export audit log: {e}")
            return False


# Example usage and testing
if __name__ == "__main__":
    # Create validation engine
    validation_engine = ValidationEngine()
    
    # Sample extracted data (simulating LlamaParse output)
    sample_data = {
        'fields': [
            {'header': 'Applicant Name', 'meaning': 'John Doe', 'confidence_score': 99.5},
            {'header': 'Total Amount', 'meaning': '15000.00', 'confidence_score': 92.3},
            {'header': 'Social Security Number', 'meaning': '123-45-6789', 'confidence_score': 95.8},
            {'header': 'Email Address', 'meaning': 'john.doe@email.com', 'confidence_score': 87.2},
            {'header': 'Signature Date', 'meaning': '2024-01-15', 'confidence_score': 94.1}
        ]
    }
    
    # Validate the document
    print("=" * 60)
    print("VALIDATION ENGINE DEMO")
    print("=" * 60)
    
    result = validation_engine.validate_document(sample_data)
    
    print(f"\nValidation Summary:")
    print(f"Total fields: {result['total_fields']}")
    print(f"Auto-approved: {result['auto_approved_count']}")
    print(f"Auto-validated: {result['auto_validated_count']}")
    print(f"Flagged for review: {result['flagged_for_review_count']}")
    
    if result['flagged_fields']:
        print(f"\nFields flagged for human review:")
        for field in result['flagged_fields']:
            print(f"  - {field['field_name']}: {field['reason']}")
    
    # Show human review queue
    review_queue = validation_engine.get_human_review_queue()
    if review_queue:
        print(f"\nHuman Review Queue ({len(review_queue)} items):")
        for item in review_queue:
            print(f"  - {item['field_name']} ({item['priority']} priority): {item['reason']}")
