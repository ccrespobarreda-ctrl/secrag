# SECRAG - Documento final de traspaso y continuidad



## 1. Estado de la release



Release final:



`SECRAG-RRF40-2026-08-17`



Estado:



`FINAL_FROZEN`



Fecha de cierre:



17 de agosto de 2026



Esta release corresponde a la configuracion, benchmark, codigo y resultados

evaluados y congelados al finalizar el proyecto.



Cualquier cambio posterior en benchmark, corpus, retrieval, prompt, modelo,

generacion o evaluadores debe considerarse una nueva version y requiere una

nueva evaluacion.



La definicion autoritativa de la release esta en:



- `FINAL_RELEASE_MANIFEST.json`

- `FINAL_RELEASE_MANIFEST.md`

- `SHA256SUMS.txt`



---



## 2. Objetivo del sistema



SECRAG es un sistema RAG para responder preguntas sobre filings SEC 10-K.



El sistema combina:



- parsing de filings SEC

- chunking consciente de secciones

- embeddings locales

- PostgreSQL + pgvector

- full-text search

- retrieval semantico

- retrieval keyword

- Reciprocal Rank Fusion

- deteccion de companias

- retrieval company-aware

- generacion con Claude

- citas por excerpt

- verificacion automatica de citas

- refusals cuando el contexto es insuficiente

- evaluacion de retrieval, groundedness y correctness



El objetivo no es solo responder preguntas, sino medir si las respuestas estan

respaldadas por los excerpts recuperados y si el sistema sabe rechazar preguntas

que no puede contestar con evidencia.



---



## 3. Corpus y benchmark final



Corpus final:



- 4,169 chunks



Benchmark canonico:



`eval/questions_canonical.yaml`



Composicion:



- 50 preguntas totales

- 34 answerable

- 16 unanswerable

- 62 gold labels canonicos



Validacion final ejecutada con:



```powershell

python .\\src\\verify_labels.py `

&#x20; --questions .\\eval\\questions_canonical.yaml
