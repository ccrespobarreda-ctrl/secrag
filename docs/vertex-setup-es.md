# Vertex AI — configuración

Todo en el navegador salvo el último bloque. Sigue el orden: **el presupuesto va
antes que la primera llamada**, no después.

---

## 1. El presupuesto, primero

`console.cloud.google.com` → **Billing** → **Budgets & alerts** → **Create budget**

- Importe: **20 €**
- Alertas: **50%, 90%, 100%**
- Marca **"Email alerts to billing admins"**

> **GCP no corta el servicio al llegar al límite. Solo avisa.** El correo es tu
> única red, así que la alerta al 50% importa más que la del 100%.

Si es tu primera vez en GCP, necesitarás una cuenta de facturación con tarjeta.
El nivel gratuito cubre de sobra este proyecto, pero la tarjeta hace falta igual.

---

## 2. Proyecto y APIs

**Crea un proyecto** llamado `secrag` — o usa uno existente. Anota el **Project
ID**, que no siempre coincide con el nombre: suele llevar un sufijo numérico.

**Habilita dos APIs** desde APIs & Services → Enable APIs:

```
Vertex AI API
Cloud Resource Manager API
```

---

## 3. Habilitar Claude en Model Garden

Vertex AI → **Model Garden** → busca `Claude`.

Los modelos de Anthropic requieren **aceptar los términos una vez** antes de
poder llamarlos. Si te saltas este paso, la primera llamada falla con un error de
permisos que no menciona Model Garden por ningún lado.

**Anota dos cosas de la ficha del modelo:**

- El **identificador exacto** del modelo. En Vertex difiere del de la API
  directa, y hay que copiarlo tal cual.
- Las **regiones donde está disponible**. Es limitado y cambia. `europe-west1` y
  `us-east5` suelen tenerlo, pero **compruébalo**: no asumas.

---

## 4. Autenticación

Instala el **Google Cloud CLI** desde `cloud.google.com/sdk`, y luego:

```powershell
gcloud auth application-default login
```

Se abre el navegador, inicias sesión, y las credenciales quedan en tu perfil de
usuario. El SDK de Anthropic las encuentra solo.

Es la vía correcta para desarrollo local: **no genera ninguna clave que pueda
acabar en un commit**. Las cuentas de servicio y sus ficheros JSON son para el
despliegue, y ahí van en Secret Manager, nunca en el repositorio.

Comprueba:

```powershell
gcloud auth application-default print-access-token
```

Si imprime un token largo, está listo.

---

## 5. Variables de entorno

```powershell
$env:GOOGLE_CLOUD_PROJECT = "tu-project-id"
$env:GOOGLE_CLOUD_REGION  = "europe-west1"
$env:GENERATION_MODEL     = "el-identificador-de-model-garden"
$env:LLM_PROVIDER         = "vertex"
```

Sustituye la región y el modelo por lo que hayas anotado en el paso 3.

**Duran solo mientras el terminal esté abierto.** Cuando esto funcione montamos
un `.env` para no repetirlo cada vez.

---

## 6. La primera llamada

Antes de gastar nada, confirma que la tubería entera funciona con el proveedor
falso:

```powershell
$env:LLM_PROVIDER = "echo"
python src/generate.py "What were Under Armour's net revenues in fiscal 2026?" --show-excerpts
```

Verás los extractos recuperados y una negativa fija. **Todo funciona salvo el
modelo.**

Ahora la de verdad:

```powershell
$env:LLM_PROVIDER = "vertex"
python src/generate.py "What were Under Armour's net revenues in fiscal 2026?" --show-excerpts
```

Coste aproximado: **menos de un céntimo**. Unos 4.000 tokens de entrada y 200 de
salida.

---

## 7. La segunda llamada importa más que la primera

```powershell
python src/generate.py "What were Wayfair's net revenues for fiscal 2030?"
```

El corpus termina mucho antes de 2030. **La respuesta correcta es
`INSUFFICIENT_CONTEXT`.**

Si en su lugar aparece una cifra, acabas de reproducir en tu propio sistema el
comportamiento que todo este proyecto existe para medir — y lo has hecho a
propósito, que es la diferencia.

---

## Si algo falla

| Error | Causa habitual |
|---|---|
| `PermissionDenied` / `403` | Model Garden sin aceptar, o API sin habilitar |
| `NotFound` con el modelo | Identificador mal copiado, o región sin ese modelo |
| `DefaultCredentialsError` | Falta `gcloud auth application-default login` |
| `InvalidArgument` sobre la región | El modelo no está en esa región; prueba `us-east5` |

Los dos primeros son casi siempre el paso 3. La documentación de Vertex cambia a
menudo, así que si un identificador no funciona, cógelo otra vez de Model Garden
en lugar de buscarlo en un tutorial.
