import logging
from get_data import db_retriever
from decision_sintomas import analizar_sintomas
from decision_urgencias import gestionar_urgencias

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Single database connection
connection_url = "mongodb+srv://Ilyas:NlzFSgDrycE0gRGt@cluster0.9t4o9.mongodb.net/"
db_retrieve = None

def initialize_db():
    global db_retrieve
    try:
        db_retrieve = db_retriever(connection=connection_url)
        db_retrieve.connect()
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False

def tomar_decision_medica(card_number, sintomas, en_urgencias, pruebas_complementarias="No hechas aún"):
    """
    Toma decisiones médicas basándose en si el paciente está en urgencias o no.
    """
    if not db_retrieve:
        if not initialize_db():
            return {"error": "Database connection failed"}

    try:
        # Get user medical data
        user_data = db_retrieve.get_user("health_card_number", card_number)
        if not user_data:
            raise ValueError(f"No medical data found for card number {card_number}")

        historial_clinico = user_data.get('medical_info', {})
        
        if en_urgencias:
            clasificacion, recomendaciones = gestionar_urgencias(
                historial_clinico=historial_clinico,
                sintomas=sintomas,
                pruebas_complementarias=pruebas_complementarias
            )
            return {
                "estado": "urgencias",
                "clasificacion": clasificacion,
                "recomendaciones": recomendaciones
            }
        else:
            evaluacion = analizar_sintomas(
                sintomas=sintomas,
                historial_clinico=historial_clinico
            )
            return {
                "estado": "sintomas",
                "evaluacion": evaluacion
            }

    except Exception as e:
        logger.error(f"Error in tomar_decision_medica: {e}")
        return {
            "error": str(e),
            "estado": "error"
        }

if __name__ == "__main__":
    try:
        # Test data
        test_card = "11"
        test_sintomas = ["fiebre", "tos"]
        
        # Test normal symptoms flow
        result = tomar_decision_medica(test_card, test_sintomas, en_urgencias=False)
        print("Normal symptoms result:", result)
        
        # Test emergency flow
        result = tomar_decision_medica(test_card, test_sintomas, en_urgencias=True)
        print("Emergency result:", result)
        
    finally:
        if db_retrieve:
            db_retrieve.close_connection()