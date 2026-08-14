# SEC Filings RAG — Especificación del proyecto

**Perfil:** data analytics · data science · ML engineering
**Ritmo:** 3–5 h/día → 11 días laborables
**Hardware:** Intel Iris Xe, sin GPU NVIDIA

**Infraestructura decidida:**

| Capa | Elección | Por qué |
|---|---|---|
| Generación | Claude vía **Vertex AI** | la vía empresarial de GCP, no la API directa |
| Embeddings | `bge-small-en-v1.5` **en CPU** | gratis, y mantiene el corpus en local |
| BD desarrollo | PostgreSQL + pgvector local | iteración sin coste |
| BD producción | Postgres gestionado gratuito (Neon / Supabase) | **evita Cloud SQL, que cobra por hora encendido** |
| Servicio | **Cloud Run** + Artifact Registry + Secret Manager | escala a cero: sin tráfico, coste cero |
| CI/CD | GitHub Actions → Cloud Run | mismo patrón que Northlane |
| Demo pública | página estática de evaluación | gratis y siempre disponible |

> **Nota de idioma:** este documento está en español para tu uso. Todo lo que
> vaya al repo —código, README, nombres de tabla, la página de resultados— va
> **en inglés**.

---

# Parte 0 — Qué construyes y por qué importa

## El proyecto en una frase

Un sistema de preguntas y respuestas sobre **20 informes anuales 10-K de la SEC**
(unas 5.000 páginas), con recuperación híbrida sobre PostgreSQL, respuestas con
citas verificables, y **un arnés de evaluación que mide si el sistema miente.**

## Por qué este y no otro RAG

El mercado está saturado de chatbots RAG que responden bonito. Casi ninguno puede
demostrar que **funciona**. Tu diferenciador es exactamente el mismo que en
Northlane, aplicado a otro dominio:

| Northlane | Este proyecto |
|---|---|
| Cualquiera monta un pipeline | Cualquiera monta un RAG |
| El arnés prueba que recupera la verdad de datos corruptos | El arnés prueba que no inventa |
| Me niego a dar CM3 por estado porque el dato no existe | El sistema responde "no lo sé" en lugar de inventar |

Los dos juntos forman una tesis profesional: **construyes sistemas que saben lo
que no saben.** Eso casi nadie lo dice, y es lo que un cliente empresarial
necesita de verdad.

## Por qué filings de la SEC y no un corpus clínico

Porque **no necesitas conocimiento de dominio para etiquetar las preguntas.** Las
respuestas están literalmente en el texto: *"¿cuáles fueron los ingresos del
segmento X en 2023?"* se verifica leyendo. En cambio *"¿es correcta esta dosis?"*
exige criterio farmacológico que no tienes.

El corazón del proyecto son **50 preguntas etiquetadas a mano con su respuesta
conocida.** Si no puedes verificar la respuesta correcta, no hay arnés — y sin
arnés esto es otro chatbot más.

---

# Parte 1 — Conceptos que tienes que dominar

**No sigas a la Parte 2 hasta poder explicar estos siete sin mirar.** Es la
lección de Northlane: construir algo que no puedes defender en una llamada no
sirve.

## 1.1 Qué es RAG, exactamente

**Retrieval-Augmented Generation.** El modelo de lenguaje no "sabe" tu corpus.
El flujo es:

```
pregunta → buscar fragmentos relevantes → meterlos en el prompt → generar
```

La calidad depende **casi entera del paso de búsqueda**. Un modelo excelente con
fragmentos irrelevantes da una respuesta mala. Un modelo mediocre con los
fragmentos correctos da una buena.

**Por eso el 70% de este proyecto es recuperación y evaluación, no generación.**

## 1.2 Chunking, y por qué no es trivial

Un 10-K tiene 250 páginas. No cabe en el prompt. Hay que partirlo en
**fragmentos** (chunks) y buscar entre ellos.

Dos parámetros:

- **Tamaño**: fragmentos pequeños son precisos pero pierden contexto; grandes
  traen ruido y gastan prompt.
