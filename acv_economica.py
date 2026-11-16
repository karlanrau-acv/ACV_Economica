import io
import re
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
# FUNÇÕES AUXILIARES
# ==========================================
def extrair_codigo_4digitos(texto, eh_produto=False):
    match = re.search(r"\d+", str(texto))
    if not match:
        return ""
    num_str = match.group(0)
    if eh_produto:
        num_str = num_str.zfill(5)
        return num_str[:4]
    else:
        num_str = num_str.zfill(4)
        return num_str[:4]

def ler_tabela_upload(arquivo, tem_indice=True, tem_coluna_codigo_produto=False):
    nome = arquivo.name.lower()
    if tem_coluna_codigo_produto:
        idx_col = [0, 1]
        conversores = {0: str, 1: str}
    else:
        idx_col = 0 if tem_indice else None
        conversores = {0: str} if tem_indice else None

    if nome.endswith(".xlsx") or nome.endswith(".xls"):
        df = pd.read_excel(arquivo, index_col=idx_col, converters=conversores)
    else:
        conteudo = arquivo.getvalue().decode("utf-8-sig", errors="replace")
        sep = ";" if conteudo.count(";") > conteudo.count(",") else ","
        decimal = "," if sep == ";" else "."
        df = pd.read_csv(io.StringIO(conteudo), sep=sep, decimal=decimal, index_col=idx_col, dtype=str)
        df = df.apply(pd.to_numeric, errors="ignore")

    df.columns = [str(c).strip() for c in df.columns]

    if tem_coluna_codigo_produto and isinstance(df.index, pd.MultiIndex):
        novos_indices = []
        for idx in df.index:
            cod = str(idx).strip()
            desc = str(idx).strip()
            if cod.isdigit() and len(cod) == 4:
                cod = cod.zfill(5)
            if not cod or cod == "nan":
                novos_indices.append(desc)
            elif desc.startswith(cod) or desc.lstrip("0").startswith(cod.lstrip("0")):
                novos_indices.append(desc)
            else:
                novos_indices.append(f"{cod} - {desc}")
        df.index = novos_indices
    elif tem_indice:
        df.index = [str(i).strip() for i in df.index]

    return df

def agregar_matriz_com_mapeamento(df_Z_full, mapa_linhas_para_setor, setores_manter, nome_agregado="Outros"):
    df_num = df_Z_full.apply(pd.to_numeric, errors="coerce").fillna(0.0)
    colunas_resto = [c for c in df_num.columns if c not in setores_manter]

    df_col_agg = df_num[setores_manter].copy()
    if len(colunas_resto) > 0:
        df_col_agg[nome_agregado] = df_num[colunas_resto].sum(axis=1)

    ordem_final = setores_manter + ([nome_agregado] if len(colunas_resto) > 0 else [])

    df_col_agg["_Setor_Destino_"] = [mapa_linhas_para_setor.get(idx, nome_agregado) for idx in df_col_agg.index]
    df_final = df_col_agg.groupby("_Setor_Destino_").sum()
    df_final = df_final.reindex(index=ordem_final, columns=ordem_final).fillna(0.0)
    return df_final

def agregar_vetor_producao_x(df_X_full, colunas_Z_originais, setores_manter, nome_agregado="Outros"):
    """Agrega o vetor x_j (1 x 68) garantindo alinhamento com o cabeçalho da Matriz Z."""
    df_num = df_X_full.iloc[:1].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    
    # Se o número de colunas for igual ao de Z, alinha diretamente pelos cabeçalhos de Z
    if len(df_num.columns) == len(colunas_Z_originais):
        df_num.columns = colunas_Z_originais

    colunas_resto = [c for c in df_num.columns if c not in setores_manter]
    df_agg = df_num[setores_manter].copy()
    if len(colunas_resto) > 0:
        df_agg[nome_agregado] = df_num[colunas_resto].sum(axis=1)
    df_agg.index = ["Produção Total (x_j)"]
    return df_agg

# ==========================================
# BARRA LATERAL
# ==========================================
with st.sidebar:
import base64

