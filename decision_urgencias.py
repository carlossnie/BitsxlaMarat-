import requests
import json
import logging
from get_data import db_retriever
# API configuration
api_key = "Pq-4b2x89gmqDvOPP3tuAPLMVqYvKkXmYkPmLm2NMcyjaMhGp8H"
api_base_url = "https://api.straico.com/v0"

db_retrieve = db_retriever()

med_data = db_retrieve.get_med_data()

# Función para generar el prompt para Straico
def generar_prompt_urgencias(historial_clinico, pruebas_complementarias="No hechas aún", sintomas="Sin especificar"):
    prompt = f"""
    Paciente con MPID. Historia clínica: {historial_clinico}.
    Resultados de pruebas complementarias: {pruebas_complementarias}.
    Sintomas reportados: {sintomas}
    Realiza una valoración inicial y clasifica al paciente en uno de los siguientes escenarios clínicos:
    a) Diagnóstico concreto ≠ neumonía (devuelve tratamiento específico).
    b) Diagnóstico concreto de neumonía (distinción entre inmunosuprimidos e inmunocompetentes).
    c) No diagnóstico concreto (descartar TEP y realizar pruebas adicionales).

    Ten en cuenta la siguiente informacion. causas de agudizacion: {med_data['causas_agudizacion']}, abreviaciones: {med_data['abreviaciones']}, 
    signos de alarma: {med_data['signos_alarma']}, cosas a evitar: {med_data['cosas_evitar']}, tipos de MPID: {med_data['tipos_mpid']}.
    """
    return prompt

# Función para obtener la respuesta de la API de Straico
def obtener_respuesta_straico(prompt):
    url = f'{api_base_url}/prompt/completion'

    payload = json.dumps({
        "model": "anthropic/claude-3.5-sonnet",
        "message": prompt
        })
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
        }
   
    try:
        response = requests.post(url, headers=headers, data=payload)
        if response.status_code == 201:  # Straico returns 201 for successful completion
            data = response.json()
            if data['success']:
                suggestion = data['data']['completion']['choices'][0]['message']['content']
                return suggestion.strip()
            else:
                logging.error(f"API error: {data.get('error', 'Unknown error')}")
                return None
        else:
            logging.error(f"Error: Received status code {response.status_code} with message {response.text}")
            return None

    except Exception as e:
        logging.error(f"Error getting diagnosis suggestion: {e}")
        return None

# Función para clasificar el escenario clínico según la respuesta
def clasificar_escenario_clinico(respuesta_api):
    if "neumonía" in respuesta_api:
        if "inmunosuprimido" in respuesta_api:
            return "Neumonía en inmunosuprimido", respuesta_api
        elif "inmunocompetente" in respuesta_api:
            return "Neumonía en inmunocompetente", respuesta_api
    elif "diagnóstico concreto" in respuesta_api:
        return "Diagnóstico concreto ≠ neumonía", respuesta_api
    elif "no diagnóstico concreto" in respuesta_api:
        return "No diagnóstico concreto", respuesta_api
    else:
        return "Resultado indeterminado", respuesta_api

# Función principal
def gestionar_urgencias(historial_clinico, sintomas="Sin especificar", pruebas_complementarias="No hechas aún"):
    prompt = generar_prompt_urgencias(historial_clinico, pruebas_complementarias, sintomas)
    respuesta_api = obtener_respuesta_straico(prompt)
    if respuesta_api:
        clasificacion, recomendaciones = clasificar_escenario_clinico(respuesta_api)
        return clasificacion, recomendaciones
    return "Error al obtener respuesta", ""

if __name__ == '__main__':
    # Ejemplo de uso
    sintomas_paciente = ["fiebre", "tos seca", "dificultad para respirar"]
    historial_clinico = {
        "tipo_MPID": "UIP", 
        "cronicidad": "alta", 
        "tratamiento_base": "corticosteroides",
        "estado_inmunitario": "bajo",  # Inmunosuprimido
        "comorbilidades": ["hipertensión"]
    }
    pruebas_complementarias = {
        "gasometria": "PaO2/FiO2 280", 
        "rx_torax": "infiltrados bilaterales"
    }

    # Ejecutar el sistema de urgencias
    clasificacion, recomendaciones = gestionar_urgencias(historial_clinico, sintomas_paciente, pruebas_complementarias)
    print(f"Clasificación: {clasificacion}")
    print(f"Recomendaciones: {recomendaciones}")
