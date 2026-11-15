import io
import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px

st.set_page_config(
    page_title="Plataforma ACV Econômica (MIP/TRU)",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# FUNÇÕES AUXILIARES DE IMPORTAÇÃO E AGREGAÇÃO
# ==========================================
def ler_tabela_upload(arquivo, tem_indice=True):
    nome = arquivo.name.lower()
    idx_col = 0 if tem_indice else None
    if nome.endswith(".xlsx") or nome.endswith(".xls"):
        df = pd.read_excel(arquivo, index_col=idx_col)
    else:
        conteudo = arquivo.getvalue().decode("utf-8-sig", errors="replace")
        sep = ";" if conteudo.count(";") > conteudo.count(",") else ","
        decimal = "," if sep == ";" else "."
        df = pd.read_csv(io.StringIO(conteudo), sep=sep, decimal=decimal, index_col=idx_col)
    df.columns = [str(c).strip() for c in df.columns]
    if tem_indice:
        df.index = [str(i).strip() for i in df.index]
    return df

def gerar_template_excel(setores_lista):
    n = len(setores_lista)
    output = io.BytesIO()
    df_z_mod = pd.DataFrame(np.zeros((n, n)), index=setores_lista, columns=setores_lista)
    df_x_mod = pd.DataFrame(np.ones((1, n)) * 1000.0, index=["Producao_Total_xj"], columns=setores_lista)
    df_b_mod = pd.DataFrame(np.zeros((2, n)), columns=setores_lista)
    df_b_mod.insert(0, "Aspecto Ambiental (Unidade)", ["Emissoes GEE (t CO2eq)", "Consumo de Energia (GJ)"])
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_z_mod.to_excel(writer, sheet_name="Matriz_Z")
        df_x_mod.to_excel(writer, sheet_name="Producao_X")
        df_b_mod.to_excel(writer, sheet_name="Matriz_B", index=False)
    return output.getvalue()

def agregar_matriz_com_mapeamento(df_Z_full, mapa_linhas_para_setor, setores_manter, nome_agregado="Outros"):
    """
    Agrega matriz 128x68 (P x S) ou 68x68 (S x S) somando múltiplos produtos (linhas)
    ao seu setor correspondente, gerando sempre uma matriz quadrada (k+1) x (k+1).
    """
    df_num = df_Z_full.apply(pd.to_numeric, errors="coerce").fillna(0.0)
    colunas_resto = [c for c in df_num.columns if c not in setores_manter]

    # 1. Agrega as colunas (Setores não selecionados viram 'Outros')
    df_col_agg = df_num[setores_manter].copy()
    if len(colunas_resto) > 0:
        df_col_agg[nome_agregado] = df_num[colunas_resto].sum(axis=1)

    ordem_final = setores_manter + ([nome_agregado] if len(colunas_resto) > 0 else [])

    # 2. Agrupa e soma as linhas (Produtos) de acordo com o setor atribuído a cada linha
    df_col_agg["_Setor_Destino_"] = [mapa_linhas_para_setor.get(idx, nome_agregado) for idx in df_col_agg.index]
    df_final = df_col_agg.groupby("_Setor_Destino_").sum()

    # Garante que todos os setores finais existam na mesma ordem nas linhas e colunas
    df_final = df_final.reindex(index=ordem_final, columns=ordem_final).fillna(0.0)
    return df_final

def agregar_vetor_ou_colunas(df_full, colunas_manter, nome_agregado="Demais Setores Agregados"):
    df_num = df_full.apply(pd.to_numeric, errors="coerce").fillna(0.0)
    colunas_resto = [c for c in df_num.columns if c not in colunas_manter]
    df_agg = df_num[colunas_manter].copy()
    if len(colunas_resto) > 0:
        df_agg[nome_agregado] = df_num[colunas_resto].sum(axis=1)
    return df_agg

# ==========================================
# BARRA LATERAL
# ==========================================
with st.sidebar:
    st.title("📊 ACV Econômica (MIP/TRU)")
    st.markdown("""
    Quantificação ambiental via **Matriz Insumo-Produto**:
    
    $$q = R_s \cdot (I - A)^{-1} \cdot y_s$$
    
    **Fluxos de Trabalho:**
    * **Aba 0:** Agregar matrizes completas (68×68 ou 128×68).
    * **FT1:** Definir função, setores e Demanda Final ($y_s$).
    * **FT2:** Calcular Matriz $A$ e Inversa de Leontief ($L$).
    * **FT3:** Calcular Coeficientes Ambientais ($R_s$).
    * **FT4:** Quantificar $q$ e analisar *hotspots*.
    """)
    st.divider()
    
    st.subheader("📂 Importação Rápida (Já Agregada)")
    arquivo_mestre = st.file_uploader(
        "Carregar Planilha Agregada (.xlsx)",
        type=["xlsx", "xls"],
        key="upload_mestre"
    )
    placeholder_template = st.empty()
    
    st.divider()
    if st.button("🔄 Restaurar Exemplo Padrão", use_container_width=True):
        st.session_state.clear()
        st.rerun()

st.title("📊 Avaliação do Ciclo de Vida Baseada em Dados Econômicos")
st.markdown("Agregação de tabelas **IBGE / NEREUS** e quantificação do inventário ambiental via **Matriz Insumo-Produto**.")

tab0, tab1, tab2, tab3, tab4 = st.tabs([
    "0️⃣ Agregador TRU / MIP (IBGE/NEREUS)",
    "1️⃣ FT1: Escopo e Demanda (y_s)",
    "2️⃣ FT2: Matriz Econômica (Z, A e L)",
    "3️⃣ FT3: Matriz Ambiental (B e R_s)",
    "4️⃣ FT4: Cálculo e Interpretação (q)"
])

# ==========================================
# ABA 0: AGREGADOR AUTOMÁTICO (68x68 ou 128x68)
# ==========================================
with tab0:
    st.header("0️⃣ Ferramenta de Agregação Automática (TRU 128×68 ou MIP 68×68)")
    st.markdown("""
    Carregue sua tabela completa do **IBGE ou NEREUS**. 
    * Na **TRU (128 × 68)**, marque os setores de interesse no **Quadro 1** e vincule **um ou mais produtos** a cada setor no **Quadro 2**.
    * Todos os setores desmarcados e produtos deixados como **"Outros"** serão somados automaticamente na linha e coluna **"Outros"**.
    """)

    tipo_tabela = st.radio(
        "Formato da tabela de fluxos intermediários (Z):",
        options=[
            "Tabela de Recursos e Usos — Produto × Setor (128 × 68)",
            "Matriz Quadrada — Setor × Setor (68 × 68)"
        ],
        horizontal=True
    )

    col_agg1, col_agg2, col_agg3 = st.columns(3)
    with col_agg1:
        up_full_Z = st.file_uploader("1. Tabela Z Completa (128×68 ou 68×68) [Obrigatório]", type=["csv", "xlsx"], key="up_full_z")
    with col_agg2:
        up_full_X = st.file_uploader("2. Vetor Produção Total x_j (1×68) [Opcional]", type=["csv", "xlsx"], key="up_full_x")
    with col_agg3:
        up_full_B = st.file_uploader("3. Matriz Ambiental B (m×68) [Opcional]", type=["csv", "xlsx"], key="up_full_b")

    if up_full_Z is None:
        if st.button("🧪 Carregar Exemplo Sintético (128×68 ou 68×68) para Testar Agregador"):
            setores_sim = [f"Setor_{i:02d}" for i in range(1, 69)]
            setores_sim = "Extração de Petróleo e Gás"
            setores_sim = "Fabricação de Resinas e Químicos"
            setores_sim = "Fabricação de Tintas e Vernizes"

            np.random.seed(42)
            if "128 × 68" in tipo_tabela:
                prods_sim = [f"Produto_{i:03d}" for i in range(1, 129)]
                prods_sim = "Petróleo bruto"
                prods_sim = "Gás natural"
                prods_sim = "Resinas termoplásticas"
                prods_sim = "Solventes e aditivos químicos"
                prods_sim = "Tintas e vernizes"
                st.session_state["sim_Z_full"] = pd.DataFrame(np.random.uniform(10, 500, (128, 68)), index=prods_sim, columns=setores_sim)
            else:
                st.session_state["sim_Z_full"] = pd.DataFrame(np.random.uniform(10, 500, (68, 68)), index=setores_sim, columns=setores_sim)

            st.session_state["sim_X_full"] = pd.DataFrame([np.random.uniform(40000, 150000, 68)], index=["Producao_Total"], columns=setores_sim)
            df_b_sim = pd.DataFrame(np.random.uniform(100, 10000, (2, 68)), columns=setores_sim)
            df_b_sim.insert(0, "Aspecto Ambiental (Unidade)", ["Emissões GEE (t CO2eq)", "Consumo de Energia (GJ)"])
            st.session_state["sim_B_full"] = df_b_sim

    df_Z_raw, df_X_raw, df_B_raw = None, None, None
    try:
        if up_full_Z is not None:
            df_Z_raw = ler_tabela_upload(up_full_Z, tem_indice=True)
            if up_full_X is not None:
                df_X_raw = ler_tabela_upload(up_full_X, tem_indice=True)
            if up_full_B is not None:
                df_B_raw = ler_tabela_upload(up_full_B, tem_indice=False)
        elif "sim_Z_full" in st.session_state:
            df_Z_raw = st.session_state["sim_Z_full"]
            df_X_raw = st.session_state.get("sim_X_full")
            df_B_raw = st.session_state.get("sim_B_full")
    except Exception as e:
        st.error(f"Erro ao ler os arquivos carregados: {e}")

    if df_Z_raw is not None:
        st.success(f"✅ Matriz carregada com dimensão: **{df_Z_raw.shape} linhas × {df_Z_raw.shape} colunas**.")
        todas_linhas = df_Z_raw.index.tolist()
        todas_colunas = df_Z_raw.columns.tolist()
        nome_grupo_agregado = "Outros"

        if "Setor × Setor" in tipo_tabela:
            st.subheader("Selecione nos quadros abaixo os setores a manter desagregados")
            opcoes = [c for c in todas_colunas if c in todas_linhas] or todas_colunas
            padrao_sel = ["Extração de Petróleo e Gás", "Fabricação de Resinas e Químicos", "Fabricação de Tintas e Vernizes"]

            df_quadro_setores = pd.DataFrame({
                "Manter Desagregado?": [s in padrao_sel for s in opcoes],
                "Setor (Linha e Coluna)": opcoes
            })
            if not df_quadro_setores["Manter Desagregado?"].any() and len(opcoes) >= 3:
                df_quadro_setores.loc[:2, "Manter Desagregado?"] = True

            df_sel_s = st.data_editor(
                df_quadro_setores,
                hide_index=True,
                use_container_width=True,
                height=320,
                disabled=["Setor (Linha e Coluna)"],
                key="quadro_sel_sxs"
            )
            colunas_escolhidas = df_sel_s[df_sel_s["Manter Desagregado?"] == True]["Setor (Linha e Coluna)"].tolist()
            mapa_linhas = {s: s for s in colunas_escolhidas}

        else:
            col_q1, col_q2 = st.columns([1, 1.3])
            with col_q1:
                st.markdown("**1º Passo: Marque os Setores (Colunas - 68)**")
                padrao_s = ["Extração de Petróleo e Gás", "Fabricação de Resinas e Químicos", "Fabricação de Tintas e Vernizes"]
                df_quadro_set = pd.DataFrame({
                    "Selecionar": [s in padrao_s for s in todas_colunas],
                    "Setor (Coluna)": todas_colunas
                })
                if not df_quadro_set["Selecionar"].any() and len(todas_colunas) >= 3:
                    df_quadro_set.loc[:2, "Selecionar"] = True

                df_sel_c = st.data_editor(
                    df_quadro_set,
                    hide_index=True,
                    use_container_width=True,
                    height=350,
                    disabled=["Setor (Coluna)"],
                    key="quadro_sel_set_pxs"
                )
                colunas_escolhidas = df_sel_c[df_sel_c["Selecionar"] == True]["Setor (Coluna)"].tolist()

            with col_q2:
                st.markdown("**2º Passo: Vincule 1 ou mais Produtos (Linhas - 128) a cada Setor**")
                opcoes_destino = [nome_grupo_agregado] + colunas_escolhidas

                # Preenchimento ilustrativo para o exemplo sintético (mostrando 2 produtos somados em 1 setor)
                mapa_exemplo = {
                    "Petróleo bruto": "Extração de Petróleo e Gás",
                    "Gás natural": "Extração de Petróleo e Gás",
                    "Resinas termoplásticas": "Fabricação de Resinas e Químicos",
                    "Solventes e aditivos químicos": "Fabricação de Resinas e Químicos",
                    "Tintas e vernizes": "Fabricação de Tintas e Vernizes"
                }
                destinos_iniciais = [
                    mapa_exemplo[p] if p in mapa_exemplo and mapa_exemplo[p] in colunas_escolhidas else nome_grupo_agregado
                    for p in todas_linhas
                ]

                df_quadro_prod = pd.DataFrame({
                    "Produto (Linha)": todas_linhas,
                    "Somar no Setor:": destinos_iniciais
                })

                df_sel_p = st.data_editor(
                    df_quadro_prod,
                    hide_index=True,
                    use_container_width=True,
                    height=350,
                    disabled=["Produto (Linha)"],
                    column_config={
                        "Somar no Setor:": st.column_config.SelectboxColumn(
                            "Somar no Setor:",
                            help="Escolha a qual setor este produto pertence. Produtos marcados como 'Outros' serão somados na linha 'Outros'.",
                            options=opcoes_destino,
                            required=True
                        )
                    },
                    key="quadro_map_prod_pxs"
                )
                mapa_linhas = dict(zip(df_sel_p["Produto (Linha)"], df_sel_p["Somar no Setor:"]))

        if len(colunas_escolhidas) > 0:
            # Verifica se todos os setores selecionados receberam pelo menos 1 produto (no modo 128x68)
            setores_sem_produto = [s for s in colunas_escolhidas if s not in mapa_linhas.values()]
            if "128 × 68" in tipo_tabela and len(setores_sem_produto) > 0:
                st.warning(f"⚠️ Os seguintes setores selecionados ainda não têm nenhum produto vinculado no Quadro 2 (ficarão com linha zerada): **{', '.join(setores_sem_produto)}**")

            df_Z_agg = agregar_matriz_com_mapeamento(df_Z_raw, mapa_linhas, colunas_escolhidas, nome_grupo_agregado)
            setores_finais_agg = df_Z_agg.columns.tolist()

            st.subheader(f"Pré-visualização da Matriz Z Agregada ({df_Z_agg.shape} × {df_Z_agg.shape})")
            st.dataframe(df_Z_agg.style.format("{:,.2f}"), use_container_width=True)

            df_X_agg = None
            if df_X_raw is not None:
                df_X_agg = agregar_vetor_ou_colunas(df_X_raw.iloc[:1], colunas_escolhidas, nome_grupo_agregado)
                df_X_agg.index = ["Produção Total (x_j)"]

            df_B_agg = None
            if df_B_raw is not None:
                col_asp = df_B_raw.columns
                df_B_agg = agregar_vetor_ou_colunas(df_B_raw.drop(columns=[col_asp]), colunas_escolhidas, nome_grupo_agregado)
                df_B_agg.insert(0, "Aspecto Ambiental (Unidade)", df_B_raw[col_asp])

            if st.button("🚀 Aplicar Agregação aos Fluxos FT1 – FT3", type="primary"):
                st.session_state["agg_setores"] = setores_finais_agg
                st.session_state["agg_Z"] = df_Z_agg
                if df_X_agg is not None:
                    st.session_state["agg_X"] = df_X_agg
                if df_B_agg is not None:
                    st.session_state["agg_B"] = df_B_agg
                st.success("✅ Dados transferidos com sucesso (demais itens agrupados em 'Outros')! Avance para as abas **FT1, FT2, FT3 e FT4**.")
        else:
             st.warning("⚠️ Marque pelo menos 1 setor no quadro acima para gerar a matriz agregada.")

# ==========================================
# FLUXO DE TRABALHO 1 (FT1)
# ==========================================
with tab1:
    st.header("1º Fluxo de Trabalho (FT1): Função, Setores e Demanda Final ($y_s$)")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        funcao = st.text_input("Função do Sistema:", value="Colorir paredes internas de uma residência")
    with col2:
        uf_economica = st.text_input("Unidade Funcional / Bloco de Consumo:", value="R$ 1.000,00 em tintas e vernizes")
    with col3:
        unidade_monetaria = st.text_input("Unidade Monetária das Tabelas:", value="R$ Milhões")

    st.subheader("Setores da Cadeia Produtiva e Demanda Final ($y_s$)")

    if "agg_setores" in st.session_state:
        st.info("ℹ️ Setores carregados automaticamente da **Aba 0 (Agregador)**.")
        setores_ini = st.session_state["agg_setores"]
        demandas_ini = [0.0] * len(setores_ini)
        if len(demandas_ini) >= 3:
            demandas_ini = 0.001
        df_ft1_inicial = pd.DataFrame({
            "Setor Econômico": setores_ini,
            "Demanda Final (y_s)": demandas_ini
        })
    else:
        df_ft1_inicial = pd.DataFrame({
            "Setor Econômico": [
                "Extração de Petróleo e Gás",
                "Fabricação de Resinas e Químicos",
                "Fabricação de Tintas e Vernizes",
                "Demais Setores Agregados"
            ],
            "Demanda Final (y_s)": [0.0, 0.0, 0.001, 0.0]
        })

    df_ft1 = st.data_editor(
        df_ft1_inicial,
        num_rows="dynamic",
        use_container_width=True,
        key="editor_eco_ft1"
    )

    df_limpo = df_ft1.dropna(subset=["Setor Econômico"]).copy()
    df_limpo["Setor Econômico"] = df_limpo["Setor Econômico"].astype(str).str.strip()
    df_limpo = df_limpo[df_limpo["Setor Econômico"] != ""]

    setores = df_limpo["Setor Econômico"].tolist()
    y_s_vetor = pd.to_numeric(df_limpo["Demanda Final (y_s)"], errors="coerce").fillna(0.0).tolist()

    if len(setores) != len(set(setores)):
        st.error("⚠️ Existem setores com nomes duplicados. Renomeie-os para evitar conflitos nas matrizes.")

    if len(setores) > 0:
        try:
            excel_bytes = gerar_template_excel(setores)
            placeholder_template.download_button(
                label="📥 Baixar Modelo Excel (.xlsx) Atual",
                data=excel_bytes,
                file_name="template_acv_economica.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        except Exception:
            pass

    st.subheader("Diagrama de Setores e Demanda Final")
    if len(setores) > 0:
        dot_code = 'digraph G {\n  rankdir=LR;\n  node [shape=box, style="rounded,filled", fontname="Arial"];\n'
        for _, row in df_limpo.iterrows():
            nome = row["Setor Econômico"].replace('"', '')
            demanda = row["Demanda Final (y_s)"] if pd.notna(row["Demanda Final (y_s)"]) else 0.0
            cor_fundo = "#d1ecf1" if demanda > 0 else "#f8f9fa"
            cor_borda = "#0c5460" if demanda > 0 else "#6c757d"
            dot_code += f'  "{nome}" [fillcolor="{cor_fundo}", color="{cor_borda}", label="{nome}\\n(y_s = {demanda} {unidade_monetaria})"];\n'
        for i in range(len(setores) - 1):
            s1 = setores[i].replace('"', '')
            s2 = setores[i+1].replace('"', '')
            dot_code += f'  "{s1}" -> "{s2}" [style=dashed, color="#adb5bd"];\n'
        dot_code += '}'
        st.graphviz_chart(dot_code)

# ==========================================
# FLUXO DE TRABALHO 2 (FT2)
# ==========================================
with tab2:
    st.header("2º Fluxo de Trabalho (FT2): Matriz $Z$, Coeficientes Técnicos ($A$) e Leontief ($L$)")
    
    if len(setores) == 0:
        st.warning("Defina pelo menos um setor econômico no FT1.")
    elif len(setores) != len(set(setores)):
        st.warning("Corrija os nomes duplicados no FT1 antes de continuar.")
    else:
        n = len(setores)
        
        if n == 4 and setores == [
            "Extração de Petróleo e Gás",
            "Fabricação de Resinas e Químicos",
            "Fabricação de Tintas e Vernizes",
            "Demais Setores Agregados"
        ]:
            z_padrao = np.array([
                [15000.0, 45000.0,   500.0, 80000.0],
                [ 2000.0, 25000.0,  6000.0, 40000.0],
                [  300.0,   800.0,  1200.0, 14000.0],
                [30000.0, 35000.0,  5500.0, 900000.0]
            ])
            x_padrao = np.array([[200000.0, 150000.0, 20000.0, 2500000.0]])
        else:
            z_padrao = np.zeros((n, n))
            x_padrao = np.ones((1, n)) * 1000.0

        df_Z_inicial = pd.DataFrame(z_padrao, index=setores, columns=setores)
        df_X_inicial = pd.DataFrame(x_padrao, index=["Produção Total (x_j)"], columns=setores)

        if "agg_Z" in st.session_state:
            df_Z_inicial = st.session_state["agg_Z"].reindex(index=setores, columns=setores).fillna(0.0)
        if "agg_X" in st.session_state:
            df_X_inicial = st.session_state["agg_X"].reindex(columns=setores).fillna(0.0)
            df_X_inicial.index = ["Produção Total (x_j)"]

        with st.expander("📤 Importar Matriz Z e Produção Total (x_j) já agregadas via CSV/Excel", expanded=False):
            col_up1, col_up2 = st.columns(2)
            with col_up1:
                up_Z = st.file_uploader("Upload Matriz Z (n x n)", type=["csv", "xlsx"], key="up_z")
            with col_up2:
                up_X = st.file_uploader("Upload Vetor Produção Total x_j (1 x n)", type=["csv", "xlsx"], key="up_x")

        try:
            if up_Z is not None:
                df_z_lido = ler_tabela_upload(up_Z, tem_indice=True)
                df_Z_inicial = df_z_lido.reindex(index=setores, columns=setores).fillna(0.0)
            elif arquivo_mestre is not None:
                xl = pd.ExcelFile(arquivo_mestre)
                if "Matriz_Z" in xl.sheet_names:
                    df_z_lido = pd.read_excel(xl, sheet_name="Matriz_Z", index_col=0)
                    df_z_lido.columns = [str(c).strip() for c in df_z_lido.columns]
                    df_z_lido.index = [str(i).strip() for i in df_z_lido.index]
                    df_Z_inicial = df_z_lido.reindex(index=setores, columns=setores).fillna(0.0)

            if up_X is not None:
                df_x_lido = ler_tabela_upload(up_X, tem_indice=True)
                df_X_inicial = df_x_lido.reindex(columns=setores).iloc[:1].fillna(0.0)
                df_X_inicial.index = ["Produção Total (x_j)"]
            elif arquivo_mestre is not None:
                xl = pd.ExcelFile(arquivo_mestre)
                if "Producao_X" in xl.sheet_names:
                    df_x_lido = pd.read_excel(xl, sheet_name="Producao_X", index_col=0)
                    df_x_lido.columns = [str(c).strip() for c in df_x_lido.columns]
                    df_X_inicial = df_x_lido.reindex(columns=setores).iloc[:1].fillna(0.0)
                    df_X_inicial.index = ["Produção Total (x_j)"]
        except Exception as e:
            st.error(f"Erro ao ler arquivo no FT2: {e}")

        st.subheader(f"1. Matriz de Fluxos Intermediários ($Z$) — [{unidade_monetaria}]")
        df_Z = st.data_editor(df_Z_inicial, use_container_width=True, key="editor_eco_Z")

        st.subheader(f"2. Valor da Produção Total Setorial ($x_j$) — [{unidade_monetaria}]")
        df_X = st.data_editor(df_X_inicial, use_container_width=True, key="editor_eco_X")

        Z_mat = df_Z.apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy()
        X_vec = df_X.apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy().flatten()

        if np.any(X_vec <= 0):
            st.error("⚠️ O Valor da Produção Total (x_j) deve ser maior que zero para todos os setores.")
        else:
            A_mat = Z_mat / X_vec[np.newaxis, :]
            I_mat = np.eye(n)
            I_minus_A = I_mat - A_mat

            col_a, col_l = st.columns(2)
            with col_a:
                st.markdown("**Matriz de Coeficientes Técnicos ($A_{ij} = z_{ij} / x_j$)**")
                df_A = pd.DataFrame(A_mat, index=setores, columns=setores)
                st.dataframe(df_A.style.format("{:.4f}"), use_container_width=True)

            with col_l:
                st.markdown("**Matriz Inversa de Leontief ($L = (I - A)^{-1}$)**")
                if np.isclose(np.linalg.det(I_minus_A), 0.0):
                    st.error("❌ A matriz (I - A) é singular (não inversível). Verifique os valores de Z e x_j.")
               
                else:
                    L_mat = np.linalg.inv(I_minus_A)
                    df_L = pd.DataFrame(L_mat, index=setores, columns=setores)
                    st.dataframe(df_L.style.format("{:.4f}"), use_container_width=True)
                    st.success("✅ Matrizes A e L calculadas com sucesso!")

# ==========================================
# FLUXO DE TRABALHO 3 (FT3)
# ==========================================
with tab3:
    st.header("3º Fluxo de Trabalho (FT3): Aspectos Ambientais ($B$) e Coeficientes ($R_s$)")

    if len(setores) == 0:
        st.warning("Defina os setores no FT1 primeiro.")
    elif "X_vec" not in locals() or np.any(X_vec <= 0):
        st.warning("Preencha valores válidos para a Produção Total (x_j) no FT2 primeiro.")
    else:
        n = len(setores)
        if n == 4 and setores == [
            "Extração de Petróleo e Gás",
            "Fabricação de Resinas e Químicos",
            "Fabricação de Tintas e Vernizes",
            "Demais Setores Agregados"
        ]:
            b_padrao = np.array([
                [42000.0, 28000.0,  1800.0, 350000.0],
                [15000.0, 22000.0,  3200.0, 480000.0]
            ])
        else:
            b_padrao = np.zeros((2, n))

        df_B_inicial = pd.DataFrame(b_padrao, columns=setores)
        df_B_inicial.insert(0, "Aspecto Ambiental (Unidade)", ["Emissões GEE (t CO2eq)", "Consumo de Energia (GJ)"])

        if "agg_B" in st.session_state:
            cols_finais = ["Aspecto Ambiental (Unidade)"] + setores
            df_B_inicial = st.session_state["agg_B"].reindex(columns=cols_finais).fillna(0.0)

        with st.expander("📤 Importar Matriz Ambiental (B) já agregada via CSV/Excel", expanded=False):
            up_B = st.file_uploader("Upload Matriz Ambiental B", type=["csv", "xlsx"], key="up_b")

        try:
            if up_B is not None:
                df_b_lido = ler_tabela_upload(up_B, tem_indice=False)
                col_nome = df_b_lido.columns[0]
                df_b_lido.rename(columns={col_nome: "Aspecto Ambiental (Unidade)"}, inplace=True)
                cols_finais = ["Aspecto Ambiental (Unidade)"] + setores
                df_B_inicial = df_b_lido.reindex(columns=cols_finais).fillna(0.0)
            elif arquivo_mestre is not None:
                xl = pd.ExcelFile(arquivo_mestre)
                if "Matriz_B" in xl.sheet_names:
                    df_b_lido = pd.read_excel(xl, sheet_name="Matriz_B")
                    df_b_lido.columns = [str(c).strip() for c in df_b_lido.columns]
                    col_nome = df_b_lido.columns[0]
                    df_b_lido.rename(columns={col_nome: "Aspecto Ambiental (Unidade)"}, inplace=True)
                    cols_finais = ["Aspecto Ambiental (Unidade)"] + setores
                    df_B_inicial = df_b_lido.reindex(columns=cols_finais).fillna(0.0)
        except Exception as e:
            st.error(f"Erro ao ler arquivo no FT3: {e}")

        st.subheader("1. Matriz de Cargas Ambientais Totais por Setor ($B$)")
        df_B = st.data_editor(
            df_B_inicial,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_eco_B"
        )

        nomes_aspectos = df_B["Aspecto Ambiental (Unidade)"].fillna("Aspecto sem nome").tolist()
        B_mat = df_B[setores].apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy()
        Rs_mat = B_mat / X_vec[np.newaxis, :]

        st.subheader(f"2. Matriz de Coeficientes Técnicos Ambientais ($R_s$) — [Unidade Ambiental / {unidade_monetaria}]")
        df_Rs = pd.DataFrame(Rs_mat, index=nomes_aspectos, columns=setores)
        st.dataframe(df_Rs.style.format("{:.6f}"), use_container_width=True)

# ==========================================
# FLUXO DE TRABALHO 4 (FT4)
# ==========================================
with tab4:
    st.header("4º Fluxo de Trabalho (FT4): Quantificação do Inventário ($q$) e Interpretação")

    if len(setores) == 0:
        st.warning("Complete os fluxos anteriores para visualizar os resultados.")
    elif "L_mat" not in locals() or "Rs_mat" not in locals():
        st.warning("⚠️ Certifique-se de que as matrizes dos passos FT2 e FT3 foram preenchidas corretamente sem erros.")
    else:
        try:
            y_vec = np.array(y_s_vetor, dtype=float).reshape(-1, 1)
            n = len(setores)
            m = len(nomes_aspectos)

            if L_mat.shape != (n, n) or Rs_mat.shape != (m, n) or y_vec.shape != (n, 1):
                st.error(
                    f"⚠️ Desalinhamento de dimensões: L={L_mat.shape}, Rs={Rs_mat.shape}, y={y_vec.shape}. "
                    "Verifique as abas anteriores."
                )
                st.stop()

            producao_induzida = np.dot(L_mat, y_vec)
            q_total = np.dot(Rs_mat, producao_induzida)
            contrib_setorial = Rs_mat * producao_induzida.T

            st.subheader(f"Resultados para: {uf_economica}")
            st.caption(f"**Função do Sistema:** {funcao}")

            col_res1, col_res2 = st.columns(2)

            with col_res1:
                st.markdown(f"**Produção Total Induzida na Economia ($x_{{ind}} = L \cdot y_s$) [{unidade_monetaria}]**")
                df_prod_ind = pd.DataFrame(producao_induzida, index=setores, columns=["Produção Induzida"])
                st.dataframe(df_prod_ind.style.format("{:.6f}"), use_container_width=True)

                st.markdown("**Carga Ambiental Total do Sistema ($q = R_s \cdot L \cdot y_s$)**")
                df_q_total = pd.DataFrame(q_total, index=nomes_aspectos, columns=["Carga Total (q)"])
                st.dataframe(df_q_total.style.format("{:.6f}"), use_container_width=True)

            with col_res2:
                st.markdown("**Contribuição por Setor Econômico (Análise de Hotspots)**")
                df_contrib = pd.DataFrame(contrib_setorial, index=nomes_aspectos, columns=setores)
                st.dataframe(df_contrib.style.format("{:.6f}"), use_container_width=True)

                modo_grafico = st.radio(
                    "Escala de visualização do gráfico:",
                    options=[
                        "Valores Absolutos",
                        "Normalizado (Log10)",
                        "Relativo (100% Empilhado)"
                    ],
                    horizontal=True,
                    help="Use Log10 quando houver grande diferença de magnitude ou Relativo (%) para ver a participação proporcional."
                )

                if modo_grafico == "Normalizado (Log10)":
                    df_transf = np.sign(df_contrib) * np.log10(np.abs(df_contrib) + 1)
                    eixo_y_label = "Log10(|Carga| + 1)"
                    titulo_grafico = "Contribuição por Setor (Escala Log10)"
                    modo_barra = "group"
                elif modo_grafico == "Relativo (100% Empilhado)":
                    somas = df_contrib.abs().sum(axis=1).replace(0, 1)
                    df_transf = df_contrib.div(somas, axis=0) * 100
                    eixo_y_label = "Participação (%)"
                    titulo_grafico = "Participação Relativa de Cada Setor (%)"
                    modo_barra = "stack"
                else:
                    df_transf = df_contrib.copy()
                    eixo_y_label = "Carga Ambiental"
                    titulo_grafico = "Participação Setorial na Carga Ambiental Total"
                    modo_barra = "stack"

                df_plot = df_transf.reset_index().melt(id_vars="index", var_name="Setor", value_name="Valor")
                df_plot.rename(columns={"index": "Aspecto Ambiental"}, inplace=True)

                fig = px.bar(
                    df_plot,
                    x="Aspecto Ambiental",
                    y="Valor",
                    color="Setor",
                    title=titulo_grafico,
                    labels={"Valor": eixo_y_label},
                    barmode=modo_barra,
                    text_auto='.2f'
                )
                st.plotly_chart(fig, use_container_width=True)

            st.divider()
            df_export = df_contrib.copy()
            df_export["Carga Total (q)"] = q_total
            csv = df_export.to_csv(sep=";", decimal=",").encode("utf-8-sig")

            st.download_button(
                label="📥 Baixar Relatório do Inventário Econômico (CSV)",
                data=csv,
                file_name="inventario_acv_economica.csv",
                mime="text/csv"
            )

        except Exception as e:
            st.error(f"❌ Ocorreu um erro inesperado no cálculo: {e}")