def renderizar_logo_nitido(caminho_imagem, largura_px=155, texto_fallback=""):
    """Exibe o logotipo em alta nitidez dentro de um card branco com bordas arredondadas."""
    try:
        with open(caminho_imagem, "rb") as img_file:
            b64_str = base64.b64encode(img_file.read()).decode()
        html_logo = f"""
        <div style="background-color: #ffffff; padding: 10px 14px; border-radius: 10px; 
                    border: 1px solid #e0e0e0; display: flex; justify-content: center; 
                    align-items: center; box-shadow: 0 2px 4px rgba(0,0,0,0.06);">
            <img src="data:image/png;base64,{b64_str}" style="width: {largura_px}px; height: auto; object-fit: contain;">
        </div>
        """
        st.markdown(html_logo, unsafe_allow_html=True)
    except Exception:
        st.caption(texto_fallback)

col_logo1, col_titulo, col_logo2 = st.columns([1.2, 4.6, 1.2], vertical_alignment="center")

with col_logo1:
    renderizar_logo_nitido("logo_ufsc.png", largura_px=145, texto_fallback="UFSC")

with col_titulo:
    st.title("📊 Avaliação do Ciclo de Vida Baseada em Dados Econômicos")
    st.markdown("Quantificação de inventário ambiental via **Matriz Insumo-Produto (MIP) / Tabela de Recursos e Usos (TRU)**.")

with col_logo2:
    renderizar_logo_nitido("logo_ifc.png", largura_px=155, texto_fallback="IFC")

st.title("📊 Avaliação do Ciclo de Vida Baseada em Dados Econômicos")
st.markdown("Quantificação de inventário ambiental via **Matriz Insumo-Produto (MIP) / Tabela de Recursos e Usos (TRU)**.")

tab1, tab2, tab3, tab4 = st.tabs([
    "1️⃣ FT1: Escopo e Demanda (y_s)",
    "2️⃣ FT2: Matriz Econômica (Z, A e L)",
    "3️⃣ FT3: Matriz Ambiental (B e R_s)",
    "4️⃣ FT4: Cálculo e Interpretação (q)"
])

# ==========================================
# FLUXO DE TRABALHO 1 (FT1)
# ==========================================
with tab1:
    st.header("1º Fluxo de Trabalho (FT1): Função do Sistema, Cadeia Produtiva e Demanda Final ($y_s$)")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        funcao = st.text_input("Função do Sistema:", value="Colorir paredes internas de uma residência")
    with col2:
        uf_economica = st.text_input("Unidade Funcional / Bloco de Consumo:", value="R$ 1.000,00 em tintas e vernizes")
    with col3:
        unidade_monetaria = st.text_input("Unidade Monetária das Tabelas:", value="R$ Milhões")

    st.subheader("Setores da Cadeia Produtiva e Demanda Final ($y_s$)")
    st.info("💡 **Dica:** Se você vai importar uma tabela completa (128×68 ou 68×68) no **FT2**, pode ir direto para o **FT2** selecionar os produtos/setores; a lista abaixo será atualizada automaticamente com os setores agregados para você preencher apenas a Demanda Final ($y_s$).")

    if "setores_agregados_ft2" in st.session_state:
        setores_ini = st.session_state["setores_agregados_ft2"]
        demandas_ini = [0.0] * len(setores_ini)
        df_ft1_inicial = pd.DataFrame({
            "Setor Econômico (Agregado no FT2)": setores_ini,
            "Demanda Final (y_s)": demandas_ini
        })
    else:
        df_ft1_inicial = pd.DataFrame({
            "Setor Econômico (Agregado no FT2)": [
                "0680 - Extração de Petróleo e Gás",
                "2010 - Fabricação de Resinas e Químicos",
                "2091 - Fabricação de Tintas e Vernizes",
                "Outros"
            ],
            "Demanda Final (y_s)": [0.0, 0.0, 0.001, 0.0]
        })

    df_ft1 = st.data_editor(
        df_ft1_inicial,
        num_rows="dynamic",
        use_container_width=True,
        key="editor_eco_ft1"
    )

    df_limpo = df_ft1.dropna(subset=["Setor Econômico (Agregado no FT2)"]).copy()
    df_limpo["Setor Econômico (Agregado no FT2)"] = df_limpo["Setor Econômico (Agregado no FT2)"].astype(str).str.strip()
    df_limpo = df_limpo[df_limpo["Setor Econômico (Agregado no FT2)"] != ""]

    setores_ft1 = df_limpo["Setor Econômico (Agregado no FT2)"].tolist()
    y_s_vetor = pd.to_numeric(df_limpo["Demanda Final (y_s)"], errors="coerce").fillna(0.0).tolist()

    st.subheader("Diagrama de Setores e Demanda Final")
    if len(setores_ft1) > 0:
        dot_code = 'digraph G {\n  rankdir=LR;\n  node [shape=box, style="rounded,filled", fontname="Arial"];\n'
        for _, row in df_limpo.iterrows():
            nome = row["Setor Econômico (Agregado no FT2)"].replace('"', '')
            demanda = row["Demanda Final (y_s)"] if pd.notna(row["Demanda Final (y_s)"]) else 0.0
            cor_fundo = "#d1ecf1" if demanda > 0 else "#f8f9fa"
            cor_borda = "#0c5460" if demanda > 0 else "#6c757d"
            dot_code += f'  "{nome}" [fillcolor="{cor_fundo}", color="{cor_borda}", label="{nome}\\n(y_s = {demanda} {unidade_monetaria})"];\n'
        for i in range(len(setores_ft1) - 1):
            s1 = setores_ft1[i].replace('"', '')
            s2 = setores_ft1[i+1].replace('"', '')
            dot_code += f'  "{s1}" -> "{s2}" [style=dashed, color="#adb5bd"];\n'
        dot_code += '}'
        st.graphviz_chart(dot_code)