- **Solape** (overlap): si cortas a ciegas, una frase clave puede quedar partida
  en dos. El solape la conserva completa en al menos uno.

**Tu decisión, y hay que justificarla por escrito:** ~800 tokens con 100 de
solape, **partiendo por secciones del 10-K**, nunca a ciegas.

## 1.3 Chunking consciente de la estructura

Un 10-K tiene una estructura rígida y obligatoria:

| Item | Contenido |
|---|---|
| Item 1 | Business — qué hace la empresa |
| Item 1A | Risk Factors — riesgos declarados |
| Item 7 | MD&A — análisis de la dirección |
| Item 8 | Financial Statements |

**Aprovecha eso:** cada fragmento lleva como metadato la empresa, el año fiscal
y el Item del que sale. Eso te permite recuperación filtrada — *"busca solo en
Risk Factors"* — que es una capacidad real, no un adorno.

Cortar a ciegas cada 800 tokens tira esa estructura a la basura. **Esa es la
diferencia entre tu proyecto y un tutorial.**

## 1.4 Embeddings y búsqueda semántica

Un **embedding** convierte texto en un vector de números. Textos con significado
parecido dan vectores cercanos. La "cercanía" se mide normalmente con **similitud
del coseno**.

Buscar semánticamente = convertir la pregunta en vector y traer los fragmentos
cuyos vectores estén más cerca.

**Su punto ciego:** falla con términos exactos. *"Item 1A"*, *"fiscal 2023"*, el
nombre concreto de un segmento — la semántica los difumina.

## 1.5 Búsqueda por palabra clave, y por qué la necesitas

PostgreSQL trae búsqueda de texto completo nativa (`tsvector` + `ts_rank`).
Encuentra coincidencias literales y las ordena por relevancia.

**Su punto ciego:** el vocabulario. Si la pregunta dice *"supplier dependency"* y
el documento dice *"reliance on a single vendor"*, no encuentra nada.

## 1.6 Recuperación híbrida y RRF

Las dos búsquedas fallan en cosas distintas, así que se combinan. El método más
simple y defendible es **Reciprocal Rank Fusion**:

```
puntuación(fragmento) = Σ  1 / (k + posición en cada lista)
```

Con `k=60` por convención. No hay que entrenar nada, no hay pesos que ajustar a
ojo, y funciona.

**Por qué esto importa en filings de la SEC concretamente:** están llenos de
términos exactos y cifras donde gana la palabra clave, y de preguntas
conceptuales donde gana la semántica. La justificación no es teórica, es del
dominio.

## 1.7 Groundedness, y las dos métricas que van en pareja

**Groundedness** = cada afirmación de la respuesta está respaldada por un
fragmento citado. Si el modelo dice algo que no está en las fuentes, ha alucinado
aunque suene razonable.

Y aquí está la trampa que casi todo el mundo cae:

> Un sistema que responde *"no lo sé"* a todo tiene **100% de tasa de negativa**
> en las preguntas sin respuesta. Y es inútil.

Por eso hacen falta **dos métricas enfrentadas**:

| Métrica | Qué mide | Objetivo |
|---|---|---|
| **Refusal rate** en preguntas sin respuesta | ¿se niega cuando debe? | alto |
| **False refusal rate** en preguntas con respuesta | ¿se niega cuando no debe? | bajo |

Optimizar una sola es hacer trampa. **Es exactamente el mismo error que mi
tolerancia única del 0,5% en Northlane**, que dejaba pasar $42.457.

---

# Parte 2 — El corpus

## 2.1 Qué descargar

**20 informes 10-K de empresas de retail y consumo de EE. UU.**, del ejercicio
más reciente disponible.

Elegir retail no es casual: **encadena con Northlane.** Tu portfolio pasa de dos
proyectos sueltos a una línea coherente sobre economía de e-commerce.

Candidatas (todas cotizadas, todas con 10-K sustancial):

