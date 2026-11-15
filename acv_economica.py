import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px

# Configuração da página
st.set_page_config(
    page_title="Plataforma ACV Econômica (Insumo-Produto)",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Barra lateral com guia rápido
with st.sidebar:
    st.title("📊 Guia Rápido - ACV Econômica")
    st.markdown("""
    Esta ferramenta automatiza a **Avaliação do Ciclo de Vida Baseada em Dados Econômicos** (Modelo Insumo-Produto / TRU):
    
    $$q = R_s \cdot (I - A)^{-1} \cdot y_s$$
    
    **Fluxos de Trabalho:**
    1. **FT1:** Defina função, setores agregados e Demanda Final ($y_s$).
    2. **FT2:** Insira a Matriz de Fluxos ($Z$) e Produção Total ($x_j$) para obter $A$ e $L = (I - A)^{-1}$.
    3. **FT3:** Insira cargas ambientais setoriais ($B$) para obter os coeficientes $R_s$.
    4. **FT4:** Calcule $q$, analise os setores críticos e exporte o relatório.
    """)
    st.divider()
    if st.button("🔄 Restaurar Exemplo Padrão"):
        st.session_state.clear()
        st.rerun()

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
    st.header("1º Fluxo de Trabalho (FT1): Função, Setores e Demanda Final ($y_s$)")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        funcao = st.text_input("Função do Sistema:", value="Colorir paredes internas de uma residência")
    with col2:
        uf_economica = st.text_input("Unidade Funcional / Bloco de Consumo:", value="R$ 1.000,00 em tintas e vernizes")
    with col3:
        unidade_monetaria = st.text_input("Unidade Monetária das Tabelas:", value="R$ Milhões")

    st.subheader("Setores da Cadeia Produtiva e Demanda Final ($y_s$)")
    st.info("Inclua os setores de interesse da cadeia produtiva e o setor agregado ('Demais Setores') conforme a TRU/MIP. Use '+' na base para adicionar linhas.")

    df_ft1_inicial = pd.DataFrame({
        "Setor Econômico": [
            "Extração de Petróleo e Gás",
            "Fabricação de Resinas e Químicos",
            "Fabricação de Tintas e Vernizes",
            "Demais Setores Agregados"
        ],
        "Demanda Final (y_s)": [0.0, 0.0, 0.001, 0.0]  # Ex: R$ 1.000 = 0.001 R$ Milhões
    })

    df_ft1 = st.data_editor(
        df_ft1_inicial,
        num_rows="dynamic",
        use_container_width=True,
        key="editor_eco_ft1"
    )

    # Limpeza e validação dos setores
    df_limpo = df_ft1.dropna(subset=["Setor Econômico"]).copy()
    df_limpo["Setor Econômico"] = df_limpo["Setor Econômico"].astype(str).str.strip()
    df_limpo = df_limpo[df_limpo["Setor Econômico"] != ""]

    setores = df_limpo["Setor Econômico"].tolist()
    y_s_vetor = pd.to_numeric(df_limpo["Demanda Final (y_s)"], errors="coerce").fillna(0.0).tolist()

    if len(setores) != len(set(setores)):
        st.error("⚠️ Existem setores com nomes duplicados. Renomeie-os para evitar conflitos nas matrizes.")

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
    st.markdown(f"Insira os fluxos intermediários da **Matriz $Z$** (consumo do setor linha pelo setor coluna, em **{unidade_monetaria}**) e o **Valor da Produção Total ($x_j$)** de cada setor.")

    if len(setores) == 0:
        st.warning("Defina pelo menos um setor econômico no FT1.")
    elif len(setores) != len(set(setores)):
        st.warning("Corrija os nomes duplicados no FT1 antes de continuar.")
    else:
        n = len(setores)
        
        # Exemplo ilustrativo padrão caso sejam os 4 setores iniciais
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

        st.subheader("1. Matriz de Fluxos Intermediários ($Z$) — [Produto/Setor × Setor]")
        df_Z_inicial = pd.DataFrame(z_padrao, index=setores, columns=setores)
        df_Z = st.data_editor(df_Z_inicial, use_container_width=True, key="editor_eco_Z")

        st.subheader(f"2. Valor da Produção Total Setorial ($x_j$) — [{unidade_monetaria}]")
        df_X_inicial = pd.DataFrame(x_padrao, index=["Produção Total (x_j)"], columns=setores)
        df_X = st.data_editor(df_X_inicial, use_container_width=True, key="editor_eco_X")

        # Conversão e cálculos do FT2: A_ij = z_ij / x_j  e  L = (I - A)^(-1)
        Z_mat = df_Z.apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy()
        X_vec = df_X.apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy().flatten()

        if np.any(X_vec <= 0):
            st.error("⚠️ O Valor da Produção Total (x_j) deve ser maior que zero para todos os setores (evita divisão por zero).")
        else:
            # Calcula Matriz A dividindo cada coluna j por x_j
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
    st.markdown("Insira as cargas ambientais totais anuais de cada setor ($b_{ij}$, ex: dados do SEEG, SIRENE, EPE, ANA). O sistema dividirá pela produção setorial ($x_j$) para obter **$R_{s,ij} = b_{ij} / x_j$**.")

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
                [42000.0, 28000.0,  1800.0, 350000.0], # Ex: t CO2eq
                [15000.0, 22000.0,  3200.0, 480000.0]  # Ex: GJ de Energia
            ])
        else:
            b_padrao = np.zeros((2, n))

        df_B_inicial = pd.DataFrame(b_padrao, columns=setores)
        df_B_inicial.insert(0, "Aspecto Ambiental (Unidade)", ["Emissões GEE (t CO2eq)", "Consumo de Energia (GJ)"])

        st.subheader("1. Matriz de Cargas Ambientais Totais por Setor ($B$)")
        df_B = st.data_editor(
            df_B_inicial,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_eco_B"
        )

        # Cálculo automático de R_s = B / x_j
        nomes_aspectos = df_B["Aspecto Ambiental (Unidade)"].fillna("Aspecto sem nome").tolist()
        B_mat = df_B[setores].apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy()
        Rs_mat = B_mat / X_vec[np.newaxis, :]

        st.subheader(f"2. Matriz de Coeficientes Técnicos Ambientais ($R_s$) — [Unidade Ambiental / {unidade_monetaria}]")
        df_Rs = pd.DataFrame(Rs_mat, index=nomes_aspectos, columns=setores)

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

            # Correção: Rs_mat tem dimensão (m, n), onde m = nº de aspectos e n = nº de setores
            if L_mat.shape != (n, n) or Rs_mat.shape != (m, n) or y_vec.shape != (n, 1):
                st.error(
                    f"⚠️ Desalinhamento de dimensões: L={L_mat.shape}, Rs={Rs_mat.shape}, y={y_vec.shape}. "
                    "Verifique as abas anteriores."
                )
                st.stop()

            # Equação fundamental: q = Rs * (I - A)^(-1) * y_s
            producao_induzida = np.dot(L_mat, y_vec)           # Vetor x_induzido = L * y_s (dimensão n x 1)
            q_total = np.dot(Rs_mat, producao_induzida)        # Vetor q = Rs * L * y_s (dimensão m x 1)
            contrib_setorial = Rs_mat * producao_induzida.T    # Contribuição de cada setor (dimensão m x n)

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

                # Seletor de escala para visualização gráfica
                modo_grafico = st.radio(
                    "Escala de visualização do gráfico:",
                    options=[
                        "Valores Absolutos",
                        "Normalizado (Log10)",
                        "Relativo (100% Empilhado)"
                    ],
                    horizontal=True,
                    help="Em ACV Econômica, emissões (kg) e energia (MJ/GJ) costumam ter ordens de grandeza muito distintas. Use Log10 ou Relativo (%) para comparar."
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

            # Exportação completa para Excel/CSV
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