# ==========================================
# FLUXO DE TRABALHO 2 (FT2)
# ==========================================
with tab2:
    st.header("2º Fluxo de Trabalho (FT2): Tabela Z, Produção Total ($x_j$), Coeficientes ($A$) e Leontief ($L$)")

    modo_ft2 = st.radio(
        "Modo de entrada dos dados econômicos:",
        options=[
            "📂 Importar e Agregar Tabela Completa (TRU 128×68 ou MIP 68×68)",
            "✍️ Editar Manualmente a Matriz Z já Agregada"
        ],
        horizontal=True
    )

    if modo_ft2 == "📂 Importar e Agregar Tabela Completa (TRU 128×68 ou MIP 68×68)":
        c_tipo, c_cod = st.columns(list((1.5, 1)))
        with c_tipo:
            tipo_tabela = st.radio(
                "Formato da Matriz Z:",
                options=[
                    "Tabela de Recursos e Usos — Produto × Setor (128 × 68)",
                    "Matriz Quadrada — Setor × Setor (68 × 68)"
                ],
                horizontal=True
            )
        with c_cod:
            possui_col_codigo = st.checkbox(
                "A 1ª coluna contém o Código do Produto (e a 2ª o Nome)?",
                value=True
            )

        col_up1, col_up2 = st.columns(2)
        with col_up1:
            up_full_Z = st.file_uploader("1. Tabela Z Completa (128×68 ou 68×68) [Obrigatório]", type=list(("csv", "xlsx")), key="up_full_z_ft2")
        with col_up2:
            up_full_X = st.file_uploader("2. Vetor Produção Total x_j (1×68) [Mesmo cabeçalho da Matriz Z]", type=list(("csv", "xlsx")), key="up_full_x_ft2")

        if up_full_Z is None:
            if st.button("🧪 Carregar Exemplo Sintético IBGE (128×68) para Testar"):
                setores_sim = [f"{i:04d} - Setor_{i:02d}" for i in range(1, 69)]
                setores_sim.__setitem__(0, "0680 - Extração de Petróleo e Gás")
                setores_sim.__setitem__(1, "2010 - Fabricação de Resinas e Químicos")
                setores_sim.__setitem__(2, "2091 - Fabricação de Tintas e Vernizes")

                np.random.seed(42)
                prods_sim = [f"{(i % 68) + 1:04d}1 - Produto_{i:03d}" for i in range(1, 129)]
                prods_sim.__setitem__(0, "06801 - Petróleo bruto")
                prods_sim.__setitem__(1, "06802 - Gás natural")
                prods_sim.__setitem__(2, "20101 - Resinas termoplásticas")
                prods_sim.__setitem__(3, "20102 - Solventes e aditivos")
                prods_sim.__setitem__(4, "20911 - Tintas e vernizes")

                st.session_state["sim_Z_ft2"] = pd.DataFrame(np.random.uniform(10, 500, (128, 68)), index=prods_sim, columns=setores_sim)
                st.session_state["sim_X_ft2"] = pd.DataFrame([np.random.uniform(40000, 150000, 68)], index=list(("Producao_Total",)), columns=setores_sim)

        df_Z_raw, df_X_raw = None, None
        try:
            if up_full_Z is not None:
                usar_duas_cols = possui_col_codigo and ("128 × 68" in tipo_tabela)
                df_Z_raw = ler_tabela_upload(up_full_Z, tem_indice=True, tem_coluna_codigo_produto=usar_duas_cols)
                if up_full_X is not None:
                    df_X_raw = ler_tabela_upload(up_full_X, tem_indice=True)
            elif "sim_Z_ft2" in st.session_state:
                df_Z_raw = st.session_state["sim_Z_ft2"]
                df_X_raw = st.session_state.get("sim_X_ft2")
        except Exception as e:
            st.error(f"Erro ao ler os arquivos no FT2: {e}")

        if df_Z_raw is not None:
            st.success(f"✅ Matriz Z carregada: **{df_Z_raw.shape.__getitem__(0)} linhas × {df_Z_raw.shape.__getitem__(1)} colunas**.")
            todas_linhas = df_Z_raw.index.tolist()
            todas_colunas = df_Z_raw.columns.tolist()
            nome_agregado = "Outros"

            mapa_cod_setor = {}
            for col_setor in todas_colunas:
                cod4 = extrair_codigo_4digitos(col_setor, eh_produto=False)
                if cod4:
                    mapa_cod_setor[cod4] = col_setor

            setor_correspondente_linha = []
            for linha in todas_linhas:
                if "Setor × Setor" in tipo_tabela and linha in todas_colunas:
                    setor_correspondente_linha.append(linha)
                else:
                    cod4 = extrair_codigo_4digitos(linha, eh_produto=True)
                    setor_correspondente_linha.append(mapa_cod_setor.get(cod4, "Sem código correspondente"))

            st.subheader("1º Passo: Selecione os Produtos / Setores de Interesse (Linhas)")
            st.caption("Marque os itens desejados. Os setores (colunas) relacionados serão ativados automaticamente e os demais somados em **'Outros'**.")

            exemplos_padrao = list(("06801 - Petróleo bruto", "20101 - Resinas termoplásticas", "20102 - Solventes e aditivos", "20911 - Tintas e vernizes"))
            selecao_inicial = [l in exemplos_padrao for l in todas_linhas]
            if not any(selecao_inicial) and len(todas_linhas) >= 3:
                selecao_inicial[:3] = list((True, True, True))

            df_quadro = pd.DataFrame({
                "Selecionar": selecao_inicial,
                "Produto / Linha": todas_linhas,
                "Setor Vinculado (Coluna)": setor_correspondente_linha
            })

            df_editado = st.data_editor(
                df_quadro,
                hide_index=True,
                use_container_width=True,
                height=300,
                disabled=list(("Produto / Linha", "Setor Vinculado (Coluna)")),
                key="quadro_ft2_selecao"
            )

            df_marcados = df_editado[df_editado["Selecionar"] == True]
            if len(df_marcados) > 0:
                setores_ativados_set = set(df_marcados["Setor Vinculado (Coluna)"]) - {"Sem código correspondente"}
                colunas_escolhidas = [c for c in todas_colunas if c in setores_ativados_set]

                if len(colunas_escolhidas) > 0:
                    # ==============================================================
                    # NOVO PASSO: AGRUPAR E/OU RENOMEAR SETORES RESULTANTES
                    # ==============================================================
                    st.subheader("2º Passo: Agrupar ou Renomear Setores Resultantes (Opcional)")
                    st.caption("Edite a coluna **'Novo Nome do Setor (Editável)'**. Para **unir** dois ou mais setores em um novo setor agregado, basta atribuir a eles o **mesmo nome**.")

                    df_renomear = pd.DataFrame({
                        "Setor Original Ativado": colunas_escolhidas,
                        "Novo Nome do Setor (Editável)": colunas_escolhidas
                    })

                    df_renomeado_edit = st.data_editor(
                        df_renomear,
                        hide_index=True,
                        use_container_width=True,
                        disabled=list(("Setor Original Ativado",)),
                        key="editor_renomear_setores_ft2"
                    )

                    # Cria dicionário: Setor Original -> Novo Nome Escolhido
                    mapa_renomeacao = {}
                    for _, r_row in df_renomeado_edit.iterrows():
                        orig = r_row["Setor Original Ativado"]
                        novo = str(r_row["Novo Nome do Setor (Editável)"]).strip()
                        mapa_renomeacao[orig] = novo if novo and novo != "nan" else orig

                    # 1. Gera matriz intermediária com os setores escolhidos + Outros
                    mapa_linhas_orig = {}
                    for _, row in df_editado.iterrows():
                        prod = row["Produto / Linha"]
                        setor_dest = row["Setor Vinculado (Coluna)"]
                        mapa_linhas_orig[prod] = setor_dest if (row["Selecionar"] and setor_dest in colunas_escolhidas) else nome_agregado

                    df_Z_interm = agregar_matriz_com_mapeamento(df_Z_raw, mapa_linhas_orig, colunas_escolhidas, nome_agregado)

                    if df_X_raw is not None:
                        df_X_interm = agregar_vetor_producao_x(df_X_raw, todas_colunas, colunas_escolhidas, nome_agregado)
                    else:
                        df_X_interm = pd.DataFrame(np.ones((1, len(df_Z_interm.columns))) * 1000.0, index=list(("Produção Total (x_j)",)), columns=df_Z_interm.columns)

                    # 2. Aplica a fusão e renomeação dos setores (somando linhas e colunas com o mesmo novo nome)
                    novos_nomes_cols = [mapa_renomeacao.get(c, c) for c in df_Z_interm.columns]
                    
                    # Ordem preservada sem duplicatas
                    ordem_final_renomeada = []
                    for nome_s in novos_nomes_cols:
                        if nome_s not in ordem_final_renomeada:
                            ordem_final_renomeada.append(nome_s)

                    df_Z_agg = df_Z_interm.copy()
                    df_Z_agg.columns = novos_nomes_cols
                    df_Z_agg.index = novos_nomes_cols
                    # Soma colunas com mesmo nome e depois linhas com mesmo nome
                    df_Z_agg = df_Z_agg.T.groupby(level=0).sum().T.groupby(level=0).sum()
                    df_Z_agg = df_Z_agg.reindex(index=ordem_final_renomeada, columns=ordem_final_renomeada).fillna(0.0)

                    df_X_agg = df_X_interm.copy()
                    df_X_agg.columns = novos_nomes_cols
                    df_X_agg = df_X_agg.T.groupby(level=0).sum().T
                    df_X_agg = df_X_agg.reindex(columns=ordem_final_renomeada).fillna(0.0)
                    df_X_agg.index = list(("Produção Total (x_j)",))

                    setores_ativos = df_Z_agg.columns.tolist()

                    if st.session_state.get("setores_agregados_ft2") != setores_ativos:
                        st.session_state["setores_agregados_ft2"] = setores_ativos

                    st.subheader(f"3º Passo: Matriz Z Agregada Final ({len(setores_ativos)} × {len(setores_ativos)}) — [{unidade_monetaria}]")
                    df_Z = st.data_editor(df_Z_agg, use_container_width=True, key="editor_Z_agregada")

                    st.subheader(f"Produção Total Setorial Agregada ($x_j$) — [{unidade_monetaria}]")
                    df_X = st.data_editor(df_X_agg, use_container_width=True, key="editor_X_agregada")
                else:
                    st.error("❌ Nenhum produto selecionado possui código correspondente às colunas de Z.")
            else:
                st.warning("⚠️ Marque pelo menos 1 item no quadro acima.")
    else:
        setores_ativos = setores_ft1
        n_man = len(setores_ativos)
        if n_man > 0:
            if n_man == 4 and setores_ativos == list((
                "0680 - Extração de Petróleo e Gás",
                "2010 - Fabricação de Resinas e Químicos",
                "2091 - Fabricação de Tintas e Vernizes",
                "Outros"
            )):
                z_pad = np.array([
                    [15000.0, 45000.0,   500.0, 80000.0],
                    [ 2000.0, 25000.0,  6000.0, 40000.0],
                    [  300.0,   800.0,  1200.0, 14000.0],
                    [30000.0, 35000.0,  5500.0, 900000.0]
                ])
                x_pad = np.array([[200000.0, 150000.0, 20000.0, 2500000.0]])
            else:
                z_pad = np.zeros((n_man, n_man))
                x_pad = np.ones((1, n_man)) * 1000.0

            st.subheader(f"1. Matriz de Fluxos Intermediários ($Z$) — [{unidade_monetaria}]")
            df_Z = st.data_editor(pd.DataFrame(z_pad, index=setores_ativos, columns=setores_ativos), use_container_width=True, key="editor_Z_manual")

            st.subheader(f"2. Valor da Produção Total Setorial ($x_j$) — [{unidade_monetaria}]")
            df_X = st.data_editor(pd.DataFrame(x_pad, index=list(("Produção Total (x_j)",)), columns=setores_ativos), use_container_width=True, key="editor_X_manual")

    if "df_Z" in locals() and "df_X" in locals():
        setores_finais = df_Z.columns.tolist()
        n = len(setores_finais)
        Z_mat = df_Z.apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy()
        X_vec = df_X.apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy().flatten()

        if np.any(X_vec <= 0):
            st.error("⚠️ O Valor da Produção Total (x_j) deve ser maior que zero para todos os setores.")
        else:
            A_mat = Z_mat / X_vec[np.newaxis, :]
            I_minus_A = np.eye(n) - A_mat

            col_a, col_l = st.columns(2)
            with col_a:
                st.markdown("**Matriz de Coeficientes Técnicos ($A_{ij} = z_{ij} / x_j$)**")
                df_A = pd.DataFrame(A_mat, index=setores_finais, columns=setores_finais)
                st.dataframe(df_A.style.format("{:.4f}"), use_container_width=True)

            with col_l:
                st.markdown("**Matriz Inversa de Leontief ($L = (I - A)^{-1}$)**")
                if np.isclose(np.linalg.det(I_minus_A), 0.0):
                    st.error("❌ A matriz (I - A) é singular (não inversível). Verifique os valores de Z e x_j.")
                else:
                    L_mat = np.linalg.inv(I_minus_A)
                    df_L = pd.DataFrame(L_mat, index=setores_finais, columns=setores_finais)
                    st.dataframe(df_L.style.format("{:.4f}"), use_container_width=True)
                    st.success("✅ Matrizes A e L prontas! Siga para o **FT3**.")

