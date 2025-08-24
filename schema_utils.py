def compile_schemas(schemas):
    """
    Compiles multiple Sub-Agent schemas into a unified schema.
    Handles the new format: "Header Name: Meaning of this header"
    """
    unified_fields = []
    
    for schema in schemas:
        # Check if schema is a string (new format) or dict (old format)
        if isinstance(schema, str):
            # Parse the new Sub-Agent format
            lines = schema.strip().split('\n')
            for line in lines:
                line = line.strip()
                if ':' in line and line.startswith('I want to extract these fields:'):
                    continue  # Skip the header line
                if ':' in line and not line.startswith('I want to extract these fields:'):
                    # Parse "Header Name: Meaning" format
                    parts = line.split(':', 1)  # Split on first colon only
                    if len(parts) == 2:
                        header_name = parts[0].strip()
                        meaning = parts[1].strip()
                        unified_fields.append({
                            "name": header_name,
                            "meaning": meaning,
                            "type": "string"  # Default type
                        })
        elif isinstance(schema, dict) and "fields" in schema:
            # Handle old format for backward compatibility
            unified_fields.extend(schema["fields"])
        else:
            print(f"Warning: Unknown schema format: {type(schema)}")
    
    return {"fields": unified_fields}
