import pdfplumber
import pandas as pd
import re
import os
import unicodedata

def normalize_text(text):
    """Remove accents, diacritics, and convert to lowercase for loose matching."""
    if not text:
        return ""
    # Normalize unicode (decompose accented characters) and remove diacritics
    normalized = unicodedata.normalize('NFD', text)
    # Remove diacritics (combining characters)
    stripped = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    return stripped.lower()

def extract_number_from_text(text):
    """Extract number from text, handling European format (point as thousand separator, comma as decimal)"""
    if not text:
        return None
    
    text = text.strip()
    
    # Look for patterns like "1.234,56" or "1234,56" or "1.234" or "1234"
    match = re.search(r'[\d.]+\s*,\s*\d{2}', text)
    if match:
        num_str = match.group(0).replace('.', '').replace(',', '.')
        try:
            return float(num_str)
        except:
            pass
    
    # Look for integer with point as thousand separator: "1.234"
    match = re.search(r'\d{1,3}(?:\.\d{3})+(?!\d)', text)
    if match:
        num_str = match.group(0).replace('.', '')
        try:
            return float(num_str)
        except:
            pass
    
    # Look for simple decimal number
    match = re.search(r'\d+\.\d{2}', text)
    if match:
        num_str = match.group(0).replace('.', '')
        try:
            return float(num_str)
        except:
            pass
            
    # Look for simple integer
    match = re.search(r'\b\d{1,3}(?:,\d{3})*\b|\b\d+\b', text.replace('.', ''))
    if match:
        num_str = match.group(0).replace(',', '')
        try:
            return float(num_str)
        except:
            pass
    
    return None

def is_plausible_value(field_name, value):
    """Check if extracted value is plausible for the field"""
    if value is None:
        return False
    
    # Plausibility ranges (adjusted based on user-provided 2025 values)
    ranges = {
        'Patrimonio': (50000.0, 20000000.0),   # From 50k to 20M (based on Salome 2025: 13M)
        'Renta Ahorro': (0.0, 200000.0),       # Up to 200k
        'Renta General': (0.0, 800000.0),      # Up to 800k
        'Impuesto Patrimonio': (0.0, 200000.0), # Up to 200k
        'Impuesto de la Renta': (0.0, 800000.0) # Up to 800k
    }
    
    min_val, max_val = ranges.get(field_name, (0, float('inf')))
    return min_val <= value <= max_val

def extract_number_near_label(lines, label_variants, start_index, max_lines_away=3):
    """Look for a number near a label, starting from start_index"""
    for j in range(0, max_lines_away + 1):
        idx = start_index + j
        if idx < len(lines):
            text_to_check = lines[idx].strip()
            number = extract_number_from_text(text_to_check)
            if number is not None:
                return number, idx
    return None, None

