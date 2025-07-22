
# 🦜🔗 LangChain Learning – Theory + Practical

LangChain is a **framework for building apps powered by language models** (like GPT) in a structured and modular way.

It enables:
- 🧠 Structured LLM interactions
- 🔗 Logical chaining of multiple steps
- 📝 Memory integration (chat history)
- 🌐 Tool and API integration
- 📂 External data access (files, DBs, APIs)

---

## 🔍 What Is LangChain?

LangChain helps developers:

✅ Structure LLM workflows  
✅ Build multi-step intelligent chains  
✅ Persist memory between interactions  
✅ Connect to external APIs and tools  
✅ Enable dynamic, context-aware apps

> **LangChain is ideal for building:**
- 🤖 Chatbots and AI Agents  
- ❓ Question Answering systems  
- 📝 Content generators  
- 🔁 Dynamic data workflows  

---

## 🔧 Key Components of LangChain

<details>
<summary>1. 💬 LLMs – Language Models</summary>

```python
from langchain.llms import OpenAI

llm = OpenAI(temperature=0.7)
```

- `temperature` controls output creativity:
  - `0` = more deterministic  
  - `1` = balanced randomness  
  - `>1` = very creative/unpredictable

</details>

<details>
<summary>2. 📄 PromptTemplate – Structured Prompts</summary>

```python
from langchain.prompts import PromptTemplate

prompt = PromptTemplate(
    input_variables=["cuisine"],
    template="I want to open restaurant for {cuisine} food. Suggest a fancy name."
)
```

- Templates make prompts **reusable** and **dynamic**.

</details>

<details>
<summary>3. 🔗 LLMChain – Single-Step Chain</summary>

```python
from langchain.chains import LLMChain

name_chain = LLMChain(llm=llm, prompt=prompt)
```

- A single **LLM + Prompt** unit to execute a step.

</details>

<details>
<summary>4. 🪄 SimpleSequentialChain – Multi-Step Pipeline</summary>

```python
from langchain.chains import SimpleSequentialChain

# Chain 1: Get restaurant name
# Chain 2: Suggest menu based on name

chain = SimpleSequentialChain(
    chains=[name_chain, food_items_chain],
    verbose=True
)

chain.run("Indian")
```

- Chain output of one step as **input to the next**.

</details>

<details>
<summary>5. 🧠 Memory (Optional) – Context Persistence</summary>

- Use memory to persist chat history between steps.  
- Important for **conversational apps** like chatbots.

</details>

---

## 🧠 Your Learning Summary

✔️ Setup OpenAI LLMs securely using API keys  
✔️ Built prompt templates with `PromptTemplate`  
✔️ Created single-step LLMChains  
✔️ Combined steps using `SimpleSequentialChain`  
✔️ Controlled creativity via `temperature`

---

## 🛠️ Use Cases You Can Try

- 🧳 **Travel planner bot**: Ask for destination ➝ Give itinerary  
- 🧑‍💼 **Resume builder**: Ask for skills ➝ Generate summary  
- 🏔️ **Trekking Q&A bot**: Answer questions using video data  
- 📊 **IT Resume Assistant**: Convert roles ➝ Summary ➝ PDF

---

## 🚀 Next Steps (Advanced Suggestions)

- 🗂️ Use **ConversationalRetrievalChain** to load knowledge from docs  
- 💬 Add memory using `ConversationBufferMemory`  
- 🌐 Build a UI using **Streamlit** or **Flask**  
- 🕸️ Use **LangGraph** for advanced workflows
