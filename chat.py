import streamlit as st
import os
import time  

from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

import google.generativeai as genai

# Configuración de la página
st.set_page_config(
    page_title="Asistente de Normativa Institucional",
    page_icon="🏛️",
    layout="wide"
)

# Funcion retriver con parámetros para experimentar
def obtener_retriever(chunk_size_test=1000, k_test=4):
    ruta_data = "./data"
    ruta_indice = f"./indice_faiss_chunk_{chunk_size_test}"
    
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    
    if os.path.exists(ruta_indice):
        vectorstore = FAISS.load_local(
            ruta_indice,
            embeddings,
            allow_dangerous_deserialization=True
        )
    else:
        if not os.path.exists(ruta_data):
            st.error(f"No existe la carpeta {ruta_data}")
            return None
            
        with st.spinner(f"Procesando documentos con chunk {chunk_size_test}..."):
            loader = PyPDFDirectoryLoader(ruta_data)
            documents = loader.load()
            
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size_test,
                chunk_overlap=int(chunk_size_test * 0.15)
            )
            docs = text_splitter.split_documents(documents)
            
            vectorstore = FAISS.from_documents(docs, embeddings)
            vectorstore.save_local(ruta_indice)
            st.success(f"Base de datos creada para chunk {chunk_size_test}")
    
    return vectorstore.as_retriever(search_kwargs={"k": k_test})

st.title("🏛️ Asistente Inteligente de Reglamentos")
st.markdown("Consulta cualquier duda sobre los 44 reglamentos institucionales.")

# Controles de experimento en la barra lateral
st.sidebar.header("Panel de Experimentos")

c_size = st.sidebar.select_slider(
    "Tamaño de Chunk (Chunk Size)",
    options=[500, 1000, 1500],
    value=1000
)

k_val = st.sidebar.slider(
    "Cantidad de fragmentos (k)",
    min_value=2,
    max_value=7,
    value=4
)

# llamamos a la función con los valores seleccionados
retriever = obtener_retriever(chunk_size_test=c_size, k_test=k_val)

# API KEY
GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=GOOGLE_API_KEY)
modelo = genai.GenerativeModel("models/gemini-2.5-flash")

# Función para formatear documentos
def format_docs(docs):
    texto = ""
    for doc in docs:
        fuente = os.path.basename(doc.metadata.get('source', ''))
        pagina = doc.metadata.get('page', '')
        texto += f"\nFuente: {fuente} (Pág. {pagina})\n"
        texto += doc.page_content + "\n\n"
    return texto

# Estado
if "messages" not in st.session_state:
    st.session_state.messages = []

# Mostrar historial
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt_usuario = st.chat_input("Escribe tu duda...")

if prompt_usuario and retriever:
    st.chat_message("user").markdown(prompt_usuario)
    st.session_state.messages.append({"role": "user", "content": prompt_usuario})

    try:
        with st.spinner("Consultando reglamentos..."):
            inicio = time.time() # <--- MARCA DE INICIO
            
            docs = retriever.invoke(prompt_usuario)
            contexto = format_docs(docs)

            prompt_final = f"""
Eres un asistente legal experto en normativa universitaria.

INSTRUCCIONES:
- Responde SOLO con base en el contexto.
- Si no hay información suficiente, di: "No tengo evidencia suficiente en los documentos".
- Cita SIEMPRE la fuente y la página.

CONTEXTO:
{contexto}

PREGUNTA:
{prompt_usuario}
"""
            respuesta = modelo.generate_content(prompt_final).text
            
            fin = time.time() 
            latencia = round(fin - inicio, 2) 

        with st.chat_message("assistant"):
            st.markdown(respuesta)
            # Mostramos la métrica de latencia justo debajo de la respuesta
            st.caption(f"Latencia de respuesta: {latencia} segundos")

            with st.expander("Ver fragmentos usados"):
                for doc in docs:
                    fuente = os.path.basename(doc.metadata.get('source', ''))
                    pagina = doc.metadata.get('page', '')
                    st.write(f"{fuente} (Pág. {pagina})")
                    st.info(doc.page_content)

        st.session_state.messages.append({
            "role": "assistant",
            "content": respuesta + f"\n\n(Latencia: {latencia}s)"
        })

    except Exception as e:
        st.error(f"Error: {e}")