```
Nike · Lululemon · Chewy · Wayfair · Etsy · Revolve Group
Yeti · Crocs · Deckers Outdoor · Under Armour · Columbia Sportswear
Gap · Abercrombie & Fitch · Urban Outfitters · Warby Parker
Figs · Olaplex · Honest Company · Solo Brands · Peloton
```

## 2.2 Cómo se descarga de EDGAR

Es gratis y no necesita clave, **pero la SEC exige identificarse** en la
cabecera. Sin eso te bloquean:

```python
HEADERS = {"User-Agent": "Cristina Crespo Barreda c.crespobarreda@gmail.com"}
```

Y respeta el límite de peticiones: **máximo 10 por segundo.** Pon un `sleep`.

Dos endpoints:

```
# índice de filings de una empresa (necesitas su CIK)
https://data.sec.gov/submissions/CIK##########.json

# el documento en sí
https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{documento}
```

El CIK de cada empresa se busca una vez en el fichero de tickers de la SEC.
Guárdalo en un CSV y no vuelvas a buscarlo.

**Verifica la documentación actual de EDGAR antes de empezar** — los endpoints y
los límites cambian.

## 2.3 Escala esperada

| | |
|---|---|
| Documentos | 20 |
| Páginas aproximadas | 5.000 |
| Tokens aproximados | 3,3 M |
| Fragmentos (800 tokens, 100 de solape) | ~4.700 |

Eso es "large knowledge" de verdad, no un PDF de demostración.

## 2.4 El parseo es la parte fea

Los 10-K son HTML generado por herramientas de reporting financiero. Vas a
encontrar:

- Tablas maquetadas con `<div>` en lugar de `<table>`
- Miles de `&nbsp;` y espacios de ancho cero
- Los encabezados de Item con formato inconsistente entre empresas
- Notas al pie intercaladas en medio de párrafos
- Documentos que empiezan con 40 páginas de portada y exhibits

**Presupuesta el día 2 entero para esto y no te sorprendas.** Es exactamente el
mismo tipo de trabajo que la capa `dirty.py` de Northlane, y merece el mismo
tratamiento: documenta cada defecto que encuentres y cómo lo resolviste.

---

# Parte 3 — Arquitectura

```
EDGAR API
    ↓  descarga + parseo HTML
documents  (una fila por filing)
    ↓  chunking consciente de secciones
chunks     (texto + metadatos + embedding + tsvector)
    ↓
PostgreSQL + pgvector
    ↓
recuperación híbrida  →  semántica (coseno) + palabra clave (ts_rank) + RRF
    ↓
generación con citas obligatorias
    ↓
arnés de evaluación  ←  50 preguntas etiquetadas
```

## 3.1 Por qué PostgreSQL y no un almacén vectorial dedicado

**Ya sabes Postgres.** Montaste un warehouse la semana pasada.

Y hace las dos búsquedas en la misma base de datos: `pgvector` para la semántica,
`tsvector` para la palabra clave. No hay que sincronizar dos sistemas ni aprender
Pinecone o Weaviate.

En el README puedes decirlo así, y es un argumento sólido:

> *One database for both retrieval paths. No separate vector store to keep in
> sync, and the hybrid fusion happens in SQL.*

## 3.2 Esquema

```sql
create extension if not exists vector;

create table documents (
    doc_id        text primary key,
    company       text not null,
    ticker        text not null,
    cik           text not null,
    form_type     text not null,          -- 10-K
    fiscal_year   int  not null,
    filed_date    date not null,
    source_url    text not null,          -- trazabilidad a EDGAR
    raw_chars     int  not null
);

create table chunks (
    chunk_id      bigserial primary key,
    doc_id        text not null references documents(doc_id),
    item_section  text,                   -- 'Item 1A', 'Item 7', ...
    section_title text,
    chunk_index   int  not null,          -- orden dentro del documento
    token_count   int  not null,
    content       text not null,
    embedding     vector(384),            -- bge-small-en-v1.5
    content_tsv   tsvector generated always as
                  (to_tsvector('english', content)) stored
);

create index on chunks using hnsw (embedding vector_cosine_ops);
create index on chunks using gin  (content_tsv);
create index on chunks (doc_id, item_section);
```

