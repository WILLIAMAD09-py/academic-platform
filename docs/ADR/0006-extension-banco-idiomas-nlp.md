# ADR-0006: Espacio de extensión para banco de preguntas, multilingüe y NLP

**Status:** Proposed
**Date:** 2026-10-22
**Deciders:** Responsable técnico del proyecto (pendiente de firma)

## Context

El responsable del producto quiere escalar el sistema, más adelante, con tres capacidades que la Fase 1
**no** incluye:

1. **Banco de preguntas**: reutilizar preguntas entre exámenes y poder seleccionarlas, ya sea a mano
   (el docente elige) o asistido por el modelo.
2. **Multilingüe**: manejar contenido en inglés, francés y alemán además del español, con traducción
   (encoder/decoder) y corrección de preguntas en esos idiomas.
3. **NLP**: un modelo de lenguaje natural local —el que aporta el usuario— para revisar y corregir
   preguntas, con traducción entre idiomas.

La Fase 1, en cambio, fija lo contrario en varios puntos (secciones 3, 4, 9 y 19 del prompt):

- Las preguntas **siempre nacen dentro de un examen**: `Question.section_id` es obligatorio y
  `Section.exam_id` también. No hay entidad "pregunta suelta".
- El contrato de IA es `QuestionReviewer` con `review`/`correct`, un **`StubReviewer`** para pruebas y
  un **`nlp_adapter.py`** de solo estructura (`load_model(path)` que lanza `NotImplementedError`).
- Está **prohibido** llamar a APIs externas de modelos y **entrenar** un modelo real; el modelo lo
  aporta el usuario por adaptador local.
- Los idiomas del producto son solo los de la interfaz de trabajo (documentación y mensajes en
  español; identificadores en inglés). No hay campo de idioma de contenido.
- Las heurísticas del dominio (`normalize_text`, `PATRONES_REFERENCIA`, `PATRONES_ORDEN_NATURAL`) están
  escritas **solo en español**.

La decisión no es *si* construir eso ahora —no corresponde a esta fase— sino **cómo dejar preparados
los puntos de extensión** para que su incorporación futura no obligue a romper contratos ya
publicados, y para que la Fase 1 no se contamine con conceptos que su prompt no contempla.

Restricciones que gobiernan la decisión:

1. No adelantar pasos: nada de banco, idioma o NLP reales en la Fase 1.
2. No romper contratos ni vocabularios ya fijados por tests (enums, firmas, envelope de error).
3. `domain/` sigue sin depender de `fastapi`, `sqlalchemy`, `pydantic` ni de librerías de IA
   (`tests/unit/test_domain_purity.py`); `src/` sigue sin importar SDKs ni endpoints de IA
   (`tests/unit/test_no_external_ai_apis.py`).
4. La regla de dependencias de ADR-0002 se mantiene: **domain ← application ← infrastructure**.
5. Todo lo nuevo debe poder probarse sin red, sin modelo entrenado y sin servicios externos.

## Decision

**Se reservan los puntos de extensión, se congelan los contratos de la Fase 1 y se decide dónde vivirá
cada capacidad futura. No se implementa ninguna lógica nueva en la Fase 1.**

### D1 — El banco de preguntas será un módulo/agregado aparte, no una mutación de `Exam`

- `Exam`, `Section` y `Question` de la Fase 1 **no cambian**: la pregunta sigue perteneciendo al
  examen. No se añade `bank_question_id` ni ninguna referencia opcional ahora, para no debilitar las
  invariantes que ya valida el dominio.
- El banco se modelará como un **agregado propio** (`QuestionBank` con `BankQuestion`), con identidad
  independiente del examen, en su propia carpeta de módulo (`modules/library/` o
  `modules/exams/bank/`, a decidir cuando llegue) y su propio repositorio `QuestionBankRepository`.
- La relación entre banco y examen será de **copia explícita ("instanciar en el examen")**, no de
  referencia compartida: al importar, se crea una `Question` nueva con `stem_original` nuevo. Así se
  conserva la invariante "`stem_original` nunca se sobrescribe" y dos exámenes nunca comparten
  mutaciones.
- La **selección asistida por el modelo** se expondrá como un **puerto de aplicación**
  (`QuestionSelector(Protocol)`), con la misma forma que `QuestionReviewer`: un `Stub` determinista
  para pruebas y un adaptador local para el modelo. El docente siempre puede elegir a mano; el modelo
  solo propone.

### D2 — El idioma de contenido será dato del dominio; la traducción, puerto de infraestructura

- Se añadirá un enum `Language(StrEnum)` (`ES`, `EN`, `FR`, `DE`) y el idioma será **del examen**
  (con posibilidad de sobrescribirse por pregunta si el caso real lo exige). Se introduce con **valor
  por defecto `ES`** en las dataclasses `frozen` para no romper `tests/builders.py`.
