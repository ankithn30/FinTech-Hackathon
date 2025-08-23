#!/usr/bin/env python3
"""
PDF form filler using pdfrw
"""

from typing import Dict, Any
import pdfrw
from pdfrw import PdfWriter, PdfDict, PdfObject


def fill_pdf_from_llama(llama_data: Dict[str, Any], pdf_path: str = "Sample.pdf", output_path: str = "Sample_filled_pdfrw.pdf") -> bool:
    """
    Fill a PDF's AcroForm fields using output from Llama schema.
    Args:
        llama_data: dict from Llama extractor (e.g., ContactInfo)
        pdf_path: input PDF path
        output_path: output PDF path
    Returns:
        True if filled and written successfully, else False.
    """
    # Map Llama schema keys to PDF field names
    pdf_field_map = {
        "(Name)": llama_data.get("name", ""),
        "(Phone)": llama_data.get("phone_number", ""),
        "(Address)": llama_data.get("address", ""),
        "(Email)": llama_data.get("email", "")
    }
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
        "phone_number": "555-1234",
        "address": "123 Main St",
        "email": "john@example.com"
    }
    fill_pdf_from_llama(llama_output)