**Detalle que importa:** `content_tsv` es una columna generada. Se mantiene sola;
no puede desincronizarse del contenido. Es la misma idea que las columnas
calculadas en los marts de Northlane.

## 3.3 Módulos

```
src/
├── config.py            todas las constantes en un sitio
├── edgar.py             descarga de filings
├── parse.py             HTML → texto por secciones
├── chunk.py             troceado consciente de estructura
├── embed.py             llamadas a la API de embeddings, por lotes
├── load.py              inserción en Postgres
├── retrieve.py          semántica, palabra clave, híbrida (RRF)
├── generate.py          prompt + parseo de citas
├── llm.py               ← interfaz del proveedor. Ver 3.4
└── evaluate.py          el arnés
eval/
├── questions.yaml       las 50 preguntas etiquetadas
└── results/             salidas de cada ejecución
```

## 3.4 La interfaz del LLM: media hora que abre el segmento caro

No llames a la API directamente desde `generate.py`. Pon una interfaz:

```python
class LLMProvider(Protocol):
    def complete(self, system: str, user: str) -> str: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...
```

Con dos implementaciones: `CloudProvider` (API) y `LocalProvider` (que puede
quedar sin terminar), seleccionadas por variable de entorno.

**Por qué:** los clientes que más pagan por RAG son bufetes, clínicas y bancos
que **legalmente no pueden mandar datos a una API externa**. Con esta interfaz
puedes escribir en el README:

> *The generation layer sits behind a provider interface. The same system runs
> against a local model inside a private VPC by changing one environment
> variable — no data leaves the network.*

Sin la interfaz, esa frase es mentira. Con ella, es cierta.

## 3.5 Recuperación híbrida en SQL

```sql
with semantic as (
    select chunk_id,
           row_number() over (order by embedding <=> %(qvec)s) as rank
    from chunks
    order by embedding <=> %(qvec)s
    limit %(pool)s
),
keyword as (
    select chunk_id,
           row_number() over (
               order by ts_rank(content_tsv, websearch_to_tsquery('english', %(q)s)) desc
           ) as rank
    from chunks
    where content_tsv @@ websearch_to_tsquery('english', %(q)s)
    limit %(pool)s
)
select coalesce(s.chunk_id, k.chunk_id) as chunk_id,
       -- Reciprocal Rank Fusion, k = 60 por convención
       coalesce(1.0 / (60 + s.rank), 0) +
       coalesce(1.0 / (60 + k.rank), 0) as rrf_score
from semantic s
full outer join keyword k using (chunk_id)
order by rrf_score desc
limit %(top_k)s;
```

`<=>` es el operador de distancia coseno de pgvector. `pool` suele ser 50 y
`top_k` entre 5 y 10.

## 3.6 Generación con citas

El prompt tiene que hacer tres cosas: numerar los fragmentos, exigir cita en cada
afirmación, y **permitir explícitamente negarse**.

```
You answer questions about SEC filings using only the numbered excerpts below.

Rules:
1. Every factual claim must end with a citation like [3] naming the excerpt it
   came from.
2. If the excerpts do not contain the answer, reply exactly:
   INSUFFICIENT_CONTEXT
   followed by one sentence saying what would be needed.
3. Never use knowledge from outside the excerpts, even if you are confident.
4. If excerpts conflict, say so and cite both.

EXCERPTS:
[1] (Nike, FY2023, Item 1A) ...
[2] (Chewy, FY2023, Item 7) ...
```

**Y después, verifica en código:**

- Que cada `[n]` citado existe entre los fragmentos que enviaste
- Que ninguna frase con dato numérico va sin cita
- Que `INSUFFICIENT_CONTEXT` sale literal cuando toca

Ese `INSUFFICIENT_CONTEXT` literal es lo que te permite medir la negativa
automáticamente. Sin un marcador exacto tendrías que interpretar texto libre.

---

# Parte 4 — El arnés de evaluación

