import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from modules.data_loader import load_all_data
from modules.compatibility import calcular_compatibilidad_total
from modules.recommendations import generar_plan_desarrollo, generar_resumen_ejecutivo
import json
from collections import defaultdict
import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components

# --- Configuración y Carga de Datos ---
st.set_page_config(page_title="Talent Gap Analyzer", layout="wide", initial_sidebar_state="expanded")
st.title("Quether Talent Gap Analyzer")
st.markdown("Optimización de Alineación de Talento en la Empresa del Futuro.")

@st.cache_data # Cachear los datos para performance
def cargar_datos():
    config, vision, talent_df = load_all_data()
    roles_lookup = {rol['id']: rol for rol in config['roles']}
    skills_lookup = {skill['id']: skill['nombre'] for skill in config['skills']}
    return config, vision, talent_df, roles_lookup, skills_lookup

config, vision, talent_df, roles_lookup, skills_lookup = cargar_datos()
roles_futuros_opciones = {rol['título']: rol for rol in vision['roles_necesarios']}

# --- Funciones de Cálculo para el Dashboard ---
def get_strategic_kpis(talent_df, vision_df, roles_lookup):
    internal_df = talent_df[talent_df['metadata'].apply(lambda x: x.get('tipo', 'Interno') == 'Interno')].copy()
    riesgo_df = internal_df[internal_df['metadata'].apply(lambda x: x.get('retention_risk') == 'Media')]
    internal_df['dedicacion_total'] = internal_df['dedicación_actual'].apply(lambda x: sum(x.values()) if isinstance(x, dict) else 0)
    capacidad_df = internal_df[internal_df['dedicacion_total'] > 95][['nombre', 'rol_actual', 'dedicacion_total']]
    project_load = defaultdict(int)
    for projects_dict in internal_df['dedicación_actual']:
        if isinstance(projects_dict, dict):
            for project, load in projects_dict.items():
                project_load[project] += load
    project_load_df = pd.DataFrame(project_load.items(), columns=['Proyecto', 'Carga Total (%)']).sort_values(by='Carga Total (%)', ascending=False)
    roles_futuros = vision_df['roles_necesarios']
    gaps_data = []
    for rol in roles_futuros:
        best_score = 0
        for idx, empleado in internal_df.iterrows():
            score = calcular_compatibilidad_total(empleado, rol, roles_lookup)
            if score > best_score:
                best_score = score
        gaps_data.append({'Rol Futuro': rol['título'], 'Mejor Score (%)': int(best_score)})
    gaps_df = pd.DataFrame(gaps_data).sort_values(by='Mejor Score (%)', ascending=True)
    return riesgo_df, capacidad_df, gaps_df, project_load_df

# --- Sidebar (Global) ---
st.sidebar.header("Captura de Talento")

# Datos para los selectores del formulario
all_skills_list = list(skills_lookup.items())
chapter_list = [c['nombre'] for c in config['chapters']]
manager_list = ['N/A'] + list(talent_df['nombre'].unique())

