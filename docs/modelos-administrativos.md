# Biblioteca de modelos administrativos

Consulta de fuentes: **10 de septiembre de 2026**. La biblioteca contiene **11 modelos**, incluidos los dos ejemplos originales. Los nueve nuevos son plantillas redactadas para Giana, con antecedentes oficiales enlazados; no son transcripciones ni actos administrativos emitidos.

## Modelos incorporados

| Modelo | Archivo | Fuente principal y alcance |
| --- | --- | --- |
| Contratación de funcionarios | [03_contratacion_funcionario.md](../backend/examples/03_contratacion_funcionario.md) | [IDL 2.025/023](https://www.gub.uy/intendencia-lavalleja/institucional/normativa/resolucion-n-2025023). La fuente inicia un concurso; el modelo de contratación posterior es una elaboración propia, no un antecedente individual idéntico. |
| Contratación zafral | [04_contratacion_zafral.md](../backend/examples/04_contratacion_zafral.md) | [IDL 2.272/026](https://www.gub.uy/intendencia-lavalleja/institucional/normativa/resolucion-n-2272026). Selección por sorteo, período, jornada y jornal. Parques y jardines es una adaptación del destino. |
| Arrendamiento de obra | [05_arrendamiento_obra.md](../backend/examples/05_arrendamiento_obra.md) | [IDL 1.863/026](https://www.gub.uy/intendencia-lavalleja/institucional/normativa/resolucion-n-1863026) y [TOCAF, artículo 38](https://www.impo.com.uy/bases/tocaf2012/150-2012/38). La plantilla exige precisar productos, aceptación y plazo; no presupone que cualquier servicio pueda contratarse como obra. |
| Llamado a concurso | [06_llamado_concurso.md](../backend/examples/06_llamado_concurso.md) | [IDL 2.025/023](https://www.gub.uy/intendencia-lavalleja/institucional/normativa/resolucion-n-2025023). Convocatoria, bases, tribunal y difusión. |
| Renovación de zafrales | [07_renovacion_zafral.md](../backend/examples/07_renovacion_zafral.md) | [IDL 1.048/025](https://www.gub.uy/intendencia-lavalleja/institucional/normativa/resolucion-n-1048025). Fuente sobre control de vigencia; el modelo individual de renovación es una elaboración propia. |
| Adjudicación de licitación | [08_adjudicacion_licitacion.md](../backend/examples/08_adjudicacion_licitacion.md) | [IDL 3.279/024](https://www.gub.uy/intendencia-lavalleja/institucional/normativa/resolucion-n-3279024). Selección de ofertas, motivación, control y formalización. |
| Aprobación de convenio | [09_aprobacion_convenio.md](../backend/examples/09_aprobacion_convenio.md) | [IDL 334/024](https://www.gub.uy/intendencia-lavalleja/institucional/normativa/resolucion-n-334024). Aprobación de texto anexo; no incluye un contrato bilateral completo. |
| Traslado interno | [10_traslado_funcionario.md](../backend/examples/10_traslado_funcionario.md) | [IDL 1.862/026](https://www.gub.uy/intendencia-lavalleja/institucional/normativa/resolucion-n-1862026). Cambio de dependencia y registro funcional. |
| Exoneración de patente | [11_exoneracion_patente.md](../backend/examples/11_exoneracion_patente.md) | [IDL 483/026](https://www.gub.uy/intendencia-lavalleja/institucional/normativa/resolucion-n-483026). Caso de vehículo de prensa; otras causales necesitan su propia habilitación. |

## Uso en Giana

Los archivos están en `backend/examples`, la carpeta que consulta el buscador local en cada nueva solicitud. No requieren indexación de Qdrant ni llamadas web al usar el modelo. No se incorporaron como resoluciones oficiales al catálogo de Configuración: su nivel de autoridad es `EXAMPLE`.

Cada archivo contiene datos para orientar el formulario, alcance, estructura de resolución con campos pendientes y fuentes. El molde general sigue siendo la estructura base. La selección del modelo conserva la validación de pertinencia y el límite de espera de la preparación inicial; disponer de un modelo no obliga a afirmar que existe un antecedente idéntico.

## Revisión jurídica de la adaptación

La [Ley 20.451](https://www.impo.com.uy/bases/leyes/20451-2025) regula ingresos y modalidades contractuales departamentales. Su artículo 7 fija vigencia desde la publicación y preserva derechos adquiridos de normas preexistentes. Por ello los modelos piden documentar la fecha, categoría del vínculo y procedimiento aplicable, sin copiar automáticamente prácticas anteriores.

El artículo 38 del TOCAF se utiliza como referencia para distinguir una obra con resultado delimitado. Las autorizaciones e incompatibilidades deben verificarse para el organismo y supuesto correspondientes. Se dejaron fuera nombres, identificaciones, montos, plazos y cláusulas de renovación de los casos originales.

Fecha de consulta no equivale a certificación de vigencia de todas las normas citadas por los antecedentes. Los apartados «Fuentes y límites» y «Datos para el formulario» son material auxiliar de la biblioteca y no forman parte del texto del acto a emitir.
