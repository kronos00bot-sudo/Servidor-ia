import pdfplumber
import pandas as pd
import re
import os
import unicodedata

def normalize_text(text):
    if not text:
        return ""
    normalized = unicodedata.normalize('NFD', text)
    stripped = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    return stripped.lower()

def extract_number_from_text(text):
    if not text:
        return None
    text = text.strip()
    match = re.search(r'[\d.]+\s*,\s*\d{2}', text)
    if match:
        num_str = match.group(0).replace('.', '').replace(',', '.')
        try:
            return float(num_str)
        except:
            pass
    match = re.search(r'\d{1,3}(?:\.\d{3})+(?!\d)', text)
    if match:
        num_str = match.group(0).replace('.', '')
        try:
            return float(num_str)
        except:
            pass
    match = re.search(r'\d+\.\d{2}', text)
    if match:
        num_str = match.group(0).replace('.', '')
        try:
            return float(num_str)
        except:
            pass
    match = re.search(r'\b\d{1,3}(?:,\d{3})*\b|\b\d+\b', text.replace('.', ''))
    if match:
        num_str = match.group(0).replace(',', '')
        try:
            return float(num_str)
        except:
            pass
    return None

def is_plausible_value(field_name, value):
    if value is None:
        return False
    ranges = {
        'Patrimonio': (50000.0, 20000000.0),
        'Renta Ahorro': (0.0, 200000.0),
        'Renta General': (0.0, 800000.0),
        'Impuesto Patrimonio': (0.0, 200000.0),
        'Impuesto de la Renta': (0.0, 800000.0)
    }
    min_val, max_val = ranges.get(field_name, (0, float('inf')))
    return min_val <= value <= max_val

def extract_data_from_pdf_cautiously(pdf_path):
    """Extract data, but return None for fields that are not confidently extracted."""
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
            
            def find_label_line(label_variants):
                for i, line in enumerate(lines):
                    line_norm = normalize_text(line)
                    for variant in label_variants:
                        if normalize_text(variant) in line_norm:
                            return i
                return -1
            
            # Extract Renta General: (0505)
            renta_gen_line = find_label_line(["(0505)", "base liquidable general", "0505"])
            if renta_gen_line >= 0:
                # Look for number in a window, but prefer the line itself or next line
                for offset in [0, 1, 2]:
                    idx = renta_gen_line + offset
                    if idx < len(lines):
                        val = extract_number_from_text(lines[idx].strip())
                        if val is not None and is_plausible_value('Renta General', val):
                            data['Renta General'] = val
                            break
            
            # Extract Renta Ahorro: (0510)
            renta_ahorro_line = find_label_line(["(0510)", "base liquidable del ahorro", "0510"])
            if renta_ahorro_line >= 0:
                for offset in [0, 1, 2]:
                    idx = renta_ahorro_line + offset
                    if idx < len(lines):
                        val = extract_number_from_text(lines[idx].strip())
                        if val is not None and is_plausible_value('Renta Ahorro', val):
                            # Avoid duplicating Renta General if values are too close and lines are near
                            if data['Renta General'] is None or abs(val - data['Renta General']) > 5.0 or abs(renta_ahorro_line - renta_gen_line) > 4:
                                data['Renta Ahorro'] = val
                            break
            
            # Extract Impuesto de la Renta: (0670)
            ir_line = find_label_line(["(0670)", "0670"])
            if ir_line >= 0:
                for offset in [0, 1, 2]:
                    idx = ir_line + offset
                    if idx < len(lines):
                        val = extract_number_from_text(lines[idx].strip())
                        if val is not None and is_plausible_value('Impuesto de la Renta', val):
                            data['Impuesto de la Renta'] = val
                            break
            
            # Extract Patrimonio: Total de bienes y derechos no exentos
            patrimonio_variants = [
                "total de bienes y derechos no exentos",
                "total de bienes y derechos",
                "total bienes y derechos",
                "bienes y derechos no exentos",
                "total de bienes",
                "activo total"
            ]
            patrimonio_line = find_label_line(patrimonio_variants)
            if patrimonio_line >= 0:
                for offset in [0, 1, 2]:
                    idx = patrimonio_line + offset
                    if idx < len(lines):
                        val = extract_number_from_text(lines[idx].strip())
                        if val is not None and is_plausible_value('Patrimonio', val):
                            data['Patrimonio'] = val
                            break
            
            # Extract Impuesto Patrimonio: Cuota a ingresar
            impuesto_variants = [
                "cuota a ingresar",
                "cuota ingresar",
                "cuota",
                "total cuota",
                "resultado patrimonial"
            ]
            impuesto_line = find_label_line(impuesto_variants)
            if impuesto_line >= 0:
                for offset in [0, 1, 2]:
                    idx = impuesto_line + offset
                    if idx < len(lines):
                        val = extract_number_from_text(lines[idx].strip())
                        if val is not None:
                            # Special handling for 100.0: only accept if not likely a false positive
                            if abs(val - 100.0) < 0.01:
                                # Check context: is there a monetary sign or decimal nearby?
                                context = " ".join(lines[max(0, idx-2):min(len(lines), idx+3)]).lower()
                                if any(x in context for x in ['€', 'euro', ',', '.']) and not any(x in context for x in ['página', 'page', 'folio']):
                                    # Likely real
                                    pass
                                else:
                                    # Likely false positive (page number, year, etc.)
                                    val = None
                            if val is not None and is_plausible_value('Impuesto Patrimonio', val):
                                data['Impuesto Patrimonio'] = val
                            break
    
    except Exception as e:
        print(f"Error processing {pdf_path}: {str(e)}")
    
    return data

