#!/usr/bin/env python3
"""
Jarvis - Agente de mantenimiento diario para análisis de Openclaw y Ollama
Envía reporte por correo a kronos00bot@gmail.com vía gog a las 3hs GMT+2
"""

import os
import subprocess
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import json

def analyze_openclaw_files():
    """Analiza archivos de Openclaw para mantenimiento"""
    results = {
        'timestamp': datetime.now().isoformat(),
        'openclaw_analysis': {},
        'ollama_analysis': {},
        'updates_available': [],
        'recommendations': []
    }
    
    # Buscar archivos de Openclaw
    openclaw_dirs = ['/opt/openclaw', '/var/lib/openclaw', '/home/user/openclaw', './openclaw']
    for dir_path in openclaw_dirs:
        if os.path.exists(dir_path):
            try:
                files = subprocess.run(['find', dir_path, '-type', 'f', '-name', '*.conf', '-o', '-name', '*.yaml', '-o', '-name', '*.yml'], 
                                     capture_output=True, text=True, timeout=10)
                if files.stdout.strip():
                    results['openclaw_analysis'][dir_path] = {
                        'config_files': len(files.stdout.strip().split('\n')),
                        'files': files.stdout.strip().split('\n')[:5]  # Primeros 5
                    }
            except Exception as e:
                results['openclaw_analysis'][dir_path] = {'error': str(e)}
    
    # Analizar Ollama
    try:
        # Verificar si Ollama está corriendo
        ollama_status = subprocess.run(['systemctl', 'is-active', 'ollama'], 
                                     capture_output=True, text=True, timeout=5)
        results['ollama_analysis']['service_status'] = ollama_status.stdout.strip()
        
        # Verificar modelos disponibles
        models_output = subprocess.run(['ollama', 'list'], 
                                     capture_output=True, text=True, timeout=10)
        if models_output.returncode == 0:
            results['ollama_analysis']['models'] = models_output.stdout.strip().split('\n')[1:]  # Excluir header
        
        # Verificar actualizaciones de Ollama
        try:
            update_check = subprocess.run(['curl', '-s', 'https://api.github.com/repos/ollama/ollama/releases/latest'], 
                                        capture_output=True, text=True, timeout=10)
            if update_check.returncode == 0:
                latest_release = json.loads(update_check.stdout)
                results['ollama_analysis']['latest_version'] = latest_release.get('tag_name', 'unknown')
        except:
            pass
            
    except Exception as e:
        results['ollama_analysis']['error'] = str(e)
    
    # Verificar actualizaciones del sistema
    try:
        # Verificar paquetes actualizables (sistema basado en Debian/Ubuntu)
        updatable = subprocess.run(['apt', 'list', '--upgradable'], 
                                 capture_output=True, text=True, timeout=15)
        if updatable.returncode == 0 and 'upgradable' in updatable.stdout:
            lines = updatable.stdout.strip().split('\n')[1:]  # Excluir header
            results['updates_available'] = [line.split('/')[0] for line in lines if line.strip()]
    except:
        pass
    
    # Generar recomendaciones
    if results['updates_available']:
        results['recommendations'].append(f"Actualizar {len(results['updates_available'])} paquetes disponibles")
    
    if 'ollama' in str(results.get('ollama_analysis', {})) and 'Service active' in str(results['ollama_analysis'].get('service_status', '')):
        results['recommendations'].append("Ollama está activo y funcionando correctamente")
    else:
        results['recommendations'].append("Revisar estado del servicio Ollama")
    
    return results

def send_email_report(report_data):
    """Envía el reporte por correo electrónico vía gog"""
    try:
        # Configuración de correo (asumiendo servidor local o gog)
        msg = MIMEMultipart()
        msg['From'] = 'jarvis@maintenance.local'
        msg['To'] = 'kronos00bot@gmail.com'
        msg['Subject'] = f'Reporte Diario de Mantenimiento - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
        
        # Crear cuerpo del mensaje
        body = f"""
REPORTE DIARIO DE MANTENIMIENTO - JARVIS
=========================================

Fecha y hora: {report_data['timestamp']}

ANÁLISIS DE OPENCLAW:
"""
        
        for path, data in report_data['openclaw_analysis'].items():
            body += f"\n  {path}:\n"
            if 'error' in data:
                body += f"    Error: {data['error']}\n"
            else:
                body += f"    Archivos de configuración encontrados: {data.get('config_files', 0)}\n"
                if data.get('files'):
                    body += f"    Ejemplos: {', '.join(data['files'][:3])}\n"
        
        body += f"\nANÁLISIS DE OLLAMA:\n"
        for key, value in report_data['ollama_analysis'].items():
            body += f"  {key}: {value}\n"
        
        body += f"\nACTUALIZACIONES DISPONIBLES:\n"
        if report_data['updates_available']:
            for update in report_data['updates_available'][:10]:  # Limitar a 10
                body += f"  - {update}\n"
            if len(report_data['updates_available']) > 10:
                body += f"  ... y {len(report_data['updates_available']) - 10} más\n"
        else:
            body += "  No hay actualizaciones disponibles\n"
        
        body += f"\nRECOMENDACIONES:\n"
        for rec in report_data['recommendations']:
            body += f"  - {rec}\n"
        
        body += f"""
---
Este reporte fue generado automáticamente por Jarvis (dpx/nemotron3-super:120b)
Para configurar el horario de ejecución, revisar el crontab del sistema.
"""
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Intentar enviar vía sendmail o SMTP local
        try:
            # Método 1: sendmail
            p = subprocess.Popen(["/usr/sbin/sendmail", "-t"], stdin=subprocess.PIPE)
            p.communicate(msg.as_string().encode('utf-8'))
            print("Reporte enviado vía sendmail")
            return True
        except:
            try:
                # Método 2: SMTP local
                server = smtplib.SMTP('localhost')
                server.send_message(msg)
                server.quit()
                print("Reporte enviado vía SMTP local")
                return True
            except Exception as e:
                print(f"Error enviando correo: {e}")
                # Guardar reporte localmente como fallback
                with open(f'/tmp/jarvis_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt', 'w') as f:
                    f.write(msg.as_string())
                print(f"Reporte guardado localmente en /tmp/jarvis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
                return False
                
    except Exception as e:
        print(f"Error preparando correo: {e}")
        return False

def main():
    """Función principal de Jarvis"""
    print(f"[{datetime.now()}] Jarvis iniciando análisis de mantenimiento...")
    
    # Ejecutar análisis
    report = analyze_openclaw_files()
    
    # Enviar reporte
    success = send_email_report(report)
    
    if success:
        print(f"[{datetime.now()}] Jarvis completado - Reporte enviado exitosamente")
    else:
        print(f"[{datetime.now()}] Jarvis completado - Reporte guardado localmente (fallback)")
    
    return 0

if __name__ == "__main__":
    exit(main())