"""
This is an API to support the LLM QA chain auto-evaluator. 
"""

import io
import os
import json
import time
import pypdf
import random
import logging
import itertools
import faiss
import pandas as pd
from dotenv import load_dotenv
from typing import Dict, List
from json import JSONDecodeError
from fastapi.middleware.cors import CORSMiddleware
from langchain_community.llms import MosaicML
from langchain_community.llms import Anthropic
from langchain_community.llms import Replicate
from langchain.schema import Document
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain.chains import QAGenerationChain
from langchain_community.retrievers import SVMRetriever
from langchain.evaluation.qa import QAEvalChain
from langchain_community.retrievers import TFIDFRetriever
from sse_starlette.sse import EventSourceResponse
from fastapi.middleware.cors import CORSMiddleware
from langchain_community.embeddings import LocalAIEmbeddings
from langchain_community.embeddings import MosaicMLInstructorEmbeddings
from fastapi import FastAPI, File, UploadFile, Form
from langchain.chains.question_answering import load_qa_chain
from langchain_google_vertexai import ChatVertexAI
from langchain_google_vertexai import VertexAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter, CharacterTextSplitter
from text_utils import GRADE_DOCS_PROMPT, GRADE_ANSWER_PROMPT, GRADE_DOCS_PROMPT_FAST, GRADE_ANSWER_PROMPT_FAST, GRADE_ANSWER_PROMPT_BIAS_CHECK, GRADE_ANSWER_PROMPT_OPENAI, QA_CHAIN_PROMPT, QA_CHAIN_PROMPT_LLAMA

load_dotenv()
MODEL_1_URL = os.getenv("MODEL_1_URL")
MODEL_2_URL = os.getenv("MODEL_2_URL")
MODEL_3_URL = os.getenv("MODEL_3_URL")
MODEL_4_URL = os.getenv("MODEL_4_URL")


MODEL_NAME_1 = os.getenv("MODEL_NAME_1")
MODEL_NAME_2 = os.getenv("MODEL_NAME_2")
MODEL_NAME_3 = os.getenv("MODEL_NAME_3")
MODEL_NAME_4 = os.getenv("MODEL_NAME_4")

def generate_eval(text, chunk, logger):
    """
    Generate question answer pair from input text 
    @param text: text to generate eval set from
    @param chunk: chunk size to draw question from text
    @param logger: logger
    @return: dict with keys "question" and "answer"
    """

    logger.info("`Generating eval QA pair ...`")
    # Generate random starting index in the doc to draw question from
    num_of_chars = len(text)
    starting_index = random.randint(0, num_of_chars-chunk)
    sub_sequence = text[starting_index:starting_index+chunk]
    # Set up QAGenerationChain chain using Chat bison as default
    chain = QAGenerationChain.from_llm(ChatVertexAI(model_name="chat-bison", temperature=0))
    eval_set = []
    # Catch any QA generation errors and re-try until QA pair is generated
    awaiting_answer = True
    while awaiting_answer:
        try:
            qa_pair = chain.run(sub_sequence)
            eval_set.append(qa_pair)
            awaiting_answer = False
        except JSONDecodeError:
            logger.error("Error on question")
            starting_index = random.randint(0, num_of_chars-chunk)
            sub_sequence = text[starting_index:starting_index+chunk]
    eval_pair = list(itertools.chain.from_iterable(eval_set))
    return eval_pair


def split_texts(text, chunk_size, overlap, split_method, logger):
    """
    Split text into chunks
    @param text: text to split
    @param chunk_size: charecters per split
    @param overlap: charecter overlap between splits
    @param split_method: method used to split text
    @param logger: logger
    @return: list of str splits
    """

    logger.info("`Splitting doc ...`")
    if split_method == "RecursiveTextSplitter":
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size,
                                                       chunk_overlap=overlap)
    elif split_method == "CharacterTextSplitter":
        text_splitter = CharacterTextSplitter(separator=" ",
                                              chunk_size=chunk_size,
                                              chunk_overlap=overlap)
    splits = text_splitter.split_text(text)
    return splits