with st.sidebar.expander("Formulario de Nuevo Talento"):
    
    # --- PASO 1: Selectores FUERA del formulario ---
    new_talent_type = st.radio(
        "Tipo de Talento",
        ('Interno (Empleado Actual)', 'Externo (Candidato / CV)'),
        horizontal=True, key="talent_type_radio"
    )
    
    skill_options = [(sid, f"{sname} ({sid})") for sid, sname in all_skills_list]
    selected_skills_tuples = st.multiselect(
        "Selecciona Habilidades", 
        options=skill_options,
        format_func=lambda x: x[1],
        key="skill_selector" # Usar session state
    )

    # --- PASO 2: El Formulario ---
    with st.form("new_talent_form", clear_on_submit=True):
        st.write("Datos Básicos")
        new_name = st.text_input("Nombre Completo")
        new_email = st.text_input("Email o Contacto")
        
        if st.session_state.talent_type_radio == 'Interno (Empleado Actual)':
            st.write("Datos del Empleado")
            new_chapter = st.selectbox("Chapter", options=chapter_list)
            new_rol = st.text_input("Rol Actual", "Junior")
            new_manager = st.selectbox("Manager", options=manager_list)
        else:
            st.file_uploader("Adjuntar CV (Opcional)", type=['pdf', 'doc', 'docx'])
            new_chapter = "Externo"
            new_rol = "Candidato Externo"
            new_manager = "N/A"
            
        # --- PASO 3: Sliders Dinámicos ---
        st.divider()
        st.write("Define el Nivel de cada Habilidad (1-10)")
        
        skill_levels_from_sliders = {} # Diccionario para guardar los niveles

        if not st.session_state.skill_selector:
            st.info("Selecciona una o más habilidades en el campo de arriba.")
        else:
            # Iterar sobre las habilidades seleccionadas FUERA del form
            for skill_tuple in st.session_state.skill_selector:
                skill_id = skill_tuple[0]
                skill_name = skill_tuple[1]
                # Crear un slider para CADA habilidad
                skill_levels_from_sliders[skill_id] = st.slider(
                    f"Nivel para: {skill_name}", 
                    min_value=1, 
                    max_value=10, 
                    value=5, 
                    key=f"slider_{skill_id}" # Clave única
                )
        
        submitted = st.form_submit_button("Añadir Talento")
        
        if submitted:
            if not new_name:
                st.error("El nombre es obligatorio.")
            elif not skill_levels_from_sliders:
                st.error("Debes seleccionar y definir el nivel de al menos una habilidad.")
            else:
                try:
                    talent_type_from_radio = st.session_state.talent_type_radio
                    new_id = (talent_df['id_empleado'].max() + 1) if not talent_df.empty else 1001
                    
                    # --- PASO 4: Usar los valores de los sliders ---
                    new_skills_dict = skill_levels_from_sliders 
                    
                    metadata_dict = {"tipo": "Interno" if talent_type_from_radio == 'Interno (Empleado Actual)' else "Externo"}
                    new_talent_data = {"id_empleado": new_id, "nombre": new_name, "email": new_email or 'N/A', "chapter": new_chapter, "rol_actual": new_rol, "manager": new_manager, "antigüedad": "0m", "habilidades": str(new_skills_dict), "responsabilidades_actuales": str([]), "dedicación_actual": str({}), "ambiciones": str({"nivel_aspiración": "junior"}), "metadata": str(metadata_dict)}
                    filepath_to_save = 'data/talento_actual.csv' if talent_type_from_radio == 'Interno (Empleado Actual)' else 'data/candidatos_externos.csv'
                    current_talent_df = pd.read_csv(filepath_to_save)
                    new_row_df = pd.DataFrame([new_talent_data])
                    updated_df = pd.concat([current_talent_df, new_row_df], ignore_index=True)
                    updated_df.to_csv(filepath_to_save, index=False)
                    
                    st.cache_data.clear()
                    st.success(f"¡Talento {new_name} añadido a {filepath_to_save}!")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

# --- Dashboard Estratégico (Vista "General") ---
st.header("Dashboard Estratégico (Vista General)")
riesgo_df, capacidad_df, gaps_df, project_load_df = get_strategic_kpis(talent_df, vision, roles_lookup)
gaps_list_criticos = gaps_df[gaps_df['Mejor Score (%)'] < 50]['Rol Futuro'].tolist()
col1, col2, col3 = st.columns(3)
col1.metric("Talento en Riesgo (Fuga)", f"{len(riesgo_df)} Empleados")
col2.metric("Empleados Sobre-asignados", f"{len(capacidad_df)} Empleados")
col3.metric("Vacíos Críticos (Contratación)", f"{len(gaps_list_criticos)} Roles")

st.subheader("Cobertura de Roles Futuros (Mejor Candidato Interno)")
gaps_df['Color'] = gaps_df['Mejor Score (%)'].apply(lambda x: 'Vacío Crítico (<50%)' if x < 50 else 'Cubierto (>50%)')
fig_gaps = px.bar(gaps_df, x='Mejor Score (%)', y='Rol Futuro', orientation='h', color='Color',
                  color_discrete_map={'Vacío Crítico (<50%)': '#FF5733', 'Cubierto (>50%)': '#33FF57'},
                  range_x=[0, 100], title="Cobertura de Roles Futuros (Mejor Candidato Interno)")
