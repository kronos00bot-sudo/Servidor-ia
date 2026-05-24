import pdfplumber
import pandas as pd
import re
import os
from datetime import datetime

def extract_number_from_text(text):
    """Extract number from text, handling European format (point as thousand separator, comma as decimal)"""
    if not text:
        return None
    
    # Look for patterns like "1.234,56" or "1234,56" or "1.234" or "1234"
    # European format: point as thousand separator, comma as decimal
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

def extract_data_from_pdf(pdf_path, campo_code):
    """Extract data from PDF based on campo code"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = ""
            for page in pdf.pages:
                full_text += page.extract_text() + "\n"
            
            # For campo codes like (0505), (0510), (0670)
            if campo_code.startswith('(') and campo_code.endswith(')'):
                # Look for the pattern: campo code followed by the value on the same line or next line
                pattern = rf'{re.escape(campo_code)}\s*[:\-]?\s*([^\n\r]*)'
                match = re.search(pattern, full_text, re.IGNORECASE)
                if match:
                    value_text = match.group(1).strip()
                    # If not found on same line, look in the next few lines
                    if not value_text or len(value_text) < 2:
                        lines = full_text.split('\n')
                        for i, line in enumerate(lines):
                            if campo_code in line:
                                # Check next 2 lines
                                for j in range(1, 3):
                                    if i + j < len(lines):
                                        value_text = lines[i + j].strip()
                                        if value_text and len(value_text) >= 2:
                                            break
                                break
                    
                    return extract_number_from_text(value_text)
            
            # For specific text labels like "Total de bienes y derechos no exentos" or "Cuota a ingresar"
            else:
                # Look for the label and extract the number that follows
                lines = full_text.split('\n')
                for i, line in enumerate(lines):
                    if campo_code.lower() in line.lower():
                        # Check current line and next few lines for the number
                        for j in range(0, 4):
                            if i + j < len(lines):
                                text_to_check = lines[i + j].strip()
                                number = extract_number_from_text(text_to_check)
                                if number is not None:
                                    return number
        
        return None
    except Exception as e:
        print(f"Error processing {pdf_path}: {str(e)}")
        return None

def main():
    base_path = "/home/mloco/Documentos/IR"
    data = []
    
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
        
        # Iterate through persons
        for person_dir in sorted(os.listdir(year_path)):
            person_path = os.path.join(year_path, person_dir)
            if not os.path.isdir(person_path):
                continue
                
            recibido_path = os.path.join(person_path, "Recebido")
            if not os.path.exists(recibido_path):
                continue
            
            # Initialize data for this person/year
            record = {
                'Año': int(year),
                'Nombre': person_dir,
                'Patrimonio': None,
                'Renta Ahorro': None,
                'Renta General': None,
                'Impuesto Patrimonio': None,
                'Impuesto de la Renta': None
            }
            
            # Look for Renta PDF
            renta_pattern = f"*{person_dir}. Just. presentación Renta {year}.pdf"
            renta_files = []
            for f in os.listdir(recibido_path):
                if re.match(rf"{re.escape(person_dir)}\. Just\. presentación Renta {year}\.pdf$", f, re.IGNORECASE):
                    renta_files.append(os.path.join(recibido_path, f))
            
            # Look for Patrimonio PDF
            patrimonio_pattern = f"*{person_dir}. Just. presentación I. Patrimonio {year}.pdf"
            patrimonio_files = []
            for f in os.listdir(recibido_path):
                if re.match(rf"{re.escape(person_dir)}\. Just\. presentación I\. Patrimonio {year}\.pdf$", f, re.IGNORECASE):
                    patrimonio_files.append(os.path.join(recibido_path, f))
            
            # Also try without the "I." for some variations
            if not patrimonio_files:
                patrimonio_pattern_alt = f"*{person_dir}. Just. presentación Patrimonio {year}.pdf"
                for f in os.listdir(recibido_path):
                    if re.match(rf"{re.escape(person_dir)}\. Just\. presentación Patrimonio {year}\.pdf$", f, re.IGNORECASE):
                        patrimonio_files.append(os.path.join(recibido_path, f))
            
            # Extract data from Renta PDF
            if renta_files:
                renta_pdf = renta_files[0]
                record['Renta General'] = extract_data_from_pdf(renta_pdf, "(0505)")
                record['Renta Ahorro'] = extract_data_from_pdf(renta_pdf, "(0510)")
                record['Impuesto de la Renta'] = extract_data_from_pdf(renta_pdf, "(0670)")
            
            # Extract data from Patrimonio PDF
            if patrimonio_files:
                patrimonio_pdf = patrimonio_files[0]
                record['Patrimonio'] = extract_data_from_pdf(patrimonio_pdf, "Total de bienes y derechos no exentos")
                record['Impuesto Patrimonio'] = extract_data_from_pdf(patrimonio_pdf, "Cuota a ingresar")
            
            # Only add record if we found at least some data
            if any(v is not None for k, v in record.items() if k not in ['Año', 'Nombre']):
                data.append(record)
    
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
    
    print(f"Data extracted and saved to {output_path}")
    print(f"Total records: {len(df)}")
    print("\nFirst few records:")
    print(df.head())
    
    return df

if __name__ == "__main__":
    main()