def make_llm(model):
    """
    Make LLM
    @param model: LLM to use
    @return: LLM
    """

    if model in ("chat-bison", "gemini-pro"):
        llm = ChatVertexAI(model_name=model, temperature=0)
    elif model == "anthropic":
        llm = Anthropic(temperature=0)
    elif model == "Anthropic-100k":
        llm = Anthropic(model="claude-v1-100k",temperature=0)
    elif model == "vicuna-13b":
        llm = Replicate(model="replicate/vicuna-13b:e6d469c2b11008bb0e446c3e9629232f9674581224536851272c54871f84076e",
                input={"temperature": 0.75, "max_length": 3000, "top_p":0.25})
    elif model == "mosaic":
        llm = MosaicML(inject_instruction_format=True,model_kwargs={'do_sample': False, 'max_length': 3000})
    return llm

def make_retriever(splits, retriever_type, embeddings, num_neighbors, llm, logger):
    """
    Make document retriever
    @param splits: list of str splits
    @param retriever_type: retriever type
    @param embedding_type: embedding type
    @param num_neighbors: number of neighbors for retrieval
    @param _llm: model
    @param logger: logger
    @return: retriever
    """

    logger.info("`Making retriever ...`")
    # Set embeddings
    if embeddings == "Vertex AI":
        embd = VertexAIEmbeddings()
    # Note: Still WIP (can't be selected by user yet)
    elif embeddings == "Model 1":
        embd = LocalAIEmbeddings(openai_api_base=MODEL_1_URL, model=MODEL_NAME_1, openai_api_key="sk-")
    elif embeddings == "Model 2":
        embd = LocalAIEmbeddings(openai_api_base=MODEL_2_URL, model=MODEL_NAME_2, openai_api_key="sk-")
    elif embeddings == "Model 3":
        embd = LocalAIEmbeddings(openai_api_base=MODEL_3_URL, model=MODEL_NAME_3, openai_api_key="sk-")
    elif embeddings == "Model 4":
        embd = LocalAIEmbeddings(openai_api_base=MODEL_4_URL, model=MODEL_NAME_4, openai_api_key="sk-")
    # Note: Test
    elif embeddings == "Mosaic":
        embd = MosaicMLInstructorEmbeddings(query_instruction="Represent the query for retrieval: ")

    # Select retriever
    if retriever_type == "similarity-search":
        vectorstore = FAISS.from_texts(splits, embd)
        retriever = vectorstore.as_retriever(k=num_neighbors)
    elif retriever_type == "SVM":
        retriever = SVMRetriever.from_texts(splits, embd)
    elif retriever_type == "TF-IDF":
        retriever = TFIDFRetriever.from_texts(splits)
    elif retriever_type == "Anthropic-100k":
         retriever = llm
    return retriever

def make_chain(llm, retriever, retriever_type, model):

    """
    Make retrieval chain
    @param llm: model
    @param retriever: retriever
    @param retriever_type: retriever type
    @return: QA chain
    """

    # Select prompt 
    if model == "vicuna-13b":
        # Note: Better answer quality using default prompt 
        # chain_type_kwargs = {"prompt": QA_CHAIN_PROMPT_LLAMA}
        chain_type_kwargs = {"prompt": QA_CHAIN_PROMPT}
    else: 
        chain_type_kwargs = {"prompt": QA_CHAIN_PROMPT}

    # Select model 
    if retriever_type == "Anthropic-100k":
        qa_chain = load_qa_chain(llm,chain_type="stuff",prompt=QA_CHAIN_PROMPT)
    else:
        qa_chain = RetrievalQA.from_chain_type(llm,
                                               chain_type="stuff",
                                               retriever=retriever,
                                               chain_type_kwargs=chain_type_kwargs,
                                               input_key="question")
    return qa_chain