**Aquí está el 70% del valor del proyecto.** Los días 6 a 8 son esto.

## 4.1 Las 50 preguntas, por tipo

Diseña la mezcla a propósito. Cada tipo mide algo distinto:

| Tipo | Nº | Qué mide | Ejemplo |
|---|---|---|---|
| **Extractiva simple** | 20 | Recuperación básica | *"What was Nike's total revenue in fiscal 2023?"* |
| **Multi-fragmento** | 10 | Síntesis dentro del corpus | *"Which risk factors does Chewy list about supplier concentration?"* |
| **Comparativa** | 5 | Recuperación en dos documentos | *"Do both Nike and Under Armour cite currency risk?"* |
| **Sin respuesta, ausente** | 10 | Negativa honesta | *"What is Etsy's CEO's home address?"* |
| **Sin respuesta, trampa** | 5 | **Resistencia a alucinar** | *"What was Wayfair's revenue in fiscal 2026?"* |

Las últimas cinco son las que separan tu proyecto del resto. Suenan
perfectamente respondibles y **el modelo tiene una tentación enorme de
inventarlas.** Casi nadie las incluye.

## 4.2 Formato de las preguntas

```yaml
- id: Q001
  question: "What was Nike's total revenue in fiscal 2023?"
  type: extractive
  answerable: true
  gold_chunk_ids: [1847]            # rellenado tras la ingesta
  gold_answer: "$51.2 billion"
  gold_doc: "NKE-10K-2023"
  gold_section: "Item 8"
  notes: "Consolidated statement of income, first line"

- id: Q044
  question: "What was Wayfair's revenue in fiscal 2026?"
  type: unanswerable_adversarial
  answerable: false
  gold_chunk_ids: []
  gold_answer: null
  notes: "Corpus ends at FY2023. Sounds answerable; it is not."
```

**Cómo se rellena `gold_chunk_ids`:** escribes la pregunta, buscas a mano en la
base de datos el fragmento que contiene la respuesta, y apuntas su id. Es trabajo
manual y no hay atajo. Son las **dos tardes mejor invertidas del proyecto**.

## 4.3 Las métricas

### Recuperación — independiente del modelo

```
Recall@k  = ¿estaba algún gold_chunk entre los k recuperados?
MRR       = 1 / posición del primer gold_chunk    (0 si no aparece)
```

**Mide esto por separado de la generación.** Si `Recall@10` es 0,4, el modelo no
puede acertar más del 40% por bueno que sea, y sabes exactamente dónde está el
problema.

### Generación — sobre las preguntas respondibles

```
Answer accuracy      ¿coincide con gold_answer?      (juicio manual o LLM-juez)
Groundedness         ¿cada afirmación tiene cita válida?
Citation precision   ¿los fragmentos citados contienen de verdad lo afirmado?
False refusal rate   ¿se negó teniendo la respuesta?   ← debe ser bajo
```

### Honestidad — sobre las preguntas sin respuesta

```
Refusal rate         ¿dijo INSUFFICIENT_CONTEXT?      ← debe ser alto
Hallucination rate   ¿se inventó una respuesta?       ← el número que importa
```

## 4.4 La tabla que resume todo

Tu página de resultados debe llevar esta tabla, y es tu carta de presentación:

| | Respondibles (35) | Sin respuesta (15) |
|---|---|---|
| Respondió correctamente | ✓ objetivo alto | — |
| Respondió mal | minimizar | **crítico: cero** |
| Se negó | **false refusal: bajo** | ✓ objetivo alto |

La celda de arriba a la derecha —*respondió mal a algo que no podía saber*— es
**la única que debe ser cero.** Todo lo demás admite matices.

## 4.5 Un aviso sobre el LLM-juez

Es tentador usar un modelo para evaluar las respuestas de otro. Es válido y
escala, **pero tiene sesgos**: tiende a premiar respuestas largas y a estar de
acuerdo con la afirmación que se le presenta.

**Etiqueta las 50 a mano al menos una vez**, y usa el juez automático solo para
las iteraciones siguientes. Y **declara en el README que lo hiciste así.** Un
revisor técnico va a preguntar precisamente por eso.