# ==========================================
# FLUXO DE TRABALHO 3 (FT3)
# ==========================================
with tab3:
    st.header("3º Fluxo de Trabalho (FT3): Matriz Ambiental ($B$) e Coeficientes ($R_s$)")

    if "setores_finais" not in locals() or "X_vec" not in locals() or np.any(X_vec <= 0):
        st.warning("⚠️ Complete a etapa econômica no **FT2** primeiro para carregar os setores agregados.")
    else:
        n = len(setores_finais)
        st.info(f"📌 Os cabeçalhos da Matriz Ambiental estão sincronizados com os **{n} setores** resultantes do FT2.")

        # Gera modelo Excel pronto da Matriz Ambiental B com os setores exatos do FT2
        def gerar_modelo_B_excel(cols_setores):
            out = io.BytesIO()
            df_mod = pd.DataFrame(np.zeros((2, len(cols_setores))), columns=cols_setores)
            df_mod.insert(0, "Aspecto Ambiental (Unidade)", ["Emissoes GEE (t CO2eq)", "Consumo de Energia (GJ)"])
            with pd.ExcelWriter(out, engine="openpyxl") as writer:
                df_mod.to_excel(writer, sheet_name="Matriz_B", index=False)
            return out.getvalue()

        col_mod1, col_mod2 = st.columns([1, 1.5])
        with col_mod1:
            try:
                st.download_button(
                    label="📥 Baixar Modelo Excel da Matriz B",
                    data=gerar_modelo_B_excel(setores_finais),
                    file_name="modelo_matriz_ambiental_B.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            except Exception:
                pass
        with col_mod2:
            up_B_ft3 = st.file_uploader(
                "Ou faça upload da Matriz Ambiental B já agregada (.xlsx ou .csv)",
                type=["xlsx", "csv"],
                key="up_b_ft3"
            )

        if n == 4 and setores_finais == [
            "0680 - Extração de Petróleo e Gás",
            "2010 - Fabricação de Resinas e Químicos",
            "2091 - Fabricação de Tintas e Vernizes",
            "Outros"
        ]:
            b_padrao = np.array([
                [42000.0, 28000.0,  1800.0, 350000.0],
                [15000.0, 22000.0,  3200.0, 480000.0]
            ])
        else:
            b_padrao = np.zeros((2, n))

        df_B_inicial = pd.DataFrame(b_padrao, columns=setores_finais)
        df_B_inicial.insert(0, "Aspecto Ambiental (Unidade)", ["Emissões GEE (t CO2eq)", "Consumo de Energia (GJ)"])

        if up_B_ft3 is not None:
            try:
                df_b_lido = ler_tabela_upload(up_B_ft3, tem_indice=False)
                col_nome = df_b_lido.columns[0]
                df_b_lido.rename(columns={col_nome: "Aspecto Ambiental (Unidade)"}, inplace=True)
                cols_esperadas = ["Aspecto Ambiental (Unidade)"] + setores_finais
                df_B_inicial = df_b_lido.reindex(columns=cols_esperadas).fillna(0.0)
                st.success("✅ Matriz Ambiental B carregada com sucesso!")
            except Exception as e:
                st.error(f"Erro ao ler Matriz B: {e}")

        st.subheader("1. Matriz de Cargas Ambientais Totais por Setor ($B$)")
        st.caption("Digite os valores diretamente na tabela abaixo (use '+' na base para adicionar mais indicadores ambientais):")
        df_B = st.data_editor(
            df_B_inicial,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_eco_B_ft3"
        )

        nomes_aspectos = df_B["Aspecto Ambiental (Unidade)"].fillna("Aspecto sem nome").tolist()
        B_mat = df_B[setores_finais].apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy()
        Rs_mat = B_mat / X_vec[np.newaxis, :]

        st.subheader(f"2. Matriz de Coeficientes Técnicos Ambientais ($R_s$) — [Unidade Ambiental / {unidade_monetaria}]")
        df_Rs = pd.DataFrame(Rs_mat, index=nomes_aspectos, columns=setores_finais)
        st.dataframe(df_Rs.style.format("{:.6f}"), use_container_width=True)

# ==========================================
# FLUXO DE TRABALHO 4 (FT4)
# ==========================================
with tab4:
    st.header("4º Fluxo de Trabalho (FT4): Quantificação do Inventário ($q$) e Interpretação")

    if "L_mat" not in locals() or "Rs_mat" not in locals() or "setores_finais" not in locals():
        st.warning("⚠️ Complete os passos nos fluxos FT1, FT2 e FT3 para visualizar os resultados.")
    else:
        try:
            n = len(setores_finais)
            m = len(nomes_aspectos)

            if len(y_s_vetor) == n:
                y_vec = np.array(y_s_vetor, dtype=float).reshape(-1, 1)
            else:
                st.warning("⚠️ Os setores foram atualizados no FT2. Ajuste a **Demanda Final ($y_s$)** abaixo ou na aba **FT1**:")
                df_y_rapido = st.data_editor(
                    pd.DataFrame({"Setor": setores_finais, "Demanda Final (y_s)": [0.0] * n}),
                    hide_index=True,
                    use_container_width=True,
                    key="y_rapido_ft4"
                )
                y_vec = pd.to_numeric(df_y_rapido["Demanda Final (y_s)"], errors="coerce").fillna(0.0).to_numpy().reshape(-1, 1)

            if L_mat.shape != (n, n) or Rs_mat.shape != (m, n) or y_vec.shape != (n, 1):
                st.error(f"⚠️ Desalinhamento de dimensões: L={L_mat.shape}, Rs={Rs_mat.shape}, y={y_vec.shape}.")
                st.stop()

            producao_induzida = np.dot(L_mat, y_vec)
            q_total = np.dot(Rs_mat, producao_induzida)
            contrib_setorial = Rs_mat * producao_induzida.T

            st.subheader(f"Resultados para: {uf_economica}")
            st.caption(f"**Função do Sistema:** {funcao}")

            col_res1, col_res2 = st.columns(2)

            with col_res1:
                st.markdown(f"**Produção Total Induzida na Economia ($x_{{ind}} = L \cdot y_s$) [{unidade_monetaria}]**")
                df_prod_ind = pd.DataFrame(producao_induzida, index=setores_finais, columns=["Produção Induzida"])
                st.dataframe(df_prod_ind.style.format("{:.6f}"), use_container_width=True)

                st.markdown("**Carga Ambiental Total do Sistema ($q = R_s \cdot L \cdot y_s$)**")
                df_q_total = pd.DataFrame(q_total, index=nomes_aspectos, columns=["Carga Total (q)"])
                st.dataframe(df_q_total.style.format("{:.6f}"), use_container_width=True)

            with col_res2:
                st.markdown("**Contribuição por Setor Econômico (Análise de Hotspots)**")
                df_contrib = pd.DataFrame(contrib_setorial, index=nomes_aspectos, columns=setores_finais)
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