def find_matching_file(directory, person_name, year, doc_type_hints, exclude_hints=None):
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
    
    exclude_hints = ["borrador", "versión", "version", "corregido", "borra", "borr", "v2", "v3", "v4", "v5", "borr."]
    
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
            
            record = {
                'Año': int(year),
                'Nombre': person_dir,
                'Disponible Renta': 'No',
                'Disponible Patrimonio': 'No',
                'Archivo Renta': '',
                'Archivo Patrimonio': '',
                'Patrimonio': '',
                'Renta Ahorro': '',
                'Renta General': '',
                'Impuesto Patrimonio': '',
                'Impuesto de la Renta': ''
            }
            
            renta_hints = ["Just. presentación Renta"]
            patrimonio_hints = ["Just. presentación I. Patrimonio", "Just. presentación Patrimonio"]
            
            renta_pdf = find_matching_file(recibido_path, person_dir, year, renta_hints, exclude_hints)
            patrimonio_pdf = find_matching_file(recibido_path, person_dir, year, patrimonio_hints, exclude_hints)
            
            if renta_pdf:
                record['Disponible Renta'] = 'Sí'
                record['Archivo Renta'] = os.path.basename(renta_pdf)
                renta_data = extract_data_from_pdf_cautiously(renta_pdf)
                # Only keep if we got a value
                if renta_data['Renta General'] is not None:
                    record['Renta General'] = renta_data['Renta General']
                if renta_data['Renta Ahorro'] is not None:
                    record['Renta Ahorro'] = renta_data['Renta Ahorro']
                if renta_data['Impuesto de la Renta'] is not None:
                    record['Impuesto de la Renta'] = renta_data['Impuesto de la Renta']
            
            if patrimonio_pdf:
                record['Disponible Patrimonio'] = 'Sí'
                record['Archivo Patrimonio'] = os.path.basename(patrimonio_pdf)
                patrimonio_data = extract_data_from_pdf_cautiously(patrimonio_pdf)
                if patrimonio_data['Patrimonio'] is not None:
                    record['Patrimonio'] = patrimonio_data['Patrimonio']
                if patrimonio_data['Impuesto Patrimonio'] is not None:
                    record['Impuesto Patrimonio'] = patrimonio_data['Impuesto Patrimonio']
            
            # Only add record if at least one PDF was found
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
        formatted = f"{val:,.2f}"
        formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
        return formatted
    
    for col in ['Patrimonio', 'Renta Ahorro', 'Renta General', 'Impuesto Patrimonio', 'Impuesto de la Renta']:
        df[col] = df[col].apply(format_number_european)
    
    # Save to Excel
    output_path = "/home/mloco/Documentos/resultado.xlsx"
    df.to_excel(output_path, index=False)
    
    print(f"\n✅ Resultado guardado en {output_path}")
    print(f"Total records: {len(df)}")
    print("\n📊 Disponibilidad y datos extraídos (confiables):")
    print(df[['Año', 'Nombre', 'Disponible Renta', 'Disponible Patrimonio', 'Archivo Renta', 'Archivo Patrimonio']].to_string(index=False))
    print("\n📊 Valores extraídos (solo si confiables):")
    print(df[['Año', 'Nombre', 'Patrimonio', 'Renta Ahorro', 'Renta General', 'Impuesto Patrimonio', 'Impuesto de la Renta']].to_string(index=False))
    
    return df

if __name__ == "__main__":
    main()