---

# Parte 5 — La prueba de sabotaje

Esto es el equivalente exacto de los $42.457 de Northlane, y es lo que hace que
un cliente técnico te crea.

**La idea:** un arnés que solo dice "todo bien" no prueba nada. Hay que
demostrar que **detecta fallos**. Así que rompes el sistema a propósito y
verificas que la métrica correcta se hunde.

| Sabotaje | Qué debería hundirse | Qué prueba |
|---|---|---|
| `top_k = 1` | Recall@k, MRR | Que la métrica de recuperación responde |
| Desactivar la palabra clave | Preguntas con términos exactos | Que el híbrido aporta de verdad |
| Barajar el mapeo fragmento→documento | Citation precision | Que verificas las citas, no solo su formato |
| Inyectar 500 fragmentos de un corpus ajeno | Precisión, groundedness | Que la contaminación se detecta |
| Quitar la regla de negarse del prompt | **Hallucination rate** | Que la instrucción es lo que sostiene la honestidad |

**El último es el más elocuente.** Enseña, con número, cuánto de la honestidad
del sistema depende de una línea del prompt. Es un hallazgo real y casi nadie lo
mide.

**Si un sabotaje no mueve ninguna métrica, tu arnés tiene un punto ciego.** Eso
también es un resultado, y decirlo suma en lugar de restar.

---

# Parte 6 — Plan por días

## Día 1 — Corpus, parte fácil

- Repositorio, entorno, Postgres con `pgvector` instalado
- CIK de las 20 empresas, guardados en CSV
- Descarga de los 20 filings con `User-Agent` y límite de peticiones
- **Fin del día:** 20 ficheros HTML en disco y una tabla `documents` poblada

## Día 2 — Corpus, parte fea

- Parseo HTML → texto limpio
- Detección de encabezados de Item, que **no son consistentes entre empresas**
- Documenta cada defecto que encuentres

**Fin del día:** texto limpio por secciones. Si te lleva más, es normal.

## Día 3 — Chunking y embeddings

- Troceado por secciones, 800 tokens con 100 de solape
- Embeddings por lotes, con reintentos
- Carga en `chunks`, índices creados
- **Fin del día:** ~4.700 fragmentos consultables

## Día 4 — Recuperación

- Semántica sola, palabra clave sola, híbrida con RRF
- Una función que devuelva los tres resultados para comparar
- **Fin del día:** puedes hacer una pregunta a mano y ver los tres rankings

## Día 5 — Generación

- Prompt con citas obligatorias y `INSUFFICIENT_CONTEXT`
- Verificación en código de que las citas existen
- **Fin del día:** preguntas y respuestas con cita funcionando

## Días 6–8 — El arnés

**Esto es el proyecto.**

- Día 6: escribir 25 preguntas y localizar sus `gold_chunk_ids` a mano
- Día 7: las otras 25, incluidas las 15 sin respuesta
- Día 8: implementar las métricas y la primera ejecución completa

**Fin:** una tabla de resultados con todas las métricas.

## Día 9 — Sabotaje

- Los cinco sabotajes, cada uno documentado con qué métrica se hundió
- **Fin:** la sección más fuerte del README

## Día 10 — Presentación

- Página estática de resultados (misma idea que `docs/index.html` de Northlane)
- README con la tabla de resultados arriba
- Documento de decisiones: chunking, RRF, por qué Postgres

## Día 11 — Despliegue en GCP

Este día es lo que convierte "usé una API" en una afirmación de cloud que
aguanta preguntas.

**Antes de la primera llamada a Vertex AI, pon el guardarraíl:**
**Billing → Budgets & alerts → presupuesto de 20 € con alerta al 50%.**
GCP **no corta el servicio** al llegar al límite, solo avisa. El aviso es tu
única red.

Y verifica dos cosas que cambian con el tiempo: que **Claude está disponible en
Vertex AI en tu región**, y que has habilitado el modelo en **Model Garden**. La
disponibilidad regional es limitada.

