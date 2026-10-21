# Interfaz web (Fase 2)

En la **Fase 1** este directorio contiene únicamente la documentación del contrato de API que
consumirá la interfaz de captura.

## Alcance de la fase 2

- React + Vite + TypeScript.
- Captura de examen estilo *Forms* (secciones, preguntas, incisos, banderas de aleatorización) y
  estilo *Kahoot* (revisión visual del examen antes de procesarlo).
- **No** se implementa en esta fase.

## Contrato de API (base `/api/v1/exams`)

Definido en la sección 12 de `docs/PROMPT_FASE1.md` y materializado en el paso 10 (API FastAPI +
OpenAPI).

| Método | Ruta | Descripción |
|--------|------|-------------|
| `POST` | `/exams` | Crear examen en `DRAFT` (`exam_code` único → `409` si existe) |
| `GET` | `/exams/{id}` | Detalle: secciones, grupos, preguntas, incisos, banderas, estado |
| `PUT` | `/exams/{id}/structure` | Reemplazar la estructura completa (reinicia el pipeline) |
| `PATCH` | `/exams/{id}/questions/{qid}/flags` | Cambiar `shuffle_question` / `shuffle_options` |
| `PATCH` | `/exams/{id}/options/{oid}/flags` | Cambiar `locked` |
| `PUT` | `/exams/{id}/blocks` | Reemplazar `QUESTION_GROUP` / `SECTION_GROUP` |
| `POST` | `/exams/{id}/validate` | Reglas de negocio: errores y advertencias |
| `POST` | `/exams/{id}/submit` | `DRAFT` → `SUBMITTED` |
| `POST` | `/exams/{id}/process` | Ejecutar el pipeline completo |
| `GET` | `/exams/{id}/review-queue` | Preguntas pendientes de decisión (antes / después / motivos) |
| `POST` | `/exams/{id}/questions/{qid}/decision` | Decisión del docente sobre una pregunta |
| `POST` | `/exams/{id}/process/continue` | Reanudar; `use_original_for_unresolved` |
| `POST` | `/exams/{id}/keys` | Generar o regenerar claves (`n_keys`, `seed`) |
| `GET` | `/exams/{id}/documents` | Documentos generados, versiones y descarga |
| `GET` | `/exams/{id}/audit` | Historial de eventos |
| `POST` | `/exams/{id}/status/{transition}` | Avance manual de pasos humanos |

### Formato de error

```json
{
  "error": {
    "code": "conflict",
    "message": "Ya existe un examen con el código 21643.",
    "details": { "exam_code": "21643", "rule": "EXAM_CODE_DUPLICATE" }
  }
}
```

El campo `code` es el de la **jerarquía de errores** del núcleo (`conflict`, `not_found`,
`validation_failed`, `invalid_state`, `invalid_transition`...); el detalle de la regla de negocio
que lo provoked va en `details.rule` con el código estable de la regla (por ejemplo
`EXAM_CODE_DUPLICATE`). Los saltos de estado inválidos usan `invalid_transition` con
`details.current` y `details.target`.

### Máquina de estados expuesta

El campo `status` de un examen sigue la máquina de estados de la sección 5 de `docs/PROMPT_FASE1.md`:
`DRAFT`, `SUBMITTED`, `VALIDATED`, `FORMAT_CHECKED`, `FORMAT_FIXED`, `QUESTIONS_REVIEWED`,
`NEEDS_TEACHER_DECISION`, `KEYS_GENERATED`, `DOCUMENTS_GENERATED`, `COMPLETED`,
`COMPLETED_WITH_WARNINGS`, `PRINT_PENDING`, `ANSWER_SHEETS_PENDING`, `FAILED`.

Los saltos manuales (`POST /exams/{id}/status/{transition}`) solo admiten transiciones declaradas en
`ALLOWED_TRANSITIONS`; cualquier otra devuelve `InvalidTransitionError`.
