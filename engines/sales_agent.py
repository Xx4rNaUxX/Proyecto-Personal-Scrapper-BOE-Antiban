"""
Agente de Ventas IA (Fase 6)
Utiliza Ollama (LocalBrain) para redactar correos electrónicos en frío (Cold Emails)
altamente persuasivos y personalizados para cerrar ventas de dominios (BOPI) o hardware (BOE).
"""
import logging
from core.llm_brain import LocalBrain
from core.models import Vector

logger = logging.getLogger("arbitraje.sales_agent")

PROMPT_BOPI = """Eres un Closer de Ventas B2B de élite.
Acabamos de detectar que la marca "{marca}" ha caducado en la OEPM (Clases Niza: {clases}).
Hemos asegurado sus dominios .com y .es.
Escribe un correo de ventas en frío CORTO, muy persuasivo y profesional dirigido a un competidor directo en su sector.
El objetivo es venderles estos dominios estratégicos antes de que los coja otro competidor.
El correo no debe superar las 100 palabras. Tono: Urgencia, exclusividad, B2B. No pongas saludos largos.
Devuelve SOLO el asunto (Subject: ...) y el cuerpo del mensaje.
"""

PROMPT_BOE = """Eres un Experto en Venta de Hardware de Segunda Mano B2B.
Acabamos de ganar una subasta del Estado por el siguiente lote:
"{lote}"
El valor estimado de mercado del lote es de {valor}€.
Escribe un correo de ventas en frío CORTO y directo a una empresa de renting tecnológico o academia de informática.
Ofrece venderles el lote completo con un descuento agresivo (B2B).
El correo no debe superar las 100 palabras.
Devuelve SOLO el asunto (Subject: ...) y el cuerpo del mensaje.
"""

class SalesAgent:
    def __init__(self):
        self.brain = LocalBrain() # Reutilizamos la conexión de Fase 3
        
    async def generar_cold_email(self, vector: Vector, titulo: str, resumen: str, valor: float) -> str:
        """Genera un borrador de correo en frío según el tipo de oportunidad."""
        prompt = ""
        if vector == Vector.BOPI:
            # Extraer marca del titulo "Marca Caducada: Nombre"
            marca = titulo.replace("Marca Caducada: ", "").replace("Marca Libre: ", "")
            prompt = PROMPT_BOPI.format(marca=marca, clases=resumen.split("|")[0])
            
        elif vector == Vector.CONCURSAL:
            lote = titulo.replace("Liquidación BOE: ", "")
            prompt = PROMPT_BOE.format(lote=lote, valor=valor)
            
        else:
            return "El generador de ventas no aplica a este vector (Usa el generador legal para PLACSP)."

        # Desactivar JSON mode temporalmente para emails
        # En la implementación actual de LocalBrain, el format=json está hardcodeado,
        # pero podemos forzar que el modelo devuelva un json con el email.
        
        prompt += "\n\nResponde ÚNICAMENTE con un JSON con la estructura: {\"asunto\": \"...\", \"cuerpo\": \"...\"}"
        
        try:
            # Reutilizamos analizar_pliego que hace el POST JSON a Ollama
            respuesta = await self.brain.analizar_pliego(prompt) 
            
            # Formateamos el resultado
            asunto = respuesta.get("asunto", "Oportunidad Estratégica B2B")
            cuerpo = respuesta.get("cuerpo", "Hubo un error al redactar el correo.")
            
            return f"📧 ASUNTO: {asunto}\n\n{cuerpo}"
            
        except Exception as e:
            logger.error(f"Error generando cold email: {e}")
            return "Error de conexión con la IA de ventas."
