import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Creamos un "lookup" para las definiciones de roles (de org_config.json)
# Lo haremos en la app principal y lo pasaremos a las funciones.

def score_skills(empleado_skills_dict, rol_skills_list):
    """
    Calcula el score de habilidades (Peso: 50%)
    Compara el dict de skills del empleado ({"S-OKR": 9})
    con la lista de skills requeridas del rol (["S-OKR", "S-ANALISIS"]).
    """
    if not rol_skills_list:
        return 50.0 # Si el rol no pide skills, está 100% cubierto.
        
    score_total = 0
    for skill_req in rol_skills_list:
        # Si el empleado tiene la skill, suma su nivel (de 0 a 10)
        # Si no la tiene, suma 0.
        level = empleado_skills_dict.get(skill_req, 0)
        score_total += (level / 10.0) # Normaliza a 0-1
    
    # Promedio de cobertura * peso
    final_score = (score_total / len(rol_skills_list)) * 50
    return final_score

def score_responsibilities(empleado_resp_list, rol_resp_list):
    """
    Calcula el score de responsabilidades (Peso: 25%)
    Usa similitud de texto (Cosine Similarity) para comparar las listas.
    """
    if not rol_resp_list:
        return 25.0 # Rol sin responsabilidades, 100% cubierto.
    if not empleado_resp_list:
        return 0.0 # Empleado sin responsabilidades.
        
    # Unimos las listas en "documentos" para comparar
    doc_empleado = " ".join(empleado_resp_list)
    doc_rol = " ".join(rol_resp_list)
    
    # TF-IDF
    tfidf_vectorizer = TfidfVectorizer().fit_transform([doc_empleado, doc_rol])
    similarity = cosine_similarity(tfidf_vectorizer[0:1], tfidf_vectorizer[1:2])
    
    # similarity[0][0] es el score de similitud (0 a 1)
    final_score = similarity[0][0] * 25
    return final_score

def score_ambitions(empleado_ambiciones_dict, rol_nivel):
    """
    Calcula el score de ambiciones (Peso: 15%)
    Compara el 'nivel_aspiración' del empleado con el 'nivel' del rol.
    """
    nivel_empleado = empleado_ambiciones_dict.get('nivel_aspiración', '').lower()
    nivel_rol = rol_nivel.lower()
    
    # Simple match
    if nivel_empleado == nivel_rol:
        return 15.0
    else:
        return 0.0 # No hay alineación

def score_dedication(empleado_dedicacion_dict, rol_modalidad):
    """
    Calcula el score de dedicación (Peso: 10%)
    Compara la dedicación total del empleado con la modalidad del rol (FT/PT).
    """
    total_dedicacion_empleado = sum(empleado_dedicacion_dict.values()) # Suma de proyectos
    
    # Mapeo simple de modalidad de rol
    if rol_modalidad == 'FT':
        dedicacion_requerida = 100
    elif rol_modalidad == 'PT':
        dedicacion_requerida = 50
    elif rol_modalidad == 'Fractional':
        dedicacion_requerida = 25 # Asunción
    else:
        dedicacion_requerida = 100 # Default a FT
        
    # Si el empleado tiene más o igual dedicación de la requerida, 100%
    if total_dedicacion_empleado >= dedicacion_requerida:
        return 10.0
    else:
        # Proporcional
        return (total_dedicacion_empleado / dedicacion_requerida) * 10

def calcular_compatibilidad_total(empleado_row, rol_futuro, roles_lookup):
    """
    Función orquestadora que calcula el score final.
    """
    
    # 1. Encontrar la definición completa del rol futuro
    rol_id = rol_futuro['id']
    rol_def = roles_lookup.get(rol_id)
    
    if not rol_def:
        # No tenemos definición para este rol en org_config.json
        return 0 
        
    # 2. Extraer los datos necesarios
    empleado_skills = empleado_row['habilidades']
    rol_skills_req = rol_def.get('habilidades_requeridas', [])
    
    empleado_resp = empleado_row['responsabilidades_actuales']
    rol_resp_req = rol_def.get('responsabilidades', [])
    
    empleado_amb = empleado_row['ambiciones']
    rol_nivel = rol_def.get('nivel', 'N/A')
    
    empleado_ded = empleado_row['dedicación_actual']
    rol_modalidad = rol_futuro.get('modalidad', 'FT') # De vision_futura.json
    
    # 3. Calcular scores parciales
    s_skills = score_skills(empleado_skills, rol_skills_req)
    s_resp = score_responsibilities(empleado_resp, rol_resp_req)
    s_amb = score_ambitions(empleado_amb, rol_nivel)
    s_ded = score_dedication(empleado_ded, rol_modalidad)
    
    # 4. Sumar
    total_score = s_skills + s_resp + s_amb + s_ded
    
    return total_score