def extract_data_from_pdf(pdf_path):
    """Extract all relevant data from a PDF"""
    data = {
        'Patrimonio': None,
        'Renta Ahorro': None,
        'Renta General': None,
        'Impuesto Patrimonio': None,
        'Impuesto de la Renta': None
    }
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
            
            if not full_text.strip():
                return data
            
            lines = full_text.split('\n')
            
            # Helper: find line index where label appears
            def find_label_line(label_variants):
                for i, line in enumerate(lines):
                    line_norm = normalize_text(line)
                    for variant in label_variants:
                        if normalize_text(variant) in line_norm:
                            return i
                return -1
            
            # Extract Renta General: (0505) → Base liquidable general
            renta_gen_line = find_label_line(["(0505)", "base liquidable general", "0505"])
            if renta_gen_line >= 0:
                val, _ = extract_number_near_label(lines, ["dummy"], renta_gen_line, max_lines_away=4)
                if val is not None and is_plausible_value('Renta General', val):
                    data['Renta General'] = val
            
            # Extract Renta Ahorro: (0510) → Base liquidable del ahorro
            renta_ahorro_line = find_label_line(["(0510)", "base liquidable del ahorro", "0510"])
            if renta_ahorro_line >= 0:
                val, _ = extract_number_near_label(lines, ["dummy"], renta_ahorro_line, max_lines_away=4)
                if val is not None and is_plausible_value('Renta Ahorro', val):
                    # Avoid duplicating Renta General value if too close
                    if data['Renta General'] is None or abs(val - data['Renta General']) > 1.0 or abs(renta_ahorro_line - renta_gen_line) > 3:
                        data['Renta Ahorro'] = val
            
            # Extract Impuesto de la Renta: (0670)
            ir_line = find_label_line(["(0670)", "0670"])
            if ir_line >= 0:
                val, _ = extract_number_near_label(lines, ["dummy"], ir_line, max_lines_away=4)
                if val is not None and is_plausible_value('Impuesto de la Renta', val):
                    data['Impuesto de la Renta'] = val
            
            # Extract Patrimonio: Total de bienes y derechos no exentos
            patrimonio_variants = [
                "total de bienes y derechos no exentos",
                "total de bienes y derechos",
                "total bienes y derechos",
                "bienes y derechos no exentos",
                "total de bienes",
                "activo total",
                "total activo"
            ]
            patrimonio_line = find_label_line(patrimonio_variants)
            if patrimonio_line >= 0:
                val, _ = extract_number_near_label(lines, ["dummy"], patrimonio_line, max_lines_away=4)
                if val is not None and is_plausible_value('Patrimonio', val):
                    data['Patrimonio'] = val
            
            # Extract Impuesto Patrimonio: Cuota a ingresar
            impuesto_patrimonio_variants = [
                "cuota a ingresar",
                "cuota ingresar",
                "cuota",
                "total cuota",
                "resultado patrimonial"
            ]
            impuesto_line = find_label_line(impuesto_patrimonio_variants)
            if impuesto_line >= 0:
                val, _ = extract_number_near_label(lines, ["dummy"], impuesto_line, max_lines_away=4)
                # Special check: reject 100.0 unless strong evidence (e.g., appears multiple times or near monetary context)
                if val is not None:
                    if abs(val - 100.0) < 0.01:
                        # Likely a false positive (page number, year, etc.)
                        # Only accept if we see strong monetary context nearby
                        line_text = normalize_text(lines[impuesto_line]) if impuesto_line < len(lines) else ""
                        if "euro" not in line_text and "€" not in line_text and "," not in lines[impuesto_line] and "." not in lines[impuesto_line]:
                            val = None  # Reject as likely false positive
                    if val is not None and is_plausible_value('Impuesto Patrimonio', val):
                        data['Impuesto Patrimonio'] = val
    
    except Exception as e:
        print(f"Error processing {pdf_path}: {str(e)}")
    
    return data

def find_matching_file(directory, person_name, year, doc_type_hints, exclude_hints=None):
    """Find a PDF file matching criteria using normalized names."""
    person_name_norm = normalize_text(person_name)
    year_str = str(year)
    
    for filename in os.listdir(directory):
        if not filename.lower().endswith('.pdf'):
            continue
        filename_norm = normalize_text(filename)
        
        if person_name_norm not in filename_norm:
            continue
        if year_str not in filename_norm:
            continue
        if not any(normalize_text(hint) in filename_norm for hint in doc_type_hints):
            continue
        if exclude_hints:
            if any(normalize_text(exclude) in filename_norm for exclude in exclude_hints):
                continue
        
        return os.path.join(directory, filename)
    
    return None

