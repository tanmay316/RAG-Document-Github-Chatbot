from flask import Flask, request, jsonify, send_from_directory
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import google.generativeai as genai
from langchain.vectorstores import FAISS
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains.question_answering import load_qa_chain
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv


load_dotenv()
os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

app = Flask(__name__)


def get_pdf_text(pdf_files):
    text = ""
    for pdf in pdf_files:
        pdf_reader = PdfReader(pdf)
        for page in pdf_reader.pages:
            text += page.extract_text()
    return text


def get_text_chunks(text):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=10000, chunk_overlap=1000)
    chunks = text_splitter.split_text(text)
    return chunks


def get_vector_store(text_chunks):
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    vector_store = FAISS.from_texts(text_chunks, embedding=embeddings)
    vector_store.save_local("faiss_index")


def get_conversational_chain():
    prompt_template = """
    Answer the question as detailed as possible from the provided context, make sure to provide all the details. If user asks for summary, then summarize all the contents of the file and give the summary of the content.\n\n
    Context:\n {context}?\n
    Question: \n{question}\n

    Answer:
    """
    model = ChatGoogleGenerativeAI(model="gemini-pro", temperature=0.3)
    prompt = PromptTemplate(
        template=prompt_template, input_variables=["context", "question"]
    )
    chain = load_qa_chain(model, chain_type="stuff", prompt=prompt)
    return chain


@app.route("/")
def serve_index():
    return send_from_directory("static", "index.html")


@app.route("/upload", methods=["POST"])
def upload_files():
    files = request.files.getlist("files")
    pdf_texts = [get_pdf_text([file]) for file in files]
    full_text = "".join(pdf_texts)
    text_chunks = get_text_chunks(full_text)
    get_vector_store(text_chunks)
    return jsonify({"message": "Files processed successfully."})


@app.route("/summarize", methods=["POST"])
def summarize_pdf():
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    vector_store = FAISS.load_local(
        "faiss_index", embeddings, allow_dangerous_deserialization=True
    )
    docs = vector_store.similarity_search("Summarize the document.")
    chain = get_conversational_chain()
    summary_response = chain(
        {"input_documents": docs, "question": "Summarize the document in detail"},
        return_only_outputs=True,
    )
    return jsonify({"summary": summary_response["output_text"]})


@app.route("/ask", methods=["POST"])
def ask_question():
    user_question = request.json.get("question")
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    vector_store = FAISS.load_local(
        "faiss_index", embeddings, allow_dangerous_deserialization=True
    )
    docs = vector_store.similarity_search(user_question)
    chain = get_conversational_chain()
    response = chain(
        {"input_documents": docs, "question": user_question}, return_only_outputs=True
    )
    return jsonify({"response": response["output_text"]})


if __name__ == "__main__":
    app.run(debug=True)
