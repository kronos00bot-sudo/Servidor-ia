import pandas as pd
import os
import re

def is_valid_pdf(filename, person_name, year, doc_type_hints, exclude_hints=None):
    """
    Check if a PDF file is valid based on:
    - Contains the person's name (as substring, case-insensitive)
    - Contains the year (as substring)
    - Contains at least one of the doc_type_hints
    - Does NOT contain any of the exclude_hints
    - Ends with .pdf
    """
    if not filename.lower().endswith('.pdf'):
        return False
    
    filename_lower = filename.lower()
    person_name_lower = person_name.lower()
    year_str = str(year).lower()
    
    # Must contain person name
    if person_name_lower not in filename_lower:
        return False
    
    # Must contain year
    if year_str not in filename_lower:
        return False
    
    # Must contain at least one of the doc_type hints
    if not any(hint.lower() in filename_lower for hint in doc_type_hints):
        return False
    
    # Must NOT contain any of the exclude hints (if provided)
    if exclude_hints:
        if any(exclude.lower() in filename_lower for exclude in exclude_hints):
            return False
    
    return True

def find_matching_file(directory, person_name, year, doc_type_hints, exclude_hints=None):
    """Find the first PDF file matching the criteria."""
    for filename in os.listdir(directory):
        if is_valid_pdf(filename, person_name, year, doc_type_hints, exclude_hints):
            return os.path.join(directory, filename)
    return None

def main():
    base_path = "/home/mloco/Documentos/IR"
    data = []
    target_persons = ["Manoel", "Salome"]
    
    # Palabras que indican que es un borrador o versión no oficial
    exclude_hints = ["borrador", "versión", "version", "corregido", "borra", "borr", "v2", "v3", "v4", "v5", "borr."]
    
    # Known correct values for 2025 (from user input)
    known_2025 = {
        "Manoel": {
            "Patrimonio": "934.016,68",
            "Renta Ahorro": "42.437,71",
            "Renta General": "50.702,81",
            "Impuesto Patrimonio": "496,50",
            "Impuesto de la Renta": "12.808,64"
        },
        "Salome": {
            "Patrimonio": "13.322.748,56",
            "Renta Ahorro": "36.543,53",
            "Renta General": "4.490,83",
            "Impuesto Patrimonio": "50.178,01",
            "Impuesto de la Renta": "6.188.36"  # Nota: corregido de 6.188,36 (el usuario usó punto como separador de miles?)
        }
    }
    # Nota: el usuario escribió "6.188,36" para Salome 2025 Impuesto de la Renta -> lo interpretamos como 6.188,36 (6 mil)
    # Pero lo escribió como "6.188,36" en el mensaje original, así que lo dejamos así.
    # Sin embargo, en el bloque anterior parece un typo: "6.188.36" vs "6.188,36". Vamos a usar el valor tal cual: "6.188,36"
    known_2025["Salome"]["Impuesto de la Renta"] = "6.188,36"
    
    # Iterate through years
    for year_dir in sorted(os.listdir(base_path)):
        year_path = os.path.join(base_path, year_dir)
        if not os.path.isdir(year_path):
            continue
            
        # Extract year from directory name (e.g., "IR 2021" -> "2021")
        year_match = re.search(r'(\d{4})', year_dir)
        if not year_match:
            continue
        year = year_match.group(1)
        
        # Iterate through persons (only Manoel and Salome)
        for person_dir in sorted(os.listdir(year_path)):
            if person_dir not in target_persons:
                continue  # Skip others
                
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
            
            # Define document type hints to search for (strict: must contain "Just. presentación")
            renta_hints = ["Just. presentación Renta"]
            patrimonio_hints = ["Just. presentación I. Patrimonio", "Just. presentación Patrimonio"]
            
            # Try to find Renta PDF
            renta_pdf = find_matching_file(recibido_path, person_dir, year, renta_hints, exclude_hints)
            if renta_pdf:
                record['Disponible Renta'] = 'Sí'
                record['Archivo Renta'] = os.path.basename(renta_pdf)
            
            # Try to find Patrimonio PDF
            patrimonio_pdf = find_matching_file(recibido_path, person_dir, year, patrimonio_hints, exclude_hints)
            if patrimonio_pdf:
                record['Disponible Patrimonio'] = 'Sí'
                record['Archivo Patrimonio'] = os.path.basename(patrimonio_pdf)
            
            # If we have known values for 2025, pre-fill them
            if year == "2025" and person_dir in known_2025:
                record['Patrimonio'] = known_2025[person_dir]['Patrimonio']
                record['Renta Ahorro'] = known_2025[person_dir]['Renta Ahorro']
                record['Renta General'] = known_2025[person_dir]['Renta General']
                record['Impuesto Patrimonio'] = known_2025[person_dir]['Impuesto Patrimonio']
                record['Impuesto de la Renta'] = known_2025[person_dir]['Impuesto de la Renta']
            
            # Always add record
            data.append(record)
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Sort by Año and Nombre
    df = df.sort_values(['Año', 'Nombre']).reset_index(drop=True)
    
    # Save to Excel
    output_path = "/home/mloco/Documentos/resultado.xlsx"
    df.to_excel(output_path, index=False)
    
    print(f"\n✅ Resultado guardado en {output_path}")
    print(f"Total records: {len(df)}")
    print("\n📊 Registros:")
    print(df.to_string(index=False))
    
    return df

if __name__ == "__main__":
    main()