def main():
    base_path = "/home/mloco/Documentos/IR"
    data = []
    target_persons = ["Manoel", "Salome"]
    
    # Exclude borradores, versiones, etc.
    exclude_hints = ["borrador", "versión", "version", "corregido", "borra", "borr", "v2", "v3", "v4", "v5", "borr."]
    
    # Known correct values for 2025 (from user) - for validation only
    known_2025 = {
        "Manoel": {
            "Patrimonio": 934016.68,
            "Renta Ahorro": 42437.71,
            "Renta General": 50702.81,
            "Impuesto Patrimonio": 496.5,
            "Impuesto de la Renta": 12808.64
        },
        "Salome": {
            "Patrimonio": 13322748.56,
            "Renta Ahorro": 36543.53,
            "Renta General": 4490.83,
            "Impuesto Patrimonio": 50178.01,
            "Impuesto de la Renta": 6188.36
        }
    }
    
    # Iterate through years
    for year_dir in sorted(os.listdir(base_path)):
        year_path = os.path.join(base_path, year_dir)
        if not os.path.isdir(year_path):
            continue
        
        year_match = re.search(r'(\d{4})', year_dir)
        if not year_match:
            continue
        year = year_match.group(1)
        
        for person_dir in sorted(os.listdir(year_path)):
            if person_dir not in target_persons:
                continue
            
            person_path = os.path.join(year_path, person_dir)
            if not os.path.isdir(person_path):
                continue
            
            recibido_path = os.path.join(person_path, "Recebido")
            if not os.path.exists(recibido_path):
                continue
            
            # Initialize record
            record = {
                'Año': int(year),
                'Nombre': person_dir,
                'Patrimonio': None,
                'Renta Ahorro': None,
                'Renta General': None,
                'Impuesto Patrimonio': None,
                'Impuesto de la Renta': None
            }
            
            # Define document type hints
            renta_hints = ["Just. presentación Renta"]
            patrimonio_hints = ["Just. presentación I. Patrimonio", "Just. presentación Patrimonio"]
            
            # Find files
            renta_pdf = find_matching_file(recibido_path, person_dir, year, renta_hints, exclude_hints)
            patrimonio_pdf = find_matching_file(recibido_path, person_dir, year, patrimonio_hints, exclude_hints)
            
            # Extract data
            if renta_pdf:
                renta_data = extract_data_from_pdf(renta_pdf)
                record['Renta General'] = renta_data['Renta General']
                record['Renta Ahorro'] = renta_data['Renta Ahorro']
                record['Impuesto de la Renta'] = renta_data['Impuesto de la Renta']
            
            if patrimonio_pdf:
                patrimonio_data = extract_data_from_pdf(patrimonio_pdf)
                record['Patrimonio'] = patrimonio_data['Patrimonio']
                record['Impuesto Patrimonio'] = patrimonio_data['Impuesto Patrimonio']
            
            # Only add if we found at least one file
            if renta_pdf or patrimonio_pdf:
                data.append(record)
                
                # Print validation for 2025
                if year == "2025" and person_dir in known_2025:
                    print(f"\n🔍 Validación 2025 {person_dir}:")
                    print(f"   Patrimonio: extraído={record['Patrimonio']}, esperado={known_2025[person_dir]['Patrimonio']}")
                    print(f"   Renta Ahorro: extraído={record['Renta Ahorro']}, esperado={known_2025[person_dir]['Renta Ahorro']}")
                    print(f"   Renta General: extraído={record['Renta General']}, esperado={known_2025[person_dir]['Renta General']}")
                    print(f"   Impuesto Patrimonio: extraído={record['Impuesto Patrimonio']}, esperado={known_2025[person_dir]['Impuesto Patrimonio']}")
                    print(f"   Impuesto de la Renta: extraído={record['Impuesto de la Renta']}, esperado={known_2025[person_dir]['Impuesto de la Renta']}")
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Sort by Año and Nombre
    df = df.sort_values(['Año', 'Nombre']).reset_index(drop=True)
    
    # Format numbers to European style (point as thousand separator, comma as decimal)
    def format_number_european(val):
        if pd.isna(val) or val is None:
            return ""
        # Format with 2 decimal places, point as thousand separator, comma as decimal
        formatted = f"{val:,.2f}"
        # Convert to European format: swap comma and point
        formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
        return formatted
    
    # Apply formatting to numeric columns
    numeric_cols = ['Patrimonio', 'Renta Ahorro', 'Renta General', 'Impuesto Patrimonio', 'Impuesto de la Renta']
    for col in numeric_cols:
        df[col] = df[col].apply(format_number_european)
    
    # Save to Excel
    output_path = "/home/mloco/Documentos/resultado.xlsx"
    df.to_excel(output_path, index=False)
    
    print(f"\n✅ Extracción completada. Resultado guardado en {output_path}")
    print(f"Total records processed: {len(df)}")
    print("\n📊 Resultados:")
    print(df.to_string(index=False))
    
    return df

if __name__ == "__main__":
    main()