Después:

1. `Dockerfile` del servicio de recuperación y generación — ya sabes Docker de
   `scoring-riesgo-credito` y `tarificacion-teleco`
2. Push de la imagen a **Artifact Registry**
3. Despliegue en **Cloud Run**, con `min-instances=0` para que escale a cero
4. Credenciales en **Secret Manager**, nunca en la imagen ni en el repo
5. Workflow de **GitHub Actions** que construye y despliega al hacer push a
   `main`
6. Migrar los datos al Postgres gestionado y comprobar que el servicio responde

**Fin del día:** una URL de Cloud Run que responde, y un pipeline que despliega
solo al hacer push.

**Lo que puedes decir después de esto, y es cierto:**

> *Containerized RAG service deployed to Cloud Run with CI/CD from GitHub
> Actions, Anthropic models served through Vertex AI, credentials in Secret
> Manager, managed Postgres with pgvector.*

**Y lo que sigue siendo cierto sobre soberanía del dato:**

> *Embeddings are computed locally; the corpus and its vectors never go to a
> third-party embedding API. The generation layer sits behind a provider
> interface that can be swapped for a local model.*

---

# Parte 7 — El problema de la demo, y cómo resolverlo

**No puedes publicar un chatbot en vivo.** Requiere claves de API, y cualquiera
que abra el enlace te gasta el saldo.

**La solución, y además es la mejor opción:** publica la **evaluación**, no el
chat.

Una página estática con:

1. La tabla resumen de 4.5 arriba del todo
2. Recall@k y MRR por tipo de pregunta
3. **Una galería de las 50 preguntas** con su respuesta generada, los fragmentos
   citados, y si acertó, falló o se negó
4. Los cinco sabotajes con su efecto en cada métrica

Eso es más fuerte que un chat en vivo, porque **un chat en vivo solo demuestra
que funciona con las preguntas que se le ocurren al visitante.** La evaluación
demuestra que funciona con 50 preguntas conocidas, y que sabes cuándo no.

Si además quieres el chat, un vídeo de 60 segundos.

**Y una aclaración sobre Cloud Run:** el servicio desplegado es la **capacidad
que demuestras**, no el artefacto público. No pongas su URL en el README abierta
a cualquiera — cada visita consume tokens de Vertex AI a tu cuenta. Menciona el
despliegue, enseña la arquitectura, y deja la evaluación estática como el enlace
que compartes.

---

# Parte 8 — Costes y preparación

## 8.1 Cuenta los tokens antes de gastar

**Verifica los precios actuales**, cambian a menudo. La estructura:

| Concepto | Tokens aproximados |
|---|---|
| Embeddings del corpus, una vez | 3,3 M |
| Re-embeddings si cambias el chunking | 3,3 M × cada vez |
| Una ejecución de evaluación (50 preguntas × ~4.000 tokens de contexto) | 200 K |
| 20 ejecuciones mientras iteras | 4 M |

Los embeddings son baratísimos; la generación repetida es donde se acumula.

**Dos consejos que ahorran dinero de verdad:**

- **Cachea las respuestas** por hash de (pregunta + fragmentos + prompt). Si no
  cambias nada, no vuelvas a pagar.
- **Fija el chunking en el día 3.** Cada cambio obliga a re-embeddear todo.

**El presupuesto de GCP va antes de la primera llamada.** Los embeddings son
gratis al ser locales, así que todo tu gasto es generación: unos pocos dólares si
cacheas, y el único riesgo real es dejar la URL de Cloud Run pública y que alguien
la use.

## 8.2 Tu portátil

**Cierra pestañas antes de empezar.** Tienes 15,3 de 15,7 GB de RAM en uso.
Postgres con 4.700 vectores va bien, pero con el sistema al 97% cualquier cosa se
arrastra.

## 8.3 Dependencias

```
psycopg2-binary · pgvector · beautifulsoup4 · lxml
tiktoken · pyyaml · pandas · python-dotenv
sentence-transformers          # embeddings locales
anthropic[vertex]              # Claude vía Vertex AI
```

