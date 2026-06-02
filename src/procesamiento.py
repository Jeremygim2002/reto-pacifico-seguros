import pandas as pd
import numpy as np
import re

# Carga de datos base
activos = pd.read_csv('data/activos.csv')
gastos = pd.read_csv('data/gastos_ope.csv')
contratos = pd.read_csv('data/contratos_alquiler.csv')

# 1. Normalización de Textos 
def extraer_datos_legales(texto):
    tipo = re.search(r"\[([^\]]+)\]|tipo\s+([^-]+)\s+-", texto)
    tipo_val = tipo.group(1) or tipo.group(2) if tipo else None
    
    distrito = re.search(r"distrito de\s+([^.]+)\.|Locación:\s+([^-]+)\s+-", texto)
    distrito_val = distrito.group(1) or distrito.group(2) if distrito else None
    
    area = re.search(r"declarada:\s*([\d\.]+)|-\s*([\d\.]+)m2", texto)
    area_val = area.group(1) or area.group(2) if area else None
    
    return pd.Series([
        tipo_val.strip().title() if tipo_val else None, 
        distrito_val.strip().title() if distrito_val else None, 
        area_val.strip() if area_val else None
    ])

# Se crean las 3 columnas 
activos[['Tipo_Activo', 'Distrito', 'Area_m2']] = activos['Descripcion_Legal'].apply(extraer_datos_legales)
activos['Area_m2'] = pd.to_numeric(activos['Area_m2'], errors='coerce')


# 2. Limpieza de Outliers (Gastos Operativos)
Q1 = gastos['Monto_USD'].quantile(0.25)
Q3 = gastos['Monto_USD'].quantile(0.75)
IQR = Q3 - Q1
limite_superior = Q3 + 1.5 * IQR

# Registros válidos
gastos_limpios = gastos[gastos['Monto_USD'] <= limite_superior]
gastos_anuales = gastos_limpios.groupby('ID_Inmueble')['Monto_USD'].sum().reset_index()
gastos_anuales.rename(columns={'Monto_USD': 'Gasto_Operativo_Anual'}, inplace=True)


# 3. Cálculo Financiero: NOI y Cap Rate
# contratos 
contratos_vigentes = contratos[contratos['Estado_Contrato'].str.upper() == 'VIGENTE']
ingresos = contratos_vigentes.groupby('ID_Inmueble')['Renta_Mensual_USD'].sum().reset_index()
ingresos['Ingreso_Anual'] = ingresos['Renta_Mensual_USD'] * 12

# Cruzar las bd
consolidado = activos.merge(gastos_anuales, on='ID_Inmueble', how='left')
consolidado = consolidado.merge(ingresos, on='ID_Inmueble', how='left')

# Colocar 0 a los gastos o ingresos que no cruzaron
consolidado['Gasto_Operativo_Anual'] = consolidado['Gasto_Operativo_Anual'].fillna(0)
consolidado['Ingreso_Anual'] = consolidado['Ingreso_Anual'].fillna(0)

# Cálculo NOI Anual
consolidado['NOI_Anual'] = consolidado['Ingreso_Anual'] - consolidado['Gasto_Operativo_Anual']

# Cálculo Cap Rate 
consolidado['Cap_Rate'] = np.where(
    consolidado['Valor_Tasacion_USD'] > 0,
    consolidado['NOI_Anual'] / consolidado['Valor_Tasacion_USD'],
    0
)

# Exportación Final
consolidado.to_excel('output/Inmuebles_Listos.xlsx', index=False)