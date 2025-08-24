#!/usr/bin/env python3
"""
PDF form filler using pdfrw
"""

from typing import Dict, Any
import pdfrw
from pdfrw import PdfWriter, PdfDict, PdfObject


def decode_pdf_string(pdf_string):
    """
    Decode PDF string that might be in Unicode format
    """
    if not pdf_string:
        return ""
    
    pdf_str = str(pdf_string).strip('()')
    
    # Check if it's a Unicode string (starts with <FEFF)
    if pdf_str.startswith('<FEFF'):
        try:
            # Remove the <FEFF prefix and > suffix
            hex_string = pdf_str[5:-1] if pdf_str.endswith('>') else pdf_str[5:]
            # Convert hex pairs to characters
            decoded = ""
            for i in range(0, len(hex_string), 4):
                hex_pair = hex_string[i:i+4]
                if len(hex_pair) == 4:
                    char_code = int(hex_pair, 16)
                    decoded += chr(char_code)
            return decoded
        except Exception as e:
            print(f"Error decoding Unicode string {pdf_str}: {e}")
            return pdf_str
    
    return pdf_str

def create_pdf_field_mapping(llama_data: Dict[str, Any], target_pdf_path: str) -> Dict[str, Any]:
    """
    Create a dynamic mapping from extracted data to PDF field names.
    This function reads the target PDF form and maps the extracted data to its fields.
    """
    try:
        # Read the target PDF to get its field names
        pdf = pdfrw.PdfReader(target_pdf_path)
        if not (pdf.Root.AcroForm and pdf.Root.AcroForm.Fields):
            print("❌ No AcroForm fields found in PDF")
            return {}
        
        pdf_field_map = {}
        
        print(f"🔍 Analyzing {len(pdf.Root.AcroForm.Fields)} PDF fields...")
        
        # Get all field names from the target PDF
        for i, field in enumerate(pdf.Root.AcroForm.Fields):
            field_name = field.T if hasattr(field, 'T') else None
            if not field_name:
                continue
            
            # Decode the field name (handle Unicode encoding)
            clean_field_name = decode_pdf_string(field_name)
            field_type = field.FT if hasattr(field, 'FT') else None
            
            print(f"  Field {i+1}: '{clean_field_name}' (Type: {field_type})")
            
            # Try to match with extracted data
            # First try exact match with normalized key names
            normalized_key = clean_field_name.lower().replace(' ', '_').replace('\t', '_')
            
            # Try different matching strategies
            matched = False
            
            # Strategy 1: Exact match
            if normalized_key in llama_data:
                if field_type == '/Btn':  # Checkbox/button
                    pdf_field_map[field_name] = llama_data[normalized_key]
                else:  # Text/choice fields
                    pdf_field_map[field_name] = str(llama_data[normalized_key])
                matched = True
                print(f"    ✅ Exact match: {normalized_key} -> {llama_data[normalized_key]}")
            
            # Strategy 2: Partial matching for similar field names
            if not matched:
                for key, value in llama_data.items():
                    key_words = key.replace('_', ' ').lower()
                    field_words = clean_field_name.lower()
                    
                    # Check for partial matches
                    if (key_words in field_words or field_words in key_words or
                        any(word in field_words for word in key_words.split()) or
                        any(word in key_words for word in field_words.split())):
                        
                        if field_type == '/Btn':
                            pdf_field_map[field_name] = value
                        else:
                            pdf_field_map[field_name] = str(value)
                        matched = True
                        print(f"    ✅ Partial match: {key} -> {value}")
                        break
            
            # Strategy 3: Smart field name matching
            if not matched:
                field_lower = clean_field_name.lower()
                for key, value in llama_data.items():
                    key_lower = key.lower()
                    
                    # Common field mappings
                    if (('name' in field_lower and 'name' in key_lower) or
                        ('email' in field_lower and 'email' in key_lower) or
                        ('phone' in field_lower and 'phone' in key_lower) or
                        ('address' in field_lower and 'address' in key_lower)):
                        
                        if field_type == '/Btn':
                            pdf_field_map[field_name] = value
                        else:
                            pdf_field_map[field_name] = str(value)
                        matched = True
                        print(f"    ✅ Smart match: {key} -> {value}")
                        break
            
            if not matched:
                print(f"    ❌ No match found for field: {clean_field_name}")
        
        print(f"📊 Field mapping summary: {len(pdf_field_map)} out of {len(pdf.Root.AcroForm.Fields)} fields mapped")
        return pdf_field_map
        
    except Exception as e:
        print(f"Error creating PDF field mapping: {e}")
        return {}

def fill_pdf_from_llama(llama_data: Dict[str, Any], pdf_path: str, output_path: str) -> bool:
    """
    Fill a PDF's AcroForm fields using output from Llama schema.
    Args:
        llama_data: dict from Llama extractor (e.g., ContactInfo)
        pdf_path: input PDF path (uploaded blank form)
        output_path: output PDF path (filled form)
    Returns:
        True if filled and written successfully, else False.
    """
    # Create dynamic mapping based on the target PDF's fields
    pdf_field_map = create_pdf_field_mapping(llama_data, pdf_path)
    return fill_pdf_pdfrw(pdf_field_map, pdf_path, output_path)

def fill_pdf_pdfrw(data: Dict[str, Any], pdf_path: str = "Sample.pdf", output_path: str = "Sample_filled_pdfrw.pdf") -> bool:
    """
    Fill a PDF's AcroForm fields using pdfrw.

    Args:
        data: mapping of field name -> value
        pdf_path: input PDF path
        output_path: output PDF path

    Returns:
        True if filled and written successfully, else False.
    """
    try:
        # Read template
        template = pdfrw.PdfReader(pdf_path)

        # Ensure AcroForm exists with fields
        if not (template.Root.AcroForm and template.Root.AcroForm.Fields):
            print("❌ No AcroForm fields found in PDF")
            return False

        # Help some viewers render appearances
        template.Root.AcroForm.update(PdfDict(NeedAppearances=PdfObject('true')))

        fields = template.Root.AcroForm.Fields
        filled = 0

        # Show and fill fields
        for field in fields:
            name = field.T if hasattr(field, 'T') else None
            if not name:
                continue

            if name in data:
                field.V = str(data[name])
                # Clear appearance to force regeneration
                field.AP = ''
                filled += 1
                print(f"✓ Filled '{name}' with '{data[name]}'")
            else:
                # Not provided in data
                pass

        # Write output
        PdfWriter().write(output_path, template)
        print(f"🎉 Wrote filled PDF -> {output_path} (fields filled: {filled})")
        return True

    except Exception as e:
        print(f"❌ Error filling PDF with pdfrw: {e}")
        return False