st.plotly_chart(fig_gaps, use_container_width=True)

st.subheader("Carga de Trabajo por Proyecto (Dedicación Total Interna)")
fig_projects = px.bar(project_load_df, x='Carga Total (%)', y='Proyecto', orientation='h',
                      title="Carga de Trabajo por Proyecto (Dedicación Total Interna)")
st.plotly_chart(fig_projects, use_container_width=True)

with st.expander("Ver Detalles del Diagnóstico"):
    c1, c2, c3 = st.columns(3)
    with c1: st.subheader("Talento en Riesgo"); st.dataframe(riesgo_df[['nombre', 'rol_actual', 'chapter']])
    with c2: st.subheader("Capacidad Excedida (>95%)"); st.dataframe(capacidad_df)
    with c3: st.subheader("Vacíos Críticos (Roles <50%)"); st.dataframe(gaps_list_criticos, column_config={"value": "Rol Futuro"})

if st.button("Generar Resumen Ejecutivo (IA)"):
    with st.spinner("La IA está analizando la situación..."):
        riesgo_str = "Ninguno" if riesgo_df.empty else riesgo_df['nombre'].to_string(index=False)
        capacidad_str = "Ninguno" if capacidad_df.empty else capacidad_df['nombre'].to_string(index=False)
        gaps_str = "Ninguno" if not gaps_list_criticos else "\n".join(gaps_list_criticos)
        resumen = generar_resumen_ejecutivo(riesgo_str, capacidad_str, gaps_str)
        st.info("Resumen Ejecutivo (Generado por IA)"); st.markdown(resumen)

st.divider()

# --- Sección de Análisis Táctico ---
with st.expander("Análisis Táctico de Roles (Mánagers)"):
    st.header("Rankings de Talento para el Rol")
    selected_rol_titulo_tactico = st.selectbox(
        "Selecciona un Rol Futuro para Analizar:",
        options=roles_futuros_opciones.keys(),
        key="tactical_selector"
    )
    selected_rol_futuro = roles_futuros_opciones[selected_rol_titulo_tactico]
    st.subheader(f"Rol Futuro Seleccionado: {selected_rol_titulo_tactico}")
    scores = []
    for idx, empleado_row in talent_df.iterrows():
        if not isinstance(empleado_row.get('metadata'), dict): empleado_row['metadata'] = {}
        score = calcular_compatibilidad_total(empleado_row, selected_rol_futuro, roles_lookup)
        talent_type = empleado_row['metadata'].get('tipo', 'Interno')
        scores.append({'ID Empleado': empleado_row['id_empleado'], 'Nombre': empleado_row['nombre'], 'Rol Actual': empleado_row['rol_actual'], 'Tipo': talent_type, 'Compatibilidad': round(score, 2)})
    ranking_df = pd.DataFrame(scores).sort_values(by='Compatibilidad', ascending=False)
    internal_df = ranking_df[ranking_df['Tipo'] == 'Interno']
    external_df = ranking_df[ranking_df['Tipo'] == 'Externo']
    def display_ranking_table(df, key_prefix):
        col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
        col1.markdown("**Nombre**"); col2.markdown("**Rol Actual / Estado**"); col3.markdown("**Compatibilidad (%)**"); col4.markdown("**Acción (Plan IA)**")
        st.divider()
        if df.empty: st.info("No hay candidatos en esta categoría."); return
        for idx, row in df.iterrows():
            col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
            col1.write(row['Nombre']); col2.write(row['Rol Actual'])
            score_val = int(row['Compatibilidad'])
            if score_val > 85: label = f"{score_val}% (READY)"
            elif score_val > 70: label = f"{score_val}% (READY_WITH_SUPPORT)"
            elif score_val > 50: label = f"{score_val}% (NEAR)"
            elif score_val > 25: label = f"{score_val}% (FAR)"
            else: label = f"{score_val}% (NOT_VIABLE)"
            col3.progress(score_val, text=label)
            if col4.button("Generar Plan", key=f"{key_prefix}_{row['ID Empleado']}"):
                with st.spinner(f"Generando plan para {row['Nombre']}..."):
                    empleado_data = talent_df[talent_df['id_empleado'] == row['ID Empleado']].iloc[0]
                    rol_def_data = roles_lookup.get(selected_rol_futuro['id'])
                    if rol_def_data:
                        plan_ia = generar_plan_desarrollo(empleado_data, selected_rol_futuro, rol_def_data, row['Compatibilidad'], skills_lookup)
                        with st.expander(f"Ver Plan de Desarrollo para {row['Nombre']}", expanded=True): st.markdown(plan_ia)
                    else: st.error(f"Error: No se encontró la definición del rol {selected_rol_futuro['id']} en org_config.json")
    tab_internos, tab_externos = st.tabs(["Ranking de Candidatos Internos", "Ranking de Candidatos Externos (Talent Pool)"])
    with tab_internos: display_ranking_table(internal_df, "internal")
    with tab_externos: display_ranking_table(external_df, "external")


