import requests
import json
import logging
from get_data import db_retriever

db_retrieve = db_retriever()

med_data = db_retrieve.get_med_data()

MEDICAL_CONTEXT = f"""Toma el rol de un médico especializado en la toma de decisiones clínicas. Tu objetivo es analizar detalladamente los síntomas y el historial clínico de los pacientes, teniendo en cuenta los siguientes puntos clave:

Signos de alarma: Identifica los síntomas o signos que indiquen peligro inmediato o que puedan poner en riesgo la vida del paciente. Estos deben ser tu prioridad al tomar una decisión.
Progresión de los síntomas: Evalúa cómo han evolucionado los síntomas en los últimos días, haciendo uso de la información del historial clínico proporcionado. Presta especial atención a si han empeorado, mejorado o si permanecen estables.
Historial clínico y causas subyacentes: Relaciona los síntomas actuales con enfermedades o condiciones previas especificadas en el historial, especialmente si el paciente padece MPID (Monitoreo Progresivo de Insuficiencia Degenerativa). Determina si los síntomas actuales agudizan esta enfermedad o si pueden derivarse de otros factores.

Ten en cuenta la siguiente informacion. causas de agudizacion: {med_data['causas_agudizacion']}, abreviaciones: {med_data['abreviaciones']}, 
signos de alarma: {med_data['signos_alarma']}, cosas a evitar: {med_data['cosas_evitar']}, tipos de MPID: {med_data['tipos_mpid']}.

Teniendo en cuenta lo anterior, analiza cada caso y elige la decisión más adecuada entre las siguientes opciones:
- Situación leve: No hay peligro ni urgencia. No es necesaria atención médica inmediata.
- Situación moderada: Aunque no hay peligro inmediato, existe la necesidad de estar en alerta. Es recomendable visitar al médico en el corto plazo.
- Situación urgente: Es necesario acudir a urgencias, pero no hace falta hacerlo con demasiada prisa. Puede haber riesgo si no se actúa a tiempo.
- Situación muy urgente: Es necesario acudir a urgencias lo antes posible, ya que la vida del paciente podría estar en peligro."""

api_key = "aF-Dco7h7mtMM8UuayArHrWHJkxQAUF2ptFHuLBpzpiGfRgPemK"
api_base_url = "https://api.straico.com/v0"

def generar_prompt_sintomas(sintomas, historial_clinico):
    prompt = f"""{MEDICAL_CONTEXT}

DATOS DEL PACIENTE A ANALIZAR:
----------------------------
Síntomas actuales: {sintomas}
Historial clínico: {historial_clinico}

Por favor proporciona:

1. Acción para el paciente: Indicación clara y precisa de lo que debe hacer.
2. Explicación del razonamiento que incluya:
   - Signos de alarma identificados (o ausencia)
   - Relevancia de la progresión de síntomas
   - Influencia del historial clínico
   - Observaciones adicionales importantes"""
    return prompt

def obtener_evaluacion_sintomas(prompt):
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
        if response.status_code == 201:
            data = response.json()
            if data['success']:
                return data['data']['completion']['choices'][0]['message']['content'].strip()
            logging.error(f"API error: {data.get('error', 'Unknown error')}")
        else:
            logging.error(f"Error: Received status code {response.status_code}")
    except Exception as e:
        logging.error(f"Error getting symptom evaluation: {e}")
    return None

def analizar_sintomas(sintomas, historial_clinico):
    prompt = generar_prompt_sintomas(sintomas, historial_clinico)
    evaluacion = obtener_evaluacion_sintomas(prompt)
    return evaluacion if evaluacion else "Error al obtener evaluación de síntomas"

if __name__ == "__main__":
    sintomas_ejemplo = {
        "principales": ["tos seca", "dificultad respiratoria"],
        "intensidad": "moderada",
        "duracion": "3 días"
    }
    
    historial_ejemplo = {
        "tipo_MPID": "FPI",
        "diagnostico": "hace 2 años",
        "tratamiento_actual": "pirfenidona",
        "comorbilidades": ["hipertension"]
    }
    
    progresion_ejemplo = "Empeoramiento gradual de la tos en últimos 3 días"
    
    resultado = analizar_sintomas(
        sintomas_ejemplo,
        historial_ejemplo, 
    )
    
    print("\nEvaluación de síntomas:")
    print(resultado)