- Las heurísticas de texto (`rules.py`) se parametrizarán por idioma: `normalize_text(value,
  language=...)` y tablas de patrones por idioma. La firma se ampliará **con valor por defecto**, de
  modo que el comportamiento actual (español) queda intacto.
- La **traducción** (`encoder/decoder`, EN/FR/DE) será un **puerto** de infraestructura
  (`QuestionTranslator(Protocol)`), nunca lógica dentro de `domain/`. El dominio no conoce ningún
  modelo: solo idiomas.
- Las etiquetas de documento (sección 11: "Examen correspondiente a", "PERIODO", ...) se moverán a la
  plantilla (`templates/<lang>/default_exam.json`) cuando exista el motor de plantillas; hoy la
  plantilla todavía no existe.

### D3 — El NLP real se enchufa en `infrastructure/reviewers/`, detrás del contrato ya previsto

- El contrato `QuestionReviewer` de la Fase 1 es el **único** punto de entrada del modelo. No se
  crean contratos paralelos para "revisar", "corregir" y "traducir" por separado: revisar y corregir
  ya están en `QuestionReviewer`; **traducir** se añade como puerto nuevo (D2) en vez de meterlo en
  `QuestionReviewer`, porque la traducción no siempre es parte del ciclo de revisión.
- El `nlp_adapter.py` es el sitio donde el usuario conecta su modelo local. Cargar un encoder/decoder
  (por ejemplo, un modelo de traducción) es un **detalle de implementación del adaptador**, no un
  concepto del dominio ni de la aplicación.
- La ubicación del contrato: el prompt lo sitúa en `infrastructure/reviewers/base.py`; ADR-0002 pide
  que los protocolos vivan en `application`/`domain`. Se resuelve **(ver "Qué revisaría")**: el
  `Protocol` se define en el lado de aplicación (`application/ports.py`) y `base.py` lo **reexporta**,
  de modo que se respeta ADR-0002 y la ruta que cita el prompt sigue funcionando.
- Los DTOs del contrato (`QuestionInput`, `ReviewResult`) **no** usarán Pydantic en `domain/`: se
  definirán con `@dataclass(frozen=True)` (o Pydantic en `application/`), lo que resuelve el choque
  entre ADR-0002 (que permitía Pydantic para esos DTOs) y `test_domain_purity.py` (que lo prohíbe).

### D4 — Prohibiciones de la Fase 1 que se mantienen

- Nada en `src/` importa SDKs de IA ni referencia endpoints externos; los tests
  `test_no_external_ai_apis.py` siguen gobernando todo `src/**/*.py`.
- El adaptador local puede usar librerías de modelo locales (por ejemplo `torch`, `transformers`,
  `sentence-transformers`) **cuando exista el modelo**: se declararán entonces en `pyproject.toml` y
  en la imagen, y habrá que vigilar que ninguna raíz prohibida (`google`, etc.) entre por dependencia
  transitiva. Hoy no se declara ninguna.
- Determinismo: cada puerto nuevo (selector, traductor, revisor) trae un stub determinista, para que
  la suite siga corriendo sin red y sin modelo.

## Options Considered

### Option A: dejar todo como está y decidir más adelante (rechazada)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Nula ahora, alta después |
| Cost | Nulo ahora |
| Scalability | Baja — los contratos ya publicados condicionan el cambio |
| Team familiarity | Alta |
| mypy estricto | Mantiene estado actual |
| Testability | Mantiene estado actual |

**Pros:** cero esfuerzo en la Fase 1.
**Cons:** cuando llegue el banco, la tentación será meter una FK de banco dentro de `Question` y
debilitar las invariantes; el idioma aparecería hardcodeado en mil sitios; y la traducción se colaría
dentro del dominio. El coste del cambio se paga con intereses.

### Option B: reservar puntos de extensión y congelar contratos (elegida)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Baja — es documentación y disciplina, no código nuevo |
| Cost | Nulo |
| Scalability | Alta — cada capacidad tiene ya su frontera |
| Team familiarity | Alta — se apoya en los puertos que ya usa el proyecto |
| mypy estricto | Sin impacto (no se añade código) |
| Testability | Sin impacto |

**Pros:** no adelanta pasos; deja escritas las fronteras; no rompe nada; futuras incorporaciones son
aditivas.
**Cons:** obliga a respetar la disciplina (nada de atajos) y a releer el ADR al llegar cada capacidad.

### Option C: implementar banco, idioma y NLP ahora (rechazada)

| Dimension | Assessment |
|-----------|------------|
| Complexity | **Alta** — entidades, migraciones, API y modelo |
| Cost | Alto — sale del alcance y del stack de la fase |
| Scalability | Alta, pero prematura |
| Team familiarity | Media |
| mypy estricto | Exigiría tipar un modelo que no existe |
| Testability | Media — sin modelo real habría que inventar dobles |

