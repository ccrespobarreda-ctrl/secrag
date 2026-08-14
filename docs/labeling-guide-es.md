# Etiquetar las 50 preguntas

Este es el trabajo que hace que el arnés valga algo, y no hay atajo: **son dos
tardes de leer y decidir.** No necesita modelo, ni API, ni gastar nada.

Tienes 35 preguntas respondibles que etiquetar. Las 15 no respondibles ya están
listas — no llevan fragmento correcto por definición.

---

## El flujo, en dos pasos

Hay una trampa evidente: para usar `--expect` necesitas saber la respuesta, y no
la sabes todavía. Por eso son dos pasos.

### Paso 1 — descubrir la respuesta

```powershell
python src/find_gold.py "What were Chewy's net sales for fiscal 2025?"
```

Sin `--expect`. Te muestra lo que devuelve el recuperador, y ahí normalmente ves
la cifra. Si un candidato te convence pero el extracto de 150 caracteres se
queda corto, léelo entero:

```powershell
python src/find_gold.py "cualquier cosa" --chunk 1847
```

### Paso 2 — encontrar **todos** los fragmentos que la contienen

```powershell
python src/find_gold.py "What were Chewy's net sales for fiscal 2025?" --expect "12,345" --ticker CHWY
```

Ahora busca esa cadena literalmente en todo el corpus, **al margen del ranking**.

**Este paso es el que hace honesto el arnés.** Si etiqueto tomando el primer
resultado del recuperador, estoy midiendo el recuperador contra sí mismo y el
`Recall@8` sale perfecto por construcción. La búsqueda literal encuentra
fragmentos que el recuperador coloca en el puesto 400 — y **esos son exactamente
los que hacen que la métrica signifique algo.**

Al final te dice en qué posición quedó cada coincidencia y marca las que se
escaparon.

---

## El criterio de decisión

Uno solo, y de él sale todo lo demás:

> **¿Podría un lector que solo viera ese fragmento responder la pregunta con
> seguridad y citarlo?**

Si tiene que inferir, combinar con otro sitio o adivinar qué columna es cuál, no
es oro.

Ejemplo real, de la pregunta de Under Armour:

| Fragmento | Contenido | ¿Oro? |
|---|---|---|
| 3236 | `2026 2025 2024` · `Net revenues (Note 10) $ 4,966,370` | **Sí** — etiqueta, años y cifra |
| 3294 | `Total net revenues $ 4,966,370` | **Sí** — misma cifra, etiquetada |
| 3189 | `Net Sales 4,885,902 ... Total net reve…` | No — las cabeceras de año están en el fragmento anterior |
| 3188 | *"Net revenues consist of net sales and license revenues"* | No — define el término, no da el número |

El 3189 es el caso instructivo: **contiene la cifra pero le faltan las cabeceras
de columna.** Quien solo viera eso no sabría si es de 2026 o de 2025.

## Varios fragmentos correctos, todos son oro

`Recall@8` pregunta *"¿había una respuesta correcta disponible?"*, no *"¿encontró
mi favorito?"*. Si marcas solo el 3236 y el sistema devuelve el 3294 primero, lo
contarías como fallo cuando habría respondido perfectamente.

**Si un fragmento produciría una respuesta correcta y citable, es oro.**

---

## Cómo rellenarlo

```yaml
- id: Q002
  question: "What were Under Armour's net revenues in fiscal 2026?"
  type: extractive
  answerable: true
  gold_chunk_ids: [3236, 3294]        # <- los ids
  gold_answer: "$4,966,370 thousand"  # <- la respuesta, con unidades
  notes: ""
```

En `gold_answer` pon **las unidades**. Los filings declaran en miles o millones,
y `$4,966,370` sin más es ambiguo.

---

## Orden recomendado

**Empieza por las extractivas** (Q001-Q020). Son las rápidas: buscas una cifra,
la encuentras o no. Con esas veinte ya puedes ejecutar el arnés y ver si el
formato te sirve antes de invertir la segunda tarde.

Luego las **multi-fragmento** y las **comparativas**, que son más lentas porque
hay que decidir cuántos fragmentos hacen falta.

Las **no respondibles no requieren nada**. Ya están.

---

## Si dudas

**Anótalo en `notes` y sigue.** Al final revisas los dudosos juntos y decides con
criterio uniforme, en lugar de decidir cada uno con el cansancio del momento.

Y si una pregunta resulta no tener respuesta en el corpus —pasa— cámbiale el tipo
a `unanswerable_absent` y anota por qué. **Eso no es un fallo del etiquetado: es
un descubrimiento sobre el corpus**, y una pregunta más para medir la negativa
honesta.

---

## Cuando termines las veinte primeras

```powershell
python src/evaluate_retrieval.py --sweep
```

Ahí responderás las tres preguntas que llevamos arrastrando: si la ruta de
palabra clave aporta algo, qué constante de fusión sirve para este corpus, y si
la regla de AND-primero vale lo que dije.
