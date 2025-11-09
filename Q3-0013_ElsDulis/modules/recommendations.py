import os
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq
# Si prefieres OpenAI, cambia la línea de arriba por:
# from langchain_openai import ChatOpenAI

# Cargar variables de entorno (API key)
load_dotenv()

def get_skill_gap(empleado_skills_dict, rol_skills_list, skills_lookup):
    """
    Identifica las habilidades que le faltan al empleado o que necesita mejorar.
    """
    gap = []
    for skill_id in rol_skills_list:
        nivel_empleado = empleado_skills_dict.get(skill_id, 0)
        skill_nombre = skills_lookup.get(skill_id, skill_id)
        
        # Asumimos que < 7 es una brecha que necesita un plan
        if nivel_empleado < 7: 
            gap.append(f"{skill_nombre} (Nivel actual: {nivel_empleado}/10)")
            
    return gap if gap else ["Ninguna brecha de habilidad significativa identificada"]

def generar_plan_desarrollo(empleado_row, rol_futuro, rol_def, score, skills_lookup):
    """
    Genera una narrativa y un plan de desarrollo usando un LLM.
    """
    
    # --- 1. Inicializar el LLM ---
    # (Asegúrate de tener la API Key en un archivo .env)
    try:
        # Usamos Groq porque es gratis y rapidísimo para hackathons
        llm = ChatGroq(temperature=0.7, model_name="llama-3.1-8b-instant")
        # Si usas OpenAI:
        # llm = ChatOpenAI(temperature=0.7, model_name="gpt-3.5-turbo")
    except Exception as e:
        return f"Error al inicializar el LLM: {e}. ¿Falta la API Key en el archivo .env?"

    # --- 2. Calcular la brecha de habilidades ---
    brecha_skills = get_skill_gap(
        empleado_row['habilidades'], 
        rol_def.get('habilidades_requeridas', []),
        skills_lookup
    )
    
    # --- 3. Crear el Prompt Template ---
    template = """
    Eres un coach de talento experto en Quether.
    
    Analiza al siguiente empleado para un rol futuro:

    **Empleado:** {nombre_empleado}
    **Rol Actual:** {rol_actual}
    **Rol Futuro Deseado:** {rol_futuro}
    
    **Análisis de Compatibilidad:**
    - Score General: {score:.0f}%
    - Ambición del Empleado: {ambicion}
    - Nivel del Rol Futuro: {nivel_rol}
    - Brecha de Habilidades Clave: {brecha}

    Por favor, genera una **"Narrativa de Talento"** breve y positiva, 
    seguida de un **"Plan de Desarrollo Personalizado"** con 3 acciones 
    concretas y cuantificables para cerrar la brecha. 
    Usa Markdown para el formato.
    """
    
    prompt = PromptTemplate.from_template(template)
    
    # --- 4. Preparar los datos para el prompt ---
    input_data = {
        "nombre_empleado": empleado_row['nombre'],
        "rol_actual": empleado_row['rol_actual'],
        "rol_futuro": rol_futuro['título'],
        "score": score,
        "ambicion": empleado_row['ambiciones'].get('nivel_aspiración', 'N/A'),
        "nivel_rol": rol_def.get('nivel', 'N/A'),
        "brecha": ", ".join(brecha_skills)
    }
    
    # --- 5. Crear y ejecutar la cadena (chain) ---
    # El StrOutputParser() solo devuelve el texto de la respuesta
    chain = prompt | llm | StrOutputParser()
    
    try:
        response = chain.invoke(input_data)
        return response
    except Exception as e:
        return f"Error al llamar a la API de IA: {e}"
    
def generar_resumen_ejecutivo(riesgo_str, capacidad_str, gaps_str):
    """
    Genera una narrativa ejecutiva basada en los KPIs de la empresa.
    """
    
    # --- 1. Inicializar el LLM ---
    try:
        llm = ChatGroq(temperature=0.7, model_name="llama-3.1-8b-instant")
    except Exception as e:
        return f"Error al inicializar el LLM: {e}. ¿Falta la API Key en el archivo .env?"

    # --- 2. Crear el Prompt Template ---
    template = """
    Eres un Consultor de Estrategia de Talento para Quether.
    Aquí tienes los diagnósticos de la empresa:

    **1. TALENTO EN RIESGO (Riesgo de Fuga 'Media' o 'Alta'):**
    {riesgo}

    **2. CAPACIDAD DEL EQUIPO (Empleados sobre-asignados > 95%):**
    {capacidad}

    **3. VACÍOS CRÍTICOS (Roles futuros sin candidato interno > 50%):**
    {gaps}

    Por favor, escribe una "Narrativa Ejecutiva" de 2 párrafos.
    En el primer párrafo, resume los 3 problemas clave.
    En el segundo párrafo, da una recomendación estratégica clara.
    """
    
    prompt = PromptTemplate.from_template(template)
    
    # --- 3. Preparar los datos y ejecutar ---
    chain = prompt | llm | StrOutputParser()
    
    try:
        response = chain.invoke({
            "riesgo": riesgo_str,
            "capacidad": capacidad_str,
            "gaps": gaps_str
        })
        return response
    except Exception as e:
        return f"Error al llamar a la API de IA: {e}"