**Pros:** adelanta trabajo.
**Cons:** viola las secciones 3, 9 y 19 del prompt (no entrenar, no adelantar el modelo); el banco
rompería invariantes del agregado; el idioma/la traducción son especulativos (no hay requisitos de
negocio cerrados: ¿idioma por examen o por pregunta?, ¿se traduce o solo se revisa?).

### Option D: mover el idioma al núcleo (`core`) como configuración de aplicación

| Dimension | Assessment |
|-----------|------------|
| Complexity | Baja |
| Cost | Nulo |
| Scalability | Media — el idioma es del contenido, no de la instalación |
| Team familiarity | Alta |
| mypy estricto | Sin impacto |
| Testability | Sin impacto |

**Pros:** reutilizable por otros módulos (documentos, minutas).
**Cons:** el idioma del **examen** es dato de negocio (varía por examen), no configuración del
proceso; modelarlo en `core` empujaría al dominio a leer configuración, que es justo lo que prohíbe
A29. Se descarta para el idioma de contenido; `core` solo guardará el **idioma por defecto**.

## Trade-off Analysis

El criterio decisivo es **dónde se paga el coste del cambio**. Un contrato ya publicado (firma de
dataclass, vocabulario de enum, envelope de error, puerto) es lo más caro de cambiar: los tests lo
fijan. Reservar ahora las fronteras —banco como agregado aparte y copia explícita; idioma como dato
del dominio con valor por defecto; traducción y selección como puertos de infraestructura— convierte
cada capacidad futura en una **adición** en lugar de una **reescritura**, y lo hace sin escribir
lógica de una fase que no toca.

La opción C (hacerlo ya) es la única que daría la funcionalidad antes, pero incumple el prompt y,
sobre todo, apostaría por decisiones de negocio todavía abiertas (granularidad del idioma, si hay
traducción y en qué dirección, si el banco comparte o copia). Decidir eso hoy con datos incompletos
sería el verdadero riesgo.

El precio asumido: la Fase 1 **no** tendrá banco, idioma ni NLP reales, y este ADR hay que releerlo
cuando cada capacidad entre en juego.

## Consequences

- La Fase 1 queda intacta: no se añade ninguna entidad, campo, endpoint ni dependencia por este ADR.
- Cuando llegue el banco, será un agregado nuevo con repositorio propio y copia explícita al examen;
  `Question` no gana referencias al banco.
- Cuando llegue el multilingüismo, `Language` entra en el dominio con defecto `ES` y las funciones de
  texto ganan un parámetro con defecto; el comportamiento actual no cambia.
- La traducción, la selección asistida y el NLP real se enchufan por puertos (`QuestionTranslator`,
  `QuestionSelector`, `QuestionReviewer`) con stub determinista obligatorio.
- Se mantienen los tests de pureza y de no-APIs-externas como barreras que impiden colar el modelo o
  el idioma por la puerta de atrás.
- Efecto colateral positivo: al obligar a que estos conceptos vivan en puertos, el día que se
  implementen ya no habrá que tocar `domain/rules.py` ni `domain/models.py` más de lo mínimo.

## Action Items

1. [x] Investigar qué dice el prompt sobre banco, idiomas y NLP (auditoría de fase).
2. [x] Decidir las fronteras y congelar los contratos de la Fase 1 (este ADR).
3. [ ] Releer este ADR al abrir el paso 7 (revisión IA) y concretar la ubicación final del
   `Protocol` y de los DTOs.
4. [ ] Cuando se pida el banco: definir `QuestionBank`/`BankQuestion`, `QuestionBankRepository` y el
   caso de uso de instanciación; no tocar `Exam`.
5. [ ] Cuando se pida el multilingüismo: definir `Language`, parametrizar las heurísticas por idioma
   y localizar la plantilla por idioma.
6. [ ] Cuando se pida traducción/NLP real: definir `QuestionTranslator` y el adaptador local,
   declarar la dependencia del modelo y verificar que sigue pasando `test_no_external_ai_apis.py`.

## Qué revisaría

- **Granularidad del idioma**: si el caso real exige mezclar idiomas dentro de un mismo examen,
  pasaría de "idioma del examen" a "idioma por pregunta", lo que afecta a la plantilla y a las
  heurísticas.
- **Identidad del banco**: si aparecen preguntas compartidas entre exámenes con edición colaborativa,
  reevaluaría la copia explícita frente a referencias con versionado.
- **Ubicación del `Protocol`**: si la aplicación acaba importando el contrato desde `infrastructure`,
  sería señal de que la frontera está mal y habría que endurecer la regla de dependencias.
- **Traducción con encoder/decoder**: si el modelo local cubre review+correct+traducción a la vez,
  reconsideraría un único puerto frente a dos, para no crear abstracciones que el modelo no necesita.