def grade_model_answer(predicted_dataset, predictions, grade_answer_prompt, logger):
    """
    Grades the answer based on ground truth and model predictions.
    @param predicted_dataset: A list of dictionaries containing ground truth questions and answers.
    @param predictions: A list of dictionaries containing model predictions for the questions.
    @param grade_answer_prompt: The prompt level for the grading. Either "Fast" or "Full".
    @param logger: logger
    @return: A list of scores for the distilled answers.
    """

    logger.info("`Grading model answer ...`")
    if grade_answer_prompt == "Fast":
        prompt = GRADE_ANSWER_PROMPT_FAST
    elif grade_answer_prompt == "Descriptive w/ bias check":
        prompt = GRADE_ANSWER_PROMPT_BIAS_CHECK
    elif grade_answer_prompt == "OpenAI grading prompt":
        prompt = GRADE_ANSWER_PROMPT_OPENAI
    else:
        prompt = GRADE_ANSWER_PROMPT

    # Note: GPT-4 grader is advised by OAI 
    eval_chain = QAEvalChain.from_llm(llm=ChatVertexAI(model_name="chat-bison", temperature=0),
                                      prompt=prompt)
    graded_outputs = eval_chain.evaluate(predicted_dataset,
                                         predictions,
                                         question_key="question",
                                         prediction_key="result",
                                         )
    print(graded_outputs)
    return graded_outputs


def grade_model_retrieval(gt_dataset, predictions, grade_docs_prompt, logger):
    """
    Grades the relevance of retrieved documents based on ground truth and model predictions.
    @param gt_dataset: list of dictionaries containing ground truth questions and answers.
    @param predictions: list of dictionaries containing model predictions for the questions
    @param grade_docs_prompt: prompt level for the grading.
    @return: list of scores for the retrieved documents.
    """

    logger.info("`Grading relevance of retrieved docs ...`")
    if grade_docs_prompt == "Fast":
        prompt = GRADE_DOCS_PROMPT_FAST
    else:
        prompt = GRADE_DOCS_PROMPT

    # Note: GPT-4 grader is advised by OAI
    eval_chain = QAEvalChain.from_llm(llm=ChatVertexAI(model_name="chat-bison", temperature=0),
                                      prompt=prompt)
    graded_outputs = eval_chain.evaluate(gt_dataset,
                                         predictions,
                                         question_key="question",
                                         prediction_key="result",
                                         )
    print(graded_outputs)
    return graded_outputs


def run_eval(chain, retriever, eval_qa_pair, grade_prompt, retriever_type, num_neighbors, text, logger):
    """
    Runs evaluation on a model's performance on a given evaluation dataset.
    @param chain: Model chain used for answering questions
    @param retriever:  Document retriever used for retrieving relevant documents
    @param eval_set: List of dictionaries containing questions and corresponding ground truth answers
    @param grade_prompt: String prompt used for grading model's performance
    @param retriever_type: String specifying the type of retriever used
    @param num_neighbors: Number of neighbors to retrieve using the retriever
    @param text: full document text
    @return: A tuple of four items:
    - answers_grade: A dictionary containing scores for the model's answers.
    - retrieval_grade: A dictionary containing scores for the model's document retrieval.
    - latencies_list: A list of latencies in seconds for each question answered.
    - predictions_list: A list of dictionaries containing the model's predicted answers and relevant documents for each question.
    """

    logger.info("`Running eval ...`")
    predictions = []
    retrieved_docs = []
    gt_dataset = []
    latency = []

    # Get answer and log latency
    start_time = time.time()
    if retriever_type == "Anthropic-100k":
        docs=[Document(page_content=text)]
        answer = chain.run(input_documents=docs,question=eval_qa_pair["question"])
        predictions.append(
            {"question": eval_qa_pair["question"], "answer": eval_qa_pair["answer"], "result": answer})
    else :
        predictions.append(chain(eval_qa_pair))
    gt_dataset.append(eval_qa_pair)
    end_time = time.time()
    elapsed_time = end_time - start_time
    latency.append(elapsed_time)

    # Extract text from retrieved docs
    retrieved_doc_text = ""
    if retriever_type == "Anthropic-100k":
        retrieved_doc_text = "Doc %s: " % str(eval_qa_pair["answer"])
    else:
        docs = retriever.get_relevant_documents(eval_qa_pair["question"])
        for i, doc in enumerate(docs):
            retrieved_doc_text += "Doc %s: " % str(i+1) + \
                doc.page_content + " "

    # Log
    retrieved = {"question": eval_qa_pair["question"],
                 "answer": eval_qa_pair["answer"], "result": retrieved_doc_text}
    retrieved_docs.append(retrieved)

    # Grade
    graded_answers = grade_model_answer(
        gt_dataset, predictions, grade_prompt, logger)
    graded_retrieval = grade_model_retrieval(
        gt_dataset, retrieved_docs, grade_prompt, logger)
    return graded_answers, graded_retrieval, latency, predictions


