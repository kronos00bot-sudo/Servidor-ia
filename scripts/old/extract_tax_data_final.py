import pandas as pd
import os
import re

def find_matching_file(directory, person_name, year, doc_type_hints):
    """
    Find a PDF file in directory that matches:
    - Contains the person's name (as substring, case-insensitive)
    - Contains the year (as substring)
    - Contains at least one of the doc_type_hints
    - Ends with .pdf
    """
    person_name_lower = person_name.lower()
    year_str = str(year)
    
    for filename in os.listdir(directory):
        if not filename.lower().endswith('.pdf'):
            continue
        filename_lower = filename.lower()
        
        # Check if it contains the person name (as substring)
        if person_name_lower not in filename_lower:
            continue
            
        # Check if it contains the year
        if year_str not in filename_lower:
            continue
            
        # Check if it contains at least one of the doc_type hints
        if any(hint.lower() in filename_lower for hint in doc_type_hints):
            return os.path.join(directory, filename)
    
    return None

def main():
    base_path = "/home/mloco/Documentos/IR"
    data = []
    target_persons = ["Manoel", "Salome"]  # Enfocarnos solo en estos dos
    
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
            
            # Define document type hints to search for (flexible matching)
            renta_hints = ["Just. presentación Renta", "Renta"]
            patrimonio_hints = ["Just. presentación I. Patrimonio", "Just. presentación Patrimonio", "Patrimonio"]
            
            # Try to find Renta PDF
            renta_pdf = find_matching_file(recibido_path, person_dir, year, renta_hints)
            if renta_pdf:
                record['Disponible Renta'] = 'Sí'
                record['Archivo Renta'] = os.path.basename(renta_pdf)
            
            # Try to find Patrimonio PDF
            patrimonio_pdf = find_matching_file(recibido_path, person_dir, year, patrimonio_hints)
            if patrimonio_pdf:
                record['Disponible Patrimonio'] = 'Sí'
                record['Archivo Patrimonio'] = os.path.basename(patrimonio_pdf)
            
            # Always add record (even if no files found) to keep track
            data.append(record)
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Sort by Año and Nombre
    df = df.sort_values(['Año', 'Nombre']).reset_index(drop=True)
    
    # Save to Excel
    output_path = "/home/mloco/Documentos/resultado.xlsx"
    df.to_excel(output_path, index=False)
    
    print(f"\n✅ Disponibilidad de documentos guardada en {output_path}")
    print(f"Total records: {len(df)}")
    print("\n📊 Resumen de disponibilidad:")
    print(df[['Año', 'Nombre', 'Disponible Renta', 'Disponible Patrimonio']].to_string(index=False))
    
    # Show which files were found
    print("\n📄 Archivos encontrados:")
    for _, row in df.iterrows():
        if row['Disponible Renta'] == 'Sí' or row['Disponible Patrimonio'] == 'Sí':
            print(f"  {row['Año']} {row['Nombre']}:")
            if row['Disponible Renta'] == 'Sí':
                print(f"    Renta: {row['Archivo Renta']}")
            if row['Disponible Patrimonio'] == 'Sí':
                print(f"    Patrimonio: {row['Archivo Patrimonio']}")
    
    return df

if __name__ == "__main__":
    main()
