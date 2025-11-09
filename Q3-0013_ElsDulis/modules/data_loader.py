import pandas as pd
import json
import ast # Necesario para el CSV

def load_json_file(filepath):
    """
    Carga un archivo JSON limpio.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error cargando JSON {filepath}: {e}")
        raise e

def load_talent_data(filepath):
    """
    Carga un CUALQUIER CSV de talento (interno o externo)
    y convierte las columnas de texto en objetos Python.
    """
    try:
        df = pd.read_csv(filepath)
    except FileNotFoundError:
        # Si no se encuentra el archivo, crea un dataframe vacío
        print(f"Advertencia: No se encontró {filepath}. Se creará uno vacío en memoria.")
        return pd.DataFrame(columns=[
            "id_empleado","nombre","email","chapter","rol_actual","manager",
            "antigüedad","habilidades","responsabilidades_actuales",
            "dedicación_actual","ambiciones","metadata"
        ])
    except Exception as e:
        print(f"Error cargando CSV {filepath}: {e}")
        raise e
        
    # Columnas que necesitan conversión
    cols_to_parse = ['habilidades', 'responsabilidades_actuales', 
                       'dedicación_actual', 'ambiciones', 'metadata']
    
    for col in cols_to_parse:
        if col not in df.columns:
            raise ValueError(f"El archivo '{filepath}' no tiene la columna requerida: '{col}'")
        
        # Asegurarse de que los datos no sean nulos antes de parsear
        df[col] = df[col].fillna('{}').apply(ast.literal_eval)
        
    return df

def load_all_data():
    """
    Función principal para cargar todo en la app.
    Ahora carga internos y externos y los une.
    """
    config = load_json_file('data/org_config.json')
    vision = load_json_file('data/vision_futura.json')
    
    # Cargar ambos CSVs de talento
    internal_df = load_talent_data('data/talento_actual.csv')
    external_df = load_talent_data('data/candidatos_externos.csv')
    
    # Unir los dos DataFrames en uno solo
    talent_df = pd.concat([internal_df, external_df], ignore_index=True)
    
    # Asegurar que el ID sea numérico para poder hacer .max()
    talent_df['id_empleado'] = pd.to_numeric(talent_df['id_empleado'])
    
    return config, vision, talent_df