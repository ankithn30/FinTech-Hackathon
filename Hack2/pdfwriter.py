#!/usr/bin/env python3
"""
PDF form filler using pdfrw
"""

from typing import Dict, Any
import pdfrw
from pdfrw import PdfWriter, PdfDict, PdfObject


def create_pdf_field_mapping(llama_data: Dict[str, Any], target_pdf_path: str) -> Dict[str, Any]:
    """
    Create a dynamic mapping from extracted data to PDF field names.
    This function reads the target PDF form and maps the extracted data to its fields.
    """
    try:
        # Read the target PDF to get its field names
        pdf = pdfrw.PdfReader(target_pdf_path)
        if not (pdf.Root.AcroForm and pdf.Root.AcroForm.Fields):
            return {}
        
        pdf_field_map = {}
        
        # Get all field names from the target PDF
        for field in pdf.Root.AcroForm.Fields:
            field_name = field.T if hasattr(field, 'T') else None
            if not field_name:
                continue
                
            clean_field_name = str(field_name).strip('()')
            field_type = field.FT if hasattr(field, 'FT') else None
            
            # Try to match with extracted data
            # First try exact match with normalized key names
            normalized_key = clean_field_name.lower().replace(' ', '_').replace('\t', '_')
            
            if normalized_key in llama_data:
                if field_type == '/Btn':  # Checkbox/button
                    pdf_field_map[field_name] = llama_data[normalized_key]
                else:  # Text/choice fields
                    pdf_field_map[field_name] = str(llama_data[normalized_key])
            else:
                # Try partial matching for similar field names
                for key, value in llama_data.items():
                    key_words = key.replace('_', ' ').lower()
                    field_words = clean_field_name.lower()
                    
                    if key_words in field_words or field_words in key_words:
                        if field_type == '/Btn':
                            pdf_field_map[field_name] = value
                        else:
                            pdf_field_map[field_name] = str(value)
                        break
        
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


if __name__ == "__main__":
    # Example: Simulate Llama output
    llama_output = {
        "name": "John Smith",
        "name_of_dependent": "Sarah Smith",
        "age_of_dependent": "12",
        "dropdown2": "Choice 2",
        "option_1": True,
        "option_2": False,
        "option_3": False,
    }
    fill_pdf_from_llama(llama_output, pdf_path="Sample.pdf", output_path="Sample_filled_pdfrw.pdf")
