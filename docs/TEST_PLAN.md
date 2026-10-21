# Plan de pruebas — Fase 1

Estrategia de pruebas del proyecto. Se define **antes** de implementar cada paso (regla de
`AGENTS.md`: *las skills de `testing-strategy` para definir pruebas antes de implementar*).

## Principios

1. **Pirámide**: muchas unitarias (rápidas, aisladas) + integraciones (pocas, con base de datos real)
   + un test de humo de extremo a extremo sobre Docker.
2. **Núcleo sin estado global mutable**: todo lo que dependa de configuración o de recursos
   (base de datos, runner de trabajos, bitácora de auditoría) se instancia explícitamente y se
   inyecta. Las pruebas nunca dependen del orden ni del estado compartido.
3. **Determinismo**: nada de red, nada de `sleep`, nada de reloj del sistema en las aserciones
   críticas. Las semillas y los identificadores se inyectan.
4. **Motor agnóstico**: la capa de datos se prueba contra SQLite (rápido, en memoria o temporal) y
   el servicio `db` de Docker cubre PostgreSQL.
5. **Cobertura**: objetivo ≥ 85 % en el núcleo de exámenes, aleatorización y formato
   (`fail_under = 85` en `pyproject.toml`). El umbral no se relaja para que las pruebas sigan en verde.

## Áreas y tipos de prueba

| Área | Tipo | Qué se comprueba | Fichero |
|------|------|------------------|---------|
| Configuración | Unitaria | Defaults, lectura de entorno, validación de URL, inmutabilidad | `tests/unit/test_config.py` |
| Logging | Unitaria | Formato JSON, campos obligatorios, contexto, niveles | `tests/unit/test_logging.py` |
| Errores | Unitaria | Jerarquía, códigos HTTP, envelope de error | `tests/unit/test_errors.py` |
| Base de datos | Unitaria + integración | Creation del engine por motor, `Base`, sesiones, `SELECT 1` | `tests/unit/test_db.py` |
| Trabajos | Unitaria | Estados, éxito, fallo, trazabilidad, awaitable | `tests/unit/test_jobs.py` |
| Auditoría | Unitaria | Registro, orden, contexto heredado | `tests/unit/test_audit.py` |
| Aplicación | Unitaria | Fábrica, ciclo de vida, middleware, healthchecks | `tests/unit/test_app.py` |
| API HTTP | Integración | `TestClient` contra la app real: errores, cabeceras, health | `tests/integration/test_app_http.py` |
| Estructura | Unitaria | Layout, imports prohibidos, sin APIs externas de IA | `tests/unit/test_scaffolding.py`, `tests/unit/test_no_external_ai_apis.py` |
| Dominio: modelo | Unitaria | Agregado inmutable, relaciones, transiciones y evento de auditoría | `tests/unit/test_domain_models.py` |
| Dominio: reglas | Unitaria | Errores y avisos de cada regla, límites, agregación | `tests/unit/test_domain_rules.py` |
| Dominio: ponderación | Unitaria | Suma exacta de 100,00, reparto y casos límite | `tests/unit/test_domain_weights.py` |
| Dominio: estados | Unitaria | Tabla de transiciones permitidas y prohibidas, estados finales | `tests/unit/test_domain_states.py` |
| Dominio: pureza | Unitaria | El dominio no importa web, ORM ni persistencia | `tests/unit/test_domain_purity.py` |
| Despliegue | Humo (Docker) | Build, stack arriba, `/health`, suite dentro del contenedor | `docs/ASSUMPTIONS.md` (A20) |

## Casos de prueba característicos del núcleo (Fase 1)

- **Configuración**: `DATABASE_URL` inválida o con driver síncrono → error temprano y legible.
- **Logging**: cada línea JSON lleva `exam_id`, `exam_code` y `request_id` aunque no informen
  (`null` si no hay contexto).
- **Base de datos**: el mismo código funciona con SQLite y con PostgreSQL; SQLite en memoria usa
  `StaticPool` para que todas las sesiones vean la misma base.
- **Trabajos**: un trabajo fallido queda registrado como `failed` y el error vuelve a propagarse.
- **Auditoría**: el `request_id` del contexto se hereda en el evento de auditoría.
- **Aplicación**: un `AppError` produce un envelope JSON estable y la cabecera `X-Request-ID` se
  devuelve siempre.
- **Disponibilidad**: `/health` responde sin tocar la base de datos; `/health/ready` consulta la base
  de datos y responde `503` (sin filtrar el detalle del error) si no está disponible.
- **CORS**: solo los orígenes configurados reciben `Access-Control-Allow-Origin`.

## Casos de prueba característicos del dominio (paso 3)

- **Reglas**: un examen válido no produce incidencias; un código de examen con menos de cinco dígitos
  o ya existente produce error; una pregunta con dos incisos correctos produce error; una pregunta
  abierta produce un error explícito (`QUESTION_TYPE_UNSUPPORTED`).
- **Avisos**: un enunciado que dice "todas las anteriores" produce aviso (no error); dos preguntas con
  el mismo enunciado (comparado tras normalizar) producen aviso.
- **Ponderación**: los pesos suman **exactamente** 100,00 para cualquier cantidad de preguntas
  (1–50) y la última pregunta absorbe la diferencia de redondeo.
- **Estados**: las transiciones permitidas y prohibidas se comprueban con una tabla; una transición no
  permitida lanza `InvalidTransitionError` (409) y **no** modifica el examen.
- **Pureza**: en un proceso limpio, importar el dominio no carga FastAPI, SQLAlchemy, Pydantic ni
  Starlette; el análisis de imports prohíbe además `api` e `infrastructure`.

## Reglas que不属于 al dominio (pasos posteriores)

La sección 16 del prompt enumera pruebas obligatorias que **no** son reglas del dominio, sino del
motor de aleatorización (paso 5). Se anotan aquí para no perderlas:

- Un `QUESTION_GROUP` se mueve como unidad y un `SECTION_GROUP` intercambia secciones solo con otro
  grupo del mismo tamaño.
- Los incisos con `locked = true` nunca cambian de letra.
- Nada cruza secciones y los incisos no salen de su pregunta; reproducibilidad con la misma seed y
  `verify_keys` detecta violaciones inyectadas.

El dominio solo aporta la **estructura** que esas reglas necesitan: los bloques (`Block`), la
pertenencia de una pregunta a un grupo y la bandera `locked` del inciso.

## Anti-patrones evitados

- No se prueba código de terceros ni getters triviales.
- No se usa la base de datos real de desarrollo en las pruebas: cada integración usa su propia
  base temporal.
- No se comprueba el texto exacto de un log: se comprueban los campos estructurados.