Verifica el nombre exacto del extra de Vertex en la documentación actual del SDK
de Anthropic.

**No metas LangChain.** Para este alcance añade abstracciones que oscurecen
exactamente lo que quieres demostrar que entiendes. Escribir la recuperación en
SQL es más corto, más rápido y más defendible en una entrevista.

---

# Parte 9 — Qué puedes afirmar

Sé honesta contigo misma sobre en qué etapa estás. Esta es la lección más
importante de Northlane.

**Después de terminarlo:**

> *"Built a hybrid retrieval system over 5,000 pages of SEC filings, with an
> evaluation harness of 50 hand-labeled questions measuring retrieval recall,
> groundedness and refusal behavior. Verified the harness by degrading the
> retriever on purpose and confirming each degradation moved the metric it should."*

Todo eso es cierto y lo puedes defender.

**Lo que no debes afirmar:**

- Que has desplegado RAG en producción con usuarios reales
- Que has servido modelos locales, si la implementación quedó a medias
- Cifras de escala que no has medido
- Que has hecho fine-tuning

**Las tres preguntas que te van a hacer:**

**"¿Por qué recuperación híbrida y no solo vectorial?"**
Porque los filings están llenos de términos exactos y cifras donde la semántica
falla. Lo medí: [tu número] de las preguntas con términos literales fallaban con
recuperación solo semántica.

**"¿Cómo sabes que no alucina?"**
Cincuenta preguntas etiquetadas a mano, quince de ellas sin respuesta en el
corpus, cinco diseñadas para inducir la alucinación. Y probé el arnés quitando la
instrucción de negarse del prompt para ver cuánto subía la tasa.

**"¿Por qué los embeddings en local si la generación va por API?"**
Porque separa las dos capas. El corpus, los fragmentos y los vectores no salen de
la máquina; solo la llamada de generación cruza la red, y está detrás de una
interfaz que se puede cambiar por un modelo local. Para un cliente con datos
regulados, eso es la diferencia entre poder usarlo y no poder.

**"¿Por qué Postgres y no Pinecone?"**
Porque hace las dos rutas de búsqueda en la misma base de datos, sin
sincronización entre sistemas, y la fusión ocurre en SQL. A esta escala un
almacén vectorial dedicado añade una dependencia sin resolver un problema.

---

# Parte 10 — Definición de terminado

Fíjala ahora o esto no acaba. Con Northlane pulimos mucho más de lo necesario.

- [ ] 20 filings ingeridos, ~4.700 fragmentos con metadatos de sección
- [ ] Las tres recuperaciones funcionando y comparables
- [ ] Generación con citas verificadas en código
- [ ] 50 preguntas etiquetadas a mano con `gold_chunk_ids`
- [ ] Todas las métricas de 4.3 calculadas
- [ ] Los cinco sabotajes ejecutados y documentados
- [ ] Página estática de resultados publicada
- [ ] README con la tabla resumen arriba
- [ ] Servicio en Cloud Run respondiendo, con despliegue desde GitHub Actions
- [ ] Presupuesto de GCP configurado con alerta
- [ ] Ningún secreto en el repo — todo en Secret Manager
- [ ] Puedes responder las tres preguntas de la Parte 9 sin mirar

**Fuera de "terminado" a propósito:** el `LocalProvider` completo, reranking con
cross-encoder, interfaz de chat, más de 20 documentos. Todo eso es "trabajo
futuro" en el README, y ponerlo ahí vale más que hacerlo a medias.

---

## Antes de empezar, dime tres cosas

1. **Qué proveedor de API vas a usar** — para ajustar dimensiones del vector y
   el detalle del prompt
2. **Si tienes Postgres instalado en local** o lo quieres en la nube
3. **Si quieres que empiece por el día 1** escribiendo el código de ingesta,
   o prefieres montar el entorno tú y arrancamos por el arnés

Y una cosa que no repito más: **responder a tus cinco clientes son treinta
minutos y no bloquea nada de esto.**
