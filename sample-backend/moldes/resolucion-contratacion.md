---
name: resolucion-contratacion
authority_level: TEMPLATE
document_type: resolucion
subtype: contratacion
jurisdiction: Intendencia Departamental de Lavalleja
variants:
  - personal
  - arrendamiento_servicios
  - servicio_proveedor
required_fields:
  - tipo_contratacion
  - persona_o_empresa
  - objeto
conditional_fields:
  - ficha
  - rut
  - iva
  - contrato
  - intervencion_rrhh
  - intervencion_contable
forbidden_inference:
  - numero_expediente
  - norma
  - competencia
  - monto
  - fecha
  - persona
  - empresa
  - rut
  - cargo
---

# RESOLUCIÓN [NÚMERO]/[AÑO]

**Minas, [FECHA].**

## VISTO

[ACTUACIÓN, SOLICITUD, INFORME, OFICIO O ANTECEDENTE QUE ORIGINA LA CONTRATACIÓN]

## RESULTANDO

[RESULTANDO — INCLUIR CUANDO SEA NECESARIO DESARROLLAR LOS ANTECEDENTES FÁCTICOS O ADMINISTRATIVOS]

I) [ANTECEDENTE FÁCTICO RELEVANTE].

II) [OTRO ANTECEDENTE SI CORRESPONDE].

## CONSIDERANDO

I) [VALORACIÓN DE LOS HECHOS].

II) [FUNDAMENTO JURÍDICO, TÉCNICO O ADMINISTRATIVO].

## ATENTO

[A LAS NORMAS, INFORMES, ANTECEDENTES Y FACULTADES EFECTIVAMENTE VERIFICADAS].

El Intendente Departamental de Lavalleja,

## RESUELVE

**1°.-** [DECISIÓN PRINCIPAL].

**2°.-** [PASE / EJECUCIÓN].

**3°.-** [NOTIFICACIÓN / COMUNICACIÓN].

**4°.-** Cumplido, archívese.

## FIRMAS

[NOMBRE / CARGO / FIRMA]

## Instrucciones internas (no forman parte del documento)

### VARIANTE A — CONTRATACIÓN DE PERSONAL

Campos típicos: `[PERSONA]`, `[FICHA, SI EXISTE]`, `[CARGO / FUNCIÓN]`, `[DEPENDENCIA]`, `[CAUSA]`, `[PERÍODO]`, `[REMUNERACIÓN]`, `[RÉGIMEN]`, `[INTERVENCIÓN RRHH]`, `[INTERVENCIÓN CONTABLE]`.

Parte resolutiva posible:
1°.- Contrátase...
2°.- Establécese...
3°.- Pase a Recursos Humanos...
4°.- Notifíquese...
5°.- Comuníquese...
6°.- Cumplido, archívese.

No utilizar mecánicamente todos los numerales.

### VARIANTE B — ARRENDAMIENTO DE SERVICIOS

Campos típicos: `[PROFESIONAL / PRESTADOR]`, `[RUT]`, `[OBJETO]`, `[PLAZO]`, `[HONORARIO]`, `[IVA SI CORRESPONDE]`, `[FORMA DE PAGO]`, `[DEPENDENCIA SUPERVISORA]`, `[CONTRATO]`.

No tratar al prestador como funcionario. No usar terminología laboral propia de funcionario si jurídicamente se trata de arrendamiento de servicios.

### VARIANTE C — CONTRATACIÓN DE SERVICIO / PROVEEDOR

Campos típicos: `[EMPRESA]`, `[RUT]`, `[SERVICIO]`, `[PROCEDIMIENTO DE CONTRATACIÓN]`, `[MONTO]`, `[PLAZO]`, `[DEPENDENCIA]`, `[CRÉDITO]`, `[INTERVENCIÓN]`.

No confundir `proveedor` con `funcionario` ni con `arrendador de servicios profesional`.

### Selección de variante

- Determinar la variante ANTES de redactar. No empezar a redactar y decidir a mitad del documento.
- Si no puede determinarse la variante, consultar el expediente, usar herramientas, solicitar aclaración o marcar la variante como pendiente. No adivinar.
- No mezclar elementos de las tres variantes.