# --- Sección de Talento Actual ---
with st.expander("Dashboard de Talento Actual (Vista de RRHH)"):
    st.header("Dashboard de Talento Actual")
    selected_chapter_hr = st.selectbox(
        "Filtrar por Chapter:", 
        options=['Todos'] + [c['nombre'] for c in config['chapters']],
        key="hr_selector"
    )
    internal_talent_df_hr = talent_df[talent_df['metadata'].apply(lambda x: x.get('tipo', 'Interno') == 'Interno')]
    if selected_chapter_hr == 'Todos': display_df = internal_talent_df_hr
    else: display_df = internal_talent_df_hr[internal_talent_df_hr['chapter'] == selected_chapter_hr]
    st.dataframe(display_df[['nombre', 'chapter', 'rol_actual', 'manager']])
    st.subheader(f"Promedio de Habilidades en: {selected_chapter_hr}")
    skills_data = []
    for idx, row in display_df.iterrows():
        if isinstance(row['habilidades'], dict):
            for skill_id, level in row['habilidades'].items():
                skills_data.append({'nombre': row['nombre'], 'skill_nombre': skills_lookup.get(skill_id, skill_id), 'nivel': level})
    skills_df = pd.DataFrame(skills_data)
    if not skills_df.empty:
        avg_skills = skills_df.groupby('skill_nombre')['nivel'].mean().reset_index().sort_values(by='nivel')
        fig_avg_skills = px.bar(avg_skills, x='nivel', y='skill_nombre', orientation='h', title="Nivel de Habilidad Promedio (0-10)")
        st.plotly_chart(fig_avg_skills, use_container_width=True)

    # --- Grafo de Habilidades (Pyvis) ---
    st.subheader("Grafo Interactivo de Conexiones (Empleados y Habilidades)")

    G = nx.Graph()
    for idx, row in display_df.iterrows():
        G.add_node(row['nombre'], type='empleado', title=row['rol_actual'], color='#1E90FF') # Azul
    for skill_id, skill_name in skills_lookup.items():
        skill_in_use = any(skill_id in row['habilidades'] for _, row in display_df.iterrows() if isinstance(row['habilidades'], dict))
        if skill_in_use:
            G.add_node(skill_name, type='habilidad', title=skill_name, color='#32CD32') # Verde
    for idx, row in display_df.iterrows():
        if isinstance(row['habilidades'], dict):
            for skill_id, level in row['habilidades'].items():
                if level > 4 and skill_id in skills_lookup:
                    skill_name = skills_lookup[skill_id]
                    if G.has_node(row['nombre']) and G.has_node(skill_name):
                        G.add_edge(row['nombre'], skill_name, value=level/2, title=f"Nivel: {level}")
    net = Network(height='750px', width='100%', bgcolor='#222222', font_color='white', notebook=True, cdn_resources='in_line')
    net.from_nx(G)
    net.toggle_physics(True)
    
    try:
        net.generate_html()
        components.html(net.html, height=800, scrolling=True)
    except Exception as e:
        st.error(f"Error al generar el grafo: {e}")