app = FastAPI()

origins = [
    "http://34.128.83.204:3000",
    "34.128.83.204:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Welcome to the Auto Evaluator!"}


def run_evaluator(
    files,
    num_eval_questions,
    chunk_chars,
    overlap,
    split_method,
    retriever_type,
    embeddings,
    model_version,
    grade_prompt,
    num_neighbors,
    test_dataset
):

    # Set up logging
    logging.config.fileConfig('logging.conf', disable_existing_loggers=False)
    logger = logging.getLogger(__name__)

    # Read content of files
    texts = []
    fnames = []
    for file in files:
        logger.info("Reading file: {}".format(file.filename))
        contents = file.file.read()
        # PDF file
        if file.content_type == 'application/pdf':
            logger.info("File {} is a PDF".format(file.filename))
            pdf_reader = pypdf.PdfReader(io.BytesIO(contents))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
            texts.append(text)
            fnames.append(file.filename)
        # Text file
        elif file.content_type == 'text/plain':
            logger.info("File {} is a TXT".format(file.filename))
            texts.append(contents.decode())
            fnames.append(file.filename)
        else:
            logger.warning(
                "Unsupported file type for file: {}".format(file.filename))
    text = " ".join(texts)

    if retriever_type == "Anthropic-100k":
        splits = ""
        model_version = "Anthropic-100k"
    else:
        logger.info("Splitting texts")
        splits = split_texts(text, chunk_chars, overlap, split_method, logger)

    logger.info("Make LLM")
    llm = make_llm(model_version)

    logger.info("Make retriever")
    retriever = make_retriever(
        splits, retriever_type, embeddings, num_neighbors, llm, logger)

    logger.info("Make chain")
    qa_chain = make_chain(llm, retriever, retriever_type, model_version)

    for i in range(num_eval_questions):

        # Generate one question
        if i < len(test_dataset):
            eval_pair = test_dataset[i]
        else:
            eval_pair = generate_eval(text, 3000, logger)
            if len(eval_pair) == 0:
                # Error in eval generation
                continue
            else:
                # This returns a list, so we unpack to dict
                eval_pair = eval_pair[0]

        # Run eval
        graded_answers, graded_retrieval, latency, predictions = run_eval(
            qa_chain, retriever, eval_pair, grade_prompt, retriever_type, num_neighbors, text, logger)

        # Assemble output
        d = pd.DataFrame(predictions)
        d['answerScore'] = [g['results'] for g in graded_answers]
        d['retrievalScore'] = [g['results'] for g in graded_retrieval]
        d['latency'] = latency

        # Summary statistics
        d['answerScore'] = [{'score': 1 if "Incorrect" not in text else 0,
                             'justification': text} for text in d['answerScore']]
        d['retrievalScore'] = [{'score': 1 if "Incorrect" not in text else 0,
                                'justification': text} for text in d['retrievalScore']]

        # Convert dataframe to dict
        d_dict = d.to_dict('records')
        if len(d_dict) == 1:
            yield json.dumps({"data":  d_dict[0]})
        else:
            logger.warn(
                "A QA pair was not evaluated correctly. Skipping this pair.")


@app.post("/evaluator-stream")
async def create_response(
    files: List[UploadFile] = File(...),
    num_eval_questions: int = Form(5),
    chunk_chars: int = Form(1000),
    overlap: int = Form(100),
    split_method: str = Form("RecursiveTextSplitter"),
    retriever_type: str = Form("similarity-search"),
    embeddings: str = Form("Model 1"),
    model_version: str = Form("gemini-pro"),
    grade_prompt: str = Form("Fast"),
    num_neighbors: int = Form(3),
    test_dataset: str = Form("[]"),
):
    test_dataset = json.loads(test_dataset)
    return EventSourceResponse(run_evaluator(files, num_eval_questions, chunk_chars,
                                             overlap, split_method, retriever_type, embeddings, model_version, grade_prompt, num_neighbors, test_dataset), headers={"Content-Type": "text/event-stream", "Connection": "keep-alive", "Cache-Control": "no-cache"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)